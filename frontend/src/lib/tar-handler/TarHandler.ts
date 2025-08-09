export class TarHandler {
  private view: DataView

  constructor(private buffer: ArrayBuffer) {
    this.view = new DataView(buffer)
  }

  private align512(size: number): number {
    const r = size % 512
    return r ? size + (512 - r) : size
  }

  private readAscii(offset: number, len: number): string {
    const bytes = new Uint8Array(this.buffer, offset, len)
    const nul = bytes.indexOf(0)
    const end = nul === -1 ? len : nul
    return new TextDecoder('ascii').decode(bytes.slice(0, end))
  }

  private readOctal(offset: number, len: number): number {
    const raw = new TextDecoder('ascii').decode(new Uint8Array(this.buffer, offset, len))
    const trimmed = raw.replace(/\0/g, '').trim()
    return trimmed ? parseInt(trimmed, 8) : 0
  }

  scan(): Map<string, [number, number]> {
    const results = new Map<string, [number, number]>()
    let off = 0

    let pendingPaxPath: string | null = null
    let pendingLongName: string | null = null

    const isZeroBlock = (o: number) => {
      for (let i = 0; i < 512; i++) if (this.view.getUint8(o + i) !== 0) return false
      return true
    }

    while (off + 512 <= this.buffer.byteLength) {
      if (isZeroBlock(off)) {
        const maybeSecond = off + 512
        if (maybeSecond + 512 <= this.buffer.byteLength && isZeroBlock(maybeSecond)) break
        break
      }

      const name = this.readAscii(off + 0, 100)
      const size = this.readOctal(off + 124, 12)
      const typeflag = this.view.getUint8(off + 156)
      const prefix = this.readAscii(off + 345, 155)

      const headerStart = off
      const dataStart = off + 512
      const dataSpan = this.align512(size)

      if (typeflag === 0x78) {
        const view = new Uint8Array(this.buffer, dataStart, size)
        let i = 0
        while (i < view.length) {
          const recStartDigits = i
          let lenStr = ''
          while (i < view.length && view[i] !== 0x20) lenStr += String.fromCharCode(view[i++])
          if (i >= view.length) break
          const recLen = parseInt(lenStr, 10)
          i++
          const recTotalEnd = recStartDigits + recLen
          const recContentEnd = recTotalEnd - 1
          if (recTotalEnd > view.length || recContentEnd < i) break
          const line = new TextDecoder('utf-8').decode(view.slice(i, recContentEnd))
          const eq = line.indexOf('=')
          if (eq !== -1) {
            const key = line.slice(0, eq)
            const val = line.slice(eq + 1)
            if (key === 'path') pendingPaxPath = val
          }
          i = recTotalEnd
        }
        off = dataStart + dataSpan
        continue
      }

      if (typeflag === 0x67) {
        off = dataStart + dataSpan
        continue
      }

      if (typeflag === 0x4c) {
        const bytes = new Uint8Array(this.buffer, dataStart, size)
        const nul = bytes.indexOf(0)
        pendingLongName = new TextDecoder('utf-8').decode(
          bytes.slice(0, nul === -1 ? bytes.length : nul),
        )
        off = dataStart + dataSpan
        continue
      }

      let fullPath: string
      if (pendingPaxPath) {
        fullPath = pendingPaxPath
        pendingPaxPath = null
      } else if (pendingLongName) {
        fullPath = pendingLongName
        pendingLongName = null
      } else if (prefix) {
        fullPath = `${prefix}/${name}`
      } else {
        fullPath = name
      }

      const isRegular = typeflag === 0x30 || typeflag === 0x00
      if (isRegular) results.set(fullPath, [dataStart, size])

      off = dataStart + dataSpan
    }

    return results
  }
}
