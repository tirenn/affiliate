import os
import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional, Set
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings

logger = logging.getLogger("security")

SENSITIVE_KEYS: Set[str] = {
    "openrouter_api_key",
    "threads_password",
    "threads_session_id",
    "proxy_url",
    "admin_passcode",
}


def _get_or_create_master_key() -> bytes:
    """
    Retrieves or derives the Fernet master key for database encryption.
    Priority:
    1. APP_SECRET_KEY or ENCRYPTION_KEY environment variable.
    2. Persisted .master_key file in DATA_PATH.
    3. Auto-generated on first run and safely saved.
    """
    env_key = os.getenv("APP_SECRET_KEY") or os.getenv("ENCRYPTION_KEY")
    if env_key:
        env_key_clean = env_key.strip()
        try:
            decoded = base64.urlsafe_b64decode(env_key_clean)
            if len(decoded) == 32:
                return env_key_clean.encode("utf-8")
        except Exception:
            pass
        digest = hashlib.sha256(env_key_clean.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    key_file = Path(settings.DATA_PATH) / ".master_key"
    try:
        if key_file.exists():
            key_data = key_file.read_text("utf-8").strip()
            if key_data:
                return key_data.encode("utf-8")
    except Exception as e:
        logger.warning(f"Failed reading .master_key from disk: {e}")

    new_key = Fernet.generate_key()
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(new_key.decode("utf-8"), encoding="utf-8")
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            pass
        logger.info("Generated new encryption master key in persistent data storage")
    except Exception as e:
        logger.error(f"Failed saving .master_key: {e}")

    return new_key


_fernet_instance: Optional[Fernet] = None


def get_cipher() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_or_create_master_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_value(plain: Optional[str]) -> str:
    """
    Encrypts a plaintext string using AES-256 (Fernet) with 'enc:' prefix.
    If value is None, empty, or already encrypted, returns as-is.
    """
    if not plain:
        return ""
    if plain.startswith("enc:"):
        return plain
    try:
        cipher = get_cipher()
        token = cipher.encrypt(plain.encode("utf-8")).decode("utf-8")
        return f"enc:{token}"
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return plain


def decrypt_value(cipher_text: Optional[str]) -> str:
    """
    Decrypts an 'enc:' prefixed ciphertext back to plaintext.
    If value is None, empty, or plain unencrypted string, returns as-is for backwards compatibility.
    """
    if not cipher_text:
        return ""
    if not cipher_text.startswith("enc:"):
        return cipher_text
    try:
        cipher = get_cipher()
        token = cipher_text[4:]
        decrypted = cipher.decrypt(token.encode("utf-8")).decode("utf-8")
        return decrypted
    except Exception as e:
        logger.error(f"Decryption error (data may have been encrypted with another key): {e}")
        return ""


async def migrate_unencrypted_settings(db: AsyncSession):
    """
    Inspects system_settings on startup.
    Any unencrypted sensitive credentials are automatically encrypted in place.
    """
    from app.models import SystemSetting

    try:
        stmt = select(SystemSetting).where(SystemSetting.key.in_(SENSITIVE_KEYS))
        res = await db.execute(stmt)
        settings_list = res.scalars().all()
        migrated_count = 0

        for s in settings_list:
            if s.value and not s.value.startswith("enc:"):
                s.value = encrypt_value(s.value)
                migrated_count += 1
                logger.info(f"Encrypted sensitive database setting: '{s.key}'")

        if migrated_count > 0:
            await db.commit()
            logger.info(f"Successfully migrated {migrated_count} sensitive settings to AES-256 ciphertext.")
    except Exception as e:
        logger.error(f"Error during settings encryption migration: {e}")


def sanitize_log_text(text: Optional[str]) -> str:
    """
    Scrubs API keys, sessionid cookies, and Bearer tokens from text before saving to logs.
    """
    if not text:
        return ""
    sanitized = text
    sanitized = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "sk-***", sanitized)
    sanitized = re.sub(r"(sessionid=)[^;&\s]+", r"\1***", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", r"\1***", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"://([^:@\s]+):([^@\s]+)@", r"://\1:***@", sanitized)
    return sanitized
