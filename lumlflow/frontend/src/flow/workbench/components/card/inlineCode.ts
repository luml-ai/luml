/** Render backtick spans as <code> without a markdown pass; escapes first. */
export function inlineCodeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono text-sm">$1</code>')
}
