"""Tests for the FastAPI application endpoints."""


from bioforge import __version__


class TestHealthEndpoint:
    """Test the /health endpoint returns correct version."""

    async def test_health_returns_correct_version(self):
        from httpx import ASGITransport, AsyncClient

        from bioforge.api.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["version"] == __version__
            assert data["version"] == "0.3.0"

    async def test_app_has_all_routers(self):
        from bioforge.api.app import create_app

        app = create_app()
        routes = [route.path for route in app.routes]
        expected_prefixes = [
            "/api/v1/workspaces",
            "/api/v1/projects",
            "/api/v1/sequences",
            "/api/v1/pipelines",
            "/api/v1/results",
            "/api/v1/agents",
            "/api/v1/modules",
            "/api/v1/search",
        ]
        for prefix in expected_prefixes:
            assert any(prefix in route for route in routes), f"Missing router: {prefix}"
