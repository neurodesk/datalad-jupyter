"""Tornado request handlers for the DataLad Jupyter extension."""

import json
import logging
import os

from tornado import web
from jupyter_server.base.handlers import JupyterHandler

log = logging.getLogger(__name__)

# Global DataladAPI instance, set by __init__._load_jupyter_server_extension
DATALAD = None


def _safe_dataset_path(datasets_path, name):
    """Resolve a dataset path and verify it stays within the datasets directory."""
    resolved = os.path.realpath(os.path.join(datasets_path, name))
    if not resolved.startswith(os.path.realpath(datasets_path) + os.sep):
        raise web.HTTPError(403, "Access denied")
    return resolved


class DatasetSearchHandler(JupyterHandler):
    """Proxy search requests to the DataLad registry API."""

    @web.authenticated
    async def get(self):
        query = self.get_query_argument("q", default=None)
        page = int(self.get_query_argument("page", default="1"))
        per_page = int(self.get_query_argument("per_page", default="20"))
        try:
            result = await DATALAD.search(query=query, page=page, per_page=per_page)
        except Exception as e:
            log.error(f"Registry search failed: {e}")
            raise web.HTTPError(502, f"Registry search failed: {e}")
        self.finish(json.dumps(result))


class DatasetListHandler(JupyterHandler):
    """List locally cloned datasets."""

    @web.authenticated
    async def get(self):
        datasets = await DATALAD.list_cloned()
        self.finish(json.dumps(datasets))


class DatasetCloneHandler(JupyterHandler):
    """Start an async clone operation."""

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        url = body.get("url")
        if not url:
            raise web.HTTPError(400, "url missing from request body")
        try:
            clone_id = DATALAD.start_clone(url)
        except RuntimeError as e:
            self.set_status(500)
            self.finish(json.dumps({"error": str(e)}))
            return
        self.set_status(202)
        self.finish(json.dumps({"clone_id": clone_id}))


class DatasetCloneStatusHandler(JupyterHandler):
    """Poll the status of a clone operation."""

    @web.authenticated
    async def get(self, clone_id):
        status = DATALAD.get_clone_status(clone_id)
        if status is None:
            raise web.HTTPError(404, "Clone operation not found")
        self.finish(json.dumps(status))


class DatasetConfigHandler(JupyterHandler):
    """Return extension configuration."""

    @web.authenticated
    async def get(self):
        self.finish(json.dumps({
            "registry_url": DATALAD.registry_url,
            "datasets_path": DATALAD.datasets_path,
            "datalad_available": DATALAD.datalad_available,
        }))


class DatasetShowHandler(JupyterHandler):
    """Show metadata for a locally cloned dataset."""

    @web.authenticated
    async def get(self, name):
        path = _safe_dataset_path(DATALAD.datasets_path, name)
        info = await DATALAD.show(path)
        if info is None:
            raise web.HTTPError(404, "Dataset not found")
        self.finish(json.dumps(info))


class DatasetTreeHandler(JupyterHandler):
    """List directory contents within a cloned dataset."""

    @web.authenticated
    async def get(self, name, subpath=""):
        path = _safe_dataset_path(DATALAD.datasets_path, name)
        entries = await DATALAD.list_tree(path, subpath)
        if entries is None:
            raise web.HTTPError(404, "Directory not found")
        self.finish(json.dumps(entries))


class DatasetGetHandler(JupyterHandler):
    """Run datalad get on a file/directory within a cloned dataset."""

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        name = body.get("name")
        subpath = body.get("path")
        if not name or not subpath:
            raise web.HTTPError(400, "name and path required")
        dataset_path = _safe_dataset_path(DATALAD.datasets_path, name)
        # Validate subpath doesn't escape the dataset
        resolved = os.path.realpath(os.path.join(dataset_path, subpath))
        if not resolved.startswith(os.path.realpath(dataset_path) + os.sep):
            raise web.HTTPError(403, "Access denied")
        try:
            result = await DATALAD.get_content(dataset_path, subpath)
        except RuntimeError as e:
            raise web.HTTPError(500, str(e))
        self.finish(json.dumps(result))


class DatasetMetadataHandler(JupyterHandler):
    """Fetch detail and metadata for a dataset by registry ID."""

    @web.authenticated
    async def get(self, dataset_id):
        try:
            result = await DATALAD.dataset_detail(dataset_id)
        except Exception as e:
            log.error(f"Registry metadata fetch failed: {e}")
            raise web.HTTPError(502, f"Registry metadata fetch failed: {e}")
        self.finish(json.dumps(result))


default_handlers = [
    (r"/dataset/search", DatasetSearchHandler),
    (r"/dataset/metadata/([^/]+)", DatasetMetadataHandler),
    (r"/dataset/clone/([^/]+)", DatasetCloneStatusHandler),
    (r"/dataset/clone", DatasetCloneHandler),
    (r"/dataset/config", DatasetConfigHandler),
    (r"/dataset/tree/([^/]+)/(.*)", DatasetTreeHandler),
    (r"/dataset/tree/([^/]+)", DatasetTreeHandler),
    (r"/dataset/get", DatasetGetHandler),
    (r"/dataset/show/([^/]+)", DatasetShowHandler),
    (r"/dataset", DatasetListHandler),
]
