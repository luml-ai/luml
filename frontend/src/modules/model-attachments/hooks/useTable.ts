import { ref, watch, type Ref } from 'vue'

export interface TableData {
  headers: string[]
  rows: string[][]
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
    const lines = text.trim().split('\n')
    if (lines.length === 0) {
      return { headers: [], rows: [], columnsCount: 0, rowsCount: 0 }
    }

    const parseRow = (line: string, lineNumber: number): string[] => {
      const result: string[] = []
      let current = ''
      let inQuotes = false

      for (let i = 0; i < line.length; i++) {
        const char = line[i]

        if (char === '"') {
          if (inQuotes && line[i + 1] === '"') {
            current += '"'
            i++
          } else {
            inQuotes = !inQuotes
          }
        } else if (char === ',' && !inQuotes) {
          result.push(current.trim())
          current = ''
        } else {
          current += char
        }
      }
      if (inQuotes) {
        throw new Error(`Malformed CSV: unclosed quote on line ${lineNumber}`)
      }

      result.push(current.trim())

      return result
    }

    try {
      const headers = parseRow(lines[0], 1)
      const rows: string[][] = []

      for (let i = 1; i < lines.length; i++) {
        if (lines[i].trim()) {
          rows.push(parseRow(lines[i], i + 1))
        }
      }

      return {
        headers,
        rows,
        columnsCount: headers.length,
        rowsCount: rows.length,
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
      const headers = Array.from(firstRow.children).map((el) => el.tagName)
      const dataRows = Array.from(rows).map((row) =>
        Array.from(row.children).map((el) => el.textContent || ''),
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
