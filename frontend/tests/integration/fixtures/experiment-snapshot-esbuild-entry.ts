import { installHarness } from './experiment-snapshot-harness'

installHarness(new Worker('/worker.js', { type: 'module' }))
