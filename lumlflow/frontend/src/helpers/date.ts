export const durationToText = (duration: number) => {
  if (duration < 1000) return `${duration}ms`
  if (duration < 1000000) return `${duration / 1000}s`
  if (duration < 60000) return `${duration / 1000000}m`
  if (duration < 3600000) return `${duration / 3600000}h`
  return `${duration / 86400000}d`
}

export const dateToText = (dataString: string) => {
  const date = new Date(dataString)
  const pad = (n: number) => String(n).padStart(2, '0')

  return (
    date.getFullYear() +
    '/' +
    pad(date.getMonth() + 1) +
    '/' +
    pad(date.getDate()) +
    ' ' +
    pad(date.getHours()) +
    ':' +
    pad(date.getMinutes()) +
    ':' +
    pad(date.getSeconds())
  )
}

export const formatUpdatedAgo = (ts: string | null) => {
  if (!ts) return ''
  const elapsedMinutes = Math.floor((Date.now() - new Date(ts).getTime()) / 60_000)
  if (elapsedMinutes < 1) return 'just now'
  if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`
  const elapsedHours = Math.floor(elapsedMinutes / 60)
  if (elapsedHours < 24) return `${elapsedHours}h ago`
  return `${Math.floor(elapsedHours / 24)}d ago`
}
