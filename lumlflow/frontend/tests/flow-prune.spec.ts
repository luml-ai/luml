// @vitest-environment node

import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { build } from 'vite'

const FRONTEND_ROOT = fileURLToPath(new URL('..', import.meta.url))

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('Prune — production bundle has no fixture or concept surfaces', () => {
  it(
    'excludes the design gallery and its fixtures from production chunks',
    async () => {
      vi.stubEnv('NODE_ENV', 'production')
      const built = await build({
        root: FRONTEND_ROOT,
        logLevel: 'silent',
        build: { write: false },
      })
      const results = Array.isArray(built) ? built : [built]
      const modulePaths = results.flatMap((result) => {
        if (!('output' in result)) throw new Error('expected a completed production build')
        return result.output.flatMap((output) =>
          output.type === 'chunk' ? Object.keys(output.modules) : [],
        )
      })

      for (const removedSurface of [
        '/flow/concepts/',
        '/flow/fixtures/',
        '/flow/workbench/gallery/',
        '/flow/workbench/fixtures/',
      ]) {
        expect(modulePaths.some((path) => path.includes(removedSurface))).toBe(false)
      }
    },
    120_000,
  )
})
