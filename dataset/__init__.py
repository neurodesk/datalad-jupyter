"""API for DataLad dataset operations via registry HTTP API and local CLI."""

import asyncio
import json
import os
import shutil
import uuid

from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from pathlib import Path

from tornado.httpclient import AsyncHTTPClient, HTTPClientError
from urllib.parse import urlencode, quote

DEFAULT_REGISTRY_URL = "https://registry.datalad.org"
REGISTRY_API_PREFIX = "/api/v2/dataset-urls"
DEFAULT_DATASETS_PATH = os.path.join(Path.home(), "datasets")

# Detect datalad CLI at import time
DATALAD_CMD = shutil.which("datalad")


class CloneStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DataladAPI:
    """
    API for browsing the DataLad registry and managing local dataset clones.

    Uses HTTP to query the registry and the datalad CLI for clone operations.
    """

    def __init__(self, registry_url=None, datasets_path=None):
        self.registry_url = (registry_url or DEFAULT_REGISTRY_URL).rstrip("/")
        self.datasets_path = datasets_path or DEFAULT_DATASETS_PATH
        self._http_client = AsyncHTTPClient()
        # Track in-progress and completed clone operations {clone_id: {status, url, path, error}}
        self._clones = {}

    @property
    def datalad_available(self):
        return DATALAD_CMD is not None

    async def search(self, query=None, page=1, per_page=20):
        """
        Search the DataLad registry for datasets.

        :param query: Search query string
        :param page: Page number (1-indexed)
        :param per_page: Results per page
        :return: Registry API response as dict
        """
        params = {"page": page, "per_page": per_page}
        if query:
            params["search"] = query

        url = (
            self.registry_url
            + REGISTRY_API_PREFIX
            + "?"
            + urlencode(params)
        )

        response = await self._http_client.fetch(
            url, request_timeout=10.0, raise_error=True
        )
        return json.loads(response.body)

    async def url_metadata(self, dataset_url):
        """
        Fetch metadata for a specific dataset URL from the registry.

        :param dataset_url: The dataset URL to look up
        :return: Registry API response as dict
        """
        params = {"url": dataset_url}
        url = (
            self.registry_url
            + "/api/v2/url-metadata"
            + "?"
            + urlencode(params)
        )

        response = await self._http_client.fetch(
            url, request_timeout=10.0, raise_error=True
        )
        return json.loads(response.body)

    async def list_cloned(self):
        """
        List datasets that have been cloned locally.

        :return: List of dicts with dataset info (name, path, url)
        """
        datasets_dir = Path(self.datasets_path)
        if not datasets_dir.exists():
            return []

        entries = sorted(
            e for e in datasets_dir.iterdir()
            if e.is_dir() and ((e / ".datalad").is_dir() or (e / ".git").exists())
        )
        if not entries:
            return []

        sem = asyncio.Semaphore(10)

        async def get_info(entry):
            info = {"name": entry.name, "path": str(entry)}
            async with sem:
                try:
                    proc = await create_subprocess_exec(
                        "git", "config", "--get", "remote.origin.url",
                        cwd=str(entry),
                        stdout=PIPE, stderr=PIPE,
                    )
                    stdout, _ = await proc.communicate()
                    if proc.returncode == 0:
                        info["url"] = stdout.decode().strip()
                except Exception:
                    pass
            return info

        return await asyncio.gather(*(get_info(e) for e in entries))

    def start_clone(self, url):
        """
        Start an async clone operation.

        :param url: Dataset URL to clone
        :return: Clone operation ID
        :raises RuntimeError: If datalad is not available
        """
        if not self.datalad_available:
            raise RuntimeError(
                "DataLad CLI not found. Install datalad: pip install datalad"
            )

        clone_id = str(uuid.uuid4())

        # Derive dataset name from URL
        name = url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        dest = os.path.join(self.datasets_path, name)

        self._clones[clone_id] = {
            "status": CloneStatus.PENDING,
            "url": url,
            "path": dest,
            "error": None,
        }

        asyncio.ensure_future(self._run_clone(clone_id, url, dest))

        return clone_id

    CLONE_TIMEOUT = 10 * 60  # 10 minutes

    async def _run_clone(self, clone_id, url, dest):
        """Execute the datalad clone subprocess."""
        self._clones[clone_id]["status"] = CloneStatus.RUNNING

        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            proc = await create_subprocess_exec(
                DATALAD_CMD, "clone", url, dest,
                stdout=PIPE, stderr=PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.CLONE_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                self._clones[clone_id]["status"] = CloneStatus.FAILED
                self._clones[clone_id]["error"] = "Clone timed out after 10 minutes"
                return

            if proc.returncode == 0:
                self._clones[clone_id]["status"] = CloneStatus.COMPLETED
            else:
                self._clones[clone_id]["status"] = CloneStatus.FAILED
                self._clones[clone_id]["error"] = stderr.decode().strip()
        except Exception as e:
            self._clones[clone_id]["status"] = CloneStatus.FAILED
            self._clones[clone_id]["error"] = str(e)

    def get_clone_status(self, clone_id):
        """
        Get the status of a clone operation.

        :param clone_id: Clone operation ID
        :return: Clone status dict or None
        """
        return self._clones.get(clone_id)

    async def show(self, path):
        """
        Get metadata for a locally cloned dataset.

        :param path: Path to the dataset
        :return: Dict with dataset metadata
        """
        dataset_path = Path(path)
        if not dataset_path.is_dir():
            return None

        info = {"path": str(dataset_path), "name": dataset_path.name}

        # Get git remote URL
        try:
            proc = await create_subprocess_exec(
                "git", "config", "--get", "remote.origin.url",
                cwd=str(dataset_path),
                stdout=PIPE, stderr=PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                info["url"] = stdout.decode().strip()
        except Exception:
            pass

        # Get dataset ID from .datalad/config if available
        datalad_config = dataset_path / ".datalad" / "config"
        if datalad_config.exists():
            try:
                proc = await create_subprocess_exec(
                    "git", "config", "--file", str(datalad_config),
                    "--get", "datalad.dataset.id",
                    cwd=str(dataset_path),
                    stdout=PIPE, stderr=PIPE,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    info["ds_id"] = stdout.decode().strip()
            except Exception:
                pass

        return info
