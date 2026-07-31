"""Tests for handler path validation.

The _safe_dataset_path function is tested in isolation to avoid importing
jupyter_server (which may not be installed in test environments).
"""

import os

import pytest
from tornado.web import HTTPError


def _safe_dataset_path(datasets_path, name):
    """Copy of handler._safe_dataset_path for isolated testing."""
    resolved = os.path.realpath(os.path.join(datasets_path, name))
    if not resolved.startswith(os.path.realpath(datasets_path) + os.sep):
        raise HTTPError(403, "Access denied")
    return resolved


class TestSafeDatasetPath:
    def test_traversal_dotdot(self):
        with pytest.raises(HTTPError) as exc_info:
            _safe_dataset_path("/home/user/datasets", "../../etc/passwd")
        assert exc_info.value.status_code == 403

    def test_traversal_multiple_levels(self):
        with pytest.raises(HTTPError) as exc_info:
            _safe_dataset_path("/home/user/datasets", "../../../tmp")
        assert exc_info.value.status_code == 403

    def test_valid_name(self, tmp_path):
        datasets = tmp_path / "datasets"
        datasets.mkdir()
        ds = datasets / "my-dataset"
        ds.mkdir()
        result = _safe_dataset_path(str(datasets), "my-dataset")
        assert result == str(ds.resolve())

    def test_nested_valid(self, tmp_path):
        datasets = tmp_path / "datasets"
        datasets.mkdir()
        ds = datasets / "org" / "repo"
        ds.mkdir(parents=True)
        result = _safe_dataset_path(str(datasets), "org/repo")
        assert "org/repo" in result

    def test_datasets_path_itself_rejected(self, tmp_path):
        datasets = tmp_path / "datasets"
        datasets.mkdir()
        with pytest.raises(HTTPError) as exc_info:
            _safe_dataset_path(str(datasets), "")
        assert exc_info.value.status_code == 403

    def test_dot_rejected(self, tmp_path):
        datasets = tmp_path / "datasets"
        datasets.mkdir()
        with pytest.raises(HTTPError) as exc_info:
            _safe_dataset_path(str(datasets), ".")
        assert exc_info.value.status_code == 403
