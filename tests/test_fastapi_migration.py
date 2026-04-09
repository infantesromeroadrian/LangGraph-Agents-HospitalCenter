"""
Tests para validar la migración de Flask a FastAPI.

Verifica que todos los endpoints funcionen correctamente después de la migración.
"""

import pytest
from fastapi.testclient import TestClient
from src.config.settings import settings
from src.web.main import app

client = TestClient(app)


class TestFastAPIMigration:
    """Suite de tests para validar la migración."""

    def test_health_endpoint(self):
        """Test que el endpoint de salud funciona."""
        response = client.get("/health")
        assert response.status_code in (200, 503)

        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["version"] == "2.0.0"
        assert data["framework"] == "FastAPI"
        assert "services" in data
        assert "worker_pid" in data

    def test_root_endpoint(self):
        """Test que la página principal carga."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"LangGraph Medical Center" in response.content

    def test_admission_route_redirects_to_root(self):
        """El flujo legacy de admisión redirige al home unificado."""
        response = client.get("/admission", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers["location"] == "/"

    def test_favicon_route_exists(self):
        """El favicon ya no devuelve 404 en la carga inicial."""
        response = client.get("/favicon.ico", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers["location"] == "/static/favicon.svg"

    def test_metrics_endpoint(self):
        """Test que el endpoint de métricas funciona."""
        response = client.get("/metrics", headers={"X-Admin-Key": settings.get_admin_api_key()})
        assert response.status_code == 200
        assert b"medical_uptime" in response.content

    def test_openapi_schema(self):
        """Test que el schema OpenAPI contiene los endpoints esperados."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/health" in schema["paths"]
        assert "/api/sessions" in schema["paths"]

    def test_cors_headers(self):
        """Test que CORS devuelve el header allow-origin para origenes configurados."""
        response = client.get("/health", headers={"Origin": "http://localhost:5000"})
        assert response.status_code in (200, 503)
        assert "access-control-allow-origin" in response.headers


class TestBackwardCompatibility:
    """Tests para verificar compatibilidad con el sistema anterior."""

    def test_health_response_format(self):
        """Test que el formato de health check es compatible."""
        response = client.get("/health")
        data = response.json()

        # Verificar que tiene los campos esperados
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "database" in data["services"]
        assert "llm" in data["services"]
        assert "graph" in data["services"]


class TestPerformance:
    """Tests básicos de performance."""

    def test_health_endpoint_latency(self):
        """Test que el endpoint de salud responde rápido."""
        import time

        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code in (200, 503)
        assert duration < 1.0, f"Health check took {duration}s (should be < 1s)"

    def test_openapi_schema_latency(self):
        """Test que el schema OpenAPI se genera rápido."""
        import time

        start = time.time()
        response = client.get("/openapi.json")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.5, f"OpenAPI schema took {duration}s (should be < 0.5s)"


class TestErrorHandling:
    """Tests de manejo de errores."""

    def test_404_not_found(self):
        """Test que endpoints inexistentes retornan 404."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_invalid_session_id(self):
        """Test que sesiones sin auth retornan 401."""
        response = client.get("/api/sessions/invalid-uuid")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
