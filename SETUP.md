# C Mini-Compiler - Setup & Installation Guide

## Quick Start (2 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Backend
```bash
python backend.py
```

You should see:
```
╔═══════════════════════════════════════════════════════════╗
║       C Mini-Compiler Backend - Flask Server             ║
╚═══════════════════════════════════════════════════════════╝

📍 Frontend:     http://localhost:5000
🔨 API Endpoint: http://localhost:5000/compile
✓ CORS Enabled

Starting server...
```

### 3. Open Browser
Navigate to: **http://localhost:5000**

### 4. Start Testing
- Paste C code or use the default example
- Click **"⚙️ Compile"** or press **Ctrl+Enter**
- See errors highlighted in real-time

---

## System Requirements

- **Python 3.8+**
- **pip** (Python package manager)
- **Modern browser** (Chrome, Firefox, Safari, Edge)
- **Port 5000** (for Flask server)

---

## Installation Steps (Detailed)

### Step 1: Check Python Version
```bash
python --version    # Should show 3.8 or higher
python3 --version   # Alternative command
```

### Step 2: Install Dependencies
```bash
cd /path/to/project
pip install -r requirements.txt
```

**What gets installed:**
- Flask 3.0.0 - Web server
- Flask-CORS 4.0.0 - Enable cross-origin requests

### Step 3: Verify Installation
```bash
python -c "import flask; import flask_cors; print('✓ All dependencies installed')"
```

### Step 4: Run Backend Server
```bash
python backend.py
```

Server will start on `http://localhost:5000`

### Step 5: Open Web Interface
Open your browser and go to: `http://localhost:5000`

---

## Testing the Installation

### Test 1: Simple Program (Should Pass)
```c
int main() {
    int x = 5;
    return 0;
}
```
Expected: **✓ Clean**

### Test 2: Missing Semicolon (Should Fail)
```c
int main() {
    int x = 5
    return 0;
}
```
Expected: **MISSING_SEMICOLON** at line 2

### Test 3: Unmatched Brace (Should Fail)
```c
int main() {
    int x = 5;
    return 0;
}}
```
Expected: **UNMATCHED_BRACE** error

### Test 4: Run Polynomial Tests
```bash
python test_polynomial.py
```

This runs three comprehensive test cases with polynomial multiplication.

---

## Project Structure

```
.
├── app.js                    ← Frontend code (editor, UI)
├── index.html                ← Web page layout
├── styles.css                ← Custom CSS styling
├── backend.py                ← Flask server
├── c_lexer.py                ← Phase 1: Tokenization
├── c_parser.py               ← Phase 2: Parsing to AST
├── c_validator.py            ← Phase 3: Semantic validation
├── test_polynomial.py        ← Test cases (polynomial mult)
├── requirements.txt          ← Python dependencies
├── README.md                 ← Project documentation
├── SETUP.md                  ← This file
└── .gitignore                ← Git ignore rules
```

---

## Common Issues & Solutions

### Issue 1: Port 5000 Already in Use

**Error:** `OSError: [Errno 48] Address already in use`

**Solution:**
```bash
# Find what's using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or change the port in backend.py
# Edit: app.run(debug=True, port=5001)
```

### Issue 2: Module Not Found Error

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
pip install Flask==3.0.0
pip install Flask-CORS==4.0.0
```

### Issue 3: CORS Error in Browser

**Error:** `Access to XMLHttpRequest blocked by CORS policy`

**Solution:**
- Ensure Flask-CORS is installed
- Check backend is running
- Refresh browser (Ctrl+F5)

### Issue 4: Can't Connect to Backend

**Error:** `Connection Error: Make sure Flask backend is running`

**Solution:**
1. Start the backend: `python backend.py`
2. Check if it's running: `http://localhost:5000/health`
3. Check browser console (F12) for actual error

### Issue 5: Code Not Compiling

**Issue:** Click compile but nothing happens

**Solutions:**
- Open browser console (F12)
- Check for JavaScript errors
- Verify backend is running
- Try the test cases first

---

## Running Individual Phase Tests

### Test Phase 1 (Lexer)
```bash
python c_lexer.py
```

Outputs:
- Token list with types, values, line/column
- Symbol table with identifier occurrences

### Test Phase 2 (Parser)
```bash
python c_parser.py
```

Outputs:
- Abstract Syntax Tree (AST)
- Pretty-printed tree structure

### Test Phase 3 (Validator)
```bash
python c_validator.py
```

Outputs:
- All validation errors found
- Pretty-printed diagnostic report
- Color-coded by error type

### Test Polynomial Cases
```bash
python test_polynomial.py
```

Outputs three test results:
1. Clean polynomial multiplication
2. With functions and helpers
3. With intentional errors

---

## Browser Support

| Browser | Status |
|---------|--------|
| Chrome 90+ | ✅ Full Support |
| Firefox 88+ | ✅ Full Support |
| Safari 14+ | ✅ Full Support |
| Edge 90+ | ✅ Full Support |
| IE 11 | ❌ Not Supported |

---

## Performance Notes

- **Typical compile time**: 10-50ms
- **Large files (100+ lines)**: 100-200ms
- **Very large files (500+ lines)**: 500-1000ms

If compilation feels slow:
1. Check CPU usage
2. Try smaller code snippets
3. Restart backend server

---

## API Endpoints

### POST /compile
Compile C code and return diagnostics

**Request:**
```json
{
  "code": "int main() { return 0; }"
}
```

**Response:**
```json
{
  "errors": []
}
```

### GET /health
Check if backend is running

**Response:**
```json
{
  "status": "ok"
}
```

### GET /
Serves the web interface

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+Enter** | Compile code |
| **Cmd+Enter** | Compile code (Mac) |
| **Ctrl+/** | Toggle comment |
| **Tab** | Indent |
| **Shift+Tab** | Unindent |
| **Ctrl+Z** | Undo |
| **Ctrl+Shift+Z** | Redo |

---

## Next Steps

1. **Learn the project**: Read [README.md](README.md)
2. **Test it out**: Run `python test_polynomial.py`
3. **Explore code**: Check out the three phases (lexer, parser, validator)
4. **Modify for learning**: Try adding new error types or features

---

## Getting Help

- **Syntax errors in your code?**  
  Check: PHP reference or C standard
  
- **Compiler errors?**  
  Run: `python test_polynomial.py` to see if it's a system issue

- **Backend won't start?**  
  Check: Python 3.8+, Flask installed, port 5000 free

- **Can't see errors in UI?**  
  Check: Browser console (F12 → Console tab)

---

## Uninstall / Reset

To completely remove and reinstall:

```bash
# Remove Python packages
pip uninstall Flask Flask-CORS -y

# Remove cached files
rm -rf __pycache__ .pytest_cache

# Reinstall
pip install -r requirements.txt

# Start fresh
python backend.py
```

---

## Advanced Configuration

### Change Flask Port
Edit `backend.py`:
```python
if __name__ == '__main__':
    app.run(debug=True, port=8080)  # Change 5000 to 8080
```

Also update `app.js`:
```javascript
const apiUrl = 'http://localhost:8080/compile';  // Update here too
```

### Enable Production Mode
Edit `backend.py`:
```python
app.run(debug=False, port=5000)  # Set debug=False
```

### Add Custom Error Types
Edit `c_validator.py` and add to `ErrorKind` enum:
```python
class ErrorKind(Enum):
    # ... existing errors ...
    CUSTOM_ERROR = auto()
```

---

## Performance Tuning

### For Large Files
```python
# In backend.py, increase timeout
app.run(debug=True, port=5000, timeout=300)
```

### For Slow Networks
In `app.js`, increase fetch timeout:
```javascript
// Not directly possible in fetch, use AbortController
```

---

## Development Tips

1. **Debug lexer**: Run `python c_lexer.py` with test code
2. **Debug parser**: Check AST output in `python c_parser.py`
3. **Debug validator**: Run `python c_validator.py` with error cases
4. **Use browser DevTools**: F12 for frontend debugging
5. **Check logs**: Flask logs appear in terminal where you ran `python backend.py`

---

## What's Next?

After setup, you can:
- ✅ Compile C code
- ✅ See syntax errors
- ✅ Run test cases
- 🔮 Modify validator for new rules
- 🔮 Add semantic checks
- 🔮 Implement code generation

See [README.md](README.md) for more details on the architecture and features.
