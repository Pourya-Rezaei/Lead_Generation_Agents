from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..service import SearchLeadsService
from ..storage import LeadStore
from .routes import router


def create_app(
    settings: Settings | None = None,
    store: LeadStore | None = None,
    service: SearchLeadsService | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_store = store or LeadStore(resolved_settings.database_path)
    resolved_service = service or SearchLeadsService(
        resolved_settings, store=resolved_store
    )
    app = FastAPI(title="جمع‌آور لید محلی")
    project_root = Path(__file__).resolve().parents[2]
    app.mount("/static", StaticFiles(directory=project_root / "static"), name="static")
    app.state.settings = resolved_settings
    app.state.store = resolved_store
    app.state.service = resolved_service
    app.state.templates = Jinja2Templates(directory=project_root / "templates")
    app.include_router(router)
    return app


def __getattr__(name: str):
    if name == "app":
        return create_app()
    raise AttributeError(name)
