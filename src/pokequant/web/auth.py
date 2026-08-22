from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from pokequant.config import get_settings

security = HTTPBasic(auto_error=False)


def require_write_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    settings = get_settings()
    if settings.app_env != "production":
        return
    expected = settings.secret_key
    if ":" in expected:
        user, pw = expected.split(":", 1)
    else:
        user, pw = "pokequant", expected
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
    ok = secrets.compare_digest(credentials.username, user) and secrets.compare_digest(
        credentials.password, pw
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
