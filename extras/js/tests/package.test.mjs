import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { build, loadConfigFromFile } from 'vite'

const packageJson = JSON.parse(await readFile(resolve('package.json'), 'utf8'))

test('package exports prioritize TypeScript declarations', () => {
  assert.equal(Object.keys(packageJson.exports['.'])[0], 'types')
})

if (packageJson.name === '@luml/experiments') {
  test('axios is declared as a runtime dependency', () => {
    assert.ok(packageJson.dependencies?.axios || packageJson.peerDependencies?.axios)
  })
}

for (const format of ['es', 'umd']) {
  test(`library builds externalize every peer and peer subpath (${format})`, async () => {
    const { config } = await loadConfigFromFile({ command: 'build', mode: 'production' })
    const peers = Object.keys(packageJson.peerDependencies)
    const requests = peers.flatMap((peer) => [peer, `${peer}/packaging-test`])
    const unrelated = `${peers[0]}-unrelated`
    const result = await build({
      configFile: false,
      logLevel: 'silent',
      plugins: [
        {
          name: 'package-test-fixture',
          enforce: 'pre',
          resolveId(id) {
            if (id === 'package-test-entry' || requests.includes(id) || id === unrelated) {
              return `\0${id}`
            }
          },
          load(id) {
            if (id === '\0package-test-entry') {
              return [...requests, unrelated]
                .map(
                  (request, index) =>
                    `import * as dep${index} from '${request}'; console.log(dep${index});`,
                )
                .join('\n')
            }
            if (id.startsWith('\0')) return 'export const marker = "bundled non-peer"'
          },
        },
      ],
      build: {
        write: false,
        minify: false,
        rollupOptions: {
          input: 'package-test-entry',
          external: config.build.rollupOptions.external,
          output: { format, name: 'PackageTest' },
        },
      },
    })
    const chunk = result.output.find((output) => output.type === 'chunk' && output.isEntry)
    assert.deepEqual(chunk.imports.toSorted(), requests.toSorted())
    assert.ok(chunk.code.includes('bundled non-peer'))
  })
}
