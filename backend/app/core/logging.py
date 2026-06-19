"""Structured, colorized logging for BankIQ powered by Rich.

A single :func:`configure_logging` call installs a :class:`RichHandler` on the
root logger, and :func:`get_logger` hands out namespaced loggers. Agents log
their lifecycle (start, complete, fail) through these helpers so development
output reads as a clean, timestamped trace of the pipeline.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Final

from rich.console import Console
from rich.logging import RichHandler

_LOGGER_NAMESPACE: Final[str] = "bankiq"
_DEFAULT_LOG_LEVEL: Final[int] = logging.INFO


def _ensure_utf8_stdio() -> None:
    """Force UTF-8 on stdout/stderr so glyphs like ``₹`` never crash logging.

    On legacy Windows consoles the default code page (cp1252) cannot encode the
    rupee sign; reconfiguring to UTF-8 with ``errors="replace"`` makes output
    robust across platforms.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


_ensure_utf8_stdio()

# A shared console so all Rich output (logs and ad-hoc panels) aligns. Disabling
# the legacy Windows renderer keeps Unicode output working on older terminals.
shared_console: Final[Console] = Console(legacy_windows=False)

_is_logging_configured: bool = False


def configure_logging(level: int = _DEFAULT_LOG_LEVEL) -> None:
    """Install the Rich logging handler on the BankIQ root logger.

    Idempotent: repeated calls do not stack handlers.

    Args:
        level: The minimum log level to emit (e.g. ``logging.INFO``).
    """
    global _is_logging_configured
    if _is_logging_configured:
        return

    handler = RichHandler(
        console=shared_console,
        rich_tracebacks=True,
        show_path=False,
        markup=True,
        omit_repeated_times=False,
    )
    handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))

    root_logger = logging.getLogger(_LOGGER_NAMESPACE)
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.propagate = False

    _is_logging_configured = True


def get_logger(component_name: str) -> logging.Logger:
    """Return a namespaced logger for a given component.

    Args:
        component_name: Short component identifier (e.g. ``"pipeline"`` or an
            agent name); becomes the suffix of the logger name.

    Returns:
        A configured :class:`logging.Logger` under the ``bankiq`` namespace.
    """
    if not _is_logging_configured:
        configure_logging()
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{component_name}")
