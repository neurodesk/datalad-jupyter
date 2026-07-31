# TODOS

## DONE

- DatasetWidget with search debouncing, infinite scroll pagination, clone progress polling
- Backend search proxy, async clone, clone status polling, dataset listing
- Registry metadata display with metalad_core format detection
- Renamed package from jupyterlmod to datalad_jupyter
- Path traversal security fix (`_safe_dataset_path` guard on all path-taking handlers)
- Backend pytest suite (24 tests covering DataladAPI, path validation, clone lifecycle)
- Subdirectory browsing (`GET /dataset/tree/<name>/<path>`) + `datalad get` (`POST /dataset/get`)
- Frontend tree-view in cloned dataset Info dialog with lazy directory expansion and inline `datalad get`

## Dataset removal with safety checks — DEFERRED
Users can delete from terminal. Focus on browse/get and tests first.

## datalad-metalad metadata integration
Integrate datalad-metalad extractors to show rich dataset metadata (BIDS, provenance, etc.) beyond what the registry API provides. The registry only stores basic metadata (URL, size, annex key count). The brainlife fork of datalad-metalad was mentioned as a reference. This would run extractors on cloned datasets to surface richer metadata in the UI.
**Depends on:** Browse/get working first.

## Benchmarking
Benchmark search and query to API endpoint at `https://registry.datalad.org/api/v2/dataset-urls` to review the improvement in the endpoint.
