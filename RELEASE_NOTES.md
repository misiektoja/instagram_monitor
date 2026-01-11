# instagram_monitor release notes

# Changes in 2.1 (TBD)

**Features and Improvements**:

- **NEW:** Integrated a comprehensive **Dual Dashboard system** featuring a beautiful **Terminal Dashboard** (Rich-powered) and a modern **Web Dashboard** (Flask-powered), providing real-time stats, activity feeds and interactive control via a new informative loading screen
- **NEW:** Added **Dashboard View Modes** - toggle between **'User'** (minimal) and **'Config'** (detailed) modes across both dashboards with a single keypress ('m') or button click; includes synchronized state throughout the tool
- **NEW:** Added **custom output directory feature** (`OUTPUT_DIR` config option and `-o` / `--output-dir` flag) to organize all downloaded files into target-specific subdirectories (**images**, **videos**, **logs**, **json**, **csvs**); significantly improves organization for multi-target monitoring (closes [#35](https://github.com/misiektoja/instagram_monitor/issues/35))
- **NEW:** Implemented **per-target logging** - in multi-target mode, each user gets their own log file; common messages (like the summary screen) are automatically broadcasted to all active logs
- **NEW:** Introduced **Verbose Mode** (`--verbose` flag or `VERBOSE_MODE` config option) - provides a middle-ground logging level that shows timing details, next check schedule and loop completion messages without the exhaustive detail of Debug Mode
- **NEW:** Implemented **Debug Mode** (`--debug` flag or `DEBUG_MODE` config) - provides full technical logging including every API request and internal state changes
- **IMPROVE:** Enhanced **CSV path resolution** - CSV files are now automatically placed in a `csvs/` subdirectory when `OUTPUT_DIR` and relative path is used. In **multi-target mode**, the tool always enforces **per-user files** (even with absolute paths) to ensure data isolation
- **IMPROVE:** Enhanced startup summary to display the configured **Output directory** and its role (root for user data vs container for per-user subdirectories)
- **IMPROVE:** Enhanced `CHECK_POSTS_IN_HOURS_RANGE` logic to support **disabling hour ranges** and updated status message (to disable any range, set both MIN and MAX to 0)
- **IMPROVE:** Added display of next user check time after the initial processing is finished
- **IMPROVE:** Simplified status messages to 'OK'
- **IMPROVE:** Enhanced **Logger** to be dashboard-aware, preventing interleaved output when the dashboard is active
- **IMPROVE:** Further enhanced **error messages** for **Instagram challenge/shadow ban detection** - when Instagram requires a challenge/re-login or temporarily shadow bans the IP, error messages now provide clear, informative explanations instead of cryptic **KeyError 'data'** messages

**Bug fixes**:

- **BUGFIX:** Fixed latest post detection logic in anonymous mode (fixes [#34](https://github.com/misiektoja/instagram_monitor/issues/34))

# Changes in 2.0.4 (04 Jan 2026)

**Features and Improvements**:

- **IMPROVE:** standardized **visual appearance** of **progress bar** to unify its width in both terminal and log files

**Bug fixes**:

- **BUGFIX:** Fixed **progress bar display issues** - Ensured `close_pbar()` is called before any print statements in the `try` block to prevent interleaved output and duplicate progress bars (thanks [@tomballgithub](https://github.com/tomballgithub))

# Changes in 2.0.3 (03 Jan 2026)
