# View Modes

The tool provides three distinct ways to visualize monitoring activity:

1. **Traditional Text Mode**: Standard CLI output, best for logging and background processes.
2. **Terminal Dashboard**: A rich, interactive terminal interface with real-time stats.
3. **Web Dashboard**: A modern web interface accessible via your browser.

---

<a id="traditional-text-mode"></a>
## Traditional Text Mode

This is the classic command-line output. It is characterized by:
- **Clean, sequential logging**: Every event is printed as it happens with a timestamp.
- **Persistence**: Ideal for running in the background (e.g., via `nohup` or `tmux`) where you want a full history of events in your terminal scrollback or log files.
- **Low Overhead**: Minimal resource usage and compatible with any terminal.

It is the default mode of operation.

---

<a id="terminal-dashboard-mode"></a>
## Terminal Dashboard

The Terminal Dashboard provides a beautiful, live-updating interface directly in your terminal. It requires the `rich` library.

To enable the terminal dashboard, use the `--dashboard` flag (or set `DASHBOARD_ENABLED = True` in your config).

**Key Features:**
- **Visual Analytics**: Real-time display of tracked targets with number of followers, followings, posts, visibility and story status.
- **Live Activity Log**: A scrolling view of the last few events.
- **Interactive Toggles**: Press **'m'** to switch between 'User' and 'Config' views instantly.
- **Remote Control**: Start, stop or recheck monitoring for all targets directly from the terminal.
- **Uptime & Status**: Clean header showing tool version, status and total runtime.

**Keyboard Shortcuts:**
- **'m'**: Toggle dashboard view (User/Config)
- **'s'**: **Start All** monitoring
- **'x'**: **Stop All** monitoring
- **'r'**: **Recheck All** targets
- **'q'**: **Exit** the tool
- **'h'**: Show help (lists commands in the activity log)

```sh
instagram_monitor target1 target2 --dashboard
```

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_terminal_dashboard.png" alt="instagram_monitor_terminal_dashboard_screenshot" width="100%"/>
</p>

---

<a id="web-dashboard-mode"></a>
## Web Dashboard

A modern, real-time web interface running on your local machine (default: `http://127.0.0.1:8000/`).

**Key Features:**
- **Full Control Panel**: Add or remove monitoring targets directly from the browser.
- **Visual Analytics**: Real-time display of tracked targets with number of followers, followings, posts, visibility and story status.
- **Live Activity Log**: A scrolling view of the last few events.
- **Manual Trigger**: A "Recheck" button to force an immediate update for specific or all users.
- **Remote Management**: Start or stop monitoring for specific or all targets with a single click.
- **Synchronization**: Changes made in the web dashboard (like mode toggles) are reflected in the terminal instantly.
- **Dynamic Configuration**: Configure sessions and settings without touching the terminal or config files.

To enable the web dashboard, use the `--web-dashboard` flag (or set `WEB_DASHBOARD_ENABLED = True` in your config).

**Flexible Usage:**
- **Standard Monitoring**: Provide targets on the CLI and the dashboard acts as a live mirror and remote management interface.
- **Control Panel Mode**: Start the tool with **only** the `--web-dashboard` flag (no initial targets). The script will wait for you to add users through the browser.

```sh
# Starting with initial targets
instagram_monitor target1 target2 --web-dashboard

# Starting as a pure control panel
instagram_monitor --web-dashboard
```

The web dashboard requires `flask`. If flask is missing, it will be disabled while the console output remains active.

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png" alt="instagram_monitor_web_dashboard_screenshot" width="90%"/>
</p>

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard_settings.png" alt="instagram_monitor_web_dashboard_settings_screenshot" width="90%"/>
</p>

---

<a id="dashboard-view-modes"></a>
## Dashboard View Modes

Both the Terminal and Web dashboards support two levels of information density:

1. **User Mode** (`user`):
   - Simple, minimal interface.
   - Focuses on core stats and latest activity.
   - Ideal for "always-on" monitoring.

2. **Config Mode** (`config`):
   - Detailed view showing all internal settings.
   - Displays User Agent strings, Hour Ranges, Jitter status and more.
   - Useful for auditing your setup and verifying configuration.

Toggle seamlessly between modes using the **'m'** key or the web dashboard toggle button.

<a id="usage"></a>
