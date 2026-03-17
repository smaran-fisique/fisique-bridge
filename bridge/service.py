"""
Installs and manages the bridge agent as a background service,
handling Windows Service, macOS launchd, and Linux systemd.
"""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

SERVICE_NAME = "fisique-bridge"
DISPLAY_NAME = "Fisique Bridge Agent"
DESCRIPTION = "ESSL fingerprint device bridge for Fisique Fitness"


def _executable() -> str:
    """Full path to the fisique-bridge CLI executable."""
    return sys.executable.replace("python", "fisique-bridge") if "python" in sys.executable \
        else str(Path(sys.executable).parent / "fisique-bridge")


# ── Windows ──────────────────────────────────────────────────────────────────

def _install_windows():
    try:
        import win32serviceutil
        import win32service
        import win32con
    except ImportError:
        print("Run: pip install pywin32  then try again.")
        return False

    exe = _executable()
    # Use NSSM if available for simpler service wrapping
    nssm = subprocess.run(["where", "nssm"], capture_output=True)
    if nssm.returncode == 0:
        nssm_path = nssm.stdout.decode().strip().splitlines()[0]
        subprocess.run([nssm_path, "install", SERVICE_NAME, exe, "run"], check=True)
        subprocess.run([nssm_path, "set", SERVICE_NAME, "DisplayName", DISPLAY_NAME], check=True)
        subprocess.run([nssm_path, "set", SERVICE_NAME, "Description", DESCRIPTION], check=True)
        subprocess.run([nssm_path, "start", SERVICE_NAME], check=True)
    else:
        # Fallback: create a simple batch wrapper and use sc
        bat = Path(os.environ["PROGRAMDATA"]) / "fisique-bridge" / "run.bat"
        bat.parent.mkdir(parents=True, exist_ok=True)
        bat.write_text(f'@echo off\n"{exe}" run\n')
        subprocess.run([
            "sc", "create", SERVICE_NAME,
            "binpath=", str(bat),
            "start=", "auto",
            "DisplayName=", DISPLAY_NAME,
        ], check=True)
        subprocess.run(["sc", "start", SERVICE_NAME], check=True)

    print(f"Windows service '{SERVICE_NAME}' installed and started.")
    return True


def _uninstall_windows():
    subprocess.run(["sc", "stop", SERVICE_NAME], capture_output=True)
    subprocess.run(["sc", "delete", SERVICE_NAME], check=True)
    print(f"Windows service '{SERVICE_NAME}' removed.")


# ── macOS ─────────────────────────────────────────────────────────────────────

LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / f"com.fisique.bridge.plist"

def _install_macos():
    exe = _executable()
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fisique.bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.fisique/bridge.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.fisique/bridge.err</string>
</dict>
</plist>"""

    LAUNCHD_PLIST.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHD_PLIST.write_text(plist)
    subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST)], check=True)
    print(f"launchd agent installed: {LAUNCHD_PLIST}")
    return True


def _uninstall_macos():
    subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)], capture_output=True)
    LAUNCHD_PLIST.unlink(missing_ok=True)
    print("launchd agent removed.")


# ── Linux (systemd) ───────────────────────────────────────────────────────────

def _systemd_unit_path() -> Path:
    # User-level systemd (no root needed)
    return Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


def _install_linux():
    exe = _executable()
    unit = f"""[Unit]
Description={DESCRIPTION}
After=network.target

[Service]
Type=simple
ExecStart={exe} run
Restart=always
RestartSec=10
StandardOutput=append:{Path.home()}/.fisique/bridge.log
StandardError=append:{Path.home()}/.fisique/bridge.err

[Install]
WantedBy=default.target
"""
    unit_path = _systemd_unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(unit)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", SERVICE_NAME], check=True)
    subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=True)
    # Enable lingering so service survives logout
    subprocess.run(["loginctl", "enable-linger", os.environ.get("USER", "")], capture_output=True)
    print(f"systemd user service installed and started: {unit_path}")
    return True


def _uninstall_linux():
    subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], capture_output=True)
    subprocess.run(["systemctl", "--user", "disable", SERVICE_NAME], capture_output=True)
    _systemd_unit_path().unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print("systemd user service removed.")


# ── Public API ────────────────────────────────────────────────────────────────

def install() -> bool:
    system = platform.system()
    if system == "Windows":
        return _install_windows()
    elif system == "Darwin":
        return _install_macos()
    elif system == "Linux":
        return _install_linux()
    else:
        print(f"Unsupported OS: {system}. Run manually with: fisique-bridge run")
        return False


def uninstall():
    system = platform.system()
    if system == "Windows":
        _uninstall_windows()
    elif system == "Darwin":
        _uninstall_macos()
    elif system == "Linux":
        _uninstall_linux()


def status() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.run(["sc", "query", SERVICE_NAME], capture_output=True, text=True)
            return "running" if "RUNNING" in result.stdout else "stopped"
        elif system == "Darwin":
            result = subprocess.run(["launchctl", "list", "com.fisique.bridge"], capture_output=True, text=True)
            return "running" if result.returncode == 0 else "stopped"
        elif system == "Linux":
            result = subprocess.run(["systemctl", "--user", "is-active", SERVICE_NAME], capture_output=True, text=True)
            return result.stdout.strip()
    except Exception:
        return "unknown"
