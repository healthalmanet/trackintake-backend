import os
import requests
from base64 import b64encode


def get_zoom_token():
    client_id     = os.getenv("ZOOM_CLIENT_ID")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET")
    account_id    = os.getenv("ZOOM_ACCOUNT_ID")

    auth = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    res  = requests.post(
        f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={account_id}",
        headers={"Authorization": f"Basic {auth}"}
    )
    res.raise_for_status()
    return res.json().get("access_token")


def create_zoom_meeting(topic: str, start_time_str: str, duration: int = 60) -> dict:
    """
    start_time_str: "2026-03-20T10:00:00"
    Returns Zoom response with join_url, start_url, password, id
    """
    token = get_zoom_token()
    res   = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        json={
            "topic":      topic,
            "type":       2,
            "start_time": start_time_str,
            "duration":   duration,
            "timezone":   "Asia/Kolkata",
            "settings": {
                "host_video":        True,
                "participant_video": True,
                "waiting_room":      True,
                "mute_upon_entry":   True,
            },
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
    )
    res.raise_for_status()
    return res.json()
