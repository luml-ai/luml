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
