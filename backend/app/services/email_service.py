"""Outbound email via SMTP (e.g. Gmail) for the "Email report" action.

The backend holds a single sending credential (configured in ``.env``), so end
users only supply a recipient address — they never authenticate. Sending uses the
standard-library :mod:`smtplib`, run in a worker thread so the async event loop is
never blocked.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from html import escape

from app.config import Settings, get_settings
from app.core.logging import get_logger

_logger = get_logger("email_service")


class EmailError(Exception):
    """Raised when an email could not be sent."""


class EmailService:
    """Sends report emails through a configured SMTP server."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the service.

        Args:
            settings: Application settings. Defaults to the cached singleton.
        """
        self._settings: Settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        """Whether SMTP credentials are present so email can be sent.

        Returns:
            True when the server has a usable SMTP username and password.
        """
        return self._settings.is_email_configured

    async def send_report(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> None:
        """Send a report email, off-loading the blocking SMTP call to a thread.

        Args:
            recipients: One or more "To" addresses.
            subject: The email subject line.
            body: The plain-text report body.
            cc: Optional "Cc" addresses.

        Raises:
            EmailError: If the server is not configured or the send fails.
        """
        if not self.is_configured:
            raise EmailError("Email sending is not configured on the server.")
        cc_list = cc or []
        try:
            await asyncio.to_thread(
                self._send_sync, recipients, cc_list, subject, body
            )
        except (smtplib.SMTPException, OSError) as error:
            _logger.exception("Failed to send report email to %s", recipients)
            raise EmailError(str(error)) from error
        _logger.info(
            "Report email sent to %d recipient(s)%s",
            len(recipients),
            f" (+{len(cc_list)} cc)" if cc_list else "",
        )

    def _send_sync(
        self, recipients: list[str], cc: list[str], subject: str, body: str
    ) -> None:
        """Build and send the MIME message synchronously over SMTP+STARTTLS.

        Args:
            recipients: The "To" addresses.
            cc: The "Cc" addresses.
            subject: The email subject line.
            body: The plain-text report body.
        """
        message = EmailMessage()
        message["From"] = (
            f"{self._settings.smtp_from_name} <{self._settings.smtp_username}>"
        )
        message["To"] = ", ".join(recipients)
        if cc:
            message["Cc"] = ", ".join(cc)
        message["Subject"] = subject
        message.set_content(body)
        # An HTML alternative wrapping the text in <pre> preserves the report's
        # alignment (tables, indentation) in clients that prefer HTML.
        message.add_alternative(
            "<pre style=\"font-family: ui-monospace, Menlo, Consolas, monospace; "
            'white-space: pre-wrap; font-size: 13px; line-height: 1.5;">'
            f"{escape(body)}</pre>",
            subtype="html",
        )

        with smtplib.SMTP(
            self._settings.smtp_host,
            self._settings.smtp_port,
            timeout=self._settings.smtp_timeout_seconds,
        ) as server:
            server.starttls()
            server.login(self._settings.smtp_username, self._settings.smtp_password)
            server.send_message(message)
