import { ref, shallowRef, watch, type Ref } from 'vue'
import { fromCSV } from 'arquero'
import type { AsyncBuffer } from 'hyparquet'
import { getFileExtension } from '../utils/fileTypes'

const PREVIEW_ROWS = 1000

export interface TableData {
  positional?: boolean
  headers: string[]
  rows: Record<string, any>[]
  columnsCount: number
  rowsCount: number
}

interface UseTablePreviewOptions {
  contentBlob: Ref<Blob | null | undefined>
  fileName: Ref<string>
  parquetFile?: Ref<AsyncBuffer | undefined>
  totalRows?: Ref<number | undefined>
  /** The blob is only the start of the file. */
  truncated?: Ref<boolean | undefined>
}

function parseCSV(text: string, limitRows: boolean, truncated: boolean): TableData {
  // A prefix ends inside a row: parse up to its last line break. A line break inside a quoted
  // value (an odd count of quotes before it) still cuts the last row short, so it is dropped.
  const kept = truncated ? text.slice(0, text.lastIndexOf('\n') + 1) : text
  const cutInQuotes = truncated && (kept.match(/"/g)?.length ?? 0) % 2 === 1
  const table = fromCSV(kept)
  const headers = table.columnNames()
  const whole = cutInQuotes ? Math.max(0, table.numRows() - 1) : Infinity
  const rows = table.objects({ limit: Math.min(limitRows ? PREVIEW_ROWS : Infinity, whole) })
  return {
    headers,
    rows,
    columnsCount: headers.length,
    rowsCount: truncated ? -1 : table.totalRows(),
  }
}

function parseXML(text: string): TableData {
  const doc = new DOMParser().parseFromString(text, 'text/xml')
  const elements = doc.querySelectorAll('row, tr, record, item')
  const headers = Array.from(elements[0]?.children ?? [], (el) => el.tagName)
  const rows = Array.from(elements, (row) =>
    Object.fromEntries(
      Array.from(row.children, (el, index) => [headers[index], el.textContent || '']),
    ),
  )
  return { headers, rows, columnsCount: headers.length, rowsCount: rows.length }
}

async function readTable(
  name: string,
  blob: Blob | null | undefined,
  parquetFile: AsyncBuffer | undefined,
  limitRows: boolean,
  truncated: boolean,
): Promise<TableData | null> {
  const ext = getFileExtension(name)
  if (ext === 'parquet') {
    const { readParquet } = await import('../utils/parquetPreview')
    if (parquetFile) return readParquet(parquetFile, PREVIEW_ROWS)
    if (!blob) return null
    return readParquet(
      {
        byteLength: blob.size,
        slice: (start, end) => blob.slice(start, end).arrayBuffer(),
      },
      PREVIEW_ROWS,
    )
  }
  if (!blob) return null
  if (ext === 'arrow') {
    const { readArrow } = await import('../utils/arrowPreview')
    return readArrow(blob, PREVIEW_ROWS, truncated)
  }
  const text = await blob.text()
  return ext === 'xml' ? parseXML(text) : parseCSV(text, limitRows || truncated, truncated)
}

export function useTablePreview(options: UseTablePreviewOptions) {
  const tableData = shallowRef<TableData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  watch(
    [
      options.fileName,
      options.contentBlob,
      () => options.parquetFile?.value,
      () => options.totalRows?.value !== undefined,
      () => options.truncated?.value === true,
    ],
    async ([name, blob, file, limitRows, truncated], _, onCleanup) => {
      let active = true
      onCleanup(() => {
        active = false
      })
      tableData.value = null
      error.value = null
      loading.value = true
      try {
        const data = await readTable(name, blob, file, limitRows, truncated)
        if (active) tableData.value = data
      } catch (e) {
        if (active) error.value = e instanceof Error ? e.message : 'Failed to parse table'
      } finally {
        if (active) loading.value = false
      }
    },
    { immediate: true },
  )

  return { tableData, loading, error }
}
