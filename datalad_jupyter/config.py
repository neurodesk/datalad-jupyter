from traitlets.config import Configurable
from traitlets import Unicode

from dataset import DEFAULT_REGISTRY_URL, DEFAULT_DATASETS_PATH


class Datalad(Configurable):
    """Configuration for the DataLad Jupyter extension."""

    registry_url = Unicode(
        DEFAULT_REGISTRY_URL,
        help="URL of the DataLad registry to search for datasets.",
    ).tag(config=True)

    datasets_path = Unicode(
        DEFAULT_DATASETS_PATH,
        help="Local directory where datasets are cloned.",
    ).tag(config=True)
