# Changelog

## [0.1.0] - 2026-08-05

Initial release of `datalad-jupyter`, a JupyterLab and Jupyter Notebook extension for browsing and cloning datasets from a DataLad registry.

### Added

- Search datasets from the DataLad registry (registry.datalad.org) with debounced server-side queries
- Infinite scroll pagination for search results
- Clone datasets from the registry with async, non-blocking clone operations and status polling
- List locally cloned datasets with dataset names
- Browse file and directory structure of cloned datasets via data tree view
- View dataset metadata
- Download files and directories from cloned datasets with `datalad get`
- JupyterLab sidebar widget and classic Jupyter Notebook support
- Configurable registry URL and datasets path via Jupyter config (`c.Datalad.registry_url`, `c.Datalad.datasets_path`)
- Directory traversal protection on all path-accepting API endpoints
- REST API endpoints: search, clone, clone status, list, show, tree, get, and config
- Trusted publishing workflow for PyPI
