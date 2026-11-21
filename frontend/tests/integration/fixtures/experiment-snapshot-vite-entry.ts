// Built by Vite with the frontend config, so the worker is bundled exactly as the app bundles it.
import { installHarness } from './experiment-snapshot-harness'

installHarness(
  new Worker(new URL('@/workers/experiment-snapshot', import.meta.url), { type: 'module' }),
)
