import * as arrow from 'apache-arrow'
import initParquet, { readParquet } from 'parquet-wasm'

export interface PreviewResult {
  columns: string[]
  rows: Record<string, unknown>[]
}

export class ParquetHandler {
  constructor(private buffer: ArrayBuffer) {}

  async init() {
    await initParquet(new URL('/parquet_wasm_bg.wasm', import.meta.url).toString())
  }

  async read() {
    const uint8 = new Uint8Array(this.buffer)
    const arrowWasmTable = readParquet(uint8)
    const table = arrow.tableFromIPC(arrowWasmTable.intoIPCStream())
    const proxyArray = table.toArray()
    const data = proxyArray.map((item) => ({ ...item }))
    return data
  }
}
