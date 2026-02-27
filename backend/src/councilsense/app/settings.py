from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    auth_session_secret: str


DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"


def get_settings() -> Settings:
    return Settings(
        auth_session_secret=os.getenv("AUTH_SESSION_SECRET", DEFAULT_SESSION_SECRET),
    )
