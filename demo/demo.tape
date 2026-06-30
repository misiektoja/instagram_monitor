# VHS tape for the instagram_monitor demo: pip install -> setup wizard -> run
#
# Render it (run from the repo root so $PWD is the project):
#     brew install vhs        # one-time (also pulls ttyd + ffmpeg)
#     vhs demo/demo.tape      # writes assets/instagram_monitor_demo.gif
#
# It builds a wheel from the local source so `pip install instagram_monitor`
# shows the current version even before it is published to PyPI. The first
# render creates a cached venv and installs dependencies (slow); see the Sleep
# note in the hidden setup below.

Output assets/instagram_monitor_demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1320
Set Height 820
Set Padding 20
Set Theme "Dracula"
Set TypingSpeed 55ms
Set WindowBar Colorful

# ---------------------------------------------------------------------------
# Hidden setup: isolated venv + local wheel so the visible `pip install` is real
# ---------------------------------------------------------------------------
Hide
Type 'REPO="$PWD"' Enter
Type 'VENV="$HOME/.cache/im-demo-venv"' Enter
Type '[ -d "$VENV" ] || { python3 -m venv "$VENV" && "$VENV/bin/pip" install -q --upgrade pip setuptools wheel build && "$VENV/bin/pip" install -q -r "$REPO/requirements.txt"; }' Enter
# First render only: deps install here. Lower this to ~3s on later renders.
Sleep 90s
Type 'source "$VENV/bin/activate"' Enter
Type 'WHEELS="$(mktemp -d)"; pip wheel -q --no-build-isolation --no-deps -w "$WHEELS" "$REPO"' Enter
Sleep 12s
Type 'export PIP_FIND_LINKS="$WHEELS" PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1' Enter
Type 'pip uninstall -y -q instagram_monitor 2>/dev/null; true' Enter
Type 'cd "$(mktemp -d)"' Enter
Type 'clear' Enter
Show

# ---------------------------------------------------------------------------
# 1. Install
# ---------------------------------------------------------------------------
Type "pip install instagram_monitor"
Sleep 800ms
Enter
Sleep 3s
Type "clear"
Enter
Sleep 500ms

# ---------------------------------------------------------------------------
# 2. Setup wizard (no-login, web dashboard, no alerts)
# ---------------------------------------------------------------------------
Type "instagram_monitor --setup"
Sleep 800ms
Enter
Sleep 3s

# Which account to monitor
Type "casual_stream"
Sleep 800ms
Enter
Sleep 2500ms

# Log in? 1 = No (no login)
Type "1"
Sleep 600ms
Enter
Sleep 2500ms

# View activity how? 1 = Web dashboard
Type "1"
Sleep 600ms
Enter
Sleep 1000ms

# Discord alerts? n
Type "n"
Sleep 500ms
Enter
Sleep 1000ms

# Email alerts? n
Type "n"
Sleep 500ms
Enter
Sleep 2500ms

# Run the doctor check now? n
Type "n"
Sleep 500ms
Enter
Sleep 2000ms

# ---------------------------------------------------------------------------
# 3. Start monitoring now? y  -> the web dashboard launches
# ---------------------------------------------------------------------------
Type "y"
Sleep 500ms
Enter
Sleep 10s

Ctrl+C
Sleep 2500ms
