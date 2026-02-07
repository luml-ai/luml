export const durationToText = (duration: number) => {
  if (duration < 1000) return `${duration}ms`
  if (duration < 1000000) return `${duration / 1000}s`
  if (duration < 60000) return `${duration / 1000000}m`
  if (duration < 3600000) return `${duration / 3600000}h`
  return `${duration / 86400000}d`
}
