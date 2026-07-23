# View Modes

Examples on this page use the PyPI command `instagram_monitor`. If you chose another installation, replace that command with the matching [command prefix](usage.md#command-format). Keep all targets and options after the prefix.

Choose one of three ways to view monitoring activity:

1. **Traditional Text Mode**: Standard CLI output, best for logging and background processes.
2. **Terminal Dashboard**: A rich, interactive terminal interface with real-time stats.
3. **Web Dashboard**: A modern web interface accessible via your browser.

---

<a id="traditional-text-mode"></a>
## Traditional Text Mode

Text mode is the default. It works in any terminal and is well suited to background processes.

- Every event is printed with a timestamp.
- Earlier events remain available in terminal scrollback and log files.
- It uses fewer terminal features than either dashboard.

---

<a id="terminal-dashboard-mode"></a>
## Terminal Dashboard

The Terminal Dashboard updates status, statistics and recent events in one terminal screen. It requires the `rich` library, which is included in normal installations.

Enable it with `--dashboard` or `DASHBOARD_ENABLED = True`.

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

The Web Dashboard runs a small web server on your computer. By default, open `http://127.0.0.1:8000/` in a browser on the same computer. The `127.0.0.1` address is local, so other devices cannot connect unless you change the server and Docker settings.

In a container the server must bind to `0.0.0.0` so Docker can forward traffic. That value means every container network interface. It is not a browser destination. Use the published host address `http://127.0.0.1:8000/` instead.

**Key Features:**

- **Full Control Panel**: Add or remove monitoring targets directly from the browser.
- **Visual Analytics**: Real-time display of tracked targets with number of followers, followings, posts, visibility and story status.
- **Live Activity Log**: A scrolling view of the last few events.
- **Manual Trigger**: A "Recheck" button to force an immediate update for specific or all users.
- **Remote Management**: Start or stop monitoring for specific or all targets with a single click.
- **Synchronization**: Changes made in the web dashboard (like mode toggles) are reflected in the terminal instantly.
- **Dynamic Configuration**: Configure sessions and settings without touching the terminal or config files.

Enable it with `--web-dashboard` or `WEB_DASHBOARD_ENABLED = True`.

**Flexible Usage:**

- **Standard Monitoring**: Provide targets on the CLI and the dashboard acts as a live mirror and remote management interface.
- **Control Panel Mode**: Start the tool with **only** the `--web-dashboard` flag (no initial targets). The script will wait for you to add users through the browser.

```sh
# Starting with initial targets
instagram_monitor target1 target2 --web-dashboard

# Starting as a pure control panel
instagram_monitor --web-dashboard
```

The Web Dashboard requires `flask`, which is included in normal installations. If it is missing, Instagram Monitor disables the dashboard but keeps console monitoring active.

Docker Compose exposes the default dashboard only at `127.0.0.1` on the host. Use `docker compose up --no-log-prefix` if setup enabled the Web Dashboard. For a one-off Compose command, add `--service-ports`. A plain `docker compose run --rm` starts the server but does not publish the service port:

```sh
docker compose run --rm --service-ports instagram_monitor target1 target2 --web-dashboard
```

For direct Docker, add `-p 127.0.0.1:8000:8000` before the image name. The complete mount and port forms are under [Monitoring Mode](usage.md#monitoring-mode).

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard.png" alt="instagram_monitor_web_dashboard_screenshot" width="90%"/>
</p>

<p align="center">
   <img src="https://raw.githubusercontent.com/misiektoja/instagram_monitor/refs/heads/main/assets/instagram_monitor_web_dashboard_settings.png" alt="instagram_monitor_web_dashboard_settings_screenshot" width="90%"/>
</p>

---

<a id="dashboard-view-modes"></a>
## Dashboard View Modes

Both dashboards offer two views:

1. **User Mode** (`user`):
   - Simple, minimal interface.
   - Focuses on core stats and latest activity.
   - Ideal for "always-on" monitoring.

2. **Config Mode** (`config`):
   - Detailed view showing all internal settings.
   - Displays User Agent strings, Hour Ranges, Jitter status and more.
   - Useful for auditing your setup and verifying configuration.

Switch views with the **'m'** key in the Terminal Dashboard or the view button in the Web Dashboard.
