// UIP-002, product:PROP-004 B-12: syntax highlighting in the preview. Design-only: a few regular
// expressions per language that wrap tokens in <span class="hl-…">, enough to show the look. The
// app picks a real highlighter (PROP-004 TQ-8); don't port this.

export type Language = 'python' | 'yaml' | 'json' | 'plain'

export function languageOf(fileName: string): Language {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'py') return 'python'
  if (ext === 'yaml' || ext === 'yml') return 'yaml'
  if (ext === 'json') return 'json'
  return 'plain'
}

const PYTHON_KEYWORDS =
  'import|from|as|def|class|return|if|elif|else|for|in|while|with|try|except|finally|raise|pass|break|continue|lambda|yield|not|and|or|is|None|True|False'

// Alternatives in priority order; each capture group is one token kind.
const RULES: Record<Exclude<Language, 'plain'>, { pattern: RegExp; kinds: string[] }> = {
  python: {
    pattern: new RegExp(
      `(#.*$)|("(?:[^"\\\\]|\\\\.)*"|'(?:[^'\\\\]|\\\\.)*')|\\b(${PYTHON_KEYWORDS})\\b|\\b(\\d+(?:\\.\\d+)?)\\b`,
      'gm',
    ),
    kinds: ['comment', 'string', 'keyword', 'number'],
  },
  yaml: {
    pattern: /(#.*$)|(^\s*-?\s*[\w.-]+)(?=\s*:)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(true|false|null|yes|no)\b|\b(\d+(?:\.\d+)?)\b/gm,
    kinds: ['comment', 'key', 'string', 'keyword', 'number'],
  },
  json: {
    pattern: /("(?:[^"\\]|\\.)*")(?=\s*:)|("(?:[^"\\]|\\.)*")|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    kinds: ['key', 'string', 'keyword', 'number'],
  },
}

function escape(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** The text as HTML with highlight spans; plain text is only escaped. */
export function highlight(text: string, language: Language): string {
  if (language === 'plain') return escape(text)
  const { pattern, kinds } = RULES[language]
  let out = ''
  let last = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0
    out += escape(text.slice(last, index))
    const kind = kinds.find((_, i) => match[i + 1] !== undefined) ?? 'plain'
    out += `<span class="hl-${kind}">${escape(match[0])}</span>`
    last = index + match[0].length
  }
  return out + escape(text.slice(last))
}
