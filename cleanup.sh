#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  C-Mini-Compiler — Safe Cleanup Script  v2
#
#  Usage:
#    bash cleanup.sh --dry-run     Preview every action, move nothing
#    bash cleanup.sh               Run interactively (prompts for grey-area files)
#    bash cleanup.sh --yes         Approve ALL removals without prompts
#
#  Files are moved to .trash/ — never permanently deleted.
#  To restore: mv .trash/<path> <path>
#  To nuke trash: rm -rf .trash/
# ═══════════════════════════════════════════════════════════════

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TRASH="$ROOT/.trash"

DRY_RUN=false
YES_ALL=false
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --yes)     YES_ALL=true  ;;
    --help)
      sed -n '2,12p' "$0" | sed 's/^#  \?//'
      exit 0 ;;
  esac
done

# ── Colours ────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED='\033[0;31m' YELLOW='\033[1;33m' GREEN='\033[0;32m'
  CYAN='\033[0;36m' BOLD='\033[1m' DIM='\033[2m' RESET='\033[0m'
else
  RED='' YELLOW='' GREEN='' CYAN='' BOLD='' DIM='' RESET=''
fi

MOVED=0; SKIPPED=0

# ── Core helpers ───────────────────────────────────────────────
_move() {
  local path="$1" reason="$2"
  local rel="${path#$ROOT/}"
  if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} ${CYAN}${rel}${RESET}  ← ${DIM}${reason}${RESET}"
    ((MOVED++)) || true
    return
  fi
  local dest="$TRASH/$rel"
  mkdir -p "$(dirname "$dest")"
  mv "$path" "$dest"
  echo -e "  ${GREEN}✓ moved${RESET}: ${CYAN}${rel}${RESET}"
  ((MOVED++)) || true
}

_ask_move() {
  local path="$1" reason="$2"
  local rel="${path#$ROOT/}"
  # Dry-run: show what would happen, no prompt
  if $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} ${CYAN}${rel}${RESET}  ← ${DIM}${reason}${RESET}"
    ((MOVED++)) || true
    return
  fi
  if $YES_ALL; then
    _move "$path" "$reason"
    return
  fi
  echo -e "  ${YELLOW}?${RESET} ${CYAN}${rel}${RESET}"
  echo -e "    ${DIM}${reason}${RESET}"
  printf "    Move to .trash/? [y/N] "
  if [[ -t 0 ]]; then
    read -r ans
  else
    ans="n"   # non-interactive shell: default keep
    echo "N (non-interactive, use --yes to auto-approve)"
  fi
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    _move "$path" "$reason"
  else
    echo -e "  ${RED}kept${RESET}: ${CYAN}${rel}${RESET}"
    ((SKIPPED++)) || true
  fi
}

_header() { echo ""; echo -e "${BOLD}── $* ──${RESET}"; }

# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  C-Mini-Compiler — Cleanup Script${RESET}"
$DRY_RUN && echo -e "  ${YELLOW}DRY-RUN MODE — nothing will actually move${RESET}"
$YES_ALL && echo -e "  ${YELLOW}--yes flag set — auto-approving all prompts${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"

mkdir -p "$TRASH"

# ── 1. __pycache__ directories (always safe) ──────────────────
_header "1 · Compiled bytecode (__pycache__ directories)"
while IFS= read -r -d '' dir; do
  _move "$dir" "bytecode cache — auto-regenerated"
done < <(find "$ROOT" \
           -not -path '*/venv/*' -not -path '*/.git/*' \
           -not -path '*/.trash/*' \
           -name '__pycache__' -type d -print0 2>/dev/null)

# ── 2. Stray .pyc / .pyo outside __pycache__ ─────────────────
_header "2 · Stray .pyc / .pyo files"
FOUND=0
while IFS= read -r -d '' f; do
  _move "$f" "compiled bytecode"
  FOUND=1
done < <(find "$ROOT" \
           -not -path '*/venv/*' -not -path '*/.git/*' \
           -not -path '*/.trash/*' -not -path '*/__pycache__/*' \
           \( -name '*.pyc' -o -name '*.pyo' \) -print0 2>/dev/null)
[[ $FOUND -eq 0 ]] && echo -e "  ${DIM}none found${RESET}"

# ── 3. src/backend.py — duplicate of root backend.py ─────────
_header "3 · src/backend.py (duplicate of root backend.py)"
SB="$ROOT/src/backend.py"
if [[ -f "$SB" ]]; then
  _ask_move "$SB" \
    "Duplicate — main.py uses root backend.py; this copy in src/ causes import confusion"
else
  echo -e "  ${DIM}not present${RESET}"
fi

# ── 4. Superseded per-phase test files ────────────────────────
_header "4 · Older per-phase test files (superseded by test_compiler.py)"
echo -e "  ${DIM}test_compiler.py covers all phases with 45 tests (100 % pass rate).${RESET}"
for f in \
  "$ROOT/tests/test_integration.py" \
  "$ROOT/tests/test_lexer.py" \
  "$ROOT/tests/test_parser.py" \
  "$ROOT/tests/test_semantic.py"
do
  if [[ -f "$f" ]]; then
    _ask_move "$f" "Older per-phase test — superseded by test_compiler.py"
  fi
done

# ── 5. OS / editor debris ─────────────────────────────────────
_header "5 · OS / editor debris"
FOUND=0
while IFS= read -r -d '' f; do
  _move "$f" "OS/editor debris"
  FOUND=1
done < <(find "$ROOT" \
           -not -path '*/venv/*' -not -path '*/.git/*' \
           -not -path '*/.trash/*' \
           \( -name '.DS_Store' -o -name 'Thumbs.db' \
              -o -name '*.swp'  -o -name '*.swo' \
              -o -name '*.bak'  -o -name '*~' \
              -o -name '*.log'  -o -name '*.tmp' \) -print0 2>/dev/null)
[[ $FOUND -eq 0 ]] && echo -e "  ${DIM}none found${RESET}"

# ── 6. test_examples/ — overlaps tests/test_cases/ ───────────
_header "6 · test_examples/ directory"
TE="$ROOT/test_examples"
if [[ -d "$TE" ]]; then
  _ask_move "$TE" \
    "2-file directory that duplicates tests/test_cases/ content"
else
  echo -e "  ${DIM}not present${RESET}"
fi

# ── 7. samples/ — demo files (optional) ──────────────────────
_header "7 · samples/ directory (optional demo files)"
SD="$ROOT/samples"
if [[ -d "$SD" ]]; then
  _ask_move "$SD" \
    "3 demo .c files — not imported by any module; useful for manual demos only"
else
  echo -e "  ${DIM}not present${RESET}"
fi

# ── 8. run_tests.sh stale reference note ─────────────────────
_header "8 · run_tests.sh stale references (info only)"
echo -e "  ${YELLOW}run_tests.sh${RESET} tests 1-3 call ${CYAN}src/c_lexer.py${RESET}, ${CYAN}src/c_parser.py${RESET},"
echo -e "  ${CYAN}src/c_validator.py${RESET} — these never existed (old filenames)."
echo -e "  Those blocks print 'FAIL' but do not abort the script."
echo -e "  ${DIM}Consider editing run_tests.sh to remove the stale blocks.${RESET}"

# ── Summary ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  DONE${RESET}"
printf "  Moved  : ${GREEN}%d${RESET}\n" "$MOVED"
printf "  Kept   : ${YELLOW}%d${RESET}\n" "$SKIPPED"
echo ""
echo -e "  Trash location : ${CYAN}.trash/${RESET}"
echo -e "  To restore     : ${DIM}mv .trash/<rel-path> <dest>${RESET}"
echo -e "  To nuke trash  : ${RED}rm -rf .trash/${RESET}"
$DRY_RUN && echo -e "  ${YELLOW}DRY-RUN — nothing was actually moved.${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${RESET}"
echo ""
