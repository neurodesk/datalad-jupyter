# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

datalad-jupyter (package name: `datalad-jupyter`) is a Jupyter extension that lets users browse and clone datasets from a DataLad registry (default: registry.datalad.org) within JupyterLab and Jupyter Notebook. It uses the DataLad registry's REST API for search/browse and the DataLad CLI for clone operations.

**Note:** This project was previously `jupyterlmod` for Lmod/Tmod environment module management. v6.0.0 pivoted to DataLad dataset management.

## Development Environment Setup

```bash
conda create -n jpdatalad python=3.12
conda activate jpdatalad
conda install -c conda-forge datalad    # includes git-annex
pip install jupyterlab jupyter-server build pytest pytest-asyncio
pip install -e .
jlpm install && jlpm run build
jlpm run install:extension
jupyter lab
```

Always start JupyterLab from the activated conda environment (`conda activate jpdatalad && jupyter lab`). The extension detects `datalad` via `shutil.which()` from the server process PATH — if jupyter is launched from a different environment or before datalad is installed, clone operations will fail with "DataLad CLI not found".

Use `conda install -c conda-forge datalad` (not `pip install datalad`) because conda-forge bundles git-annex. Without git-annex, datalad clone/get silently fail.

## Build Commands

**Python package (wheel + tarball):**
```
pyproject-build
```

**JupyterLab extension (frontend):**
```
jlpm install
jlpm run build           # dev build
jlpm run build:prod      # production build
jlpm run install:extension  # install in jupyterlab dev mode
```

**Lint:**
```
jlpm run eslint:check    # check only
jlpm run eslint          # check and fix
```

**Watch mode (development):**
```
jlpm run watch
```

**Tests:**
```
pytest tests/ -v
```

**Version bumping:** Uses `tbump` (configured in pyproject.toml). Version is sourced from `package.json`.

## Architecture

The project has three main layers:

### 1. `dataset/` — Python DataLad API
- `dataset/__init__.py`: Core async API with `DataladAPI` class.
- Uses HTTP (`tornado.httpclient.AsyncHTTPClient`) to query the DataLad registry REST API (`/api/v2/dataset-urls`) for search/browse.
- Uses `asyncio.create_subprocess_exec` to run `datalad clone` for dataset cloning (security: never uses shell=True).
- Tracks in-progress clone operations in memory with UUID-keyed status dict.
- Detects DataLad CLI via `shutil.which("datalad")`, re-checking PATH on each operation (`_find_datalad()`) so installing datalad after server start works without restart.

### 2. `datalad-jupyter/` — Jupyter Server Extension (Python backend)
- `handler.py`: Tornado request handlers exposing REST API at `/dataset/*` endpoints:
  - `GET /dataset/search` — proxy to registry API
  - `GET /dataset` — list locally cloned datasets
  - `POST /dataset/clone` — start async clone (returns 202)
  - `GET /dataset/clone/<id>` — poll clone status
  - `GET /dataset/config` — return extension config
  - `GET /dataset/show/<name>` — dataset metadata
  - `GET /dataset/tree/<name>/<path>` — list directory contents in a cloned dataset
  - `POST /dataset/get` — run `datalad get` on a file/directory
- `config.py`: Traitlets-based configuration (`Datalad` class) for `registry_url` and `datasets_path`.
- `__init__.py`: Extension registration — sets up handlers and loads config.
- `static/`: JS files for classic notebook extension.

### 3. `src/` — JupyterLab Extension (TypeScript frontend)
- `src/index.ts`: JupyterLab plugin — `DatasetWidget` sidebar panel with search (debounced, server-side via registry API), cloned dataset list, and async clone with polling.
- Uses `Dataset` class from `datalad-jupyter/static/dataset.js` (shared JS API client).

### Security
- All handlers that accept path parameters use `_safe_dataset_path()` to prevent directory traversal attacks (resolves symlinks, verifies the path stays within `datasets_path`).
- `DatasetGetHandler` double-validates both the dataset name and the subpath.

### Key Design Details
- The `dataset.js` client (in `datalad-jupyter/static/`) is the shared HTTP client used by both the classic notebook extension and the JupyterLab extension.
- Lab extension output goes to `datalad-jupyter/labextension/` (built artifact, not committed).
- Build system uses hatchling with `hatch-jupyter-builder` for the Python package and `@jupyterlab/builder` for the lab extension.
- Registry URL and datasets path are configurable via Jupyter config (`c.Datalad.registry_url`, `c.Datalad.datasets_path`).

### Skills
When debugging any bug, test failure, or unexpected behavior, or inspect the planning or criticize the design follow the systematic debugging process in `~/.agents/skills/`.