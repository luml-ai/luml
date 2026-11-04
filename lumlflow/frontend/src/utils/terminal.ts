export const TERMINAL_TEXT_LIMIT = 256 * 1024

type AnsiState = 'text' | 'escape' | 'csi' | 'osc' | 'osc-escape'

export class TerminalBuffer {
  private finished = ''
  private line = ''
  private carriageReturn = false
  private ansi: AnsiState = 'text'

  constructor(private readonly limit: number = TERMINAL_TEXT_LIMIT) {}

  append(source: string): string {
    for (const character of source) {
      if (this.consumeAnsi(character)) continue
      if (character === '\r') {
        this.carriageReturn = true
      } else if (character === '\n') {
        this.carriageReturn = false
        this.finished += `${this.line}\n`
        this.line = ''
      } else {
        if (this.carriageReturn) this.line = ''
        this.carriageReturn = false
        this.line += character
      }
    }
    this.trim()
    return this.text
  }

  reset(): void {
    this.finished = ''
    this.line = ''
    this.carriageReturn = false
    this.ansi = 'text'
  }

  get text(): string {
    return this.finished + this.line
  }

  private consumeAnsi(character: string): boolean {
    if (this.ansi === 'text') {
      if (character === '\u001b') {
        this.ansi = 'escape'
        return true
      }
      if (character === '\u009b') {
        this.ansi = 'csi'
        return true
      }
      return false
    }
    if (this.ansi === 'escape') {
      this.ansi = character === '[' ? 'csi' : character === ']' ? 'osc' : 'text'
      return true
    }
    if (this.ansi === 'csi') {
      if (character >= '@' && character <= '~') this.ansi = 'text'
      return true
    }
    if (this.ansi === 'osc') {
      if (character === '\u0007') this.ansi = 'text'
      else if (character === '\u001b') this.ansi = 'osc-escape'
      return true
    }
    this.ansi = character === '\\' ? 'text' : character === '\u001b' ? 'osc-escape' : 'osc'
    return true
  }

  private trim(): void {
    const overflow = this.finished.length + this.line.length - this.limit
    if (overflow <= 0) return
    if (overflow < this.finished.length) {
      this.finished = this.finished.slice(overflow)
      return
    }
    this.line = this.line.slice(overflow - this.finished.length)
    this.finished = ''
  }
}

export function terminalText(source: string): string {
  return new TerminalBuffer().append(source)
}
