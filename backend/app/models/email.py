"""Request model for the "Email report" endpoint."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# A deliberately permissive check — enough to reject obvious typos without
# pulling in a full email-validation dependency.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email_list(values: list[str]) -> list[str]:
    """Trim, validate, and de-duplicate a list of email addresses.

    Args:
        values: Raw email strings.

    Returns:
        The cleaned, order-preserving, de-duplicated list.

    Raises:
        ValueError: If any address is not a plausible email.
    """
    cleaned: list[str] = []
    for raw in values:
        trimmed = raw.strip()
        if not trimmed:
            continue
        if not _EMAIL_PATTERN.match(trimmed):
            raise ValueError(f"invalid email address: {raw!r}")
        if trimmed.lower() not in {existing.lower() for existing in cleaned}:
            cleaned.append(trimmed)
    return cleaned


class SendReportRequest(BaseModel):
    """A request to email a generated report to one or more recipients.

    Attributes:
        recipients: One or more "To" addresses (at least one required).
        cc: Optional "Cc" addresses.
        subject: The email subject line.
        body: The plain-text report body to send.
    """

    recipients: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    subject: str = Field(default="Enterprise Decision Analysis Agent Investigation Report", max_length=200)
    body: str = Field(min_length=1, max_length=100_000)

    @field_validator("recipients", "cc")
    @classmethod
    def _validate_emails(cls, value: list[str]) -> list[str]:
        """Validate and normalize each address in a recipient list.

        Args:
            value: The raw list of addresses.

        Returns:
            The cleaned list.
        """
        return _clean_email_list(value)
