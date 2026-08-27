import secrets
import datetime
from fastapi import HTTPException, Security, Depends, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import UserApiKey

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


class AuthService:
    """Manages generation, storage, and validation of developer API keys."""

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """
        Generate an OpenAI-style secret key and safe display prefix.
        Example key: vel_sk_8f29e1c390a4...
        Example prefix: vel_sk_...90a4
        """
        random_token = secrets.token_hex(20)  # 40 chars
        full_key = f"vel_sk_{random_token}"
        key_prefix = f"vel_sk_...{random_token[-4:]}"
        return full_key, key_prefix


def verify_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
):
    """
    Authenticate API requests:
    1. Checks if it matches master admin key (from .env).
    2. OR checks if it matches any active developer UserApiKey in SQLite database.
    3. Increments usage counter and updates last_used_at timestamp.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please pass 'x-api-key' in request headers."
        )

    # 1. Master Admin Key check
    if api_key == settings.API_SECRET_KEY:
        return {"type": "admin", "key_id": None, "name": "Master Admin"}

    # 2. Developer Client Key check
    user_key = db.query(UserApiKey).filter(
        UserApiKey.key == api_key,
        UserApiKey.is_active == True
    ).first()

    if not user_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key."
        )

    # Increment request counter and update last active timestamp
    user_key.total_requests += 1
    user_key.last_used_at = datetime.datetime.utcnow()
    db.commit()

    return {"type": "developer", "key_id": user_key.id, "name": user_key.name}
