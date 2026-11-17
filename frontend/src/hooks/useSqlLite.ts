import type { SqlJsStatic } from 'sql.js'
import initSqlJs from 'sql.js'
import sqlJsWasmUrl from 'sql.js/dist/sql-wasm.wasm?url'
import { computed, ref } from 'vue'

export const useSqlLite = () => {
  const SQL = ref<SqlJsStatic | null>()

  const getSQL = computed(() => {
    if (!SQL.value) throw new Error('Init SQL before')
    return SQL.value
  })

  async function initSql() {
    SQL.value = await initSqlJs({
      locateFile: () => sqlJsWasmUrl,
    })
  }

  return {
    initSql,
    getSQL,
  }
}
