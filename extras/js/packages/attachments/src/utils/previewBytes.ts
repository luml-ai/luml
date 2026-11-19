// A range request must never fall back to buffering an entire large file.
export async function urlPreviewBytes(url: string, size?: number, options?: RequestInit) {
  const headers = new Headers(options?.headers)
  if (size === undefined) {
    headers.set('Range', 'bytes=0-0')
    const response = await fetch(url, { ...options, headers })
    await response.body?.cancel()
    if (response.status === 416 && response.headers.get('Content-Range') === 'bytes */0') size = 0
    else {
      const match = /^bytes 0-0\/(\d+)$/i.exec(response.headers.get('Content-Range') ?? '')
      if (response.status !== 206 || !match) throw new Error('Could not determine the file size')
      size = Number(match[1])
    }
  }
  const byteLength = size
  if (!Number.isSafeInteger(byteLength) || byteLength < 0) throw new Error('Invalid file size')
  return {
    byteLength,
    async slice(start: number, end = byteLength) {
      if (
        !Number.isSafeInteger(start) ||
        !Number.isSafeInteger(end) ||
        start < 0 ||
        start > end ||
        end > byteLength
      )
        throw new RangeError('Invalid file range')
      if (start === end) return new ArrayBuffer(0)
      const requestHeaders = new Headers(headers)
      requestHeaders.set('Range', `bytes=${start}-${end - 1}`)
      const response = await fetch(url, { ...options, headers: requestHeaders })
      const range = response.headers.get('Content-Range')
      if (
        response.status !== 206 ||
        (range && range !== `bytes ${start}-${end - 1}/${byteLength}`)
      ) {
        await response.body?.cancel()
        throw new Error('Could not read the requested file range')
      }
      const bytes = await response.arrayBuffer()
      if (bytes.byteLength !== end - start) throw new Error('Incomplete file range')
      return bytes
    },
  }
}
