"""Load the sample's configuration from the environment or ignored root .env."""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BOT_NAME = "grok demo"
load_dotenv(ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in .env before starting the demo.")
    return value


def public_origin() -> str:
    value = require_env("GROK_PUBLIC_URL").rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("GROK_PUBLIC_URL must be a public HTTPS origin without a path.")
    return value


def session_timeout() -> int:
    try:
        seconds = int(os.getenv("SESSION_TIMEOUT_SECONDS", "600"))
        if 30 <= seconds <= 3600:
            return seconds
    except ValueError:
        pass
    raise ValueError("SESSION_TIMEOUT_SECONDS must be between 30 and 3600.")


def grok_voice() -> str:
    value = os.getenv("GROK_VOICE", "ara").strip()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", value):
        raise ValueError("GROK_VOICE must be a lowercase xAI voice ID, such as ara.")
    return value


def validate_agent_settings() -> None:
    public_origin()
    session_timeout()
    grok_voice()
