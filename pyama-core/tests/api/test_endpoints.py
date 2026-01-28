"""Tests for FastAPI endpoints."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pyama_core.api.server import create_app

# Test data path - real nd2 file for integration testing
# Can be overridden via PYAMA_TEST_ND2_FILE environment variable
# Default: {repo_root}/data/test.nd2
_REPO_ROOT = Path(__file__).parent.parent.parent
TEST_ND2_FILE = Path(os.environ.get("PYAMA_TEST_ND2_FILE", str(_REPO_ROOT / "data" / "test.nd2")))


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


class TestProcessingConfig:
    """Tests for GET /processing/config endpoint."""

    def test_get_config_schema(self, client: TestClient):
        """Should return the ProcessingConfig as JSON schema."""
        response = client.get("/api/processing/config")

        assert response.status_code == 200
        data = response.json()

        # Check it's a valid JSON schema
        assert "title" in data
        assert data["title"] == "ProcessingConfig"
        assert "properties" in data
        assert "$defs" in data

        # Check expected nested schemas
        assert "Channels" in data["$defs"]


class TestMicroscopyEndpoint:
    """Tests for POST /data/microscopy endpoint."""

    @pytest.mark.skipif(
        not TEST_ND2_FILE.exists(),
        reason=f"Test file not found: {TEST_ND2_FILE}",
    )
    def test_load_microscopy_metadata(self, client: TestClient):
        """Should return metadata for a valid nd2 file."""
        response = client.post(
            "/api/data/microscopy",
            json={"file_path": str(TEST_ND2_FILE)},
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert data["file_path"] == str(TEST_ND2_FILE)
        assert data["base_name"] == "250129_HuH7"
        assert data["file_type"] == "nd2"

        # Check dimensions
        assert data["n_fovs"] == 132
        assert data["n_frames"] == 181
        assert data["n_channels"] == 3

        # Check channel names
        assert data["channel_names"] == ["BF_10x", "DsRed", "Cy5_1000"]

        # Check image dimensions
        assert data["width"] == 2048
        assert data["height"] == 2044

    def test_load_microscopy_file_not_found(self, client: TestClient):
        """Should return 404 for non-existent file."""
        response = client.post(
            "/api/data/microscopy",
            json={"file_path": "/nonexistent/file.nd2"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_load_microscopy_invalid_request(self, client: TestClient):
        """Should return 422 for invalid request body."""
        response = client.post(
            "/api/data/microscopy",
            json={},  # Missing required file_path
        )

        assert response.status_code == 422


class TestTasksEndpoint:
    """Tests for /processing/tasks endpoints."""

    def test_list_tasks_empty(self, client: TestClient):
        """Should return empty task list initially."""
        response = client.get("/api/processing/tasks")

        assert response.status_code == 200
        data = response.json()

        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    @pytest.mark.skipif(
        not TEST_ND2_FILE.exists(),
        reason=f"Test file not found: {TEST_ND2_FILE}",
    )
    def test_create_task(self, client: TestClient):
        """Should create a new processing task."""
        response = client.post(
            "/api/processing/tasks",
            json={
                "file_path": str(TEST_ND2_FILE),
                "config": {
                    "channels": {
                        "pc": {"channel": 0, "features": ["area"]},
                        "fl": [{"channel": 1, "features": ["intensity_total"]}],
                    },
                    "params": {"segmentation_method": "cellpose"},
                },
            },
        )

        assert response.status_code == 201  # Created
        data = response.json()

        assert "id" in data
        assert data["status"] == "pending"
        assert data["file_path"] == str(TEST_ND2_FILE)

        # Clean up - cancel the task
        task_id = data["id"]
        client.delete(f"/api/processing/tasks/{task_id}")

    def test_get_task_not_found(self, client: TestClient):
        """Should return 404 for non-existent task."""
        response = client.get("/api/processing/tasks/nonexistent-id")

        assert response.status_code == 404


class TestFakeTask:
    """Tests for fake task execution."""

    def test_create_fake_task(self, client: TestClient):
        """Test creating a fake task returns pending status."""
        response = client.post(
            "/api/processing/tasks",
            json={
                "file_path": "/fake/file.nd2",
                "config": {},
                "fake": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["file_path"] == "/fake/file.nd2"

    def test_fake_task_without_real_file(self, client: TestClient):
        """Fake task should work without a real file existing."""
        response = client.post(
            "/api/processing/tasks",
            json={
                "file_path": "/nonexistent/path/test.nd2",
                "config": {},
                "fake": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert "id" in data

    def test_fake_task_with_empty_config(self, client: TestClient):
        """Fake task should accept empty config."""
        response = client.post(
            "/api/processing/tasks",
            json={
                "file_path": "/fake/file.nd2",
                "config": {},
                "fake": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["config"]["channels"] is None
        # ProcessingParams has typed defaults, not empty dict
        assert "batch_size" in data["config"]["params"]
        assert data["config"]["params"]["batch_size"] == 2

    def test_fake_default_is_false(self, client: TestClient):
        """Task without fake flag should default to false (real task).

        A real task requires output_dir, so omitting it proves fake=False.
        """
        response = client.post(
            "/api/processing/tasks",
            json={
                "file_path": "/some/file.nd2",
                "config": {},
            },
        )

        # Validation rejects real tasks without output_dir, proving fake defaults to False
        assert response.status_code == 422
        detail = response.json()["detail"][0]
        assert "output_dir" in detail["msg"]
