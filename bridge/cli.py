"""
fisique-bridge CLI
All commands a gym operator needs to run and manage the bridge agent.
"""

import logging
import sys
import threading
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from bridge import api, config, device, service, sync

console = Console()


def _setup_logging():
    level = getattr(logging, config.get("log_level"), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


@click.group()
def cli():
    """Fisique Bridge Agent — connects ESSL fingerprint device to your web app."""
    pass


# ── setup ─────────────────────────────────────────────────────────────────────

@cli.command()
def setup():
    """Interactive setup wizard. Run this first."""
    console.print("\n[bold purple]Fisique Bridge Setup[/bold purple]\n")

    cfg = config.load()

    cfg["device_ip"] = click.prompt(
        "ESSL device IP address",
        default=cfg.get("device_ip") or "192.168.1.100",
    )
    cfg["device_port"] = click.prompt(
        "ESSL device port",
        default=cfg.get("device_port", 4370),
        type=int,
    )
    cfg["device_password"] = click.prompt(
        "ESSL device password (0 if none)",
        default=cfg.get("device_password", 0),
        type=int,
    )
    cfg["web_app_url"] = click.prompt(
        "Web app base URL (e.g. https://yourapp.lovable.app)",
        default=cfg.get("web_app_url") or "",
    )
    cfg["api_key"] = click.prompt(
        "API key (from your web app settings)",
        default=cfg.get("api_key") or "",
        hide_input=True,
    )
    cfg["sync_hour"] = click.prompt(
        "Nightly sync hour (0-23, 24h)",
        default=cfg.get("sync_hour", 2),
        type=int,
    )

    config.save(cfg)
    console.print("\n[green]Config saved to ~/.fisique/config.json[/green]")

    console.print("\n[dim]Testing device connection...[/dim]")
    if device.ping():
        console.print("[green]Device reachable[/green]")
    else:
        console.print("[red]Cannot reach device — check IP and port[/red]")

    console.print("\n[dim]Testing web app connection...[/dim]")
    members = api.get_active_members()
    if members is not None:
        console.print(f"[green]Web app reachable — {len(members)} active members[/green]")
    else:
        console.print("[red]Cannot reach web app — check URL and API key[/red]")

    console.print("\n[bold]Setup complete.[/bold] Run [cyan]fisique-bridge install[/cyan] to start as a background service.\n")


# ── install / uninstall ───────────────────────────────────────────────────────

@cli.command()
def install():
    """Install and start the bridge as a background service (survives reboots)."""
    if not config.is_configured():
        console.print("[red]Not configured. Run: fisique-bridge setup[/red]")
        sys.exit(1)
    service.install()


@cli.command()
def uninstall():
    """Remove the background service."""
    service.uninstall()


@cli.command()
def status():
    """Show service status and device connectivity."""
    svc_status = service.status()
    color = "green" if svc_status == "running" else "red"
    console.print(f"Service:  [{color}]{svc_status}[/{color}]")

    device_ok = device.ping()
    console.print(f"Device:   [{'green' if device_ok else 'red'}]{'reachable' if device_ok else 'unreachable'}[/]")

    cfg = config.load()
    console.print(f"Device:   {cfg['device_ip']}:{cfg['device_port']}")
    console.print(f"Web app:  {cfg['web_app_url']}")


# ── run (called by service manager) ──────────────────────────────────────────

@cli.command()
def app():
    """Launch the tray app (the normal way to run for non-technical users)."""
    from bridge.tray import run as tray_run
    tray_run()


@cli.command()
def run():
    """
    Start the bridge agent (foreground). The service manager calls this.
    You can also run this directly to test before installing as a service.
    """
    if not config.is_configured():
        console.print("[red]Not configured. Run: fisique-bridge setup[/red]")
        sys.exit(1)

    _setup_logging()
    log = logging.getLogger("bridge")
    log.info("Fisique Bridge Agent starting...")

    # Start local HTTP server in background thread
    from bridge import server
    port = config.get("agent_port") or 7474
    server.start_in_thread(port=port)
    log.info(f"Local HTTP server started on port {port}")

    # Run scheduler in the main thread (blocking)
    sync.start_scheduler()


# ── enroll ────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("member_id", type=int)
def enroll(member_id: int):
    """
    Enroll a fingerprint for a member.

    MEMBER_ID is the member's ID from your web app.

    Example: fisique-bridge enroll 42
    """
    console.print(f"\n[bold]Enrolling fingerprint for member ID {member_id}[/bold]")

    member = api.get_member_for_enrollment(member_id)
    if not member:
        console.print(f"[red]Member {member_id} not found in web app[/red]")
        sys.exit(1)

    name = member.get("name", f"Member {member_id}")
    # Use member_id directly as device UID (keep it simple)
    device_uid = member_id

    console.print(f"Member: [cyan]{name}[/cyan]")
    console.print(f"[dim]Device UID will be: {device_uid}[/dim]\n")
    console.print("[yellow]Ask the member to place their finger on the reader now...[/yellow]")

    try:
        ok = device.enroll_user(user_id=device_uid, name=name)
    except Exception as e:
        console.print(f"[red]Enrollment failed: {e}[/red]")
        sys.exit(1)

    if ok:
        api.confirm_enrollment(member_id=member_id, device_user_id=device_uid)
        console.print(f"[green]Enrollment complete for {name}[/green]\n")
    else:
        console.print("[red]Enrollment did not complete — member may not have placed finger[/red]")
        sys.exit(1)


# ── sync (manual trigger) ─────────────────────────────────────────────────────

@cli.command()
def sync_now():
    """Manually trigger the sync job right now."""
    _setup_logging()
    console.print("[dim]Running sync...[/dim]")
    sync.run_nightly()
    console.print("[green]Sync complete[/green]")


# ── logs ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--lines", "-n", default=50, help="Number of lines to show")
def logs(lines: int):
    """Tail the bridge log file."""
    from pathlib import Path
    log_file = Path.home() / ".fisique" / "bridge.log"
    if not log_file.exists():
        console.print("[dim]No log file yet. Start the service first.[/dim]")
        return
    with open(log_file) as f:
        all_lines = f.readlines()
    for line in all_lines[-lines:]:
        console.print(line.rstrip())


# ── device-users (debug) ──────────────────────────────────────────────────────

@cli.command()
def device_users():
    """List all users currently stored on the ESSL device."""
    try:
        uids = device.get_all_user_ids()
    except Exception as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if not uids:
        console.print("[dim]No users enrolled on device[/dim]")
        return

    table = Table(title="Device Users")
    table.add_column("Device UID", style="cyan")
    for uid in sorted(uids):
        table.add_row(str(uid))
    console.print(table)


if __name__ == "__main__":
    cli()
