// @vitest-environment node
/// <reference types="node" />
import { createServer } from 'node:http'
import { chromium } from '@playwright/test'
import { transformWithEsbuild } from 'vite'
import { expect, it } from 'vitest'
import clientSource from '../previewStream.ts?raw'
import workerSource from '../../../public/attachment-preview-sw.js?raw'

it('serves browser media requests from bounded slices and releases the source', async () => {
  const { code } = await transformWithEsbuild(clientSource, 'previewStream.ts')
  const server = createServer((request, response) => {
    if (request.url === '/worker.js' || request.url === '/client.js') {
      response.setHeader('Content-Type', 'text/javascript')
      response.end(request.url === '/worker.js' ? workerSource : code)
    } else {
      response.setHeader('Content-Type', 'text/html')
      response.end(
        '<!doctype html><script type="module">import * as client from "/client.js"; window.previewClient = client</script>',
      )
    }
  })
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  let browser
  try {
    const address = server.address()
    if (!address || typeof address === 'string') throw new Error('Missing server port')
    browser = await chromium.launch()
    const page = await browser.newPage()
    await page.goto(`http://127.0.0.1:${address.port}`)
    const result = await page.evaluate(async () => {
      const client = Reflect.get(window, 'previewClient') as typeof import('../previewStream')
      const requests: number[][] = []
      const size = 1024 * 1024 + 50
      const url = await client.createPreviewStreamUrl(
        'sample.mp4',
        {
          byteLength: size,
          async slice(start, end = size) {
            requests.push([start, end])
            return new Uint8Array(end - start).fill(start % 256).buffer
          },
        },
        '/worker.js',
      )
      const head = await fetch(url, { method: 'HEAD' })
      const full = await fetch(url)
      const fullLength = (await full.arrayBuffer()).byteLength
      const tail = await fetch(url, { headers: { Range: 'bytes=-3' } })
      const tailBytes = Array.from(new Uint8Array(await tail.arrayBuffer()))
      const invalid = await fetch(url, { headers: { Range: `bytes=${size}-` } })
      client.releasePreviewStreamUrl(url)
      const closed = await fetch(url)
      return {
        requests,
        fullLength,
        size: head.headers.get('content-length'),
        mime: head.headers.get('content-type'),
        tailStatus: tail.status,
        tailRange: tail.headers.get('content-range'),
        tailBytes,
        invalid: invalid.status,
        closed: closed.status,
      }
    })
    expect(result).toEqual({
      requests: [
        [0, 1048576],
        [1048576, 1048626],
        [1048623, 1048626],
      ],
      fullLength: 1048626,
      size: '1048626',
      mime: 'video/mp4',
      tailStatus: 206,
      tailRange: 'bytes 1048623-1048625/1048626',
      tailBytes: [47, 47, 47],
      invalid: 416,
      closed: 410,
    })
  } finally {
    await browser?.close()
    await new Promise<void>((resolve) => server.close(() => resolve()))
  }
}, 20_000)
