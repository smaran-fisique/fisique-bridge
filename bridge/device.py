"""
Wrapper around the zk library for ESSL / ZKTeco devices.
All device interaction goes through this module.
"""

import logging
from contextlib import contextmanager
from typing import Optional

from zk import ZK, const
from zk.exception import ZKErrorResponse, ZKNetworkError

from bridge import config

log = logging.getLogger(__name__)


@contextmanager
def connect():
    """Context manager that yields an open ZK connection."""
    cfg = config.load()
    zk = ZK(
        cfg["device_ip"],
        port=cfg["device_port"],
        timeout=10,
        password=cfg["device_password"],
        force_udp=False,
        ommit_ping=True,
    )
    conn = None
    try:
        conn = zk.connect()
        conn.disable_device()   # pause device during operations
        yield conn
    except ZKNetworkError as e:
        log.error(f"Cannot reach ESSL device at {cfg['device_ip']}:{cfg['device_port']} — {e}")
        raise
    except ZKErrorResponse as e:
        log.error(f"ESSL device returned error: {e}")
        raise
    finally:
        if conn:
            conn.enable_device()
            conn.disconnect()


def ping() -> bool:
    """Return True if the device is reachable."""
    try:
        with connect() as conn:
            info = conn.get_firmware_version()
            log.debug(f"Device firmware: {info}")
        return True
    except Exception:
        return False


def enroll_user(user_id: int, name: str, privilege: int = const.USER_DEFAULT) -> bool:
    """
    Create a user slot on the device and trigger a fingerprint enrollment.
    The person must place their finger on the reader when prompted.

    Returns True when enrollment succeeds.
    """
    with connect() as conn:
        # Create or update user record on device
        conn.set_user(
            uid=user_id,
            name=name[:23],   # ESSL name field max 24 chars
            privilege=privilege,
            password="",
            group_id="",
            user_id=str(user_id),
        )
        log.info(f"User slot created on device: uid={user_id} name={name}")

        # Trigger live enrollment — device LEDs will activate
        result = conn.enroll_user(uid=user_id, temp_id=0)
        if result:
            log.info(f"Fingerprint enrolled for uid={user_id}")
            return True
        else:
            log.warning(f"Enrollment returned no result for uid={user_id}")
            return False


def delete_user(user_id: int) -> bool:
    """Remove a user and all their templates from the device."""
    try:
        with connect() as conn:
            conn.delete_user(uid=user_id)
            log.info(f"Deleted user uid={user_id} from device")
            return True
    except Exception as e:
        log.error(f"Failed to delete uid={user_id}: {e}")
        return False


def get_all_user_ids() -> list[int]:
    """Return list of all user IDs currently stored on the device."""
    with connect() as conn:
        users = conn.get_users()
        return [u.uid for u in users]


def pull_attendance_logs() -> list[dict]:
    """
    Pull all attendance records from device and clear the buffer.
    Each record: {user_id, timestamp, status}
    """
    records = []
    with connect() as conn:
        attendance = conn.get_attendance()
        for a in attendance:
            records.append({
                "device_user_id": a.user_id,
                "timestamp": a.timestamp.isoformat(),
                "status": a.status,
                "punch": a.punch,
            })
        if records:
            conn.clear_attendance()
            log.info(f"Pulled {len(records)} attendance records from device")
    return records
