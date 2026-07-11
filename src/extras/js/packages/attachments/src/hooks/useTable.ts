import { ref, watch, type Ref } from 'vue'
import { fromCSV } from 'arquero'

export interface TableData {
  headers: string[]
  rows: Record<string, any>[]
  columnsCount: number
  rowsCount: number
}

interface UseTablePreviewOptions {
  contentBlob: Ref<Blob | null>
  fileName: Ref<string>
}

export function useTablePreview(options: UseTablePreviewOptions) {
  const { contentBlob, fileName } = options

  const tableData = ref<TableData | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const parseCSV = (text: string): TableData => {
    try {
      const table = fromCSV(text)
      return {
        headers: table.columnNames(),
        rows: table.objects(),
        columnsCount: table.columnNames().length,
        rowsCount: table.totalRows(),
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to parse CSV content'
      return { headers: [], rows: [], columnsCount: 0, rowsCount: 0 }
    }
  }

  const parseXML = (text: string): TableData => {
    try {
      const parser = new DOMParser()
      const doc = parser.parseFromString(text, 'text/xml')
      const rows = doc.querySelectorAll('row, tr, record, item')
      if (rows.length === 0) {
        return { headers: [], rows: [], columnsCount: 0, rowsCount: 0 }
      }
      const firstRow = rows[0]
      const headers = Array.from(firstRow?.children || []).map((el) => el.tagName)
      const dataRows = Array.from(rows).map((row) =>
        Array.from(row.children).reduce<Record<string, any>>((acc, el, index) => {
          acc[headers[index] as string] = el.textContent || ''
          return acc
        }, {}),
      )

      return {
        headers,
        rows: dataRows,
        columnsCount: headers.length,
        rowsCount: dataRows.length,
      }
    } catch {
      return { headers: [], rows: [], columnsCount: 0, rowsCount: 0 }
    }
  }

  const loadTable = async () => {
    if (!contentBlob.value) {
      tableData.value = null
      return
    }

    loading.value = true
    error.value = null

    try {
      const text = await contentBlob.value.text()
      const ext = fileName.value.split('.').pop()?.toLowerCase()

      if (ext === 'csv') {
        tableData.value = parseCSV(text)
      } else if (ext === 'xml') {
        tableData.value = parseXML(text)
      } else {
        tableData.value = parseCSV(text)
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to parse table'
      tableData.value = null
    } finally {
      loading.value = false
    }
  }

  watch(contentBlob, loadTable, { immediate: true })

  return {
    tableData,
    loading,
    error,
  }
}
