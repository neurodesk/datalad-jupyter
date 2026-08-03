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

# Detect datalad CLI at import time (fallback; re-checked on each call)
DATALAD_CMD = shutil.which("datalad")


def _find_datalad():
    """Return path to datalad CLI, re-checking PATH if not found at import time."""
    global DATALAD_CMD
    if DATALAD_CMD is None:
        DATALAD_CMD = shutil.which("datalad")
    return DATALAD_CMD


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
        return _find_datalad() is not None

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

    async def dataset_detail(self, dataset_id):
        """
        Fetch detail and metadata for a dataset by its registry ID.

        :param dataset_id: Numeric dataset URL ID from the registry
        :return: Registry API response as dict
        """
        url = (
            self.registry_url
            + REGISTRY_API_PREFIX
            + "/"
            + str(dataset_id)
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
            # Read BIDS name if available
            desc_file = entry / "dataset_description.json"
            if desc_file.is_file():
                try:
                    with open(desc_file) as f:
                        bids = json.load(f)
                    if bids.get("Name"):
                        info["bids_name"] = bids["Name"]
                except (json.JSONDecodeError, OSError):
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
                _find_datalad(), "clone", url, dest,
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

            stderr_text = stderr.decode().strip()
            stdout_text = stdout.decode().strip()
            if proc.returncode == 0:
                self._clones[clone_id]["status"] = CloneStatus.COMPLETED
                if stderr_text:
                    self._clones[clone_id]["log"] = stderr_text
            else:
                self._clones[clone_id]["status"] = CloneStatus.FAILED
                # datalad writes install(error) results to stdout
                combined = "\n".join(filter(None, [stdout_text, stderr_text]))
                self._clones[clone_id]["error"] = (
                    f"datalad clone exited with code {proc.returncode}:\n{combined}"
                    if combined
                    else f"datalad clone exited with code {proc.returncode}"
                )
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

    async def list_tree(self, dataset_path, subpath=""):
        """
        List directory contents within a cloned dataset.

        :param dataset_path: Root path of the dataset
        :param subpath: Relative subdirectory to list
        :return: List of dicts with entry info (name, type, has_content)
        """
        target = Path(dataset_path)
        if subpath:
            target = target / subpath

        if not target.is_dir():
            return None

        entries = []
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            entry = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
            if item.is_file():
                # Check if this is an annex pointer (symlink to .git/annex)
                if item.is_symlink():
                    link_target = str(os.readlink(item))
                    entry["annexed"] = ".git/annex" in link_target
                    entry["has_content"] = item.exists()
                else:
                    entry["annexed"] = False
                    entry["has_content"] = True
                entry["size"] = item.stat().st_size if entry["has_content"] else 0
            entries.append(entry)
        return entries

    async def get_content(self, dataset_path, subpath):
        """
        Run `datalad get` to fetch content for a file or directory.

        :param dataset_path: Root path of the dataset
        :param subpath: Relative path within the dataset to get
        :return: Dict with status and error info
        """
        if not self.datalad_available:
            raise RuntimeError("DataLad CLI not found")

        target = Path(dataset_path) / subpath
        proc = await create_subprocess_exec(
            _find_datalad(), "get", str(target),
            cwd=dataset_path,
            stdout=PIPE, stderr=PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.CLONE_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"status": "failed", "error": "datalad get timed out"}

        if proc.returncode == 0:
            return {"status": "completed"}
        else:
            return {"status": "failed", "error": stderr.decode().strip()}

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

        # Read BIDS dataset_description.json if present
        desc_file = os.path.join(str(dataset_path), "dataset_description.json")
        if os.path.isfile(desc_file):
            try:
                with open(desc_file) as f:
                    bids_desc = json.load(f)
                if bids_desc.get("Name"):
                    info["bids_name"] = bids_desc["Name"]
                if bids_desc.get("Authors"):
                    info["authors"] = bids_desc["Authors"]
                if bids_desc.get("License"):
                    info["license"] = bids_desc["License"]
                if bids_desc.get("DatasetDOI"):
                    info["doi"] = bids_desc["DatasetDOI"]
                if bids_desc.get("BIDSVersion"):
                    info["bids_version"] = bids_desc["BIDSVersion"]
            except (json.JSONDecodeError, OSError):
                pass

        # Read README if present
        for readme_name in ("README.md", "README", "README.txt", "README.rst"):
            readme_path = os.path.join(str(dataset_path), readme_name)
            if os.path.isfile(readme_path):
                try:
                    with open(readme_path) as f:
                        info["readme"] = f.read(10000)  # cap at 10KB
                except OSError:
                    pass
                break

        return info
