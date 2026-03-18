from __future__ import annotations

import logging
import os

logger = logging.getLogger("uvicorn.error")


def send_verification_email(email: str, verification_link: str) -> None:
    """
    Minimal email sender for verification links.

    For now this just logs the link; it can be wired to Resend/SMTP later.
    """
    # In a real deployment, integrate with SMTP or a provider (Resend, etc.)
    if os.environ.get("EMAIL_DEBUG_LOG", "1") == "1":
        logger.info("Send verification email to %s: %s", email, verification_link)

