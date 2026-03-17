"""
System tray application for Fisique Bridge.
Cross-platform: Windows, macOS, Linux (with AppIndicator).

Wraps the bridge agent (sync scheduler + HTTP server) in a visible,
non-technical UI that front desk staff can understand at a glance.
"""

import threading
import time
import tkinter as tk
from tkinter import messagebox
import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from bridge import config, device, sync, server

log = logging.getLogger(__name__)


# ── Shared state ──────────────────────────────────────────────────────────────

class AppState:
    def __init__(self):
        self.device_ok    = False
        self.cloud_ok     = False
        self.last_sync    = None
        self.enrolled     = 0
        self.sync_overdue = False
        self.lock         = threading.Lock()

    def status(self) -> str:
        with self.lock:
            if not self.device_ok:  return "device_offline"
            if not self.cloud_ok:   return "cloud_offline"
            if self.sync_overdue:   return "sync_overdue"
            return "ok"

    def summary(self) -> dict:
        with self.lock:
            return {
                "device_ok":   self.device_ok,
                "cloud_ok":    self.cloud_ok,
                "last_sync":   self.last_sync,
                "enrolled":    self.enrolled,
            }

STATE = AppState()


# ── Icon ──────────────────────────────────────────────────────────────────────

COLOURS = {
    "ok":             "#1D9E75",
    "device_offline": "#E24B4A",
    "cloud_offline":  "#888780",
    "sync_overdue":   "#EF9F27",
}

def _make_icon(status: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colour = COLOURS.get(status, "#888780")
    m = 6
    draw.ellipse([m, m, size - m, size - m], fill=colour)
    if status == "ok":
        i = 20
        draw.ellipse([i, i, size - i, size - i], fill="white")
    return img

TOOLTIPS = {
    "ok":             "Fisique Bridge — All good",
    "device_offline": "Fisique Bridge — Device offline!",
    "cloud_offline":  "Fisique Bridge — Cloud unreachable",
    "sync_overdue":   "Fisique Bridge — Sync overdue",
}


# ── Health check loop ─────────────────────────────────────────────────────────

def _health_loop(icon: pystray.Icon):
    from bridge import api
    while True:
        device_ok = device.ping()
        members   = api.get_active_members()
        cloud_ok  = isinstance(members, list)
        enrolled  = len([m for m in (members or []) if m.get("device_user_id")])

        with STATE.lock:
            STATE.device_ok = device_ok
            STATE.cloud_ok  = cloud_ok
            STATE.enrolled  = enrolled
            if STATE.last_sync:
                hours = (datetime.now() - STATE.last_sync).total_seconds() / 3600
                STATE.sync_overdue = hours > 26
            else:
                STATE.sync_overdue = False

        status = STATE.status()
        icon.icon  = _make_icon(status)
        icon.title = TOOLTIPS.get(status, "Fisique Bridge")
        time.sleep(30)


# ── Settings window ───────────────────────────────────────────────────────────

def _open_settings():
    root = tk.Tk()
    root.title("Fisique Bridge — Settings")
    root.resizable(False, False)

    cfg = config.load()
    p = {"padx": 14, "pady": 5}

    tk.Label(root, text="Fisique Bridge", font=("Helvetica", 15, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(18, 10), padx=14)

    fields = [
        ("Device IP address",        "device_ip",       False),
        ("Device port",              "device_port",     False),
        ("Device password (0=none)", "device_password", False),
        ("Web app URL",              "web_app_url",     False),
        ("API key",                  "api_key",         True),
        ("Nightly sync hour (0-23)", "sync_hour",       False),
    ]

    entries = {}
    for i, (label, key, secret) in enumerate(fields, start=1):
        tk.Label(root, text=label, anchor="w", width=26).grid(row=i, column=0, sticky="w", **p)
        e = tk.Entry(root, width=34, show="*" if secret else "")
        e.insert(0, str(cfg.get(key, "")))
        e.grid(row=i, column=1, **p)
        entries[key] = e

    status_var = tk.StringVar()
    tk.Label(root, textvariable=status_var, fg="gray", font=("Helvetica", 10)).grid(
        row=len(fields)+1, column=0, columnspan=2)

    def _save():
        for key, entry in entries.items():
            val = entry.get().strip()
            if key in ("device_port", "device_password", "sync_hour"):
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showerror("Error", f"'{key}' must be a number.")
                    return
            cfg[key] = val
        config.save(cfg)
        status_var.set("Saved.")

    def _test():
        status_var.set("Testing device...")
        root.update()
        ok = device.ping()
        status_var.set("Device reachable!" if ok else "Cannot reach device — check IP and port.")

    def _sync():
        status_var.set("Syncing...")
        root.update()
        def _run():
            sync.run_nightly()
            with STATE.lock:
                STATE.last_sync = datetime.now()
            root.after(0, lambda: status_var.set(
                f"Done — {datetime.now().strftime('%I:%M %p')}"))
        threading.Thread(target=_run, daemon=True).start()

    btn = tk.Frame(root)
    btn.grid(row=len(fields)+2, column=0, columnspan=2, pady=(8, 18), padx=14)
    tk.Button(btn, text="Test device", command=_test,  width=13).pack(side="left", padx=4)
    tk.Button(btn, text="Save",        command=_save,  width=13).pack(side="left", padx=4)
    tk.Button(btn, text="Sync now",    command=_sync,  width=13).pack(side="left", padx=4)

    root.mainloop()


# ── Status window ─────────────────────────────────────────────────────────────

def _open_status():
    s = STATE.summary()
    root = tk.Tk()
    root.title("Fisique Bridge — Status")
    root.resizable(False, False)

    tk.Label(root, text="Bridge Status", font=("Helvetica", 14, "bold")).pack(
        pady=(16, 10), padx=24)

    frame = tk.Frame(root, bd=1, relief="sunken", padx=16, pady=12)
    frame.pack(padx=20, pady=4, fill="x")

    def _row(label, value, good=True):
        r = tk.Frame(frame)
        r.pack(fill="x", pady=3)
        tk.Label(r, text=label, width=16, anchor="w",
                 font=("Helvetica", 11, "bold")).pack(side="left")
        colour = "#1D9E75" if good else "#E24B4A"
        tk.Label(r, text=value, anchor="w", font=("Helvetica", 11),
                 fg=colour).pack(side="left")

    _row("Device",    "Connected"    if s["device_ok"] else "OFFLINE",   s["device_ok"])
    _row("Cloud",     "Reachable"    if s["cloud_ok"]  else "OFFLINE",   s["cloud_ok"])
    _row("Enrolled",  str(s["enrolled"]),                                  True)
    _row("Last sync", s["last_sync"].strftime("%d %b %I:%M %p")
                      if s["last_sync"] else "Never",                      s["last_sync"] is not None)

    tk.Label(root, text="Recent log", font=("Helvetica", 11, "bold")).pack(
        anchor="w", padx=20, pady=(12, 2))

    log_box = tk.Text(root, height=9, width=56, state="disabled",
                      font=("Courier", 9), bg="#f5f5f5")
    log_box.pack(padx=20)

    log_file = Path.home() / ".fisique" / "bridge.log"
    if log_file.exists():
        tail = log_file.read_text().splitlines()[-20:]
        log_box.config(state="normal")
        log_box.insert("end", "\n".join(tail))
        log_box.config(state="disabled")
        log_box.see("end")

    tk.Button(root, text="Open log folder",
              command=lambda: webbrowser.open(str(Path.home() / ".fisique"))
              ).pack(pady=(8, 16))

    root.mainloop()


# ── Tray menu ─────────────────────────────────────────────────────────────────

def _build_menu(icon: pystray.Icon) -> pystray.Menu:

    def on_status(_):
        threading.Thread(target=_open_status,   daemon=True).start()

    def on_sync(_):
        def _run():
            sync.run_nightly()
            with STATE.lock:
                STATE.last_sync = datetime.now()
        threading.Thread(target=_run, daemon=True).start()

    def on_settings(_):
        threading.Thread(target=_open_settings, daemon=True).start()

    def on_quit(_):
        icon.stop()
        sys.exit(0)

    return pystray.Menu(
        pystray.MenuItem("Fisique Bridge", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Status",   on_status),
        pystray.MenuItem("Sync now", on_sync),
        pystray.MenuItem("Settings", on_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit",     on_quit),
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def run():
    (Path.home() / ".fisique").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(Path.home() / ".fisique" / "bridge.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # First-run: open settings if not configured
    if not config.is_configured():
        _open_settings()

    icon = pystray.Icon(
        name="fisique-bridge",
        icon=_make_icon("cloud_offline"),
        title="Fisique Bridge — starting...",
    )
    icon.menu = _build_menu(icon)

    # Start all background services
    threading.Thread(target=server.start,          daemon=True).start()
    threading.Thread(target=sync.start_scheduler,  daemon=True).start()
    threading.Thread(target=_health_loop, args=(icon,), daemon=True).start()

    log.info("Fisique Bridge tray started")
    icon.run()
