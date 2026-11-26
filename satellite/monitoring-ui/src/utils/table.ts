export function getTableMinWidth(widths: Record<string, number>): number {
  return Object.values(widths).reduce((sum, width) => sum + width, 0)
}

export function getColumnStyle(width: number) {
  return { width: `${width}px` }
}
