from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.runtime import build_dependencies

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(override=False)
    database = os.getenv("CLINICAL_DATABASE", str(ROOT / "clinical_demo.db"))
    use_fakes = os.getenv("API_USE_FAKES", "false").lower() in {"1", "true", "yes"}
    app.state.deps = build_dependencies(database, use_fakes, check_same_thread=False)
    app.state.invoke_lock = threading.Lock()
    app.state.use_fakes = use_fakes
    try:
        yield
    finally:
        connection = getattr(app.state.deps.repository, "connection", None)
        if connection is not None:
            connection.close()


def create_app() -> FastAPI:
    application = FastAPI(title="Assistente Clínico Materno-Infantil", lifespan=lifespan)
    application.include_router(router)
    # Montar o frontend depois de /api/* para o StaticFiles não capturar a API.
    if FRONTEND_DIST.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=FRONTEND_DIST, html=True),
            name="frontend",
        )
    return application


app = create_app()
