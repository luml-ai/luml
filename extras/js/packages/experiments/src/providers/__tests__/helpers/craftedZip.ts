export interface CraftedZipEntry {
  name: string
  size: number
  /** Writes the ZIP64 marker into the size fields and this size into a ZIP64 extra block. */
  zip64Size?: number
}

/**
 * A zip of local headers without data and a directory that claims the given sizes; `padding`
 * zero bytes stand in for the entry data before the directory.
 */
export function craftedZip(entries: CraftedZipEntry[], comment = '', padding = 0): Uint8Array {
  const encoder = new TextEncoder()
  const locals: Uint8Array[] = []
  const directory: Uint8Array[] = []
  let offset = 0
  for (const { name, size, zip64Size } of entries) {
    const nameBytes = encoder.encode(name)
    const local = new Uint8Array(30 + nameBytes.length)
    const localView = new DataView(local.buffer)
    localView.setUint32(0, 0x04034b50, true)
    localView.setUint32(18, size, true)
    localView.setUint32(22, size, true)
    localView.setUint16(26, nameBytes.length, true)
    local.set(nameBytes, 30)
    const extraLength = zip64Size === undefined ? 0 : 20
    const central = new Uint8Array(46 + nameBytes.length + extraLength)
    const centralView = new DataView(central.buffer)
    const fieldSize = zip64Size === undefined ? size : 0xffffffff
    centralView.setUint32(0, 0x02014b50, true)
    centralView.setUint32(20, fieldSize, true)
    centralView.setUint32(24, fieldSize, true)
    centralView.setUint16(28, nameBytes.length, true)
    centralView.setUint16(30, extraLength, true)
    centralView.setUint32(42, offset, true)
    central.set(nameBytes, 46)
    if (zip64Size !== undefined) {
      const extra = 46 + nameBytes.length
      centralView.setUint16(extra, 0x0001, true)
      centralView.setUint16(extra + 2, 16, true)
      centralView.setBigUint64(extra + 4, BigInt(zip64Size), true)
      centralView.setBigUint64(extra + 12, BigInt(zip64Size), true)
    }
    locals.push(local)
    directory.push(central)
    offset += local.length
  }
  const commentBytes = encoder.encode(comment)
  const directorySize = directory.reduce((sum, part) => sum + part.length, 0)
  const end = new Uint8Array(22 + commentBytes.length)
  const endView = new DataView(end.buffer)
  endView.setUint32(0, 0x06054b50, true)
  endView.setUint16(8, entries.length, true)
  endView.setUint16(10, entries.length, true)
  endView.setUint32(12, directorySize, true)
  endView.setUint32(16, offset + padding, true)
  endView.setUint16(20, commentBytes.length, true)
  end.set(commentBytes, 22)
  const parts = [...locals, new Uint8Array(padding), ...directory, end]
  const zip = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0))
  let at = 0
  for (const part of parts) {
    zip.set(part, at)
    at += part.length
  }
  return zip
}
