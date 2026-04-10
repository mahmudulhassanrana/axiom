from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from axiom_api import __version__
from axiom_api.core.deployment_security import api_docs_exposed, get_cors_allow_origins
from axiom_api.core.exception_handlers import register_exception_handlers
from axiom_api.core.lifespan import app_lifespan
from axiom_api.core.logging_setup import configure_logging
from axiom_api.core.openapi_tags import OPENAPI_TAGS
from axiom_api.middleware.body_size_limit import BodySizeLimitMiddleware
from axiom_api.middleware.security_headers import SecurityHeadersMiddleware
from axiom_api.middleware.tracing import TracingMiddleware
from axiom_api.routes import admin, auth, exports, health, jobs, root, runs, schedules, scrape


def create_app() -> FastAPI:
    configure_logging()

    _docs = api_docs_exposed()

    app = FastAPI(
        title="Axiom API",
        version=__version__,
        description=(
            "HTTP API for Axiom: compliant, rate-limited scraping and ingestion. "
            "OpenAPI is enabled for integration and client generation."
        ),
        docs_url="/docs" if _docs else None,
        redoc_url="/redoc" if _docs else None,
        openapi_url="/openapi.json" if _docs else None,
        openapi_tags=OPENAPI_TAGS,
        lifespan=app_lifespan,
    )

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TracingMiddleware)

    app.include_router(health.router)
    app.include_router(root.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(scrape.router)
    app.include_router(jobs.router)
    app.include_router(runs.router)
    app.include_router(exports.router)
    app.include_router(schedules.router)

    return app
