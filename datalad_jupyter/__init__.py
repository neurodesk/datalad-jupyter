import json
import logging

from jupyter_server.utils import url_path_join as ujoin
from pathlib import Path

from .config import Datalad as DataladConfig
from .handler import default_handlers
from dataset import DataladAPI, _find_datalad

import datalad_jupyter.handler as handler_module

HERE = Path(__file__).parent.resolve()
_LAB_EXT_NAME = None

try:
    with (HERE / "labextension" / "package.json").open() as fid:
        _LAB_EXT_NAME = json.load(fid)["name"]
except FileNotFoundError:
    pass


def _jupyter_labextension_paths():
    if _LAB_EXT_NAME is None:
        return []
    return [{
        "src": "labextension",
        "dest": _LAB_EXT_NAME
    }]


def _jupyter_server_extension_points():
    return [{"module": "datalad_jupyter"}]


def _jupyter_nbextension_paths():
    return [
        dict(
            section="tree", src="static", dest="datalad_jupyter",
            require="datalad_jupyter/main"
        )
    ]


def _load_jupyter_server_extension(nbapp):
    """
    Called when the extension is loaded.

    Args:
        nbapp: handle to the Notebook webserver instance.
    """
    log = logging.getLogger(__name__)
    log.info("Loading datalad_jupyter extension")

    datalad_config = DataladConfig(parent=nbapp)

    # Initialize the global DataladAPI instance
    handler_module.DATALAD = DataladAPI(
        registry_url=datalad_config.registry_url,
        datasets_path=datalad_config.datasets_path,
    )

    if _find_datalad():
        log.info(f"DataLad CLI found: {_find_datalad()}")
    else:
        log.warning(
            "DataLad CLI not found. Clone operations will not work. "
            "Install datalad: pip install datalad"
        )

    log.info(f"Registry URL: {datalad_config.registry_url}")
    log.info(f"Datasets path: {datalad_config.datasets_path}")

    web_app = nbapp.web_app
    base_url = web_app.settings["base_url"]
    for path, class_ in default_handlers:
        web_app.add_handlers(".*$", [(ujoin(base_url, path), class_)])


# For backward compatibility
load_jupyter_server_extension = _load_jupyter_server_extension
_jupyter_server_extension_paths = _jupyter_server_extension_points
