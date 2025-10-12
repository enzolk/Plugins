from fastapi.routing import APIRoute

from app.main import app


def test_routes_registered():
    paths = {route.path.rstrip("/") for route in app.router.routes if isinstance(route, APIRoute)}
    assert "/patients" in paths
    assert "/invoices" in paths
    assert "/appointments" in paths

