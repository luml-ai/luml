import { Blob as NodeBlob } from 'node:buffer'
import { Table, tableFromArrays, tableToIPC } from 'apache-arrow'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readArrow } from '../arrowPreview'
import { leadingDoctypeEnd, processHtmlContent } from '../fileContentProcessors'
import { urlPreviewBytes } from '../previewBytes'

beforeEach(() => vi.stubGlobal('Blob', NodeBlob))
afterEach(() => vi.unstubAllGlobals())

describe('processHtmlContent', () => {
  async function previewed(html: string) {
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:preview') })
    await processHtmlContent(new Blob([html]))
    const [blob] = vi.mocked(URL.createObjectURL).mock.calls[0]! as [Blob]
    // Keep a byte order mark in view: `Blob.text()` drops it.
    return new TextDecoder('utf-8', { ignoreBOM: true }).decode(await blob.arrayBuffer())
  }

  it('keeps a leading doctype first, so the report renders in standards mode', async () => {
    const html = '﻿<!-- report -->\n<!DOCTYPE html><html><body><img src="x"></body></html>'
    const text = await previewed(html)
    expect(text).toMatch(
      /^﻿<!-- report -->\n<!DOCTYPE html><meta http-equiv="Content-Security-Policy" [^>]+><html>/,
    )
  })

  it('puts the policy first in a document without a doctype', async () => {
    const text = await previewed('<img src="https://example.com/x.png">')
    expect(text).toMatch(/^<meta http-equiv="Content-Security-Policy" [^>]+><img /)
  })
})

describe('leadingDoctypeEnd', () => {
  it('scans many leading comments without a doctype in linear time', () => {
    // Each further comment used to double the work of the old pattern.
    const html = '<!-- note -->\n'.repeat(40) + '<html><body>x</body></html>'
    const start = performance.now()
    expect(leadingDoctypeEnd(html)).toBe(0)
    expect(leadingDoctypeEnd('<!-- note -->'.repeat(5000) + '<p>')).toBe(0)
    expect(performance.now() - start).toBeLessThan(50)
  })

  it('ends after a doctype that follows comments', () => {
    const prefix = '<!-- note -->\n'.repeat(40)
    const html = prefix + '<!DOCTYPE html><html></html>'
    expect(leadingDoctypeEnd(html)).toBe(prefix.length + '<!DOCTYPE html>'.length)
  })

  it('finds no doctype after an unclosed comment', () => {
    expect(leadingDoctypeEnd('<!-- open <!DOCTYPE html><html></html>')).toBe(0)
  })

  it('skips a whole byte order mark, read as Latin-1 bytes', () => {
    expect(leadingDoctypeEnd('\xef\xbb\xbf <!doctype html>')).toBe(3 + 1 + 15)
    expect(leadingDoctypeEnd('\xef\xbb<!doctype html>')).toBe(0)
  })

  it('needs the doctype to come before any content', () => {
    expect(leadingDoctypeEnd('<p>x</p><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd(' \t\r\n\f<!DocType html>rest')).toBe(5 + 15)
  })

  it('finds no doctype after a comment the browser ends sooner than at `-->`', () => {
    expect(leadingDoctypeEnd('<!-->x--><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!--->x--><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!-- a --!> x --> <!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!----!> x --> <!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!-- a <!--!> x --> <!doctype html>')).toBe(0)
  })

  it('ends a comment where the browser does for every other run of dashes', () => {
    for (const comment of ['<!---->', '<!----->', '<!---x-->', '<!--!>-->', '<!-- --!-->']) {
      expect(leadingDoctypeEnd(comment + '<!doctype html>')).toBe(comment.length + 15)
    }
  })

  it('counts white space the HTML parser keeps as text as content', () => {
    expect(leadingDoctypeEnd('\x0b<!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('\xa0<!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('\x00<!doctype html>')).toBe(0)
  })

  it('finds no doctype after a bogus comment', () => {
    expect(leadingDoctypeEnd('<!x><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<?xml version="1.0"?><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!- x -><!doctype html>')).toBe(0)
  })

  it('ends the doctype at its first `>`, as the browser does even within quotes', () => {
    expect(leadingDoctypeEnd('<!doctype html "a>b">')).toBe(18)
  })

  it('gives 0 for control characters that could change how the bytes decode', () => {
    // In ISO-2022-JP, the escape turns the `-->` that follows into two-byte text.
    expect(leadingDoctypeEnd('<!-- \x1b$B --> <!doctype \x1b(B html>')).toBe(0)
    expect(leadingDoctypeEnd('<!-- \x00 --><!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('<!-- \xa9 2024 --><!doctype html>')).toBe(15 + 15)
  })

  it('reads a UTF-16 byte order mark as content', () => {
    expect(leadingDoctypeEnd('\xff\xfe<!doctype html>')).toBe(0)
    expect(leadingDoctypeEnd('\xfe\xff<!doctype html>')).toBe(0)
  })
})

describe('urlPreviewBytes', () => {
  function rangeResponse(bytes: Uint8Array, range: string) {
    const [, start, end] = /bytes=(\d+)-(\d+)/.exec(range)!.map(Number)
    return new Response(bytes.slice(start!, end! + 1), {
      status: 206,
      headers: { 'Content-Range': `bytes ${start}-${end}/${bytes.length}` },
    })
  }

  it('renews an expired signed URL once and keeps reading with the new one', async () => {
    const bytes = new Uint8Array([1, 2, 3, 4])
    const urls = ['/file?ticket=1', '/file?ticket=2']
    const renew = vi.fn(async () => urls.shift()!)
    const fetch = vi.fn(async (url: string, options: RequestInit) =>
      url.endsWith('ticket=1')
        ? new Response(null, { status: 401 })
        : rangeResponse(bytes, new Headers(options.headers).get('Range')!),
    )
    vi.stubGlobal('fetch', fetch)

    const file = await urlPreviewBytes(renew, bytes.length)
    expect(new Uint8Array(await file.slice(1, 3))).toEqual(new Uint8Array([2, 3]))
    expect(new Uint8Array(await file.slice(0, 1))).toEqual(new Uint8Array([1]))
    expect(renew).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      '/file?ticket=1',
      '/file?ticket=2',
      '/file?ticket=2',
    ])
  })
})

describe('readArrow of a prefix', () => {
  // As PyArrow writes an IPC file: magic and padding, then the stream with its schema first.
  function arrowFile(batchRows: number[]) {
    const batches = batchRows.map(
      (rows, batch) =>
        tableFromArrays({ id: Int32Array.from({ length: rows }, (_, i) => batch * 1000 + i) })
          .batches[0]!,
    )
    const stream = tableToIPC(new Table(batches), 'stream')
    return new Uint8Array([...new TextEncoder().encode('ARROW1\0\0'), ...stream])
  }

  it('shows the whole record batches before the point the prefix was cut', async () => {
    const bytes = arrowFile([100, 100, 100])
    // Within the last batch: the end of the third batch and the footer are gone.
    const prefix = new Blob([bytes.slice(0, bytes.length - 300)])

    const table = await readArrow(prefix, 1000, true)

    expect(table.rows).toHaveLength(200)
    expect(table.rows[table.rows.length - 1]).toEqual([1099])
    expect(table.rowsCount).toBe(-1)
  })

  it('stops at the row limit', async () => {
    const table = await readArrow(new Blob([arrowFile([600, 600, 600])]), 1000, true)
    expect(table.rows).toHaveLength(1000)
  })

  it('says so when not even the first batch fits in the prefix', async () => {
    const bytes = arrowFile([5000])
    await expect(readArrow(new Blob([bytes.slice(0, 400)]), 1000, true)).rejects.toThrow(
      'The first record batch of this file is larger than the 400 B read for preview, so no rows can be shown.',
    )
  })

  it('reports a schema it cannot read as it is, not as a batch too large', async () => {
    const error = await readArrow(new Blob(['not an arrow file']), 1000, true).catch((e) => e)
    expect(error).toBeInstanceOf(Error)
    expect(error.message).not.toMatch(/first record batch/)
  })
})
