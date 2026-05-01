"""
Flask backend for C Mini-Compiler
Provides:
  POST /compile   — syntax validation (Phase 1-3) + semantic analysis (Phase 4)
  GET  /symbols   — symbol table for the last successfully parsed program
  GET  /health    — health check
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from src.validator import validate_string
from src.semantic  import analyze_string

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)


@app.route('/', methods=['GET'])
def serve_frontend():
    return send_from_directory('web', 'index.html')


@app.route('/compile', methods=['POST'])
def compile_code():
    """
    Compile and validate C code through all four phases.

    Request body (JSON):
        { "code": "<C source code>" }

    Response (JSON):
        {
            "errors": [
                {
                    "kind":     "<ERROR_KIND>",
                    "message":  "<description>",
                    "line":     <int>,
                    "column":   <int>,
                    "phase":    "syntax" | "semantic",
                    "severity": "error" | "warning"
                },
                ...
            ],
            "symbol_table": {
                "functions": [...],
                "variables": [...]
            }
        }
    """
    try:
        data = request.get_json() or {}
        code = data.get('code', '')

        errors = []

        # ── Phase 1-3: Syntax validation ───────────────────────
        diagnostics = validate_string(code)
        for d in diagnostics:
            errors.append({
                'kind':     d.kind.name,
                'message':  d.message,
                'line':     d.line,
                'column':   d.column,
                'phase':    'syntax',
                'severity': 'error',
            })

        # ── Phase 4: Semantic analysis ─────────────────────────
        sem_errors, symbol_table = analyze_string(code)
        for e in sem_errors:
            errors.append({
                'kind':     e.kind.name,
                'message':  e.message,
                'line':     e.line,
                'column':   e.column,
                'phase':    'semantic',
                'severity': 'warning' if e.is_warning else 'error',
            })

        # Sort all errors by line then column
        errors.sort(key=lambda x: (x['line'], x['column']))

        return jsonify({
            'errors':       errors,
            'symbol_table': symbol_table.to_dict(),
        }), 200

    except Exception as exc:
        return jsonify({
            'errors': [{
                'kind':     'SERVER_ERROR',
                'message':  str(exc),
                'line':     0,
                'column':   0,
                'phase':    'server',
                'severity': 'error',
            }],
            'symbol_table': {'functions': [], 'variables': []},
        }), 500


@app.route('/symbols', methods=['POST'])
def get_symbols():
    """
    Return only the symbol table for the given C code.
    Useful for displaying declarations without running full validation.

    Request body (JSON):  { "code": "<C source code>" }
    Response (JSON):      { "symbol_table": { "functions": [...], "variables": [...] } }
    """
    try:
        data = request.get_json() or {}
        code = data.get('code', '')
        _, symbol_table = analyze_string(code)
        return jsonify({'symbol_table': symbol_table.to_dict()}), 200
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'phases': 4}), 200


if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════╗
║       C Mini-Compiler Backend - Flask Server             ║
║       Phases: Lexer → Parser → Validator → Semantics     ║
╚═══════════════════════════════════════════════════════════╝

  Frontend:      http://localhost:5000
  Compile API:   http://localhost:5000/compile
  Symbols API:   http://localhost:5000/symbols
  Health check:  http://localhost:5000/health

Starting server...
    """)
    app.run(debug=True, port=5000, host='0.0.0.0')
