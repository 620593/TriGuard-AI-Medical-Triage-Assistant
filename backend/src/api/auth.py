import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
import os
import httpx
import secrets
from fastapi.responses import RedirectResponse

from backend.src.tools.mongodb_tool import get_user_by_email, create_user
from backend.src.tools.security import verify_password, get_password_hash, create_access_token

# Configuration will be read dynamically in the endpoints to avoid import-time empty values.

router = APIRouter()

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    name: str

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    existing_user = await get_user_by_email(req.email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    hashed_password = get_password_hash(req.password)
    user_id = str(uuid.uuid4())
    
    user_data = {
        "user_id": user_id,
        "name": req.name,
        "email": req.email,
        "hashed_password": hashed_password
    }
    
    await create_user(user_data)
    
    access_token = create_access_token(data={"sub": user_id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        name=req.name
    )

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await get_user_by_email(req.email)
    if not user or not verify_password(req.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id = user["user_id"]
    access_token = create_access_token(data={"sub": user_id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        name=user.get("name", "")
    )


@router.get("/google")
async def google_login():
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v3/auth/google/callback")

    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    redirect_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={google_client_id}&redirect_uri={google_redirect_uri}&response_type=code&scope=openid email profile&access_type=offline&state={state}"

    response = RedirectResponse(redirect_url)
    # Set the state in an HttpOnly cookie to verify during callback
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("TRIGUARD_ENV", "development") == "production"
    )
    return response


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str = None):
    # Verify CSRF state
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or not state or secrets.compare_digest(cookie_state, state) is False:
        raise HTTPException(status_code=400, detail="Invalid state parameter. CSRF attempt suspected.")

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v3/auth/google/callback")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": google_client_id,
        "client_secret": google_client_secret,
        "redirect_uri": google_redirect_uri,
        "grant_type": "authorization_code",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve token from Google")
            
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_response = await client.get(user_info_url, headers=headers)
        
        if user_info_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to retrieve user info from Google")
            
        user_info = user_info_response.json()
    
    email = user_info.get("email")
    name = user_info.get("name", "Google User")
    
    if not email:
        raise HTTPException(status_code=400, detail="Google account does not have an email")
        
    user = await get_user_by_email(email)
    if not user:
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(str(uuid.uuid4()))
        
        user_data = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "hashed_password": hashed_password,
            "google_oauth": True
        }
        await create_user(user_data)
    else:
        user_id = user.get("user_id", str(user.get("_id")))
        
    jwt_token = create_access_token(data={"sub": user_id})
    
    import urllib.parse
    safe_name = urllib.parse.quote(name)
    safe_uid = urllib.parse.quote(str(user_id))
    
    response = RedirectResponse(f"{frontend_url}/dashboard?token={jwt_token}&name={safe_name}&uid={safe_uid}")
    response.delete_cookie("oauth_state")
    return response
