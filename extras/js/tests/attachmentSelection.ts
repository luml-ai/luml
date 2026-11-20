import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { VueWrapper } from '@vue/test-utils'
import { expect, vi } from 'vitest'

export const pythonSource = 'def train():\n    return 42\n'

export function largeParquet() {
  const bytes = readFileSync(
    resolve(
      import.meta.dirname,
      '../packages/attachments/src/components/preview/__tests__/fixtures/samples.parquet',
    ),
  )
  const size = 400 * 1024 ** 2
  // Insert empty space before the footer without changing any column offsets.
  const dataEnd = bytes.length - 8 - bytes.readUInt32LE(bytes.length - 8)
  const footerStart = size - (bytes.length - dataEnd)
  let transferred = 0
  return {
    size,
    get transferred() {
      return transferred
    },
    slice(start: number, end: number) {
      if (start < 0 || end > size || end < start || end - start >= size)
        throw new Error('Expected a partial read within the selected attachment')
      const chunk = new Uint8Array(end - start)
      if (start < dataEnd) chunk.set(bytes.subarray(start, Math.min(end, dataEnd)))
      if (end > footerStart) {
        const offset = Math.max(start, footerStart)
        chunk.set(
          bytes.subarray(dataEnd + offset - footerStart, dataEnd + end - footerStart),
          offset - start,
        )
      }
      transferred += chunk.length
      return chunk
    },
  }
}

export async function checkAttachmentSelection(
  tab: VueWrapper,
  file: ReturnType<typeof largeParquet>,
) {
  async function select(name: string) {
    await vi.waitFor(() =>
      expect(tab.findAll('.node-name').map((node) => node.text())).toContain(name),
    )
    await tab
      .findAll('.node-name')
      .find((node) => node.text() === name)!
      .trigger('click')
  }
  await select('train.parquet')
  await vi.waitFor(() => expect(tab.text()).toContain('Showing first 1,000 of 1,024 rows'), {
    timeout: 10000,
  })
  expect(tab.findAll('thead th').map((cell) => cell.text())).toEqual(['sample.id', 'score'])
  expect(tab.findAll('tbody tr')).toHaveLength(10)
  expect(tab.get('tbody td').text()).toBe('0')
  await tab.get('[aria-label="Last Page"]').trigger('click')
  expect(tab.get('tbody tr:last-child td').text()).toBe('999')
  expect(file.transferred).toBeGreaterThan(0)
  expect(file.transferred).toBeLessThan(file.size)
  await select('train.py')
  await vi.waitFor(() =>
    expect(tab.findAll('.cm-line span').map((span) => span.text())).toContain('def'),
  )
}
