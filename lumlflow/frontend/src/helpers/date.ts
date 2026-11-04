/**
 * A run's duration for people. The tracker stores it in seconds (luml-sdk:
 * `(julianday('now') - julianday(created_at)) * 86400`).
 */
export const durationToText = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds < 0) return '-'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${Number(seconds.toFixed(1))}s`
  const whole = Math.round(seconds)
  const days = Math.floor(whole / 86400)
  const hours = Math.floor((whole % 86400) / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  const rest = whole % 60
  if (days) return hours ? `${days}d ${hours}h` : `${days}d`
  if (hours) return minutes ? `${hours}h ${minutes}m` : `${hours}h`
  return rest ? `${minutes}m ${rest}s` : `${minutes}m`
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
