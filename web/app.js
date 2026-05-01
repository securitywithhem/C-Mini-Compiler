/**
 * C Mini-Compiler Frontend
 * Handles code editing, compilation, and error display
 */

// ────────────────────────────────────────────────────────────
// CodeMirror Editor Setup
// ────────────────────────────────────────────────────────────

const editor = CodeMirror(document.getElementById('editor'), {
    mode: 'text/x-csrc',
    theme: 'material-darker',
    lineNumbers: true,
    indentUnit: 4,
    indentWithTabs: false,
    lineWrapping: true,
    matchBrackets: true,
    autoCloseBrackets: true,
    highlightSelectionMatches: { showToken: /\w/, annotateScrollbar: true },
    styleActiveLine: true,
    value: `#include <stdio.h>

int multiply(int a, int b) {
    return a * b;
}

int main(void) {
    int x = 5, y = 10;
    int result = multiply(x, y);
    printf("Result: %d\\n", result);
    return 0;
}`
});

// ────────────────────────────────────────────────────────────
// Error Rendering & Line Marking
// ────────────────────────────────────────────────────────────

let diagnosticMarkers = [];

function clearErrorMarkers() {
    diagnosticMarkers.forEach(marker => marker.clear());
    diagnosticMarkers = [];
}

function renderErrors(diagnostics) {
    const errorList = document.getElementById('errorList');
    const errorCount = document.getElementById('errorCount');

    clearErrorMarkers();

    if (diagnostics.length === 0) {
        errorList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✓</div>
                <div class="success-badge">No errors found</div>
                <div class="empty-state-desc">Code is syntactically correct!</div>
            </div>
        `;
        errorCount.textContent = '✓ Clean';
        errorCount.classList.remove('has-errors');
        errorCount.classList.add('success');
        return;
    }

    // Group errors by type
    const byKind = {};
    diagnostics.forEach(d => {
        byKind[d.kind] = (byKind[d.kind] || 0) + 1;
    });

    // Render error list
    errorList.innerHTML = diagnostics.map((d, i) => `
        <div class="error-item ${getErrorClass(d.kind)}" data-index="${i}">
            <div class="error-kind">${d.kind.replace(/_/g, ' ')}</div>
            <div class="error-message">${escapeHtml(d.message)}</div>
            <div class="error-line">Line ${d.line}, Col ${d.column}</div>
        </div>
    `).join('');

    // Add click handlers to jump to error
    document.querySelectorAll('.error-item').forEach((el, i) => {
        el.addEventListener('click', () => {
            const line = diagnostics[i].line;
            const col = diagnostics[i].column;
            editor.setCursor(line - 1, col - 1);
            editor.focus();
        });
    });

    // Mark error lines in editor
    diagnostics.forEach(d => {
        const lineHandle = editor.markText(
            { line: d.line - 1, ch: 0 },
            { line: d.line - 1, ch: null },
            {
                className: 'diagnostic-line',
                title: d.message,
            }
        );
        diagnosticMarkers.push(lineHandle);
    });

    // Update error count
    const counts = Object.entries(byKind)
        .map(([kind, count]) => `${count} ${kind.toLowerCase()}`)
        .join(' • ');
    errorCount.innerHTML = `⚠️ ${counts}`;
    errorCount.classList.add('has-errors');
    errorCount.classList.remove('success');
}

function getErrorClass(kind) {
    if (kind === 'MISSING_RETURN' || kind === 'MISSING_SEMICOLON') {
        return 'warning';
    }
    return 'error';
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ────────────────────────────────────────────────────────────
// Compilation & API
// ────────────────────────────────────────────────────────────

const compileBtn = document.getElementById('compileBtn');
const compileBtnText = document.getElementById('compileBtnText');

async function compile() {
    const code = editor.getValue();
    const apiUrl = 'http://localhost:5000/compile';

    // UI feedback
    compileBtn.classList.add('loading');
    compileBtn.disabled = true;
    compileBtnText.textContent = '⏳ Compiling...';

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code }),
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        renderErrors(data.errors || []);

    } catch (error) {
        console.error('Compilation error:', error);
        document.getElementById('errorList').innerHTML = `
            <div class="error-item error">
                <div class="error-kind">Connection Error</div>
                <div class="error-message">${escapeHtml(error.message)}</div>
                <div class="error-line" style="margin-top: 8px; color: #6e7681;">
                    Make sure Flask backend is running:<br>
                    <code style="background: rgba(0,0,0,0.3); padding: 2px 4px; border-radius: 3px;">python backend.py</code>
                </div>
            </div>
        `;
        document.getElementById('errorCount').textContent = '✗ Error';
    } finally {
        compileBtn.classList.remove('loading');
        compileBtn.disabled = false;
        compileBtnText.textContent = '⚙️ Compile';
    }
}

// Attach compile button
compileBtn.addEventListener('click', compile);

// Auto-compile on Ctrl+Enter or Cmd+Enter
editor.setOption('extraKeys', {
    'Ctrl-Enter': compile,
    'Cmd-Enter': compile,
});

// ────────────────────────────────────────────────────────────
// Initialization
// ────────────────────────────────────────────────────────────

console.log('%c🔨 C Mini-Compiler Frontend Loaded', 'color: #4ec9b0; font-size: 14px; font-weight: bold;');
console.log('Backend API: http://localhost:5000/compile');
console.log('Press Ctrl+Enter to compile');

// Show welcome message
document.getElementById('errorList').innerHTML = `
    <div class="empty-state">
        <div class="empty-state-icon">👨‍💻</div>
        <div class="success-badge">Ready</div>
        <div class="empty-state-desc">
            Click "Compile" or press <kbd>Ctrl+Enter</kbd><br>
            to check your code
        </div>
    </div>
`;
