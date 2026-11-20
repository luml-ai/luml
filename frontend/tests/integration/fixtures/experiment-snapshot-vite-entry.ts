// Built by Vite with the frontend config, so the worker is bundled exactly as the app bundles it.
import { installHarness } from './experiment-snapshot-harness'

installHarness(
  new Worker(new URL('../../../../extras/js/experimentSnapshotWorker.ts', import.meta.url), {
    type: 'module',
  }),
)
