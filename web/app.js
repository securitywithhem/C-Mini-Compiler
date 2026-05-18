/**
 * C-Mini Compiler - Frontend Logic
 * Modernized for stability, performance, and rich aesthetics.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── DOM Elements ──────────────────────────────────────────
    const editorArea = document.getElementById('editor');
    const compileBtn = document.getElementById('compileBtn');
    const compileBtnText = document.getElementById('compileBtnText');
    const errorList = document.getElementById('errorList');
    const errorCount = document.getElementById('errorCount');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');

    // ── Initialize CodeMirror ──────────────────────────────────
    const editor = CodeMirror.fromTextArea(editorArea, {
        mode: 'text/x-csrc',
        theme: 'material-palenight',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        tabSize: 4,
        indentUnit: 4,
        lineWrapping: true,
        extraKeys: {
            "Ctrl-Enter": compileCode,
            "Cmd-Enter": compileCode
        }
    });

    // Default code to get started
    const defaultCode = `int main() {
    int a = 10;
    int b = 20;
    int sum = a + b;
    // Try adding errors like:
    // int x = ;
    return 0;
}`;
    
    // Load from localStorage or use default
    const savedCode = localStorage.getItem('mini_c_code');
    editor.setValue(savedCode || defaultCode);

    // ── Diagnostic State ───────────────────────────────────────
    let markers = [];

    function clearMarkers() {
        markers.forEach(m => m.clear());
        markers = [];
        // Clear line classes
        for (let i = 0; i < editor.lineCount(); i++) {
            editor.removeLineClass(i, 'background', 'diagnostic-line');
        }
    }

    function highlightError(line, column) {
        const lineIdx = Math.max(0, line - 1);
        const colIdx = Math.max(0, column - 1);
        
        // Highlight line with smooth background
        editor.addLineClass(lineIdx, 'background', 'diagnostic-line');
        
        // Add text marker
        const marker = editor.markText(
            {line: lineIdx, ch: colIdx},
            {line: lineIdx, ch: colIdx + 2}, // highlight a few chars
            {className: 'cm-error-underline'}
        );
        markers.push(marker);
        
        editor.scrollIntoView({line: lineIdx, ch: 0}, 200);
    }

    // ── API Communication ──────────────────────────────────────
    async function compileCode() {
        const code = editor.getValue();
        localStorage.setItem('mini_c_code', code);

        // UI Loading State
        compileBtn.disabled = true;
        const icon = compileBtn.querySelector('i');
        const originalIconClass = icon.className;
        icon.className = 'fas fa-circle-notch loading-icon';
        compileBtnText.textContent = 'Analyzing...';
        
        statusText.textContent = 'Compiling...';
        statusDot.style.background = 'var(--warning-yellow)';
        statusDot.classList.add('pulse'); // If pulse animation is defined

        try {
            const response = await fetch('http://localhost:5001/compile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (!response.ok) throw new Error(`Backend Error (${response.status})`);

            const data = await response.json();
            // The backend returns { errors: [...] } or { diagnostics: [...] }
            // Let's handle both for compatibility
            const results = data.errors || data.diagnostics || [];
            renderDiagnostics(results);
        } catch (err) {
            console.error('Compilation failed:', err);
            renderErrorItem('Connection Error', err.message);
        } finally {
            compileBtn.disabled = false;
            icon.className = originalIconClass;
            compileBtnText.textContent = 'Compile & Run';
        }
    }

    // ── Diagnostic Rendering ───────────────────────────────────
    function renderDiagnostics(diagnostics) {
        errorList.innerHTML = '';
        clearMarkers();

        if (!diagnostics || diagnostics.length === 0) {
            renderSuccessState();
            return;
        }

        // Performance Optimization: Virtual Truncation
        // Browsers struggle with thousands of DOM nodes.
        const displayLimit = 50;
        const toDisplay = diagnostics.slice(0, displayLimit);

        const fragment = document.createDocumentFragment();
        
        toDisplay.forEach((diag, index) => {
            const item = document.createElement('div');
            const isWarning = diag.kind && diag.kind.toLowerCase().includes('warning');
            item.className = `error-item ${isWarning ? 'warning' : ''}`;
            
            // Staggered animation
            item.style.animationDelay = `${index * 0.03}s`;

            item.innerHTML = `
                <div class="error-kind">${diag.kind ? diag.kind.replace(/_/g, ' ') : 'SYNTAX ERROR'}</div>
                <div class="error-message">${escapeHtml(diag.message)}</div>
                <div class="error-line">Line ${diag.line}, Column ${diag.column}</div>
            `;

            item.onclick = () => {
                editor.setCursor(diag.line - 1, diag.column - 1);
                editor.focus();
                highlightError(diag.line, diag.column);
            };

            fragment.appendChild(item);
        });

        errorList.appendChild(fragment);

        // Update Footer Stats
        statusText.textContent = `${diagnostics.length} issues detected`;
        statusDot.style.background = 'var(--error-red)';
        
        if (diagnostics.length > displayLimit) {
            const info = document.createElement('div');
            info.style.padding = '15px';
            info.style.fontSize = '12px';
            info.style.color = 'var(--text-muted)';
            info.style.textAlign = 'center';
            info.innerHTML = `<i>+ ${diagnostics.length - displayLimit} more errors truncated for speed</i>`;
            errorList.appendChild(info);
        }
    }

    function renderSuccessState() {
        errorList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🛡️</div>
                <div class="success-badge">Code Clean</div>
                <div style="font-size: 13px; color: var(--text-muted); margin-top: 10px;">
                    No issues found in current analysis.
                </div>
            </div>
        `;
        statusText.textContent = 'System Healthy';
        statusDot.style.background = 'var(--accent-primary)';
    }

    function renderErrorItem(kind, msg) {
        errorList.innerHTML = `
            <div class="error-item">
                <div class="error-kind">${kind}</div>
                <div class="error-message">${msg}</div>
            </div>
        `;
        statusText.textContent = 'System Fault';
        statusDot.style.background = 'var(--error-red)';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ── Listeners ─────────────────────────────────────────────
    compileBtn.onclick = compileCode;
});
