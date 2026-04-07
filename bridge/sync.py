"""
Sync logic:
1. Pull active member list from web app
2. Pull current user list from device
3. Delete device users not in active list
4. Process attendance logs → post to web app
"""

import logging
from datetime import datetime

import schedule
import time

from bridge import api, config, device

log = logging.getLogger(__name__)


def sync_users() -> dict:
    """
    Diff active members (web app) vs enrolled users (device).
    Delete anyone on the device who's no longer active.
    Returns summary dict.
    """
    log.info("Starting user sync...")
    summary = {"checked": 0, "deleted": 0, "errors": 0}

    active_members = api.get_active_members()
    if not active_members:
        log.warning("No active members returned — skipping sync to avoid wiping device")
        return summary

    # Build set of device_user_ids that should have access
    active_ids = {
        int(m["device_user_id"])
        for m in active_members
        if m.get("device_user_id") is not None
    }

    try:
        device_ids = device.get_all_user_ids()
    except Exception as e:
        log.error(f"Could not read device users: {e}")
        return summary

    summary["checked"] = len(device_ids)

    preserve_uid = config.get("wipe_preserve_uid") or 999

    for uid in device_ids:
        if uid == preserve_uid:
            continue
        if uid not in active_ids:
            log.info(f"Removing expired/inactive user uid={uid} from device")
            ok = device.delete_user(uid)
            if ok:
                summary["deleted"] += 1
            else:
                summary["errors"] += 1

    log.info(f"Sync complete: {summary}")
    return summary


def process_attendance() -> int:
    """
    Pull attendance logs from device and push to web app.
    Returns number of records processed.
    """
    try:
        records = device.pull_attendance_logs()
    except Exception as e:
        log.error(f"Could not pull attendance: {e}")
        return 0

    if not records:
        return 0

    # Get active member map to decide granted/denied
    active_members = api.get_active_members()
    active_ids = {
        int(m["device_user_id"])
        for m in active_members
        if m.get("device_user_id") is not None
    }

    count = 0
    for record in records:
        uid = int(record["device_user_id"]) if record["device_user_id"] else None
        if uid is None:
            continue
        granted = uid in active_ids
        reason = "active" if granted else "not_in_active_list"
        ok = api.post_access_event(
            device_user_id=uid,
            timestamp=record["timestamp"],
            granted=granted,
            reason=reason,
        )
        if ok:
            count += 1

    log.info(f"Processed {count} attendance records")
    return count


def run_nightly():
    """Full nightly job: attendance first, then user sync."""
    log.info(f"=== Nightly job started at {datetime.now().isoformat()} ===")
    process_attendance()
    sync_users()
    log.info("=== Nightly job complete ===")


def start_scheduler():
    """Set up and run the schedule loop. Blocking."""
    sync_hour = config.get("sync_hour")
    run_time = f"{sync_hour:02d}:00"
    log.info(f"Scheduler started — nightly sync at {run_time}")

    schedule.every().day.at(run_time).do(run_nightly)
    # Also process attendance every 15 minutes for near-real-time logs
    schedule.every(15).minutes.do(process_attendance)

    while True:
        schedule.run_pending()
        time.sleep(30)
