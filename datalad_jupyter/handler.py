"""Tornado request handlers for the DataLad Jupyter extension."""

import json

from tornado import web
from jupyter_server.base.handlers import JupyterHandler


# Global DataladAPI instance, set by __init__._load_jupyter_server_extension
DATALAD = None


class DatasetSearchHandler(JupyterHandler):
    """Proxy search requests to the DataLad registry API."""

    @web.authenticated
    async def get(self):
        query = self.get_query_argument("q", default=None)
        page = int(self.get_query_argument("page", default="1"))
        per_page = int(self.get_query_argument("per_page", default="20"))
        result = await DATALAD.search(query=query, page=page, per_page=per_page)
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
        import os
        path = os.path.join(DATALAD.datasets_path, name)
        info = await DATALAD.show(path)
        if info is None:
            raise web.HTTPError(404, "Dataset not found")
        self.finish(json.dumps(info))


class DatasetMetadataHandler(JupyterHandler):
    """Fetch metadata for a dataset URL from the registry."""

    @web.authenticated
    async def get(self):
        url = self.get_query_argument("url")
        if not url:
            raise web.HTTPError(400, "url query parameter required")
        result = await DATALAD.url_metadata(url)
        self.finish(json.dumps(result))


default_handlers = [
    (r"/dataset/search", DatasetSearchHandler),
    (r"/dataset/metadata", DatasetMetadataHandler),
    (r"/dataset/clone/([^/]+)", DatasetCloneStatusHandler),
    (r"/dataset/clone", DatasetCloneHandler),
    (r"/dataset/config", DatasetConfigHandler),
    (r"/dataset/show/([^/]+)", DatasetShowHandler),
    (r"/dataset", DatasetListHandler),
]
