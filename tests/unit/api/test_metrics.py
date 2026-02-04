"""Tests for metrics API routes."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.routes.metrics import router
from agent_pump.models.metrics import (
    FeatureCompletion,
    ProjectMetrics,
    WorkspaceMetrics,
)
from agent_pump.services.metrics_service import MetricsService


@pytest.fixture
def client():
    """Create a test client with mocked metrics service."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from agent_pump.api.middleware.cors import get_cors_config

    app = FastAPI()
    cors_config = get_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)
    app.include_router(router)

    # Create a proper mock metrics service
    service = MagicMock(spec=MetricsService)
    # Set up default return values to avoid MagicMock issues
    service.get_metrics.return_value = WorkspaceMetrics()
    service.get_project_metrics.return_value = None
    service.export_to_json.return_value = '{"version": "1.0"}'
    service.export_to_csv.return_value = "project_name,feature_name\n"
    app.state.metrics_service = service

    return TestClient(app), service


class TestGetMetrics:
    """Tests for GET /metrics endpoint."""

    def test_get_metrics_success(self, client):
        """Test successfully retrieving metrics."""
        client, mock_metrics_service = client
        # Setup mock workspace metrics
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="Feature 1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]
        mock_metrics_service.get_metrics.return_value = workspace

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["totalFeatures"] == 1
        assert data["successfulFeatures"] == 1

    def test_get_metrics_empty(self, client):
        """Test retrieving metrics when empty."""
        client, mock_metrics_service = client
        mock_metrics_service.get_metrics.return_value = WorkspaceMetrics()

        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["totalFeatures"] == 0
        assert data["averageDurationSeconds"] == 0.0


class TestGetMetricsSummary:
    """Tests for GET /metrics/summary endpoint."""

    def test_get_summary_by_day(self, client):
        """Test getting daily summary."""
        client, mock_metrics_service = client
        workspace = WorkspaceMetrics()
        p1 = workspace.get_or_create_project_metrics(Path("/test/p1"), "Project 1")
        p1.features = [
            FeatureCompletion(
                name="F1",
                project_path=Path("/test/p1"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]
        mock_metrics_service.get_metrics.return_value = workspace

        response = client.get("/metrics/summary?period=day")

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "period" in data
        assert data["period"] == "day"

    def test_get_summary_by_week(self, client):
        """Test getting weekly summary."""
        client, mock_metrics_service = client
        workspace = WorkspaceMetrics()
        mock_metrics_service.get_metrics.return_value = workspace

        response = client.get("/metrics/summary?period=week")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "week"

    def test_get_summary_by_month(self, client):
        """Test getting monthly summary."""
        client, mock_metrics_service = client
        workspace = WorkspaceMetrics()
        mock_metrics_service.get_metrics.return_value = workspace

        response = client.get("/metrics/summary?period=month")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "month"

    def test_get_summary_invalid_period(self, client):
        """Test getting summary with invalid period."""
        client, mock_metrics_service = client
        workspace = WorkspaceMetrics()
        mock_metrics_service.get_metrics.return_value = workspace

        response = client.get("/metrics/summary?period=invalid")

        # Should default to 'day' or handle gracefully
        assert response.status_code == 200


class TestGetProjectMetrics:
    """Tests for GET /metrics/projects/{project_path} endpoint."""

    def test_get_project_metrics_success(self, client):
        """Test successfully retrieving project metrics."""
        client, mock_metrics_service = client
        project_metrics = ProjectMetrics(
            project_path=Path("/test/project"),
            project_name="Test Project",
        )
        project_metrics.features = [
            FeatureCompletion(
                name="Feature 1",
                project_path=Path("/test/project"),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=True,
            ),
        ]
        mock_metrics_service.get_project_metrics.return_value = project_metrics

        response = client.get("/metrics/projects/%2Ftest%2Fproject")

        assert response.status_code == 200
        data = response.json()
        assert data["projectName"] == "Test Project"
        assert data["totalFeatures"] == 1

    def test_get_project_metrics_not_found(self, client):
        """Test retrieving metrics for non-existent project."""
        client, mock_metrics_service = client
        mock_metrics_service.get_project_metrics.return_value = None

        response = client.get("/metrics/projects/%2Fnonexistent")

        assert response.status_code == 404


class TestExportMetrics:
    """Tests for export endpoints."""

    def test_export_json(self, client):
        """Test exporting metrics as JSON."""
        client, mock_metrics_service = client
        mock_metrics_service.export_to_json.return_value = '{"version": "1.0"}'

        response = client.get("/metrics/export/json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert data["format"] == "json"
        assert "version" in data["data"]

    def test_export_csv(self, client):
        """Test exporting metrics as CSV."""
        client, mock_metrics_service = client
        csv_content = "project_name,feature_name\nTest,Feature1"
        mock_metrics_service.export_to_csv.return_value = csv_content

        response = client.get("/metrics/export/csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert data["format"] == "csv"
        assert "project_name" in data["data"]


class TestCorsHeaders:
    """Tests for CORS headers on metrics endpoints."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present on metrics endpoints."""
        client, _ = client
        response = client.get("/metrics", headers={"Origin": "http://localhost:3000"})

        assert "access-control-allow-origin" in response.headers
