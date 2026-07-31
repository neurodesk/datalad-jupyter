# Jupyter DataLad

Jupyter interactive notebook server extension that allows users
to browse and clone datasets from a [DataLad](https://www.datalad.org/) registry
(such as [registry.datalad.org](https://registry.datalad.org/)) directly from
JupyterLab or Jupyter Notebook.

## Requirements

- [jupyter notebook](https://github.com/jupyter/notebook) >= 6.0
- [DataLad](https://www.datalad.org/) (for clone operations)
- optional: [jupyterlab](https://github.com/jupyterlab/jupyterlab) >= 4.0

## Support
- JupyterLab extension
- Jupyter Server extension

## Setup

### Install

```
pip install datalad-jupyter
```

DataLad must also be installed for clone operations:
```
pip install datalad
```

### Configuration

The extension can be configured in the Jupyter configuration file:

```python
# Set a custom DataLad registry URL (default: https://registry.datalad.org)
c.Datalad.registry_url = 'https://registry.datalad.org'

# Set where cloned datasets are stored (default: ~/datasets)
c.Datalad.datasets_path = '/path/to/datasets'
```

## Features

- **Browse** datasets from a DataLad registry with search and pagination
- **Clone** datasets to a local directory with async progress tracking
- **View** cloned datasets and their metadata
- **Browse files** within cloned datasets with directory tree view
- **Download** annexed files via `datalad get` directly from the UI

## Development Environment Setup

### Conda environment (recommended)

Create and activate a conda environment with all dependencies:

```bash
conda create -n jpdatalad python=3.12
conda activate jpdatalad

# Install datalad via conda-forge (recommended — includes git-annex)
conda install -c conda-forge datalad

# Install jupyter and build dependencies
pip install jupyterlab jupyter-server build

# Install the extension in editable mode
pip install -e ".[dev]"
```

**Important:** `conda install -c conda-forge datalad` is strongly preferred over `pip install datalad` because conda-forge bundles `git-annex`, which datalad requires. Installing datalad via pip requires you to install git-annex separately (e.g. `brew install git-annex` on macOS or `apt install git-annex` on Debian/Ubuntu).

### Verifying datalad is available

After installation, verify that datalad is on the PATH **in the same environment** where JupyterLab runs:

```bash
conda activate jpdatalad
which datalad          # should print a path
datalad --version      # should print version
```

### Common pitfall: "datalad not found" in JupyterLab

If `datalad clone` works in your terminal but JupyterLab reports "DataLad CLI not found", the most likely causes are:

1. **JupyterLab was started from a different environment.** The server process inherits the PATH from whatever shell launched it. If you ran `conda activate jpdatalad` but started JupyterLab from a different terminal (or a system-level jupyter), it won't see conda packages. Fix: always start JupyterLab from the activated environment.

2. **JupyterLab was started before installing datalad.** The extension previously detected datalad only at import time. This is now fixed (it re-checks PATH on each operation), but restarting the server after installing datalad is still good practice.

3. **datalad installed via pip without git-annex.** `pip install datalad` installs the Python package but not git-annex. Without git-annex, many datalad commands fail. Use `conda install -c conda-forge datalad` which includes git-annex, or install git-annex separately.

### Build

- Start conda environment:
    ```bash
    conda activate jpdatalad
    ```

- Frontend (JupyterLab extension):
    ```bash
    jlpm install
    jlpm run build           # dev build
    jlpm run build:prod      # production build
    jlpm run install:extension  # install in jupyterlab dev mode
    ```

- Watch mode (auto-rebuild on changes):
    ```bash
    jlpm run watch
    ```

- Start jupyter lab environment to test the extension:
    ```bash
    jupyter lab
    ```

- Python package (wheel + tarball):
    ```bash
    pyproject-build
    ```

### Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Migration from jupyter-lmod

This package (v6.0.0+) replaces the previous `jupyterlmod` extension which
provided Lmod/Tmod environment module management. If you need the Lmod extension,
pin to `jupyterlmod<6`.
