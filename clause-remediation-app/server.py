"""Flask server with SSE endpoint for the remediation dashboard.

Serves the static dashboard and streams orchestrator events
in real-time via Server-Sent Events.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv(Path(__file__).resolve().parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "agents"))

from agents.orchestrator_stream import run_remediation_stream
from tools.supabase_tools import get_document_stats, search_documents

app = Flask(__name__, static_folder="static")
CORS(app)


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
    app.run(debug=False, port=5001, threaded=True)
