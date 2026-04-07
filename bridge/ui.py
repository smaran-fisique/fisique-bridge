"""
Full multi-screen tkinter UI for Fisique Bridge.
Open from the tray via bridge.ui.open_dashboard().
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path
import logging

from bridge import api, config, device, sync

log = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────

BG     = "#1C1C1E"
SIDEBAR= "#2C2C2E"
ACCENT = "#1D9E75"
FG     = "#F2F2F7"
FG2    = "#8E8E93"
RED    = "#E24B4A"
CARD   = "#3A3A3C"
ENTRY  = "#4A4A4C"


# ── Main window ───────────────────────────────────────────────────────────────

class BridgeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fisique Bridge")
        self.geometry("980x660")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._nav_buttons: dict[str, tk.Button] = {}
        self._build_layout()
        self._show_screen("dashboard")

    def _build_layout(self):
        # ── Sidebar
        sb = tk.Frame(self, bg=SIDEBAR, width=210)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Label(sb, text="Fisique", fg=ACCENT, bg=SIDEBAR,
                 font=("Helvetica", 19, "bold")).pack(pady=(26, 0), padx=18, anchor="w")
        tk.Label(sb, text="Bridge", fg=FG, bg=SIDEBAR,
                 font=("Helvetica", 19)).pack(pady=(0, 26), padx=18, anchor="w")

        nav_items = [
            ("dashboard", "Dashboard"),
            ("enroll",    "Enroll Members"),
            ("checkin",   "Check-in Display"),
            ("logs",      "Access Logs"),
            ("settings",  "Settings"),
        ]
        for key, label in nav_items:
            btn = tk.Button(
                sb, text=label, anchor="w",
                bg=SIDEBAR, fg=FG, bd=0, cursor="hand2",
                font=("Helvetica", 12), padx=22, pady=11,
                activebackground=ACCENT, activeforeground=FG,
                command=lambda k=key: self._show_screen(k),
            )
            btn.pack(fill="x")
            self._nav_buttons[key] = btn

        # ── Content area
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="right", fill="both", expand=True)

    def _show_screen(self, name: str):
        for key, btn in self._nav_buttons.items():
            btn.configure(bg=ACCENT if key == name else SIDEBAR)
        for w in self.content.winfo_children():
            w.destroy()
        screens = {
            "dashboard": DashboardScreen,
            "enroll":    EnrollScreen,
            "checkin":   CheckinScreen,
            "logs":      LogsScreen,
            "settings":  SettingsScreen,
        }
        if name in screens:
            screens[name](self.content).pack(fill="both", expand=True)


# ── Base screen ───────────────────────────────────────────────────────────────

class _Screen(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)

    def _title(self, text: str):
        tk.Label(self, text=text, fg=FG, bg=BG,
                 font=("Helvetica", 20, "bold")).pack(anchor="w", padx=32, pady=(28, 4))

    def _button(self, parent, text, command, accent=False, danger=False) -> tk.Button:
        bg = ACCENT if accent else (RED if danger else CARD)
        return tk.Button(parent, text=text, command=command,
                         bg=bg, fg=FG, font=("Helvetica", 11),
                         bd=0, padx=16, pady=8, cursor="hand2",
                         activebackground=bg, activeforeground=FG)


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardScreen(_Screen):
    def __init__(self, parent):
        super().__init__(parent)
        self._title("Dashboard")
        self._build()
        self.after(100, self._refresh)

    def _build(self):
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x", padx=32, pady=(16, 0))

        self._device_lbl   = self._stat_card(row, "Device",    "…")
        self._cloud_lbl    = self._stat_card(row, "Cloud",     "…")
        self._enrolled_lbl = self._stat_card(row, "Enrolled",  "…")
        self._sync_lbl     = self._stat_card(row, "Last Sync", "—")

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(anchor="w", padx=32, pady=(24, 0))
        self._button(btn_row, "Sync Now",       self._sync_now, accent=True).pack(side="left", padx=(0, 12))
        self._button(btn_row, "Refresh Status", self._refresh).pack(side="left")

        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, fg=FG2, bg=BG,
                 font=("Helvetica", 10)).pack(anchor="w", padx=32, pady=(10, 0))

    def _stat_card(self, parent, label, value) -> tk.Label:
        f = tk.Frame(parent, bg=CARD, padx=20, pady=16, width=185)
        f.pack(side="left", padx=(0, 16))
        f.pack_propagate(False)
        tk.Label(f, text=label, fg=FG2, bg=CARD, font=("Helvetica", 10)).pack(anchor="w")
        lbl = tk.Label(f, text=value, fg=FG, bg=CARD, font=("Helvetica", 22, "bold"))
        lbl.pack(anchor="w", pady=(4, 0))
        return lbl

    def _refresh(self):
        self._status_var.set("Refreshing…")
        def _run():
            dev_ok  = device.ping()
            members = api.get_active_members()
            cloud_ok = isinstance(members, list)
            enrolled = len([m for m in (members or []) if m.get("device_user_id")])
            self.after(0, lambda: self._update(dev_ok, cloud_ok, enrolled))
        threading.Thread(target=_run, daemon=True).start()

    def _update(self, dev_ok, cloud_ok, enrolled):
        self._device_lbl.configure(
            text="Online" if dev_ok else "OFFLINE", fg=ACCENT if dev_ok else RED)
        self._cloud_lbl.configure(
            text="Online" if cloud_ok else "OFFLINE", fg=ACCENT if cloud_ok else RED)
        self._enrolled_lbl.configure(text=str(enrolled), fg=FG)
        self._status_var.set(f"Updated {datetime.now().strftime('%I:%M %p')}")

    def _sync_now(self):
        self._status_var.set("Syncing…")
        def _run():
            sync.run_nightly()
            self.after(0, lambda: self._status_var.set(
                f"Sync done — {datetime.now().strftime('%I:%M %p')}"))
        threading.Thread(target=_run, daemon=True).start()


# ── Enroll Members ────────────────────────────────────────────────────────────

class EnrollScreen(_Screen):
    def __init__(self, parent):
        super().__init__(parent)
        self._members: list[dict] = []
        self._filtered: list[dict] = []
        self._title("Enroll Members")
        self._build()
        self.after(100, self._load)

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=32, pady=(12, 8))
        tk.Label(top, text="Search:", fg=FG2, bg=BG,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 8))
        self._q = tk.StringVar()
        self._q.trace_add("write", lambda *_: self._filter())
        tk.Entry(top, textvariable=self._q, font=("Helvetica", 12),
                 bg=CARD, fg=FG, insertbackground=FG, bd=0,
                 width=32).pack(side="left")

        self._status_var = tk.StringVar(value="Loading…")
        tk.Label(self, textvariable=self._status_var, fg=FG2, bg=BG,
                 font=("Helvetica", 10)).pack(anchor="w", padx=32, pady=(0, 6))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, foreground=FG,
                        fieldbackground=CARD, rowheight=30, font=("Helvetica", 11))
        style.configure("Treeview.Heading", background=SIDEBAR, foreground=FG2,
                        font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])

        cols = ("Name", "Type", "Status", "Device UID")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=13)
        widths = {"Name": 220, "Type": 110, "Status": 110, "Device UID": 120}
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=widths[col], anchor="w")
        self._tree.pack(fill="both", expand=True, padx=32, pady=(0, 12))

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(anchor="w", padx=32, pady=(0, 24))
        self._button(btn_row, "Enroll Fingerprint",  self._enroll,  accent=True).pack(side="left", padx=(0, 12))
        self._button(btn_row, "Remove from Device",  self._remove,  danger=True).pack(side="left", padx=(0, 12))
        self._button(btn_row, "Refresh",             self._load).pack(side="left")

    def _load(self):
        self._status_var.set("Loading members…")
        def _run():
            members = api.get_active_members()
            self.after(0, lambda: self._set(members or []))
        threading.Thread(target=_run, daemon=True).start()

    def _set(self, members):
        self._members = members
        self._filter()
        self._status_var.set(f"{len(members)} members loaded")

    def _filter(self):
        q = self._q.get().lower()
        self._filtered = [m for m in self._members
                          if q in (m.get("name") or "").lower()]
        self._tree.delete(*self._tree.get_children())
        for m in self._filtered:
            self._tree.insert("", "end", values=(
                m.get("name", "—"),
                m.get("person_type", "member"),
                "Active" if m.get("active", True) else "Expired",
                m.get("device_user_id") or "—",
            ))

    def _selected(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select member", "Please select a member first.")
            return None
        return self._filtered[self._tree.index(sel[0])]

    def _enroll(self):
        m = self._selected()
        if not m:
            return
        name = m.get("name", "Member")
        self._status_var.set(f"Preparing enrollment for {name}…")

        def _run():
            preserve = config.get("wipe_preserve_uid") or 999
            # If already assigned, re-enroll on the same UID
            uid = m.get("device_user_id")
            if not uid:
                # Auto-assign next available UID on the device
                try:
                    existing = device.get_all_user_ids()
                except Exception as e:
                    self.after(0, lambda: self._status_var.set(f"Cannot reach device: {e}"))
                    return
                candidates = [u for u in existing if u != preserve]
                uid = (max(candidates) + 1) if candidates else 1
                if uid == preserve:
                    uid += 1

            self.after(0, lambda: self._status_var.set(
                f"Enrolling {name} (UID {uid}) — ask them to place their finger on the reader…"))
            ok = device.enroll_user(user_id=int(uid), name=name)
            if ok:
                api.confirm_enrollment(
                    person_id=m["person_id"],
                    person_type=m.get("person_type", "member"),
                    device_user_id=int(uid),
                )
                self.after(0, lambda: (
                    self._status_var.set(f"Enrolled {name} as UID {uid}."),
                    self._load(),
                ))
            else:
                self.after(0, lambda: self._status_var.set(f"Enrollment failed for {name}."))

        threading.Thread(target=_run, daemon=True).start()

    def _remove(self):
        m = self._selected()
        if not m:
            return
        uid = m.get("device_user_id")
        if not uid:
            messagebox.showinfo("Not Enrolled", "This member is not enrolled on the device.")
            return
        if not messagebox.askyesno("Confirm", f"Remove {m.get('name')} from the device?"):
            return
        ok = device.delete_user(int(uid))
        self._status_var.set("Removed." if ok else "Failed to remove.")
        self._load()


# ── Check-in Display ──────────────────────────────────────────────────────────

class CheckinScreen(_Screen):
    def __init__(self, parent):
        super().__init__(parent)
        self._title("Check-in Display")
        self._build()

    def _build(self):
        card = tk.Frame(self, bg=CARD, padx=48, pady=48)
        card.pack(fill="both", expand=True, padx=32, pady=(12, 32))

        tk.Label(card, text="Welcome", fg=ACCENT, bg=CARD,
                 font=("Helvetica", 52, "bold")).pack(pady=(40, 8))

        self._name_var = tk.StringVar(value="Waiting for scan…")
        self._name_lbl = tk.Label(card, textvariable=self._name_var,
                                  fg=FG, bg=CARD, font=("Helvetica", 34))
        self._name_lbl.pack()

        self._time_var = tk.StringVar()
        tk.Label(card, textvariable=self._time_var,
                 fg=FG2, bg=CARD, font=("Helvetica", 16)).pack(pady=(10, 0))

        tk.Label(card, text="Place your finger on the reader",
                 fg=FG2, bg=CARD, font=("Helvetica", 13)).pack(pady=(44, 0))

        self._tick()

    def _tick(self):
        self._time_var.set(datetime.now().strftime("%A, %d %B %Y  %I:%M:%S %p"))
        self.after(1000, self._tick)

    def on_scan(self, name: str, granted: bool):
        """Call this when a scan event arrives to update the welcome board."""
        self._name_var.set(name)
        self._name_lbl.configure(fg=ACCENT if granted else RED)
        self.after(5000, lambda: (
            self._name_var.set("Waiting for scan…"),
            self._name_lbl.configure(fg=FG),
        ))


# ── Access Logs ───────────────────────────────────────────────────────────────

class LogsScreen(_Screen):
    def __init__(self, parent):
        super().__init__(parent)
        self._title("Access Logs")
        self._build()
        self._load()

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=32, pady=(8, 8))
        self._button(top, "Refresh",    self._load).pack(side="left", padx=(0, 8))
        self._button(top, "Clear View", self._clear).pack(side="left")

        frame = tk.Frame(self, bg=BG)
        frame.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        self._text = tk.Text(frame, font=("Courier New", 10), bg=CARD, fg=FG,
                             insertbackground=FG, state="disabled",
                             wrap="none", padx=12, pady=12)
        sb = ttk.Scrollbar(frame, command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)

    def _load(self):
        log_file = Path.home() / ".fisique" / "bridge.log"
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if log_file.exists():
            lines = log_file.read_text(errors="replace").splitlines()
            self._text.insert("end", "\n".join(lines[-500:]))
            self._text.see("end")
        else:
            self._text.insert("end", "No log file at ~/.fisique/bridge.log")
        self._text.configure(state="disabled")

    def _clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsScreen(_Screen):
    def __init__(self, parent):
        super().__init__(parent)
        self._title("Settings")
        self._entries: dict[str, tk.Entry] = {}
        self._build()

    def _build(self):
        # Scrollable inner frame
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=(32, 0), pady=(0, 0))

        cfg = config.load()
        sections = [
            ("Device", [
                ("Device IP",       "device_ip",       False),
                ("Device Port",     "device_port",     False),
                ("Device Password", "device_password", True),
            ]),
            ("Web App", [
                ("Web App URL", "web_app_url", False),
                ("API Key",     "api_key",     True),
            ]),
            ("API Endpoints", [
                ("Active Members",     "ep_active_members",     False),
                ("All Members",        "ep_all_members",        False),
                ("Confirm Enrollment", "ep_confirm_enrollment", False),
                ("Access Log",         "ep_access_log",         False),
                ("Member Lookup",      "ep_member_lookup",      False),
            ]),
            ("Sync & Agent", [
                ("Nightly Sync Hour (0–23)", "sync_hour",  False),
                ("Agent Port",               "agent_port", False),
            ]),
        ]

        for section_name, fields in sections:
            tk.Label(inner, text=section_name, fg=ACCENT, bg=BG,
                     font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(20, 4))
            card = tk.Frame(inner, bg=CARD, padx=20, pady=12)
            card.pack(fill="x", pady=(0, 4), padx=(0, 32))
            for label, key, secret in fields:
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", pady=5)
                tk.Label(row, text=label, fg=FG2, bg=CARD,
                         font=("Helvetica", 11), width=26, anchor="w").pack(side="left")
                e = tk.Entry(row, font=("Helvetica", 11), bg=ENTRY, fg=FG,
                             insertbackground=FG, bd=0, width=42,
                             show="*" if secret else "")
                e.insert(0, str(cfg.get(key, "")))
                e.pack(side="left", padx=(8, 0))
                self._entries[key] = e

        self._status_var = tk.StringVar()
        tk.Label(inner, textvariable=self._status_var, fg=FG2, bg=BG,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(14, 4))

        btn_row = tk.Frame(inner, bg=BG)
        btn_row.pack(anchor="w", pady=(0, 32), padx=(0, 32))
        self._button(btn_row, "Save",          self._save,  accent=True).pack(side="left", padx=(0, 12))
        self._button(btn_row, "Test Device",   self._test).pack(side="left", padx=(0, 12))
        self._button(btn_row, "Wipe & Resync", self._wipe,  danger=True).pack(side="left")

    def _save(self):
        cfg = config.load()
        int_keys = {"device_port", "device_password", "sync_hour", "agent_port"}
        for key, entry in self._entries.items():
            val: int | str = entry.get().strip()
            if key in int_keys:
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showerror("Invalid input", f"'{key}' must be a number.")
                    return
            cfg[key] = val
        config.save(cfg)
        self._status_var.set("Saved.")

    def _test(self):
        self._status_var.set("Testing device connection…")
        def _run():
            ok = device.ping()
            self.after(0, lambda: self._status_var.set(
                "Device reachable!" if ok else "Cannot reach device — check IP and port."))
        threading.Thread(target=_run, daemon=True).start()

    def _wipe(self):
        preserve = config.get("wipe_preserve_uid") or 999
        if not messagebox.askyesno(
            "Confirm wipe",
            f"Remove ALL device users except UID {preserve}, then re-sync active members?\n"
            "This cannot be undone."
        ):
            return
        self._status_var.set("Wiping device…")
        def _run():
            try:
                uids = device.get_all_user_ids()
                for uid in uids:
                    if uid != preserve:
                        device.delete_user(uid)
                sync.run_nightly()
                self.after(0, lambda: self._status_var.set("Wipe and re-sync complete."))
            except Exception as e:
                self.after(0, lambda: self._status_var.set(f"Error: {e}"))
        threading.Thread(target=_run, daemon=True).start()


# ── Public entry point ────────────────────────────────────────────────────────

_instance: BridgeApp | None = None


def open_dashboard():
    """Open or raise the main Bridge window. Safe to call from any thread."""
    global _instance

    def _launch():
        global _instance
        if _instance and _instance.winfo_exists():
            _instance.lift()
            _instance.focus_force()
            return
        _instance = BridgeApp()
        _instance.mainloop()

    if threading.current_thread() is threading.main_thread():
        _launch()
    else:
        # Schedule on the main thread if already running a Tk loop
        if _instance and _instance.winfo_exists():
            _instance.after(0, _launch)
        else:
            threading.Thread(target=_launch, daemon=True).start()
