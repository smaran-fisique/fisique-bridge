"""
HTTP client for communicating with the Fisique web app API.
All outbound calls to the web app go through here.
"""

import logging
from typing import Optional

import requests

from bridge import config

log = logging.getLogger(__name__)

TIMEOUT = 10  # seconds


def _headers() -> dict:
    return {
        "x-api-key": config.get("api_key"),
        "Content-Type": "application/json",
    }


def _base() -> str:
    return config.get("web_app_url").rstrip("/")


def get_active_members() -> list[dict]:
    """
    Fetch all members/staff/trainers who should have device access.
    Expected response: [{finger_id, member_id, name, role, expiry}, ...]
    """
    url = f"{_base()}{config.get('ep_active_members')}"
    try:
        r = requests.get(url, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        log.info(f"Fetched {len(data)} active members from web app")
        return data
    except requests.RequestException as e:
        log.error(f"Failed to fetch active members: {e}")
        return []


def post_access_event(device_user_id: int, timestamp: str, granted: bool, reason: str = "") -> bool:
    """
    Post a scan event to the web app for logging.
    """
    url = f"{_base()}{config.get('ep_access_log')}"
    payload = {
        "device_user_id": device_user_id,
        "timestamp": timestamp,
        "granted": granted,
        "reason": reason,
    }
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning(f"Failed to post access event: {e}")
        return False


def confirm_enrollment(person_id: str, person_type: str, device_user_id: int) -> bool:
    """
    Tell the web app that enrollment succeeded and save the device_user_id mapping.
    """
    url = f"{_base()}{config.get('ep_confirm_enrollment')}"
    payload = {
        "person_id": person_id,
        "person_type": person_type,
        "device_user_id": device_user_id,
    }
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        log.info(f"Confirmed enrollment: person_id={person_id} device_user_id={device_user_id}")
        return True
    except requests.RequestException as e:
        log.error(f"Failed to confirm enrollment: {e}")
        return False


def get_member_for_enrollment(person_id: str) -> Optional[dict]:
    """
    Fetch member details needed for enrollment (name, role).
    """
    url = f"{_base()}{config.get('ep_member_lookup')}"
    try:
        r = requests.get(url, params={"person_id": person_id}, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        log.error(f"Failed to fetch member {person_id}: {e}")
        return None
