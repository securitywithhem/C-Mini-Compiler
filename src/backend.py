"""
Flask backend for the C Mini-Compiler.

Endpoints
---------
    GET  /          serve the web UI (index.html from /web)
    GET  /<path>    serve any other static asset from /web
    POST /compile   run all phases, return errors + symbol table
    POST /symbols   return only the symbol table
    GET  /health    liveness probe

Run from the project root:

    python -m src.backend
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from .validator import validate_string
from .semantic  import analyze_string

# ─── Project paths ──────────────────────────────────────────
_HERE     = Path(__file__).resolve().parent
_WEB_DIR  = (_HERE.parent / "web").resolve()


app = Flask(
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="",
)
CORS(app)


# ─── Static / UI ────────────────────────────────────────────

@app.route("/", methods=["GET"])
def serve_index():
    """Serve the web UI."""
    return send_from_directory(str(_WEB_DIR), "index.html")


# ─── Compilation API ────────────────────────────────────────

@app.route("/compile", methods=["POST"])
def compile_code():
    """
    Run the full pipeline (syntax + semantic) on the supplied C source.

    Request JSON:
        { "code": "<C source>" }

    Response JSON:
        {
            "errors": [
                {
                    "kind":     "<KIND>",
                    "message":  "<text>",
                    "line":     <int>,
                    "column":   <int>,
                    "phase":    "syntax" | "semantic",
                    "severity": "error" | "warning"
                },
                ...
            ],
            "symbol_table": { "functions": [...], "variables": [...] }
        }
    """
    try:
        data = request.get_json() or {}
        code = data.get("code", "")
        errors: list[dict] = []

        # Phase 1-3: syntax
        for d in validate_string(code):
            errors.append({
                "kind":     d.kind.name,
                "message":  d.message,
                "line":     d.line,
                "column":   d.column,
                "phase":    "syntax",
                "severity": "error",
            })

        # Phase 4: semantic
        sem_errors, table = analyze_string(code)
        for e in sem_errors:
            errors.append({
                "kind":     e.kind.name,
                "message":  e.message,
                "line":     e.line,
                "column":   e.column,
                "phase":    "semantic",
                "severity": "warning" if e.is_warning else "error",
            })

        errors.sort(key=lambda x: (x["line"], x["column"]))
        return jsonify({"errors": errors, "symbol_table": table.to_dict()}), 200

    except Exception as exc:   # pragma: no cover — last-resort guard
        return jsonify({
            "errors": [{
                "kind":     "SERVER_ERROR",
                "message":  str(exc),
                "line":     0,
                "column":   0,
                "phase":    "server",
                "severity": "error",
            }],
            "symbol_table": {"functions": [], "variables": []},
        }), 500


@app.route("/symbols", methods=["POST"])
def get_symbols():
    """Return just the symbol table for the supplied source."""
    try:
        data = request.get_json() or {}
        _, table = analyze_string(data.get("code", ""))
        return jsonify({"symbol_table": table.to_dict()}), 200
    except Exception as exc:   # pragma: no cover
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "phases": 5}), 200


# ─── Entry point ────────────────────────────────────────────

def _print_banner(host: str, port: int) -> None:
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   C Mini-Compiler Backend - Flask Server                  ║
║   Phases: Lexer → Parser → Validator → Semantic → Report  ║
╚═══════════════════════════════════════════════════════════╝

  Frontend:      http://{host}:{port}/
  Compile API:   POST  http://{host}:{port}/compile
  Symbols API:   POST  http://{host}:{port}/symbols
  Health check:  GET   http://{host}:{port}/health

Starting server...
""")


if __name__ == "__main__":
    # Lazy import so the package doesn't need config at import time
    try:
        from config import BACKEND_HOST, BACKEND_PORT, BACKEND_DEBUG
    except ImportError:
        BACKEND_HOST, BACKEND_PORT, BACKEND_DEBUG = "0.0.0.0", 5000, True

    _print_banner("localhost", BACKEND_PORT)
    app.run(host=BACKEND_HOST, port=BACKEND_PORT, debug=BACKEND_DEBUG)
