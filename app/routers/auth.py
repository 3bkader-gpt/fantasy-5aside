import logging
import os
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, Request, Form, Response, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..core import security
from ..core.csrf import (
    CSRF_COOKIE_NAME,
    get_or_create_csrf_token_from_request,
    set_csrf_cookie,
    verify_csrf_token,
)
from ..core.rate_limit import limiter
from ..core.revocation import revoke_token
from ..dependencies import get_league_repository, get_db, ILeagueRepository, get_current_user
from ..models.user_model import User
if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger("uvicorn.error")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""

@router.get("/login")
def login_page(request: Request, msg: str = None):
    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"msg": msg, "is_admin": False, "csrf_token": token}
    )
    set_csrf_cookie(resp, token)
    return resp

@router.post("/login")
@limiter.limit("5/minute")
def login_submit(
    request: Request,
    response: Response,
    league_name: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(None),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    league_name = league_name.strip()
    league = league_repo.get_by_name(league_name)
    ip = _client_ip(request)

    if not league or not security.verify_password(password, league.admin_password):
        logger.warning("Login failed ip=%s league_name_len=%d", ip, len(league_name))
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "League name or password incorrect", "is_admin": False}
        )

    logger.info("Login success ip=%s league_slug=%s", ip, league.slug)
    # Valid credentials, create token
    token = security.create_access_token(data={"sub": league.slug})
    
    # Redirect to admin dashboard
    redirect = RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    redirect.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return redirect


@router.post("/user/login")
@limiter.limit("10/minute")
def user_login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(None),
    db: "Session" = Depends(get_db),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    email_clean = email.strip().lower()
    from ..models.user_model import User  # local import to avoid circulars in some tools

    user: User | None = (
        db.query(User)
        .filter(User.email == email_clean)
        .first()
    )
    if not user or not security.verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Email or password incorrect", "is_admin": False},
        )

    token = security.create_access_token(data={"sub": str(user.id), "scope": "user"})
    redirect = RedirectResponse(url="/dashboard", status_code=303)
    redirect.set_cookie(
        key="user_access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENV") == "production",
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return redirect

@router.get("/logout")
def logout(request: Request, db: "Session" = Depends(get_db)):
    authorization = request.cookies.get("access_token")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = security.verify_token(token)
        if payload and payload.get("jti") and payload.get("exp"):
            from datetime import datetime, timezone
            exp_ts = payload["exp"]
            expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            revoke_token(db, payload["jti"], expires_at)
    redirect = RedirectResponse(url="/?msg=logged_out", status_code=303)
    redirect.delete_cookie("access_token")
    redirect.delete_cookie("user_access_token")
    return redirect
