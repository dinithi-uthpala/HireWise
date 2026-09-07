"""File-upload guards + at-rest encryption (Agent 1 intake & storage).

- Upload validation: small allow-list of document extensions, size limit,
  empty-file / executable-magic rejection ("malware-safe upload rules").
- Fernet (AES-128-CBC + HMAC) encryption so the *original CV* is stored
  securely at rest; downstream agents never see the raw document.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings

# Binary magic numbers that should never be inside an allowed document.
_EXECUTABLE_MAGIC = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe")
_FORMAT_MAGIC = (b"%PDF-", b"PK\x03\x04", b"\xff\xd8\xff")  # pdf / docx / jpg


class UploadValidationError(ValueError):
    """Raised when an upload violates the intake rules."""


def _fernet_key() -> bytes:
    """Resolve the Fernet key.

    Priority: settings.encryption_key (if a real value is configured) ->
    a deterministic key derived from the app secret so the project runs out
    of the box in development.
    """
    settings = get_settings()
    if settings.encryption_key and not settings.encryption_key.startswith("placeholder"):
        try:
            return settings.encryption_key.encode("utf-8")
        except AttributeError:
            pass
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_fernet_key())


def validate_upload(filename: str, data: bytes) -> None:
    """Validate file type and size. Raises :class:`UploadValidationError`.

    Checks (in order): size limit -> extension allow-list -> non-empty
    content -> not disguised as an executable.
    """
    if len(data) > get_settings().max_upload_bytes:
        raise UploadValidationError(
            f"File exceeds the {get_settings().max_upload_mb} MB upload limit."
        )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in get_settings().allowed_ext_list:
        raise UploadValidationError(
            f"File type '.{ext or 'unknown'}' is not allowed. "
            f"Allowed: {', '.join(get_settings().allowed_ext_list)}"
        )
    if not data.strip():
        raise UploadValidationError("Empty file provided.")

    head = data[:8].upper()
    if head.startswith(_EXECUTABLE_MAGIC):
        raise UploadValidationError("File content looks like an executable and was rejected.")
    if ext in ("pdf", "docx") and not head.startswith(_FORMAT_MAGIC):
        # allow plain text disguised reasonably, but require the declared magic
        # for the two binary formats.
        raise UploadValidationError(
            f"File claims to be '.{ext}' but its content does not match the format."
        )


def sha256_bytes(data: bytes) -> str:
    """SHA-256 digest used for document integrity."""
    return hashlib.sha256(data).hexdigest()


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def store_encrypted(directory: Path, candidate_code: str, data: bytes) -> str:
    """Encrypt and persist an original CV. Returns the stored file path."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{candidate_code}.enc"
    target.write_bytes(encrypt_bytes(data))
    return str(target)


def load_encrypted(path: str) -> bytes:
    """Read and decrypt a stored original CV."""
    try:
        return decrypt_bytes(Path(path).read_bytes())
    except (InvalidToken, FileNotFoundError, OSError) as exc:
        raise UploadValidationError("Stored CV could not be decrypted or read.") from exc