from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import UserApiKey
from app.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
from app.services.auth_service import AuthService, verify_api_key

router = APIRouter(prefix="/api/v1/keys", tags=["Developer API Keys (OpenAI-Style)"])


@router.post("", response_model=ApiKeyCreatedResponse, summary="Create a new developer API key")
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_api_key)
):
    """
    Generate a new OpenAI-style API key (`vel_sk_...`).
    The full secret key is returned **ONLY ONCE** in this response.
    """
    full_key, prefix = AuthService.generate_api_key()

    record = UserApiKey(
        name=payload.name.strip(),
        key=full_key,
        key_prefix=prefix,
        rate_limit_per_minute=payload.rate_limit_per_minute or 60,
        is_active=True
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "name": record.name,
        "key": full_key,
        "key_prefix": prefix,
        "message": "Copy your secret key now! It will never be shown again."
    }


@router.get("", response_model=List[ApiKeyResponse], summary="List all developer API keys")
def list_api_keys(
    db: Session = Depends(get_db),
    _: dict = Depends(verify_api_key)
):
    """
    List all generated API keys with usage statistics and safe prefixes (`vel_sk_...xxxx`).
    The full secret key is never exposed.
    """
    keys = db.query(UserApiKey).order_by(desc(UserApiKey.created_at)).all()
    return keys


@router.delete("/{key_id}", summary="Revoke an API key")
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_api_key)
):
    """Revoke / delete an API key so it can no longer be used."""
    key_obj = db.query(UserApiKey).filter(UserApiKey.id == key_id).first()
    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found."
        )

    db.delete(key_obj)
    db.commit()
    return {"status": "success", "message": f"API key '{key_obj.name}' has been revoked."}
