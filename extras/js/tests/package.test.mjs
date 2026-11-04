import assert from 'node:assert/strict'
import { once } from 'node:events'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import { Worker } from 'node:worker_threads'
import { build, loadConfigFromFile } from 'vite'

const packageJson = JSON.parse(await readFile(resolve('package.json'), 'utf8'))
const externals = { ...packageJson.peerDependencies, ...packageJson.dependencies }

test('package exports prioritize TypeScript declarations', () => {
  assert.equal(Object.keys(packageJson.exports['.'])[0], 'types')
})

if (packageJson.name === '@luml/experiments') {
  test('axios is declared as a runtime dependency', () => {
    assert.ok(packageJson.dependencies?.axios || packageJson.peerDependencies?.axios)
  })
}

for (const format of ['es', 'umd']) {
  test(`library builds externalize every peer, runtime dependency and subpath (${format})`, async () => {
    const { config } = await loadConfigFromFile({ command: 'build', mode: 'production' })
    const peers = Object.keys(externals)
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

test('UMD builds use the browser globals exposed by peer packages', async () => {
  const { config } = await loadConfigFromFile({
    command: 'build',
    mode: 'production',
  })
  const browserGlobals = {
    vue: 'Vue',
    primevue: 'PrimeVue',
    pinia: 'Pinia',
    'lucide-vue-next': 'LucideVueNext',
    arquero: 'aq',
    dompurify: 'DOMPurify',
    marked: 'marked',
    '@vueuse/core': 'VueUse',
    'js-yaml': 'jsyaml',
    jszip: 'JSZip',
    'sql.js': 'initSqlJs',
    uuid: 'uuid',
    'plotly.js-dist': 'Plotly',
    axios: 'axios',
  }
  const peers = Object.keys(browserGlobals).filter((peer) => peer in externals)
  const result = await build({
    configFile: false,
    logLevel: 'silent',
    plugins: [
      {
        name: 'browser-global-fixture',
        resolveId(id) {
          if (id === 'browser-global-entry') return `\0${id}`
        },
        load(id) {
          if (id === '\0browser-global-entry') {
            return peers
              .map((peer, index) => `export { marker as dep${index} } from '${peer}'`)
              .join('\n')
          }
        },
      },
    ],
    build: {
      write: false,
      minify: false,
      rollupOptions: {
        input: 'browser-global-entry',
        preserveEntrySignatures: 'strict',
        external: config.build.rollupOptions.external,
        output: {
          ...config.build.rollupOptions.output,
          format: 'umd',
          name: 'PackageTest',
        },
      },
    },
  })
  const context = Object.fromEntries(peers.map((peer) => [browserGlobals[peer], { marker: peer }]))
  runInNewContext(result.output.find((output) => output.type === 'chunk').code, context)
  for (const [index, peer] of peers.entries())
    assert.equal(context.PackageTest[`dep${index}`], peer)
})

test(
  'peer CSS is extracted so the JavaScript entry can run in a worker',
  { timeout: 10_000 },
  async () => {
    const { config } = await loadConfigFromFile({
      command: 'build',
      mode: 'production',
    })
    const result = await build({
      configFile: false,
      logLevel: 'silent',
      plugins: [
        {
          name: 'worker-style-fixture',
          resolveId(id) {
            if (id === 'worker-style-entry' || id === resolve('worker-style-entry'))
              return '\0worker-style-entry'
          },
          load(id) {
            if (id === '\0worker-style-entry') {
              return 'import "github-markdown-css/github-markdown.css"; export const ready = true'
            }
          },
        },
      ],
      build: {
        write: false,
        lib: {
          entry: 'worker-style-entry',
          formats: ['es'],
          fileName: 'worker-style',
        },
        rollupOptions: { external: config.build.rollupOptions.external },
      },
    })
    const { output } = result[0]
    const entry = output.find((output) => output.type === 'chunk' && output.isEntry)
    assert.ok(
      output.some(
        (output) => output.type === 'asset' && String(output.source).includes('.markdown-body'),
      ),
    )
    assert.deepEqual(entry.imports, [])
    const entryUrl = `data:text/javascript,${encodeURIComponent(entry.code)}`
    const worker = new Worker(
      new URL(
        `data:text/javascript,${encodeURIComponent(`
    import { parentPort } from 'node:worker_threads'
    const { ready } = await import(${JSON.stringify(entryUrl)})
    parentPort.postMessage(ready)
  `)}`,
      ),
    )
    try {
      assert.deepEqual(await once(worker, 'message'), [true])
    } finally {
      await worker.terminate()
    }
  },
)
