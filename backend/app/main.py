from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.dataset import router as dataset_router
from app.api.entities import router as entities_router
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.api.transactions import router as transactions_router
from app.api.analysis import router as analysis_router
from app.api.leads import router as leads_router
from app.api.clusters import router as clusters_router
from app.api.patterns import router as patterns_router
from app.api.dashboard import router as dashboard_router
from app.api.extra import router as extra_router
from app.config import settings
from app.core.logging import configure_logging


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

configure_logging(settings.log_level)

logger = logging.getLogger("bitcoin-intelligence-backend")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bitcoin Intelligence Backend",
    version=settings.version,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
#
# Keep the production frontend explicitly allowed so deployment does not
# depend entirely on the Render environment variable being formatted exactly
# as expected.
#
# settings.cors_origins is still respected, so additional origins can be
# configured through the backend environment.
#
# Trailing "/" characters are normalized because browsers send the Origin
# without a trailing slash.
# ---------------------------------------------------------------------------

production_frontend = "https://bitcoin-intelligence-frontend.onrender.com"

cors_origins = {
    origin.strip().rstrip("/")
    for origin in settings.cors_origins
    if origin and origin.strip()
}

# Production frontend
cors_origins.add(production_frontend)

# Local development
cors_origins.update(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API routers
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(dataset_router)

# The analysis-backed entity routes
# (/entities/{id}/evidence, /findings, /indicators, /timeline,
# /entities/wallet/{id}, /entities/ip/{id})
# must be registered before the graph entity lookup routes.
#
# Otherwise /entities/{entity_type}/{entity_id} can shadow these
# analysis paths and reject them with HTTP 422.
app.include_router(extra_router)

app.include_router(entities_router)
app.include_router(graph_router)
app.include_router(transactions_router)
app.include_router(analysis_router)
app.include_router(leads_router)
app.include_router(clusters_router)
app.include_router(patterns_router)
app.include_router(dashboard_router)


# ---------------------------------------------------------------------------
# Startup log
# ---------------------------------------------------------------------------

logger.info(
    "Started %s version %s",
    settings.service_name,
    settings.version,
)