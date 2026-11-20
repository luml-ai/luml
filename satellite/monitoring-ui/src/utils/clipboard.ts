function copyWithSelection(text: string) {
  const previousFocus =
    document.activeElement instanceof HTMLElement ? document.activeElement : null
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.top = '0'
  area.style.left = '0'
  area.style.opacity = '0'
  document.body.appendChild(area)
  try {
    area.focus()
    area.select()
    area.setSelectionRange(0, text.length)
    if (!document.execCommand('copy')) throw new Error('copy command was rejected')
  } finally {
    document.body.removeChild(area)
    previousFocus?.focus()
  }
}

export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      copyWithSelection(text)
      return
    }
  }
  copyWithSelection(text)
}
