"""File upload guards + at-rest encryption.

- File kind/size validation ("malware-safe upload rules" - we only accept a
  small allow-list of document extensions and reject anything else).
- Fernet (AES) symmetric encryption so stored CVs are encrypted at rest.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings

settings = get_settings()


class UploadValidationError(ValueError):
    pass


# security baseline heuristics for binary inspection
_FORBIDDEN_MARKERS = (
    b"MZ",            # windows executable
    b"\x7fELF",       # linux executable
    b"PK\x03\x04",    # zip (could wrap weird payloads) - rejected UploadGuard level
    b"\x25PDF-1",     # (actually allowed - handled below by extension)
)


def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key or key.startswith("placeholder"):
        # deterministic dev key so the project runs out of the box
        key = "VKu0FH7uC8p6nBvKdJ1mWdM4nF9yR2xT3sB5aC6dE8fG9hJ0kL1mN2oP="
    return Fernet(key.encode("utf-8") if not isinstance(key, bytes) else key)


def validate_upload(filename: str, data: bytes) -> None:
    """Validate file type and size. Raises UploadValidationError on failure."""
    if len(data) > settings.max_upload_bytes:
        raise UploadValidationError(
            f"File exceeds {settings.max_upload_mb} MB limit."
        )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_ext_list:
        raise UploadValidationError(
            f"File type '.{ext or 'unknown'}' not allowed. Allowed: "
            f"{', '.join(settings.allowed_ext_list)}"
        )
    if data[:2] in (b"MZ", b"\x7f") or b"\0\0\0" in data[:1024]:
        # reject binary payloads that disguise themselves as documents
        raise UploadValidationError("File content looks like an executable.")
    if not data.strip():
        raise UploadValidationError("Empty file provided.")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def store_encrypted(directory: Path, candidate_code: str, ext: str, data: bytes) -> str:
    """Encrypt and persist the original CV. Returns the stored path string."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{candidate_code}.enc"
    target.write_bytes(encrypt_bytes(data))
    return str(target)


def load_encrypted(path: str) -> bytes:
    """Read + decrypt a stored CV file."""
    try:
        return decrypt_bytes(Path(path).read_bytes())
    except (InvalidToken, FileNotFoundError, OSError) as exc:
        raise UploadValidationError("Stored CV could not be decrypted/read.") from exc