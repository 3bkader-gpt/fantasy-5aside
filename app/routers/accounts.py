from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from ..core import security
from ..core.csrf import (
    CSRF_COOKIE_NAME,
    generate_csrf_token,
    set_csrf_cookie,
    verify_csrf_token,
)
from ..dependencies import get_current_user, get_user_service, get_email_service
from ..database import get_db
from ..services.user_service import UserService
from ..services.email_service import EmailService


router = APIRouter(prefix="", tags=["accounts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register")
def register_page(request: Request):
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"csrf_token": token},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    if password != password_confirm:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Passwords do not match"},
        )

    try:
        user = user_service.register_user(email=email, password=password)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": str(exc)},
        )

    base_url = os.environ.get("BASE_URL") or request.base_url._url.rstrip("/")
    verify_link = f"{base_url}/verify/{user.verification_token}"
    email_service.send_verification_email(user.email, verify_link)

    return RedirectResponse(url="/login?msg=check_email", status_code=303)


@router.get("/verify/{token}")
def verify_email(token: str, request: Request, user_service: UserService = Depends(get_user_service)):
    user = user_service.verify_user_by_token(token)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Invalid or expired verification link", "is_admin": False},
        )
    return RedirectResponse(url="/login?msg=verified", status_code=303)


@router.get("/dashboard")
def dashboard(
    request: Request,
    current_user = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    leagues = user_service.get_owned_leagues(current_user)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": current_user, "leagues": leagues},
    )

