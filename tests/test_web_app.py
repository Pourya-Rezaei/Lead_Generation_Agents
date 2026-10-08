from src.config import Settings
from src.web.app import create_app


def test_create_app_registers_web_routes(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "web.db")))
    paths = {
        path
        for route in app.router.routes
        for path in [getattr(route, "path", None)]
        if path is not None
    }
    included = next(route for route in app.router.routes if hasattr(route, "original_router"))
    paths.update(route.path for route in included.original_router.routes)
    assert "/" in paths
    assert "/campaigns" in paths
    assert "/search" in paths
