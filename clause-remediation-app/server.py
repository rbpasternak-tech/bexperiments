"""Flask server with SSE endpoint for the remediation dashboard.

Serves the static dashboard and streams orchestrator events
in real-time via Server-Sent Events.

The dashboard is served from this same origin, so no CORS is enabled.
/api/run stays a GET because the browser consumes it with EventSource
(GET-only); because it starts paid Claude calls and writes files, it
rejects requests the browser marks as coming from another site.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, abort, jsonify, request, send_from_directory

load_dotenv(Path(__file__).resolve().parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "agents"))

from agents.orchestrator_stream import run_remediation_stream
from tools.supabase_tools import get_document_stats

app = Flask(__name__, static_folder="static")

HOST = "127.0.0.1"
PORT = 5001


def _is_cross_site_request():
    """Return True if the browser marked this request as cross-site.

    Uses the Sec-Fetch-Site header when present, falling back to comparing
    the Origin header with the request host. Non-browser clients (curl)
    send neither header and are allowed, since the server only listens on
    localhost.
    """
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site:
        return fetch_site not in ("same-origin", "none")
    origin = request.headers.get("Origin")
    if origin:
        return origin.rstrip("/") != request.host_url.rstrip("/")
    return False


@app.route("/")
def index():
    """Serve the dashboard page."""
    return send_from_directory("static", "index.html")


@app.route("/css/<path:filename>")
def css(filename):
    """Serve CSS files."""
    return send_from_directory("static/css", filename)


@app.route("/js/<path:filename>")
def js(filename):
    """Serve JS files."""
    return send_from_directory("static/js", filename)


@app.route("/api/stats")
def stats():
    """Return portfolio stats for the dashboard landing state."""
    try:
        doc_stats = get_document_stats()
        total = sum(doc_stats.values())
        return jsonify({"categories": doc_stats, "total": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/run")
def run_sse():
    """SSE endpoint that streams remediation events."""
    if _is_cross_site_request():
        abort(403)
    clause_type = request.args.get("clause_type", "arbitration")
    old_standard = request.args.get("old_standard", "AAA Commercial Arbitration Rules (2013)")
    new_standard = request.args.get("new_standard", "AAA Commercial Arbitration Rules (2024)")
    category_filter = request.args.get("category_filter", "Services & Commercial")
    if category_filter == "":
        category_filter = None

    def generate():
        try:
            for event in run_remediation_stream(
                clause_type=clause_type,
                old_standard=old_standard,
                new_standard=new_standard,
                category_filter=category_filter,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
