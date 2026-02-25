from fastapi import APIRouter, Depends, Request, Form, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..core import security
from ..dependencies import get_league_repository, ILeagueRepository

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/login")
def login_page(request: Request, msg: str = None):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"msg": msg, "is_admin": False}
    )

@router.post("/login")
def login_submit(
    request: Request,
    response: Response,
    league_name: str = Form(...),
    password: str = Form(...),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    league_name = league_name.strip()
    league = league_repo.get_by_name(league_name)
    
    if not league or not security.verify_password(password, league.admin_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "League name or password incorrect", "is_admin": False}
        )
        
    # Valid credentials, create token
    token = security.create_access_token(data={"sub": league.slug})
    
    # Redirect to admin dashboard
    redirect = RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    redirect.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return redirect

@router.get("/logout")
def logout():
    redirect = RedirectResponse(url="/?msg=logged_out", status_code=303)
    redirect.delete_cookie("access_token")
    return redirect
