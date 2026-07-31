"""Shared fixtures for datalad_jupyter tests."""

import asyncio
import json
import os

import pytest


@pytest.fixture
def tmp_datasets_dir(tmp_path):
    """Create a temporary datasets directory."""
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    return str(datasets)


@pytest.fixture
def make_fake_dataset(tmp_datasets_dir):
    """Factory fixture to create a fake cloned dataset on disk."""

    def _make(name, url="https://github.com/example/dataset.git", ds_id=None):
        ds_path = os.path.join(tmp_datasets_dir, name)
        os.makedirs(ds_path)
        # Minimal git repo structure
        git_dir = os.path.join(ds_path, ".git")
        os.makedirs(git_dir)
        # Write a config with remote.origin.url
        with open(os.path.join(git_dir, "config"), "w") as f:
            f.write(f"[remote \"origin\"]\n\turl = {url}\n")
        # .datalad/config with dataset id
        datalad_dir = os.path.join(ds_path, ".datalad")
        os.makedirs(datalad_dir)
        config_content = ""
        if ds_id:
            config_content = f"[datalad \"dataset\"]\n\tid = {ds_id}\n"
        with open(os.path.join(datalad_dir, "config"), "w") as f:
            f.write(config_content)
        return ds_path

    return _make


@pytest.fixture
def api(tmp_datasets_dir):
    """Create a DataladAPI instance with a temporary datasets directory."""
    from dataset import DataladAPI

    return DataladAPI(
        registry_url="https://registry.datalad.org",
        datasets_path=tmp_datasets_dir,
    )


@pytest.fixture
def mock_http_response():
    """Factory to create a mock HTTP response."""

    class MockResponse:
        def __init__(self, body_dict, code=200):
            self.body = json.dumps(body_dict).encode()
            self.code = code

    return MockResponse
