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

## Develop

### Requirements

- pip >= 23
- [build](https://pypi.org/project/build/)
- nodejs >= 18.x

### Build

- wheel and tarball:
    ```shell
    pyproject-build
    ```
- labextension
    ```shell
    jlpm install
    jlpm run build
    # To install extension in jupyterlab in develop mode:
    jlpm run install:extension
    ```

## Migration from jupyter-lmod

This package (v6.0.0+) replaces the previous `jupyterlmod` extension which
provided Lmod/Tmod environment module management. If you need the Lmod extension,
pin to `jupyterlmod<6`.

