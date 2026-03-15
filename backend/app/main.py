"""FastAPI application factory and top-level ASGI app instance."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import settings
from app.database.postgres_db import init_db


def create_app() -> FastAPI:
	"""Create and configure the FastAPI application with middleware, routes, and startup hooks."""
	@asynccontextmanager
	async def lifespan(_: FastAPI):
		"""Initialize relational tables on startup without failing local development if DB is absent."""
		try:
			init_db()
		except Exception:
			# Keep startup alive if local DB is not available yet.
			pass
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
