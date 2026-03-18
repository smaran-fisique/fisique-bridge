# Fisique Bridge Agent

Connects your ESSL fingerprint reader to your Fisique web app over LAN. Works on Windows, macOS, and Linux.

## Requirements

- Python 3.9+
- ESSL/ZKTeco device on the same LAN
- Your Fisique web app URL and API key

## Install

```bash
pip install fisique-bridge
```

## First-time setup

```bash
fisique-bridge setup
```

This will ask for:
- ESSL device IP (find it in the device's network settings menu)
- ESSL device port (default: 4370)
- ESSL device password (usually 0)
- Your web app URL (e.g. `https://yourapp.lovable.app`)
- Your API key (generate from web app settings)

## Install as background service

Once setup is done, install as a system service so it starts automatically on boot:

```bash
fisique-bridge install
```

This handles Windows Service, macOS launchd, and Linux systemd automatically.

## Enrolling a fingerprint

Open your web app, find the member, copy their Member ID, then run:

```bash
fisique-bridge enroll 42
```

The device LEDs will activate. Ask the member to place their finger. Done.

## Commands

| Command | Description |
|---|---|
| `fisique-bridge setup` | Interactive setup wizard |
| `fisique-bridge install` | Install as background service |
| `fisique-bridge uninstall` | Remove background service |
| `fisique-bridge status` | Show service + device status |
| `fisique-bridge run` | Run in foreground (for testing) |
| `fisique-bridge enroll <id>` | Enroll a fingerprint for a member |
| `fisique-bridge sync-now` | Manually trigger sync job |
| `fisique-bridge device-users` | List all users on device |
| `fisique-bridge logs` | Tail the log file |

## Web App API Endpoints Required

Your Lovable app needs these endpoints for the bridge to work:

| Method | Path | Description |
|---|---|---|
| GET | `/api/bridge/active-members` | Returns all active members with finger_id |
| GET | `/api/bridge/member/:id` | Returns single member details |
| POST | `/api/bridge/confirm-enrollment` | Saves finger_id after enrollment |
| POST | `/api/bridge/access-log` | Receives scan events |

All requests are authenticated via `Authorization: Bearer <api_key>` header.

### Active members response format

```json
[
  {
    "member_id": 42,
    "device_user_id": 42,
    "name": "Priya Sharma",
    "role": "member",
    "expiry": "2025-12-31"
  }
]
```

## How sync works

- Every 15 minutes: attendance logs are pulled from device and posted to web app
- Every night at 2 AM (configurable): full sync runs — anyone not in the active list is deleted from the device

Config is stored at `~/.fisique/config.json`. Logs at `~/.fisique/bridge.log`.
