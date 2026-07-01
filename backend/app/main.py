"""FastAPI application entry point for the Enterprise Decision Analysis Agent backend.

Wires together logging, CORS, and the API router, and performs a light startup
readiness check (warns if the datasets have not been generated yet). Run with:

    cd backend
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router as investigation_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.dataset_repository import DatasetRepository

configure_logging()
_logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup readiness checks and shutdown logging.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the running application.
    """
    settings = get_settings()
    repository = DatasetRepository(settings)

    if not settings.is_llm_configured:
        _logger.warning(
            "GROQ_API_KEY is not set. Enterprise Decision Analysis Agent will return degraded reports until "
            "a key is configured in the .env file."
        )
    if not repository.all_datasets_present():
        _logger.warning(
            "Datasets are missing from %s. Run "
            "`python scripts/generate_synthetic_data.py` before investigating.",
            settings.data_dir,
        )
    _logger.info("Enterprise Decision Analysis Agent backend v%s ready (model=%s).", __version__, settings.groq_model)
    yield
    _logger.info("Enterprise Decision Analysis Agent backend shutting down.")


def create_application() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        The configured :class:`FastAPI` instance.
    """
    settings = get_settings()
    application = FastAPI(
        title="Enterprise Decision Analysis Agent — Enterprise Decision Intelligence Agent",
        description=(
            "Autonomous five-agent investigation of banking KPI anomalies with "
            "causal evidence chains, financial impact, and board-ready reports."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(investigation_router)
    return application


app = create_application()
