"""Tests for dataset.DataladAPI."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dataset import DataladAPI, CloneStatus, DATALAD_CMD


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_happy_path(self, api, mock_http_response):
        body = {
            "dataset_urls": [{"id": 1, "url": "https://example.com/ds"}],
            "collection_stats": {"summary": {"ds_count": 1}},
        }
        mock_resp = mock_http_response(body)
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, return_value=mock_resp):
            result = await api.search(query="test")
        assert result["dataset_urls"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_search_empty_results(self, api, mock_http_response):
        body = {"dataset_urls": [], "collection_stats": {"summary": {"ds_count": 0}}}
        mock_resp = mock_http_response(body)
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, return_value=mock_resp):
            result = await api.search()
        assert result["dataset_urls"] == []

    @pytest.mark.asyncio
    async def test_search_network_error(self, api):
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, side_effect=Exception("Connection refused")):
            with pytest.raises(Exception, match="Connection refused"):
                await api.search(query="test")

    @pytest.mark.asyncio
    async def test_search_pagination(self, api, mock_http_response):
        body = {"dataset_urls": [{"id": 2}], "collection_stats": {"summary": {"ds_count": 100}}}
        mock_resp = mock_http_response(body)
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, return_value=mock_resp) as mock_fetch:
            await api.search(query="test", page=3, per_page=10)
        call_url = mock_fetch.call_args[0][0]
        assert "page=3" in call_url
        assert "per_page=10" in call_url


class TestListCloned:
    @pytest.mark.asyncio
    async def test_empty_dir(self, api):
        result = await api.list_cloned()
        assert result == []

    @pytest.mark.asyncio
    async def test_datasets_found(self, api, make_fake_dataset):
        make_fake_dataset("my_dataset", url="https://github.com/org/repo.git")
        with patch("dataset.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"https://github.com/org/repo.git\n", b""))
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await api.list_cloned()
        assert len(result) == 1
        assert result[0]["name"] == "my_dataset"
        assert result[0]["url"] == "https://github.com/org/repo.git"

    @pytest.mark.asyncio
    async def test_git_config_failure(self, api, make_fake_dataset):
        make_fake_dataset("broken_ds")
        with patch("dataset.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b"", b"error"))
            proc.returncode = 1
            mock_exec.return_value = proc
            result = await api.list_cloned()
        assert len(result) == 1
        assert "url" not in result[0]


class TestClone:
    def test_start_clone_no_datalad(self, api):
        with patch("dataset._find_datalad", return_value=None):
            with pytest.raises(RuntimeError, match="DataLad CLI not found"):
                api.start_clone("https://example.com/ds.git")

    @pytest.mark.asyncio
    async def test_clone_success(self, api):
        with patch("dataset._find_datalad", return_value="/usr/bin/datalad"):
            with patch("dataset.create_subprocess_exec") as mock_exec:
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
                proc.returncode = 0
                mock_exec.return_value = proc
                clone_id = api.start_clone("https://example.com/ds.git")
                # Let the background task run
                await asyncio.sleep(0.1)
        status = api.get_clone_status(clone_id)
        assert status["status"] == CloneStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_clone_failure(self, api):
        with patch("dataset._find_datalad", return_value="/usr/bin/datalad"):
            with patch("dataset.create_subprocess_exec") as mock_exec:
                proc = AsyncMock()
                proc.communicate = AsyncMock(return_value=(
                    b"install(error): /tmp/ds [No working git-annex installation]\n",
                    b"[INFO] Cloning...\n",
                ))
                proc.returncode = 1
                mock_exec.return_value = proc
                clone_id = api.start_clone("https://example.com/ds.git")
                await asyncio.sleep(0.1)
        status = api.get_clone_status(clone_id)
        assert status["status"] == CloneStatus.FAILED
        # stdout error (install(error)) must appear in the error message
        assert "No working git-annex installation" in status["error"]
        # stderr info should also be included
        assert "[INFO] Cloning" in status["error"]


class TestDatasetDetail:
    @pytest.mark.asyncio
    async def test_detail_success(self, api, mock_http_response):
        body = {"id": 42, "url": "https://example.com/ds", "ds_id": "abc123"}
        mock_resp = mock_http_response(body)
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, return_value=mock_resp):
            result = await api.dataset_detail(42)
        assert result["ds_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_detail_not_found(self, api):
        from tornado.httpclient import HTTPClientError
        with patch.object(api._http_client, "fetch", new_callable=AsyncMock, side_effect=HTTPClientError(404)):
            with pytest.raises(HTTPClientError):
                await api.dataset_detail(99999)


class TestShow:
    @pytest.mark.asyncio
    async def test_show_valid_dataset(self, api, make_fake_dataset):
        ds_path = make_fake_dataset("test_ds", url="https://example.com/ds.git", ds_id="abc-123")
        with patch("dataset.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            # First call: git remote url, second call: datalad dataset id
            proc.communicate = AsyncMock(side_effect=[
                (b"https://example.com/ds.git\n", b""),
                (b"abc-123\n", b""),
            ])
            proc.returncode = 0
            mock_exec.return_value = proc
            result = await api.show(ds_path)
        assert result["name"] == "test_ds"

    @pytest.mark.asyncio
    async def test_show_missing_dataset(self, api):
        result = await api.show("/nonexistent/path")
        assert result is None


class TestListTree:
    @pytest.mark.asyncio
    async def test_list_tree_root(self, api, make_fake_dataset):
        ds_path = make_fake_dataset("tree_ds")
        # Create some files
        Path(ds_path, "README.md").write_text("hello")
        Path(ds_path, "sub").mkdir()
        Path(ds_path, "sub", "data.csv").write_text("a,b,c")

        result = await api.list_tree(ds_path)
        names = [e["name"] for e in result]
        assert "README.md" in names
        assert "sub" in names

    @pytest.mark.asyncio
    async def test_list_tree_subdir(self, api, make_fake_dataset):
        ds_path = make_fake_dataset("tree_ds2")
        Path(ds_path, "sub").mkdir()
        Path(ds_path, "sub", "data.csv").write_text("a,b,c")

        result = await api.list_tree(ds_path, "sub")
        assert len(result) == 1
        assert result[0]["name"] == "data.csv"
        assert result[0]["type"] == "file"

    @pytest.mark.asyncio
    async def test_list_tree_nonexistent(self, api, make_fake_dataset):
        ds_path = make_fake_dataset("tree_ds3")
        result = await api.list_tree(ds_path, "nonexistent")
        assert result is None


class TestGetContent:
    @pytest.mark.asyncio
    async def test_get_content_no_datalad(self, api, make_fake_dataset):
        ds_path = make_fake_dataset("get_ds")
        with patch("dataset._find_datalad", return_value=None):
            with pytest.raises(RuntimeError, match="DataLad CLI not found"):
                await api.get_content(ds_path, "file.txt")
