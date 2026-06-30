"""
Auth Routes

"""
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import HTTPBearer
from jose import jwt

from app.core.config import get_settings
from app.core.db import get_conn
from app.core.security import verify_token
from app.models.schemas import TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()
security = HTTPBearer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        # Support both string and bytes for the stored hash
        h_bytes = hashed if isinstance(hashed, bytes) else hashed.encode("utf-8")
        return bcrypt.checkpw(plain.encode("utf-8"), h_bytes)
    except Exception as e:
        print(f"[auth] [ERROR] Verification error: {e}")
        return False


def _create_token(user_id: str, email: str, full_name: str) -> dict:
    """Create a signed JWT token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "name": full_name,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {
        "access_token": token,
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(
    email: str = Form(...),
    password: str = Form(..., format="password"),
    full_name: str = Form("")
):
    """Create a new user account via Form Data."""
    email = email.lower().strip()
    async with get_conn() as conn:
        # Check if email already exists
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1", email
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed = _hash_password(password)
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, full_name)
            VALUES ($1, $2, $3)
            RETURNING id, email, full_name
            """,
            email, hashed, full_name,
        )

    token_data = _create_token(str(row["id"]), row["email"], row["full_name"] or "")
    return {
        "message": "Account created successfully.",
        "user_id": str(row["id"]),
        "email": row["email"],
        **token_data,
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    email: str = Form(...),
    password: str = Form(..., format="password")
):
    """Authenticate user via Form Data and return JWT token."""
    email = email.lower().strip()
    print(f"[auth] Login attempt for: {email}")
    
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, full_name, password_hash FROM users WHERE email = $1",
            email,
        )

    if not row:
        print(f"[auth] [FAILED] Login failed: User '{email}' not found")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not _verify_password(password, row["password_hash"]):
        print(f"[auth] [FAILED] Login failed: Password mismatch for '{email}'")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    print(f"[auth] [SUCCESS] Login successful for: {email}")

    token_data = _create_token(str(row["id"]), row["email"], row["full_name"] or "")
    return {
        "access_token": token_data["access_token"],
        "refresh_token": "",       # No separate refresh token needed (long-lived JWT)
        "expires_in": token_data["expires_in"],
        "user": {
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["full_name"] or "",
        },
    }


@router.post("/logout")
async def logout(payload: dict = Depends(verify_token)):
    """Logout (client-side: discard the token)."""
    # JWTs are stateless — logout is handled client-side by discarding the token.
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(request: Request):
    """
    Re-issue a token using the existing valid JWT.
    Since tokens are long-lived (1 week), the client just sends the current token.
    """
    body = await request.json()
    old_token = body.get("access_token") or body.get("refresh_token")
    if not old_token:
        raise HTTPException(status_code=400, detail="access_token or refresh_token required")

    from jose import JWTError
    try:
        payload = jwt.decode(old_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    token_data = _create_token(payload["sub"], payload["email"], payload.get("name", ""))
    return {
        "access_token": token_data["access_token"],
        "expires_in": token_data["expires_in"],
    }


@router.get("/me")
async def get_me(payload: dict = Depends(verify_token)):
    """Get current user info from token."""
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name", ""),
        "role": payload.get("role", "user"),
    }


async def _send_reset_email(email: str, reset_url: str):
    """Sends a reset email using Resend if API key is present, otherwise prints to console."""
    api_key = settings.RESEND_API_KEY
    if api_key:
        try:
            import resend
            resend.api_key = api_key
            resend.Emails.send({
                "from": "DocChat <onboarding@resend.dev>", # Temporary test sender
                "to": [email],
                "subject": "Reset your DocsChat password",
                "html": f"""
                    <div style="font-family: sans-serif; padding: 20px; color: #333;">
                        <h2>Password Reset Request</h2>
                        <p>You requested a password reset for your DocsChat account.</p>
                        <p>Click the button below to set a new password. This link is valid for 1 hour.</p>
                        <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background: #E8A830; color: #000; text-decoration: none; border-radius: 8px; font-weight: bold;">Reset Password</a>
                        <p style="margin-top: 20px; font-size: 12px; color: #888;">If you didn't request this, you can safely ignore this email.</p>
                    </div>
                """
            })
            print(f"[auth] [EMAIL] Reset email sent to {email} via Resend")
            return
        except Exception as e:
            print(f"[auth] [ERROR] Failed to send email via Resend: {e}")

    # Fallback to console
    print("\n" + "="*60)
    print("PASSWORD RESET REQUESTED (LOCAL FALLBACK)")
    print(f"Email: {email}")
    print(f"Reset Link: {reset_url}")
    print("="*60 + "\n")


@router.post("/forgot-password")
async def forgot_password(request: Request):
    """Generate a password reset token and send it."""
    body = await request.json()
    email = (body.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    async with get_conn() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if not user:
            # Helpful for dev, maybe obfuscate for production
            raise HTTPException(status_code=404, detail="User with this email does not exist")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        await conn.execute(
            """
            INSERT INTO password_reset_tokens (email, token, expires_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (email) DO UPDATE SET token = $2, expires_at = $3
            """,
            email, token, expires_at
        )

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        reset_url = f"{frontend_url}/reset-password?token={token}&email={email}"
        
        await _send_reset_email(email, reset_url)

    return {"message": "Password reset link has been generated. Check your email (or console)."}


@router.post("/reset-password")
async def reset_password(request: Request):
    """Verify the token and update the user's password."""
    body = await request.json()
    email = (body.get("email") or "").lower().strip()
    token = body.get("token")
    new_password = body.get("password")

    if not all([email, token, new_password]):
        raise HTTPException(status_code=400, detail="Email, token, and new password are required")

    async with get_conn() as conn:
        # 1. Verify token
        from datetime import datetime
        row = await conn.fetchrow(
            "SELECT token, expires_at FROM password_reset_tokens WHERE email = $1",
            email
        )
        if not row or row["token"] != token or row["expires_at"] < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        # 2. Update password
        # Use local _hash_password to avoid circular import if needed, 
        # but it's already in this file.
        new_hash = _hash_password(new_password)
        await conn.execute("UPDATE users SET password_hash = $1 WHERE email = $2", new_hash, email)

        # 3. Cleanup token
        await conn.execute("DELETE FROM password_reset_tokens WHERE email = $1", email)

    return {"message": "Password has been reset successfully. You can now log in."}
