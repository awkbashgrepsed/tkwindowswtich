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
