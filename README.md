# Tk Windows Switcher

A lightweight multi-monitor window switcher for Windows, built with Python and Tkinter.

## Features

- Detects all connected monitors dynamically.
- Lists visible, titled top-level windows under the monitor they currently occupy.
- Double-click a window or use **Switch to window** to activate it.
- Move the selected window to any connected monitor.
- Refreshes the window lists automatically, while preserving the current selection.
- Opens on the monitor containing the mouse pointer when launched.
- Uses the Python standard library and Windows APIs; no third-party packages are required.

## Requirements

- Windows 10 or Windows 11
- Python 3 with Tkinter installed

## Run

```powershell
py main.py
```

The monitor containing the mouse pointer at launch is used as the startup display. If the pointer cannot be queried, the foreground window's monitor is used as a fallback.

Only visible, titled top-level windows are listed. Windows hidden by the Desktop Window Manager (for example, windows on another virtual desktop) are excluded.

## Build a Windows executable

On Windows, with Python 3 installed (including Tkinter), double-click `build.bat` or run it from Command Prompt. The script installs/updates Nuitka and builds a single-file GUI executable at `dist\TkWindowsSwitcher.exe`.

The executable is built in **one-file mode** and bundles the Python runtime, application code, and required Tk components. It does not require Python to be installed on the target PC. Nuitka one-file executables extract bundled files to a temporary directory when launched, so this is not a literally static binary; normal Windows system DLLs remain external. Build on Windows for Windows, and choose a build environment matching the architecture you want to target.
