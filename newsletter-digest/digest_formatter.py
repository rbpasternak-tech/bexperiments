"""Format the markdown digest summary into a clean HTML email."""

import html
import re

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_SAFE_SCHEMES = ("http://", "https://")


def format_digest_html(markdown_content, date_range_start, date_range_end):
    """Convert markdown digest into a styled HTML email.

    Args:
        markdown_content: Markdown string from the summarizer.
        date_range_start: Start date string for the header.
        date_range_end: End date string for the header.

    Returns:
        Complete HTML string ready to be sent as an email.
    """
    body_html = _markdown_to_html(markdown_content)

    return f"""\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #1a1a1a;
    max-width: 680px;
    margin: 0 auto;
    padding: 20px;
    background-color: #fafafa;
  }}
  .header {{
    border-bottom: 3px solid #2563eb;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }}
  .header h1 {{
    font-size: 24px;
    color: #1e293b;
    margin: 0 0 4px 0;
  }}
  .header .date-range {{
    font-size: 14px;
    color: #64748b;
  }}
  h2 {{
    font-size: 20px;
    color: #1e40af;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 8px;
    margin-top: 32px;
  }}
  h3 {{
    font-size: 16px;
    color: #334155;
    margin-top: 20px;
  }}
  p {{
    margin: 8px 0;
    color: #374151;
  }}
  ul {{
    padding-left: 20px;
  }}
  li {{
    margin: 6px 0;
    color: #374151;
  }}
  a {{
    color: #2563eb;
    text-decoration: none;
  }}
  a:hover {{
    text-decoration: underline;
  }}
  strong {{
    color: #1e293b;
  }}
  .footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #e2e8f0;
    font-size: 12px;
    color: #94a3b8;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>Tech & Legal Tech Digest</h1>
    <div class="date-range">{date_range_start} — {date_range_end}</div>
  </div>

  {body_html}

  <div class="footer">
    Generated automatically by Newsletter Digest.
    <br>Powered by Claude API.
  </div>
</body>
</html>
"""


def _markdown_to_html(md):
    """Simple markdown to HTML conversion for digest content."""
    lines = md.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
            continue

        # Headers
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{_inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{_inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{_inline_format(stripped[2:])}</h2>")
        # List items
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_format(stripped[2:])}</li>")
        # Horizontal rule
        elif stripped in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
        # Regular paragraph
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{_inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _inline_format(text):
    """Apply inline markdown formatting (bold, italic, links) safely.

    The model's text is HTML-escaped first, so any markup it contains is
    shown literally rather than injected into the email. Only http(s) links
    become anchors; other schemes (javascript:, data:, ...) keep just their
    link text.

    Args:
        text: One line of markdown from the summarizer.

    Returns:
        An HTML fragment.
    """
    text = html.escape(text.replace("\x00", ""), quote=True)
    links = []

    def _link(match):
        label, url = _emphasis(match.group(1)), match.group(2)
        if not html.unescape(url).strip().lower().startswith(_SAFE_SCHEMES):
            return label
        links.append(f'<a href="{url}">{label}</a>')
        return f"\x00{len(links) - 1}\x00"

    # Links become placeholders so the emphasis rules cannot alter URLs.
    text = _emphasis(_LINK_RE.sub(_link, text))
    return re.sub("\x00(\\d+)\x00", lambda m: links[int(m.group(1))], text)


def _emphasis(text):
    """Convert **bold** and *italic* markdown in already-escaped text."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
