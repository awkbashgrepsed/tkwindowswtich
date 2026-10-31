"""
Tk Windows Switcher
A lightweight Windows window switcher and monitor mover built with Tkinter.
Uses only the Python standard library and the Windows API.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Optional

if __import__("os").name != "nt":
    raise SystemExit("Tk Windows Switcher currently supports Windows only.")

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

MONITOR_DEFAULTTONEAREST = 2
MONITORINFOF_PRIMARY = 1
DWMWA_CLOAKED = 14
SW_RESTORE = 9
SW_SHOW = 5
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
GW_OWNER = 4

LONG_PTR = ctypes.c_ssize_t


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG), ("top", wintypes.LONG),
        ("right", wintypes.LONG), ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# Declare Win32 signatures explicitly so HWND/HMONITOR handles are not
# truncated on 64-bit Windows.
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC, ctypes.POINTER(RECT), ctypes.c_void_p, wintypes.LPARAM
]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.EnumWindows.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


@dataclass
class Monitor:
    handle: int
    name: str
    bounds: RECT
    work: RECT
    primary: bool

    @property
    def width(self) -> int:
        return self.bounds.right - self.bounds.left

    @property
    def height(self) -> int:
        return self.bounds.bottom - self.bounds.top


@dataclass
class Window:
    handle: int
    title: str
    monitor_handle: int
    rect: RECT
    process_id: int


def _rect_copy(rect: RECT) -> RECT:
    return RECT(rect.left, rect.top, rect.right, rect.bottom)


def get_monitors() -> list[Monitor]:
    monitors: list[Monitor] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(RECT), wintypes.LPARAM
    )

    def callback(handle, _hdc, _rect, _data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            index = len(monitors) + 1
            primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            label = f"Monitor {index}" + (" (Primary)" if primary else "")
            monitors.append(Monitor(
                int(handle), label, _rect_copy(info.rcMonitor),
                _rect_copy(info.rcWork), primary
            ))
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(callback), 0)
    return monitors


def monitor_for_window(hwnd: int) -> int:
    return int(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST) or 0)


def monitor_for_point(x: int, y: int) -> int:
    point = POINT(x, y)
    return int(user32.MonitorFromPoint(point, MONITOR_DEFAULTTONEAREST) or 0)


def get_startup_monitor(monitors: list[Monitor]) -> Optional[Monitor]:
    # The cursor is the most reliable indication of which display the user
    # launched the utility from (including launches from the Start menu).
    point = POINT()
    if user32.GetCursorPos(ctypes.byref(point)):
        handle = monitor_for_point(point.x, point.y)
        for monitor in monitors:
            if monitor.handle == handle:
                return monitor

    foreground = int(user32.GetForegroundWindow() or 0)
    handle = monitor_for_window(foreground) if foreground else 0
    return next((m for m in monitors if m.handle == handle), None)


def get_windows(monitors: list[Monitor], own_pid: int) -> list[Window]:
    found: list[Window] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND)

    def callback(hwnd):
        if not user32.IsWindowVisible(hwnd):
            return True

        title_length = user32.GetWindowTextLengthW(hwnd)
        if title_length <= 0:
            return True

        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value == own_pid:
            return True

        # Exclude DWM-cloaked windows (for example, windows hidden on another
        # virtual desktop) while retaining ordinary minimized windows.
        cloaked = wintypes.DWORD()
        try:
            result = dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked),
                ctypes.sizeof(cloaked)
            )
            if result == 0 and cloaked.value:
                return True
        except (AttributeError, OSError):
            pass

        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value.strip()
        if not title:
            return True

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True

        handle = monitor_for_window(hwnd)
        found.append(Window(
            int(hwnd), title, handle, _rect_copy(rect), process_id.value
        ))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return found


def move_window_to_monitor(window: Window, target: Monitor) -> bool:
    left, top, right, bottom = (
        window.rect.left, window.rect.top,
        window.rect.right, window.rect.bottom
    )
    width = max(160, right - left)
    height = max(100, bottom - top)

    source = next(
        (m for m in get_monitors() if m.handle == window.monitor_handle), None
    )
    # Keep the window's relative position when possible; otherwise center it.
    if source and source.width > 0 and source.height > 0:
        rel_x = (left - source.bounds.left) / source.width
        rel_y = (top - source.bounds.top) / source.height
        x = target.bounds.left + round(rel_x * target.width)
        y = target.bounds.top + round(rel_y * target.height)
    else:
        x = target.bounds.left + (target.width - width) // 2
        y = target.bounds.top + (target.height - height) // 2

    work = target.work
    work_width = work.right - work.left
    work_height = work.bottom - work.top
    width = min(width, work_width)
    height = min(height, work_height)
    x = min(max(x, work.left), work.right - width)
    y = min(max(y, work.top), work.bottom - height)

    user32.ShowWindow(window.handle, SW_RESTORE)
    return bool(user32.SetWindowPos(
        window.handle, None, x, y, width, height,
        SWP_NOZORDER | SWP_NOACTIVATE
    ))


class WindowSwitcher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.own_pid = __import__("os").getpid()
        self.monitors: list[Monitor] = []
        self.windows: list[Window] = []
        self.listboxes: dict[int, tk.Listbox] = {}
        self.tab_monitor: dict[str, int] = {}
        self.tab_labels: dict[int, str] = {}

        root.title("Tk Windows Switcher")
        root.minsize(520, 360)
        root.geometry("760x500")
        self._build_ui()
        self.refresh()

        startup_monitor = get_startup_monitor(self.monitors)
        if startup_monitor:
            root.withdraw()
            root.update_idletasks()
            self._place_on_monitor(startup_monitor)
            root.deiconify()
        self.root.after(1800, self._periodic_refresh)

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            header, text="Open windows",
            font=("Segoe UI", 13, "bold")
        ).pack(side="left")
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text="Move selected window to:").pack(side="left")
        self.target_combo = ttk.Combobox(
            footer, state="readonly", width=24
        )
        self.target_combo.pack(side="left", padx=8)
        ttk.Button(
            footer, text="Move",
            command=self.move_selected
        ).pack(side="left")
        ttk.Button(
            footer, text="Switch to window",
            command=self.activate_selected
        ).pack(side="right")

        self.status = ttk.Label(outer, text="", anchor="w")
        self.status.pack(fill="x", pady=(7, 0))

    def _place_on_monitor(self, monitor: Monitor):
        self.root.update_idletasks()
        width = max(520, self.root.winfo_width())
        height = max(360, self.root.winfo_height())
        x = monitor.work.left + (monitor.work.right - monitor.work.left - width) // 2
        y = monitor.work.top + (monitor.work.bottom - monitor.work.top - height) // 2
        self.root.geometry(f"{width}x{height}{x:+d}{y:+d}")

    def refresh(self):
        selected_handle = None
        selected_window_handle = None
        current_tab = self.notebook.select() if hasattr(self, "notebook") else None
        if current_tab:
            selected_handle = self.tab_monitor.get(current_tab)
            old_listing = self.listboxes.get(selected_handle)
            if old_listing and old_listing.curselection():
                old_candidates = [
                    w for w in self.windows if w.monitor_handle == selected_handle
                ]
                old_index = old_listing.curselection()[0]
                if old_index < len(old_candidates):
                    selected_window_handle = old_candidates[old_index].handle

        self.monitors = get_monitors()
        self.windows = get_windows(self.monitors, self.own_pid)

        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        self.listboxes.clear()
        self.tab_monitor.clear()
        self.tab_labels.clear()

        for index, monitor in enumerate(self.monitors, start=1):
            frame = ttk.Frame(self.notebook, padding=8)
            frame.pack(fill="both", expand=True)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

            listing = tk.Listbox(
                frame, activestyle="dotbox", font=("Segoe UI", 10),
                selectmode=tk.SINGLE, exportselection=False
            )
            scrollbar = ttk.Scrollbar(
                frame, orient="vertical", command=listing.yview
            )
            listing.configure(yscrollcommand=scrollbar.set)
            listing.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            listing.bind("<Double-Button-1>", lambda _e: self.activate_selected())

            monitor_windows = [
                w for w in self.windows if w.monitor_handle == monitor.handle
            ]
            for window in monitor_windows:
                listing.insert("end", window.title)
            if monitor.handle == selected_handle and selected_window_handle:
                for row, window in enumerate(monitor_windows):
                    if window.handle == selected_window_handle:
                        listing.selection_set(row)
                        listing.activate(row)
                        break
            if not monitor_windows:
                listing.insert("end", "(No open windows)")
                listing.itemconfigure(0, foreground="gray")

            tab_id = self.notebook.add(frame, text=monitor.name)
            tab_id = self.notebook.tabs()[-1]
            self.listboxes[monitor.handle] = listing
            self.tab_monitor[tab_id] = monitor.handle
            self.tab_labels[monitor.handle] = monitor.name

            if monitor.handle == selected_handle:
                self.notebook.select(tab_id)

        self.target_combo["values"] = [
            f"{m.name} — {m.width}×{m.height}" for m in self.monitors
        ]
        if self.monitors and self.target_combo.current() < 0:
            self.target_combo.current(0)

        self.status.configure(
            text=f"{len(self.windows)} windows across {len(self.monitors)} monitor(s)"
        )

    def _selected_window(self) -> Optional[Window]:
        tab = self.notebook.select()
        monitor_handle = self.tab_monitor.get(tab)
        listing = self.listboxes.get(monitor_handle)
        if listing is None or not listing.curselection():
            return None
        index = listing.curselection()[0]
        candidates = [
            w for w in self.windows if w.monitor_handle == monitor_handle
        ]
        return candidates[index] if index < len(candidates) else None

    def activate_selected(self):
        window = self._selected_window()
        if not window:
            return
        user32.ShowWindow(window.handle, SW_RESTORE)
        user32.BringWindowToTop(window.handle)
        user32.SetForegroundWindow(window.handle)

    def move_selected(self):
        window = self._selected_window()
        target_index = self.target_combo.current()
        if not window or target_index < 0 or target_index >= len(self.monitors):
            return
        target = self.monitors[target_index]
        if target.handle == window.monitor_handle:
            self.status.configure(text="That window is already on this monitor.")
            return
        if move_window_to_monitor(window, target):
            self.status.configure(text=f"Moved “{window.title}” to {target.name}.")
            self.refresh()
        else:
            messagebox.showerror(
                "Move failed",
                "Windows could not move this window. It may be protected by the system."
            )

    def _periodic_refresh(self):
        # Avoid rebuilding the lists while the user is selecting an item.
        try:
            self.refresh()
        finally:
            self.root.after(1800, self._periodic_refresh)


def main():
    root = tk.Tk()
    WindowSwitcher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
