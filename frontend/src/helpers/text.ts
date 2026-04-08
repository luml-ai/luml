export const getShortcutCountText = (count: number) => {
  if (count < 1000) return `${count}`
  if (count < 1000000) return `${(count / 1000).toFixed()}k`
  return `${(count / 1000000).toFixed()}m`
}
