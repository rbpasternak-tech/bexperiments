"""Fetch what a shared link actually says: video transcript or article text.

Short videos (Instagram reels, TikToks, YouTube Shorts, X/Facebook clips) are
downloaded with yt-dlp and transcribed on this Mac with faster-whisper — the
audio never leaves the machine. Articles are extracted with trafilatura.
Everything here is read-only with respect to the vault; clip_ingest.py turns
the result into a note.

Media and the Whisper model live under ~/Library/Application Support/
agent-team/ (outside iCloud, so launchd can always read them).
"""

import re
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from state import DEFAULT_STATE_DIR

DEFAULT_WHISPER_MODEL = "small"
DEFAULT_MAX_TRANSCRIBE_SECONDS = 900
WHISPER_DIR = DEFAULT_STATE_DIR / "whisper"
MEDIA_TMP_DIR = DEFAULT_STATE_DIR / "clips-tmp"
MAX_MEDIA_BYTES = 300 * 1024 * 1024
SAMPLE_RATE = 16000
MAX_ARTICLE_CHARS = 40000

# Hosts whose links are (almost always) a video to transcribe.
VIDEO_HOSTS = (
    "instagram.com", "tiktok.com", "youtube.com", "youtu.be", "vimeo.com",
    "facebook.com", "fb.watch", "x.com", "twitter.com", "threads.net",
    "threads.com",
)

URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+")

# Whisper is memory-hungry (~1 GB for `small`); transcribe one clip at a time.
_TRANSCRIBE_LOCK = threading.Lock()


class ClipError(Exception):
    """The link's content could not be fetched; the message says why."""


def find_urls(text):
    """Return the http(s) URLs in a message, trailing punctuation trimmed.

    Args:
        text: Any message text.

    Returns:
        A list of URL strings in order of appearance (may be empty).
    """
    return [u.rstrip(".,;:!?)*_'\"") for u in URL_RE.findall(text or "")]


def site_of(url):
    """Return a short site name for a URL ('instagram', 'youtube', ...)."""
    host = (urlparse(url).netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for known in VIDEO_HOSTS:
        if host == known or host.endswith("." + known):
            return known.split(".")[0].replace("youtu", "youtube")
    return host.split(":")[0] or "web"


def is_video_url(url):
    """True when the URL's host is one of the short-video platforms."""
    host = (urlparse(url).netloc or "").lower()
    return any(host == h or host.endswith("." + h) for h in VIDEO_HOSTS)


def fetch_clip(url, settings=None):
    """Fetch a link's content for filing.

    Args:
        url: The shared link.
        settings: Optional dict from config.yaml `clips` (whisper_model,
            max_transcribe_seconds, cookies_from_browser).

    Returns:
        A dict with kind ('video' or 'article'), url, site, title, creator,
        description, duration (seconds or None), published, text (the
        transcript or article body), text_kind ('transcript' or 'article'),
        language, and truncated (bool).

    Raises:
        ClipError: When neither a video nor an article could be fetched.
    """
    settings = settings or {}
    if is_video_url(url):
        return _fetch_video(url, settings)
    try:
        return _fetch_article(url)
    except ClipError as article_error:
        # Some article-looking links are really embedded videos (a news
        # site's clip page); give yt-dlp one try before giving up.
        try:
            return _fetch_video(url, settings)
        except ClipError:
            raise article_error


def transcribe_file(path, settings=None):
    """Transcribe a local audio/video file (e.g. a video sent to Telegram).

    Args:
        path: Path to the media file.
        settings: Optional `clips` config dict.

    Returns:
        (text, language, truncated) — the transcript, its detected language
        code, and whether it was cut at max_transcribe_seconds.

    Raises:
        ClipError: When the file cannot be decoded or Whisper is missing.
    """
    settings = settings or {}
    limit = int(settings.get("max_transcribe_seconds") or DEFAULT_MAX_TRANSCRIBE_SECONDS)
    audio = _decode_audio(path, limit)
    if audio is None or len(audio) < SAMPLE_RATE // 2:
        raise ClipError("the file has no decodable audio")
    truncated = len(audio) >= limit * SAMPLE_RATE
    with _TRANSCRIBE_LOCK:
        model = _load_whisper(settings.get("whisper_model") or DEFAULT_WHISPER_MODEL)
        segments, info = model.transcribe(audio, vad_filter=True, beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        del model  # release ~1 GB; reloading from disk takes about a second
    return text, getattr(info, "language", None), truncated


def _fetch_video(url, settings):
    """Download a video's audio with yt-dlp and transcribe it locally."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise ClipError("yt-dlp is not installed; re-run install-launchd.sh") from exc
    MEDIA_TMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="clip-", dir=MEDIA_TMP_DIR))
    options = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "max_filesize": MAX_MEDIA_BYTES,
        "socket_timeout": 30,
        "retries": 2,
    }
    browser = (settings.get("cookies_from_browser") or "").strip()
    if browser:
        options["cookiesfrombrowser"] = (browser,)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if "entries" in info:  # a playlist-ish page: take the first item
                info = next((e for e in info["entries"] if e), info)
            media_path = ydl.prepare_filename(info)
        text, language, truncated = transcribe_file(media_path, settings)
        return {
            "kind": "video",
            "url": info.get("webpage_url") or url,
            "site": site_of(url),
            "title": (info.get("title") or "").strip() or "Untitled clip",
            "creator": info.get("uploader") or info.get("channel") or info.get("creator") or "",
            "description": (info.get("description") or "").strip(),
            "duration": info.get("duration"),
            "published": _upload_date(info.get("upload_date")),
            "text": text,
            "text_kind": "transcript",
            "language": language,
            "truncated": truncated,
        }
    except ClipError:
        raise
    except Exception as exc:  # yt-dlp raises many types; the message matters
        raise ClipError(_short_error(exc)) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _fetch_article(url):
    """Extract an article's title, author, date and body text."""
    try:
        import trafilatura
    except ImportError as exc:
        raise ClipError("trafilatura is not installed; re-run install-launchd.sh") from exc
    import json

    html = trafilatura.fetch_url(url)
    if not html:
        raise ClipError("the page could not be downloaded (login wall, blocked, or offline)")
    extracted = trafilatura.extract(
        html, output_format="json", with_metadata=True, include_comments=False
    )
    if not extracted:
        raise ClipError("no readable article text was found on the page")
    data = json.loads(extracted)
    text = (data.get("text") or "").strip()
    if len(text.split()) < 40:
        raise ClipError("the page had almost no readable text (probably needs a login)")
    truncated = len(text) > MAX_ARTICLE_CHARS
    return {
        "kind": "article",
        "url": data.get("source") or url,
        "site": data.get("sitename") or data.get("hostname") or site_of(url),
        "title": (data.get("title") or "").strip() or "Untitled article",
        "creator": data.get("author") or "",
        "description": (data.get("description") or "").strip(),
        "duration": None,
        "published": data.get("date") or "",
        "text": text[:MAX_ARTICLE_CHARS],
        "text_kind": "article",
        "language": None,
        "truncated": truncated,
    }


def _decode_audio(path, max_seconds):
    """Decode a media file to mono 16 kHz float32 samples with PyAV.

    Done here rather than via faster-whisper's own decoder because that
    decoder breaks on newer PyAV releases; this uses only stable API.

    Args:
        path: Media file path.
        max_seconds: Stop decoding after this many seconds of audio.

    Returns:
        A numpy float32 array, or None when the file has no audio stream.
    """
    try:
        import av
        import numpy as np
    except ImportError as exc:
        raise ClipError("PyAV/numpy are not installed; re-run install-launchd.sh") from exc
    chunks, total = [], 0
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                return None
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            for frame in container.decode(container.streams.audio[0]):
                for out in resampler.resample(frame):
                    array = out.to_ndarray()
                    chunks.append(array)
                    total += array.shape[1]
                if total >= max_seconds * SAMPLE_RATE:
                    break
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray())
    except Exception as exc:
        raise ClipError(f"could not decode audio: {_short_error(exc)}") from exc
    if not chunks:
        return None
    audio = np.concatenate(chunks, axis=1)[0].astype(np.float32) / 32768.0
    return audio[: int(max_seconds * SAMPLE_RATE)]


def _load_whisper(model_name):
    """Load the Whisper model from the local cache, downloading it once."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ClipError("faster-whisper is not installed; re-run install-launchd.sh") from exc
    WHISPER_DIR.mkdir(parents=True, exist_ok=True)
    common = {"device": "cpu", "compute_type": "int8", "download_root": str(WHISPER_DIR)}
    try:
        # Offline first: a Hugging Face freshness check can hang for minutes
        # on a flaky connection, and the cached model is all we need.
        return WhisperModel(model_name, local_files_only=True, **common)
    except Exception:
        print(f"[clips] downloading Whisper model '{model_name}' to {WHISPER_DIR}", flush=True)
        try:
            return WhisperModel(model_name, **common)
        except Exception as exc:
            raise ClipError(f"Whisper model '{model_name}' unavailable: {_short_error(exc)}") from exc


def _upload_date(value):
    """Turn yt-dlp's YYYYMMDD upload_date into YYYY-MM-DD (or '')."""
    if value and len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return ""


def _short_error(exc):
    """Trim a library exception to one readable sentence."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    text = re.sub(r"^ERROR:\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*[\w-]*:?\s*", "", text)  # "[Instagram] abc: msg"
    needs_login = re.search(r"logged.in|cookies|login|private", text, re.I)
    text = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].rstrip(".")
    if needs_login:
        text += " (private or login-only; set clips.cookies_from_browser in config.yaml, or paste the caption)"
    return text[:200]
