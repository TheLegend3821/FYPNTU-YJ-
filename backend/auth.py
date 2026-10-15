import hmac

from fastapi import Request, HTTPException

from config import ADMIN_USERNAME, ADMIN_PASSWORD


def check_credentials(username: str, password: str) -> bool:
    return hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)


def login(request: Request):
    request.session["admin_user"] = ADMIN_USERNAME


def logout(request: Request):
    request.session.pop("admin_user", None)


def is_logged_in(request: Request) -> bool:
    return request.session.get("admin_user") == ADMIN_USERNAME


def require_admin(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
