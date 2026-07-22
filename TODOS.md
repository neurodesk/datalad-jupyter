# TODOS

## Full UI redesign for dataset browsing
Replace the ModuleWidget (load/unload modules) with a DatasetWidget (search/browse/clone datasets) with proper pagination, search debouncing, and clone progress indicators. The current module-oriented UI doesn't map well to dataset browsing (23K items vs ~200, async clone vs instant load). Backend-only v1 reuses existing widget structure — this covers the proper UI that takes advantage of server-side search and async clone status.
**Depends on:** Backend implementation being stable first.

## Dataset removal with safety checks
Add a 'remove' operation for cloned datasets with confirmation dialog and size display. Users will need to clean up datasets without using the terminal. Deferred from v1 to avoid building destructive operations before the core browse/clone flow is validated.
**Depends on:** Backend v1 + UI redesign.

## Full test suite with mocking
Comprehensive pytest suite with mocked HTTP (registry API) and mocked subprocess (datalad CLI) covering happy paths and error cases. The backend proxies HTTP and runs shell commands — both are failure-prone. User chose smoke tests only for v1.
**Depends on:** Backend API being stable.

## datalad-metalad metadata integration
Integrate datalad-metalad extractors to show rich dataset metadata (BIDS, provenance, etc.) beyond what the registry API provides. The registry only stores basic metadata (URL, size, annex key count). The brainlife fork of datalad-metalad was mentioned as a reference. This would run extractors on cloned datasets to surface richer metadata in the UI.
**Depends on:** Backend v1 + clone functionality working.
