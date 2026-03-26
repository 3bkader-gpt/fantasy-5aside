"""VAPID key normalization and validation for Web Push."""
import base64


def normalize_vapid_key(raw: str | None) -> str:
    """Strip copy-paste artifacts and whitespace from VAPID key."""
    if not raw:
        return ""
    s = raw.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    for prefix in (
        "PublicKey:",
        "Public Key:",
        "PrivateKey:",
        "Private Key:",
        "VAPID_PUBLIC_KEY=",
        "VAPID_PRIVATE_KEY=",
        "public_key=",
        "private_key=",
    ):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix) :].strip()

    # pywebpush expects standard base64url padding.
    # If developers paste keys without trailing '=', normalize by adding missing padding.
    if s and "=" not in s:
        pad = (-len(s)) % 4
        if pad:
            s = s + ("=" * pad)
    return s


def is_vapid_public_key_valid(key: str) -> bool:
    """VAPID public key must decode to 65 bytes (uncompressed P-256)."""
    if not key:
        return False
    try:
        pad = (4 - len(key) % 4) % 4
        decoded = base64.urlsafe_b64decode(key + "=" * pad)
        return len(decoded) == 65
    except Exception:
        return False
