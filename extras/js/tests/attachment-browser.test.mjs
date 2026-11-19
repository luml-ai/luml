import assert from 'node:assert/strict'
import { once } from 'node:events'
import { readFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { resolve } from 'node:path'
import { after, before, test } from 'node:test'
import { chromium } from '@playwright/test'
import { build } from 'esbuild'

const fixtures = resolve('src/components/preview/__tests__/fixtures')
const videoSize = 300 * 1024 ** 2
const ranges = []
let externalRequests = 0
let browser, server, origin

before(async () => {
  // Load the actual peer implementations under their UMD global names.
  const peers = {
    Vue: 'vue',
    PrimeVue: 'primevue',
    LucideVueNext: 'lucide-vue-next',
    aq: 'arquero',
    Arrow: 'apache-arrow',
    jsyaml: 'js-yaml',
    marked: 'marked',
    jsoncParser: 'jsonc-parser',
    state: '@codemirror/state',
    view: '@codemirror/view',
    language: '@codemirror/language',
    highlight: '@lezer/highlight',
  }
  for (const lang of [
    'css',
    'html',
    'javascript',
    'json',
    'markdown',
    'python',
    'sql',
    'xml',
    'yaml',
  ]) {
    peers['lang' + lang[0].toUpperCase() + lang.slice(1)] = '@codemirror/lang-' + lang
  }
  const host = await build({
    stdin: {
      resolveDir: process.cwd(),
      contents: [
        ...Object.entries(peers).map(([name, id]) => `import * as ${name} from '${id}'`),
        "import DOMPurify from 'dompurify'",
        "import config from 'primevue/config'",
        `Object.assign(window, { DOMPurify, ${Object.keys(peers).join(',')} })`,
        `window.preview = props => Vue.createApp(window['luml-attachments'].FilePreview, props).use(config, {unstyled:true}).mount('#app')`,
      ].join('\n'),
    },
    bundle: true,
    format: 'iife',
    write: false,
    minify: true,
    define: { 'process.env.NODE_ENV': '"production"' },
  })
  const scripts = new Map([['/host.js', host.outputFiles[0].contents]])
  scripts.set('/luml-attachments.umd.js', await readFile('dist/luml-attachments.umd.js'))
  scripts.set('/worker.js', await readFile('public/attachment-preview-sw.js'))
  // These two MP4 extents contain the index and real VP9/Opus chunks on
  // either side of an unused region of mdat. Seeking crosses that region.
  const prefix = await readFile(resolve(fixtures, 'video-prefix.bin'))
  const suffix = await readFile(resolve(fixtures, 'video-suffix.bin'))
  server = createServer((req, res) => {
    if (req.url === '/external-media.wav') {
      externalRequests++
      res.writeHead(404).end()
    } else if (scripts.has(req.url)) {
      res.writeHead(200, { 'Content-Type': 'text/javascript' }).end(scripts.get(req.url))
    } else if (req.url === '/movie') {
      const range = /^bytes=(\d+)-(\d+)$/.exec(req.headers.range ?? '')
      if (!range) return res.writeHead(400).end()
      const start = Number(range[1]),
        end = Number(range[2]) + 1
      if (end > videoSize || start >= end) return res.writeHead(416).end()
      const data = Buffer.alloc(end - start)
      if (start < prefix.length) prefix.copy(data, 0, start, Math.min(end, prefix.length))
      const tail = videoSize - suffix.length
      if (end > tail)
        suffix.copy(data, Math.max(0, tail - start), Math.max(0, start - tail), end - tail)
      ranges.push({ start, bytes: data.length })
      res
        .writeHead(206, {
          'Content-Range': `bytes ${start}-${end - 1}/${videoSize}`,
        })
        .end(data)
    } else {
      res
        .writeHead(200, { 'Content-Type': 'text/html' })
        .end(
          '<div id="app"></div><script src="/host.js"></script><script src="/luml-attachments.umd.js"></script>',
        )
    }
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  origin = 'http://127.0.0.1:' + server.address().port
  browser = await chromium.launch()
})

after(async () => {
  await browser?.close()
  if (server) await new Promise((resolve) => server.close(resolve))
})

for (const extension of ['arrow', 'parquet']) {
  test(`the browser-global script opens the ${extension} table`, async () => {
    const page = await browser.newPage()
    try {
      await page.goto(origin)
      const fileName = 'samples.' + extension
      const bytes = await readFile(resolve(fixtures, fileName))
      await page.evaluate(
        ({ fileName, bytes }) => {
          window.preview({
            fileName,
            source: new Blob([new Uint8Array(bytes)]),
          })
        },
        { fileName, bytes: [...bytes] },
      )
      await page.getByText('Showing first 1,000 of 1,024 rows').waitFor()
      assert.equal(await page.locator('tbody tr').count(), 10)
    } finally {
      await page.close()
    }
  })
}

test(
  'a 300 MiB video plays and seeks across the file with partial transfers',
  { timeout: 30000 },
  async (testContext) => {
    const page = await browser.newPage()
    try {
      await page.goto(origin)
      await page.evaluate(async (size) => {
        const preview = window['luml-attachments']
        const source = await preview.createPreviewStreamUrl(
          'run.mp4',
          {
            byteLength: size,
            async slice(start, end) {
              const response = await fetch('/movie', {
                headers: { Range: `bytes=${start}-${end - 1}` },
              })
              if (response.status !== 206) throw new Error('Expected partial video data')
              return response.arrayBuffer()
            },
          },
          '/worker.js',
        )
        window.preview({ fileName: 'run.mp4', fileSize: size, source })
        const video = document.querySelector('video')
        video.muted = true
        await video.play()
      }, videoSize)
      await page.waitForFunction(() => document.querySelector('video').currentTime > 0.2)
      await page.locator('video').evaluate(
        (video) =>
          new Promise((resolve) => {
            video.addEventListener('seeked', () => resolve(), { once: true })
            video.currentTime = 6
          }),
      )
      await page.waitForFunction(() => document.querySelector('video').currentTime > 6.2)
      assert.ok(ranges.some((range) => range.start > videoSize / 2))
      const bytes = ranges.reduce((sum, range) => sum + range.bytes, 0)
      testContext.diagnostic(`Transferred ${bytes} of ${videoSize} bytes`)
      assert.ok(bytes < videoSize / 4, `Transferred ${bytes} of ${videoSize} bytes`)
    } finally {
      await page.close()
    }
  },
)

test('sandboxed HTML plays embedded audio while suppressing remote media', async () => {
  const page = await browser.newPage()
  try {
    await page.goto(origin)
    await page.evaluate(() => {
      // One second of unsigned 8-bit PCM silence.
      const header = atob('UklGRmQfAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YUAfAAA=')
      const wav = btoa(header + String.fromCharCode(128).repeat(8000))
      const html = `<audio id="local" controls preload="auto" src="data:audio/wav;base64,${wav}"></audio><audio preload="auto" src="${location.origin}/external-media.wav"></audio>`
      window.preview({ fileName: 'report.html', source: new Blob([html]) })
    })
    const audio = page.frameLocator('iframe').locator('#local')
    await audio.evaluate(async (audio) => {
      audio.muted = true
      await audio.play()
    })
    assert.ok(await audio.evaluate((audio) => audio.duration > 0))
    assert.equal(externalRequests, 0)
  } finally {
    await page.close()
  }
})
