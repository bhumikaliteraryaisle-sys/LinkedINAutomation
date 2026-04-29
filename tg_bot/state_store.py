"""
Simple file-based state store using /tmp.
Works within a warm Vercel instance. State is lost on cold start,
which is acceptable for a single-user interactive bot session.
"""
import json
import os

_STATE_DIR = "/tmp/linkedin_agent_state"


def _path(user_id: int) -> str:
    os.makedirs(_STATE_DIR, exist_ok=True)
    return os.path.join(_STATE_DIR, f"{user_id}.json")


def get(user_id: int) -> dict:
    try:
        with open(_path(user_id)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def set(user_id: int, data: dict) -> None:
    with open(_path(user_id), "w") as f:
        json.dump(data, f)


def update(user_id: int, **kwargs) -> None:
    data = get(user_id)
    data.update(kwargs)
    set(user_id, data)


def clear(user_id: int) -> None:
    try:
        os.remove(_path(user_id))
    except FileNotFoundError:
        pass
