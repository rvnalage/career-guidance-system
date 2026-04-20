"""FastAPI application factory and top-level ASGI app instance."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import settings
from app.database.postgres_db import init_db
from app.services.rag_service import ingest_directory
from app.utils.logger import get_logger


logger = get_logger(__name__)


def create_app() -> FastAPI:
	"""Create and configure the FastAPI application with middleware, routes, and startup hooks."""
	@asynccontextmanager
	async def lifespan(_: FastAPI):
		"""Initialize relational tables on startup without failing local development if DB is absent."""
		try:
			init_db()
		except Exception:
			# Keep startup alive if local DB is not available yet.
			logger.exception("Database initialization failed during startup")
		if settings.rag_enabled:
			try:
				ingest_result = ingest_directory(None)
				logger.info(
					"RAG auto-ingest complete: files=%s chunks=%s skipped_files=%s",
					len(ingest_result.get("ingested_files", [])),
					ingest_result.get("ingested_chunks", 0),
					len(ingest_result.get("skipped_files", [])),
				)
			except Exception:
				# Do not block API startup if the knowledge directory is missing or ingest fails.
				logger.exception("RAG auto-ingest failed during startup")
		yield

	app = FastAPI(
		title=settings.app_name,
		version=settings.app_version,
		docs_url="/docs",
		redoc_url="/redoc",
		lifespan=lifespan,
	)

	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.cors_origins,
		allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	@app.get("/", tags=["system"])
	async def root() -> dict[str, str]:
		return {
			"message": "Career Guidance System API is running",
			"version": settings.app_version,
			"environment": settings.environment,
		}

	@app.get("/health", tags=["system"])
	async def health_check() -> dict[str, str]:
		return {"status": "ok"}

	app.include_router(api_router, prefix=settings.api_v1_prefix)
	return app


app = create_app()

