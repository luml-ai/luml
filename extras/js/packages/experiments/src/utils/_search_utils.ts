import { LumlFilterError } from './_exceptions.js'

// ─── Tokenizer ────────────────────────────────────────────────────────────────

const enum TK {
  IDENTIFIER = 'IDENTIFIER',
  STRING = 'STRING',
  NUMBER = 'NUMBER',
  KEYWORD = 'KEYWORD',
  OP = 'OP',
  LPAREN = 'LPAREN',
  RPAREN = 'RPAREN',
  COMMA = 'COMMA',
  EOF = 'EOF',
}

interface Token {
  kind: TK
  value: string
}

const KEYWORDS = new Set(['AND', 'OR', 'NOT', 'IN', 'LIKE', 'ILIKE', 'TRUE', 'FALSE'])

function tokenize(input: string): Token[] {
  const tokens: Token[] = []
  let i = 0

  while (i < input.length) {
    const ch = input[i]

    if (/\s/.test(ch || '')) {
      i++
      continue
    }

    // String literals: 'value' or "value"
    if (ch === "'" || ch === '"') {
      const quote = ch
      let j = i + 1
      while (j < input.length && input[j] !== quote) {
        if (input[j] === '\\') j++
        j++
      }
      if (j >= input.length) {
        throw new LumlFilterError(`Unterminated string at position ${i}`)
      }
      tokens.push({ kind: TK.STRING, value: input.slice(i, j + 1) })
      i = j + 1
      continue
    }

    // Numbers
    if (/[0-9]/.test(ch || '')) {
      let j = i
      while (j < input.length && /[0-9]/.test(input[j] || '')) j++
      if (j < input.length && input[j] === '.') {
        j++
        while (j < input.length && /[0-9]/.test(input[j] || '')) j++
      }
      tokens.push({ kind: TK.NUMBER, value: input.slice(i, j) })
      i = j
      continue
    }

    // Two-char operators
    if (i + 1 < input.length) {
      const two = input.slice(i, i + 2)
      if (two === '!=' || two === '<=' || two === '>=') {
        tokens.push({ kind: TK.OP, value: two })
        i += 2
        continue
      }
    }

    // Single-char operators
    if (ch === '=' || ch === '<' || ch === '>') {
      tokens.push({ kind: TK.OP, value: ch })
      i++
      continue
    }
    if (ch === '(') {
      tokens.push({ kind: TK.LPAREN, value: '(' })
      i++
      continue
    }
    if (ch === ')') {
      tokens.push({ kind: TK.RPAREN, value: ')' })
      i++
      continue
    }
    if (ch === ',') {
      tokens.push({ kind: TK.COMMA, value: ',' })
      i++
      continue
    }

    // Backtick-quoted identifier
    if (ch === '`') {
      let j = i + 1
      while (j < input.length && input[j] !== '`') j++
      tokens.push({ kind: TK.IDENTIFIER, value: input.slice(i, j + 1) })
      i = j + 1
      continue
    }

    // Word: identifier or keyword (may contain dots, e.g. "param.lr", "attributes.http.method").
    // Backtick-quoted segments within a dotted path are also consumed as part of the same
    // token so that annotations.feedback.`First annotation` becomes one IDENTIFIER token.
    if (/[a-zA-Z_]/.test(ch || '')) {
      let j = i
      while (j < input.length) {
        if (/[a-zA-Z0-9_.-]/.test(input[j] || '')) {
          j++
        } else if (input[j] === '`') {
          // Backtick-quoted segment — read until closing backtick (spaces inside are ok)
          j++ // skip opening `
          while (j < input.length && input[j] !== '`') j++
          if (j < input.length) j++ // skip closing `
        } else {
          break
        }
      }
      const word = input.slice(i, j)
      const upper = word.toUpperCase()
      if (KEYWORDS.has(upper)) {
        tokens.push({ kind: TK.KEYWORD, value: upper })
      } else {
        tokens.push({ kind: TK.IDENTIFIER, value: word })
      }
      i = j
      continue
    }

    throw new LumlFilterError(`Unexpected character '${ch}' at position ${i}`)
  }

  tokens.push({ kind: TK.EOF, value: '' })
  return tokens
}

// ─── Parsed Value Types ───────────────────────────────────────────────────────

type ParsedValue =
  | { kind: 'string'; raw: string } // 'quoted' or "quoted" — raw includes the quotes
  | { kind: 'number'; raw: string } // numeric literal
  | { kind: 'bool'; raw: string } // TRUE or FALSE
  | { kind: 'list'; items: string[] } // IN (...) list — items already unquoted

// ─── Filter Node Types ────────────────────────────────────────────────────────

export type FilterNode = { operator: 'AND' | 'OR' } | { group: FilterNode[] } | ComparisonDict

export interface ComparisonDict {
  type: string
  key: string
  comparator: string
  value: unknown
  column?: string
  kind?: string | null
}

interface RawComparison {
  identifierStr: string
  comparator: string
  parsedValue: ParsedValue
}

// ─── Recursive-Descent Parser ─────────────────────────────────────────────────

class FilterParser {
  private pos = 0

  constructor(private readonly tokens: Token[]) {}

  private peek(): Token {
    return this.tokens[this.pos]!
  }
  private advance(): Token {
    return this.tokens[this.pos++]!
  }

  parseExpression(): Array<{ operator: 'AND' | 'OR' } | { group: FilterNode[] } | RawComparison> {
    const result: Array<{ operator: 'AND' | 'OR' } | { group: FilterNode[] } | RawComparison> = []
    result.push(...this.parseTerm())

    while (
      this.peek().kind === TK.KEYWORD &&
      (this.peek().value === 'AND' || this.peek().value === 'OR')
    ) {
      const op = this.advance()
      result.push({ operator: op.value as 'AND' | 'OR' })
      result.push(...this.parseTerm())
    }

    return result
  }

  private parseTerm(): Array<{ operator: 'AND' | 'OR' } | { group: FilterNode[] } | RawComparison> {
    if (this.peek().kind === TK.LPAREN) {
      this.advance() // consume '('
      const inner = this.parseExpression()
      if (this.peek().kind !== TK.RPAREN) {
        throw new LumlFilterError(`Expected ')' but got '${this.peek().value}'`)
      }
      this.advance() // consume ')'
      return [{ group: inner as FilterNode[] }]
    }
    return [this.parseComparison()]
  }

  private parseComparison(): RawComparison {
    const left = this.peek()
    if (left.kind !== TK.IDENTIFIER) {
      throw new LumlFilterError(`Invalid clause(s) in filter string: '${left.value}'`)
    }
    this.advance()

    const comparator = this.parseComparator()
    const parsedValue = this.parseValue(comparator)

    return { identifierStr: left.value, comparator, parsedValue }
  }

  private parseComparator(): string {
    const tok = this.peek()
    if (tok.kind === TK.OP) {
      return this.advance().value
    }
    if (tok.kind === TK.KEYWORD) {
      if (tok.value === 'LIKE' || tok.value === 'ILIKE') {
        return this.advance().value
      }
      if (tok.value === 'IN') {
        return this.advance().value
      }
      if (tok.value === 'NOT') {
        this.advance()
        const next = this.peek()
        if (next.kind === TK.KEYWORD && next.value === 'IN') {
          this.advance()
          return 'NOT IN'
        }
        throw new LumlFilterError(`Expected 'IN' after 'NOT', got '${next.value}'`)
      }
    }
    throw new LumlFilterError(`Expected comparator, got '${tok.value}'`)
  }

  private parseValue(comparator: string): ParsedValue {
    const tok = this.peek()

    if (comparator === 'IN' || comparator === 'NOT IN') {
      if (tok.kind !== TK.LPAREN) {
        throw new LumlFilterError(`Expected '(' after ${comparator}`)
      }
      return this.parseInList()
    }

    if (tok.kind === TK.STRING) {
      this.advance()
      return { kind: 'string', raw: tok.value }
    }
    if (tok.kind === TK.NUMBER) {
      this.advance()
      return { kind: 'number', raw: tok.value }
    }
    if (tok.kind === TK.KEYWORD && (tok.value === 'TRUE' || tok.value === 'FALSE')) {
      this.advance()
      return { kind: 'bool', raw: tok.value }
    }
    if (tok.kind === TK.IDENTIFIER) {
      throw new LumlFilterError(
        `Parameter value is either not quoted or unidentified quote types used for string value ${tok.value}. Use either single or double quotes.`,
      )
    }

    throw new LumlFilterError(`Expected value, got '${tok.value}'`)
  }

  private parseInList(): ParsedValue {
    this.advance() // consume '('
    const items: string[] = []

    while (this.peek().kind !== TK.RPAREN && this.peek().kind !== TK.EOF) {
      if (this.peek().kind === TK.COMMA) {
        this.advance()
        continue
      }
      const tok = this.peek()
      if (tok.kind !== TK.STRING) {
        throw new LumlFilterError(
          `While parsing a list in the query, expected string value, punctuation, or whitespace, but got different type in list: ${tok.value}`,
        )
      }
      this.advance()
      items.push(tok.value.slice(1, -1)) // strip outer quotes
    }

    if (this.peek().kind !== TK.RPAREN) {
      throw new LumlFilterError('Unterminated IN list')
    }
    this.advance() // consume ')'

    if (items.length === 0) {
      throw new LumlFilterError(
        'While parsing a list in the query, expected a non-empty list of string values, but got empty list',
      )
    }
    return { kind: 'list', items }
  }
}

// ─── String helper functions ──────────────────────────────────────────────────

function convertLikePatternToRegex(pattern: string, flags = ''): RegExp {
  if (!pattern.startsWith('%')) pattern = '^' + pattern
  if (!pattern.endsWith('%')) pattern = pattern + '$'
  return new RegExp(pattern.replace(/_/g, '.').replace(/%/g, '.*'), flags)
}

function likeMatch(str: string, pattern: string): boolean {
  return convertLikePatternToRegex(pattern).test(str)
}

function ilikeMatch(str: string, pattern: string): boolean {
  return convertLikePatternToRegex(pattern, 'i').test(str)
}

// ─── SearchUtils base class ───────────────────────────────────────────────────

export class SearchUtils {
  static readonly LIKE_OPERATOR = 'LIKE'
  static readonly ILIKE_OPERATOR = 'ILIKE'
  static readonly VALID_METRIC_COMPARATORS = new Set(['>', '>=', '!=', '=', '<', '<='])
  static readonly VALID_PARAM_COMPARATORS = new Set(['!=', '=', 'LIKE', 'ILIKE'])
  static readonly VALID_TAG_COMPARATORS = new Set(['!=', '=', 'LIKE', 'ILIKE'])
  static readonly VALID_STRING_ATTRIBUTE_COMPARATORS = new Set([
    '!=',
    '=',
    'LIKE',
    'ILIKE',
    'IN',
    'NOT IN',
  ])
  static readonly VALID_NUMERIC_ATTRIBUTE_COMPARATORS = new Set(['>', '>=', '!=', '=', '<', '<='])
  static readonly VALID_BOOLEAN_ATTRIBUTE_COMPARATORS = new Set(['=', '!='])

  static getComparisonFunc(comparator: string): (a: unknown, b: unknown) => boolean {
    const ops: Record<string, (a: unknown, b: unknown) => boolean> = {
      '>': (a, b) => (a as number) > (b as number),
      '>=': (a, b) => (a as number) >= (b as number),
      '=': (a, b) => a === b,
      '!=': (a, b) => a !== b,
      '<=': (a, b) => (a as number) <= (b as number),
      '<': (a, b) => (a as number) < (b as number),
      LIKE: (a, b) => likeMatch(a as string, b as string),
      ILIKE: (a, b) => ilikeMatch(a as string, b as string),
      IN: (a, b) => (b as unknown[]).includes(a),
      'NOT IN': (a, b) => !(b as unknown[]).includes(a),
    }
    const fn = ops[comparator]
    if (!fn) throw new LumlFilterError(`Unknown comparator '${comparator}'`)
    return fn
  }

  protected static trimBackticks(s: string): string {
    if (s.length >= 2 && s.startsWith('`') && s.endsWith('`')) {
      return s.slice(1, -1)
    }
    return s
  }

  protected static stripQuotes(value: string, expectQuotedValue = false): string {
    if (
      (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) ||
      (value.length >= 2 && value.startsWith('"') && value.endsWith('"'))
    ) {
      return value.slice(1, -1)
    }
    if (expectQuotedValue) {
      throw new LumlFilterError(
        `Parameter value is either not quoted or unidentified quote types used for string value ${value}. Use either single or double quotes.`,
      )
    }
    return value
  }

  protected static validateDateString(value: string, key: string): void {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || isNaN(Date.parse(value))) {
      throw new LumlFilterError(
        `Invalid date value '${value}' for '${key}'. Expected ISO format: YYYY-MM-DD.`,
      )
    }
  }

  protected static preprocessFilter(filterString: string): string {
    // CONTAINS "val" → LIKE "%val%"
    filterString = filterString.replace(
      /\bCONTAINS\b\s+(['"])(.*?)\1/gi,
      (_match, quote: string, val: string) => {
        if (!val.startsWith('%')) val = '%' + val
        if (!val.endsWith('%')) val = val + '%'
        return `LIKE ${quote}${val}${quote}`
      },
    )
    // bare true/false → 1/0 (skip quoted)
    filterString = filterString.replace(/(?<!['"])\btrue\b(?!['"])/gi, '1')
    filterString = filterString.replace(/(?<!['"])\bfalse\b(?!['"])/gi, '0')

    // Wrap annotation keys containing spaces in backticks before tokenisation.
    // The tokenizer handles backtick-quoted segments within dotted identifiers,
    // and trimBackticks in _getIdentifier strips them back out.
    // Only fires when the key is not already quoted (quotes are excluded from the
    // key character class).
    filterString = filterString.replace(
      // group 1: annotation prefix including trailing dot
      // group 2: key (possibly multi-word, no quotes/backticks)
      /((?:annotations(?:\.(?:feedback|expectations?))?|annotations_(?:feedback|expectations?))\.)((?:[^=!<>'"` \t\n\r][^=!<>'"` \n\r]*)(?:[ \t]+(?:[^=!<>'"` \n\r]+))*)(?=[ \t]*(?:!=|>=?|<=?|=|\bLIKE\b|\bILIKE\b|\bNOT[ \t]+IN\b|\bIN\b|\bCONTAINS\b))/gi,
      (_match, prefix: string, key: string) => {
        const trimmedKey = key.trimEnd()
        if (trimmedKey.includes(' ') || trimmedKey.includes('\t')) {
          return `${prefix}\`${trimmedKey}\``
        }
        return _match
      },
    )

    return filterString
  }

  // Subclasses override these:

  protected static _getIdentifier(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _identifierStr: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _validAttributes: Set<string>,
  ): Record<string, unknown> {
    throw new Error('_getIdentifier not implemented')
  }

   
  protected static _getValue(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _identifierType: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _key: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _parsedValue: ParsedValue,
  ): unknown {
    throw new Error('_getValue not implemented')
  }

  protected static _getComparison(raw: RawComparison): ComparisonDict {
     
    const cls = this as any
    const comp = cls._getIdentifier(
      raw.identifierStr,
      cls.VALID_SEARCH_ATTRIBUTE_KEYS,
    ) as ComparisonDict
    comp.comparator = raw.comparator
    comp.value = cls._getValue(comp.type, comp.key, raw.parsedValue)
    return comp
  }

  protected static _parseFilter(filterString: string): FilterNode[] {
    const tokens = tokenize(filterString)
    const parser = new FilterParser(tokens)
     
    const cls = this as any
    const nodes = parser.parseExpression()

    const result: FilterNode[] = []
    for (const node of nodes) {
      if ('operator' in node) {
        result.push(node as { operator: 'AND' | 'OR' })
      } else if ('group' in node) {
        const inner = cls._resolveNodes(node.group)
        result.push({ group: inner })
      } else {
        result.push(cls._getComparison(node as RawComparison))
      }
    }
    return result
  }

  protected static _resolveNodes(nodes: Array<unknown>): FilterNode[] {
     
    const cls = this as any
    const result: FilterNode[] = []
    for (const node of nodes) {
      const n = node as Record<string, unknown>
      if ('operator' in n) {
        result.push(n as { operator: 'AND' | 'OR' })
      } else if ('group' in n) {
        const inner = cls._resolveNodes(n['group'] as unknown[])
        result.push({ group: inner })
      } else {
        result.push(cls._getComparison(n as unknown as RawComparison))
      }
    }
    return result
  }

  static parseSearchFilter(filterString: string | null | undefined): FilterNode[] {
    if (!filterString) return []
     
    const cls = this as any
    const preprocessed = cls.preprocessFilter(filterString) as string
    try {
      return cls._parseFilter(preprocessed) as FilterNode[]
    } catch (e) {
      if (e instanceof LumlFilterError) throw e
      throw new LumlFilterError(`Error on parsing filter '${filterString}'`)
    }
  }
}

// ─── SearchExperimentsUtils ───────────────────────────────────────────────────

export class SearchExperimentsUtils extends SearchUtils {
  static readonly VALID_SEARCH_ATTRIBUTE_KEYS = new Set([
    'id',
    'name',
    'status',
    'created_at',
    'duration',
    'description',
    'group_id',
  ])
  static readonly VALID_ORDER_BY_ATTRIBUTE_KEYS = new Set([
    'name',
    'status',
    'created_at',
    'duration',
    'id',
  ])
  static readonly NUMERIC_ATTRIBUTES = new Set(['duration', 'created_at'])
  static readonly STRING_ATTRIBUTES = new Set(['id', 'name', 'status', 'description', 'group_id'])

  private static readonly _METRIC_IDENTIFIER = 'metric'
  private static readonly _PARAM_IDENTIFIER = 'param'
  private static readonly _TAG_IDENTIFIER = 'tag'
  private static readonly _ATTRIBUTE_IDENTIFIER = 'attribute'

  private static readonly _PARAM_IDENTIFIERS = new Set([
    'param',
    'params',
    'parameter',
    'parameters',
    'static_params',
  ])
  private static readonly _METRIC_IDENTIFIERS = new Set(['metric', 'metrics', 'dynamic_params'])
  private static readonly _TAG_IDENTIFIERS = new Set(['tag', 'tags'])
  private static readonly _ATTRIBUTE_IDENTIFIERS = new Set(['attribute', 'attr'])

  protected static override _getIdentifier(
    identifierStr: string,
    validAttributes: Set<string>,
  ): Record<string, unknown> {
    identifierStr = SearchExperimentsUtils.trimBackticks(identifierStr.trim())
    const dotIdx = identifierStr.indexOf('.')

    if (dotIdx === -1) {
      const key = SearchExperimentsUtils.trimBackticks(
        SearchExperimentsUtils.stripQuotes(identifierStr),
      )
      const keyLower = key.toLowerCase()
      if (SearchExperimentsUtils._TAG_IDENTIFIERS.has(keyLower)) {
        return { type: SearchExperimentsUtils._TAG_IDENTIFIER, key }
      }
      // single-part → attribute
      if (!validAttributes.has(key)) {
        throw new LumlFilterError(
          `Invalid attribute key '${key}' specified. ` +
            `Valid attribute keys are ${[...validAttributes].sort()}. ` +
            `For dynamic metrics use: metric.<key> or dynamic_params.<key>. ` +
            `For static params use: param.<key> or static_params.<key>.`,
        )
      }
      return { type: SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER, key }
    }

    const entityTypeStr = identifierStr.slice(0, dotIdx)
    const rawKey = identifierStr.slice(dotIdx + 1)
    const entityTypeLower = entityTypeStr.toLowerCase()
    const key = SearchExperimentsUtils.trimBackticks(SearchExperimentsUtils.stripQuotes(rawKey))

    let entityType: string
    if (SearchExperimentsUtils._PARAM_IDENTIFIERS.has(entityTypeLower)) {
      entityType = SearchExperimentsUtils._PARAM_IDENTIFIER
    } else if (SearchExperimentsUtils._METRIC_IDENTIFIERS.has(entityTypeLower)) {
      entityType = SearchExperimentsUtils._METRIC_IDENTIFIER
    } else if (SearchExperimentsUtils._TAG_IDENTIFIERS.has(entityTypeLower)) {
      entityType = SearchExperimentsUtils._TAG_IDENTIFIER
    } else if (SearchExperimentsUtils._ATTRIBUTE_IDENTIFIERS.has(entityTypeLower)) {
      entityType = SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER
    } else {
      throw new LumlFilterError(
        `Invalid entity type '${entityTypeStr}'. ` +
          `Valid types are: attribute, tag, param/params/static_params, metric/metrics/dynamic_params`,
      )
    }

    if (entityType === SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER && !validAttributes.has(key)) {
      throw new LumlFilterError(
        `Invalid attribute key '${key}' specified. ` +
          `Valid attribute keys are ${[...validAttributes].sort()}. ` +
          `For dynamic metrics use: metric.<key> or dynamic_params.<key>. ` +
          `For static params use: param.<key> or static_params.<key>.`,
      )
    }

    if (
      (entityType === SearchExperimentsUtils._PARAM_IDENTIFIER ||
        entityType === SearchExperimentsUtils._METRIC_IDENTIFIER) &&
      !/^[a-zA-Z0-9_.\-]+$/.test(key)
    ) {
      throw new LumlFilterError(
        `Invalid key '${key}' for ${entityType}. ` +
          `Keys may only contain alphanumeric characters, underscores, dots, and hyphens.`,
      )
    }

    return { type: entityType, key }
  }

  protected static override _getValue(
    identifierType: string,
    key: string,
    parsedValue: ParsedValue,
  ): unknown {
    if (identifierType === SearchExperimentsUtils._METRIC_IDENTIFIER) {
      if (parsedValue.kind !== 'number') {
        const raw =
          parsedValue.kind === 'string'
            ? parsedValue.raw
            : ((parsedValue as { raw?: string }).raw ?? '')
        throw new LumlFilterError(`Expected numeric value type for metric. Found ${raw}`)
      }
      return parseFloat(parsedValue.raw)
    }

    if (identifierType === SearchExperimentsUtils._PARAM_IDENTIFIER) {
      if (parsedValue.kind === 'number') return parseFloat(parsedValue.raw)
      if (parsedValue.kind === 'string') {
        return SearchExperimentsUtils.stripQuotes(parsedValue.raw, true)
      }
      if (parsedValue.kind === 'bool') {
        return parsedValue.raw === 'TRUE'
      }
      throw new LumlFilterError(
        `Expected string or numeric value for param. Got ${JSON.stringify(parsedValue)}`,
      )
    }

    if (identifierType === SearchExperimentsUtils._TAG_IDENTIFIER) {
      if (parsedValue.kind === 'string') {
        return SearchExperimentsUtils.stripQuotes(parsedValue.raw, true)
      }
      throw new LumlFilterError(
        `Expected quoted string value for tag. Got ${JSON.stringify(parsedValue)}`,
      )
    }

    if (identifierType === SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER) {
      if (key === 'duration') {
        if (parsedValue.kind !== 'number') {
          throw new LumlFilterError(
            `Expected numeric value for 'duration'. Got ${JSON.stringify(parsedValue)}`,
          )
        }
        return parseFloat(parsedValue.raw)
      }
      if (key === 'created_at') {
        if (parsedValue.kind === 'string') {
          const dateStr = SearchExperimentsUtils.stripQuotes(parsedValue.raw, true)
          SearchExperimentsUtils.validateDateString(dateStr, key)
          return dateStr
        }
        if (parsedValue.kind === 'number') return parsedValue.raw
        throw new LumlFilterError(
          `Expected quoted date string for 'created_at'. Got ${JSON.stringify(parsedValue)}`,
        )
      }
      // String attributes
      if (parsedValue.kind === 'string') {
        return SearchExperimentsUtils.stripQuotes(parsedValue.raw, true)
      }
      if (parsedValue.kind === 'list') return parsedValue.items
      throw new LumlFilterError(
        `Expected quoted string value for attribute '${key}'. Got ${JSON.stringify(parsedValue)}`,
      )
    }

    throw new LumlFilterError(`Invalid identifier type '${identifierType}'`)
  }

  protected static override _getComparison(raw: RawComparison): ComparisonDict {
    const comp = SearchExperimentsUtils._getIdentifier(
      raw.identifierStr,
      SearchExperimentsUtils.VALID_SEARCH_ATTRIBUTE_KEYS,
    ) as unknown as ComparisonDict
    const comparator = raw.comparator.toUpperCase()

    let validComparators: Set<string>
    if (comp.type === SearchExperimentsUtils._METRIC_IDENTIFIER) {
      validComparators = SearchExperimentsUtils.VALID_METRIC_COMPARATORS
    } else if (comp.type === SearchExperimentsUtils._PARAM_IDENTIFIER) {
      validComparators = SearchExperimentsUtils.VALID_PARAM_COMPARATORS
    } else if (comp.type === SearchExperimentsUtils._TAG_IDENTIFIER) {
      validComparators = SearchExperimentsUtils.VALID_TAG_COMPARATORS
    } else if (comp.type === SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER) {
      validComparators = SearchExperimentsUtils.NUMERIC_ATTRIBUTES.has(comp.key)
        ? SearchExperimentsUtils.VALID_NUMERIC_ATTRIBUTE_COMPARATORS
        : SearchExperimentsUtils.VALID_STRING_ATTRIBUTE_COMPARATORS
    } else {
      validComparators = new Set()
    }

    if (!validComparators.has(comparator)) {
      throw new LumlFilterError(
        `Invalid comparator '${comparator}' for ${comp.type} '${comp.key}'. ` +
          `Valid comparators are: ${[...validComparators].sort()}`,
      )
    }

    comp.comparator = comparator
    comp.value = SearchExperimentsUtils._getValue(comp.type, comp.key, raw.parsedValue)
    return comp
  }

  static parseOrderBy(orderByStr: string): [string, string, boolean] {
    const parts = orderByStr.trim().split(/\s+/)
    let identifierStr: string
    let isAscending: boolean

    if (parts.length === 2 && ['ASC', 'DESC'].includes(parts[1]!.toUpperCase())) {
      identifierStr = parts[0]!
      isAscending = parts[1]!.toUpperCase() === 'ASC'
    } else if (parts.length === 1) {
      identifierStr = parts[0]!
      isAscending = true
    } else {
      throw new LumlFilterError(
        `Invalid order_by clause '${orderByStr}'. Expected format: '<key> [ASC|DESC]'`,
      )
    }

    const identifier = SearchExperimentsUtils._getIdentifier(
      identifierStr,
      SearchExperimentsUtils.VALID_ORDER_BY_ATTRIBUTE_KEYS,
    )
    return [identifier['type'] as string, identifier['key'] as string, isAscending]
  }

  static override parseSearchFilter(filterString: string | null | undefined): FilterNode[] {
    if (!filterString) return []
    const preprocessed = SearchExperimentsUtils.preprocessFilter(filterString)
    try {
      return SearchExperimentsUtils._parseFilter(preprocessed)
    } catch (e) {
      if (e instanceof LumlFilterError) throw e
      throw new LumlFilterError(`Error on parsing filter '${filterString}'`)
    }
  }

  private static _buildSqlFilter(parsedFilters: FilterNode[]): [string, unknown[]] {
    const sqlParts: string[] = []
    const params: unknown[] = []

    for (const item of parsedFilters) {
      if ('operator' in item) {
        sqlParts.push(item.operator)
        continue
      }
      if ('group' in item) {
        const [subSql, subParams] = SearchExperimentsUtils._buildSqlFilter(item.group)
        sqlParts.push(`(${subSql})`)
        params.push(...subParams)
        continue
      }

      const { type: keyType, key, value, comparator } = item

      if (keyType === SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER) {
        if (comparator === 'IN') {
          const ph = (value as string[]).map(() => '?').join(',')
          sqlParts.push(`${key} IN (${ph})`)
          params.push(...(value as unknown[]))
        } else if (comparator === 'NOT IN') {
          const ph = (value as string[]).map(() => '?').join(',')
          sqlParts.push(`${key} NOT IN (${ph})`)
          params.push(...(value as unknown[]))
        } else if (comparator === 'ILIKE') {
          sqlParts.push(`UPPER(${key}) LIKE UPPER(?)`)
          params.push(value)
        } else {
          sqlParts.push(`${key} ${comparator} ?`)
          params.push(value)
        }
      } else if (keyType === SearchExperimentsUtils._TAG_IDENTIFIER) {
        if (comparator === 'ILIKE') {
          sqlParts.push('UPPER(tags) LIKE UPPER(?)')
          params.push(value)
        } else {
          sqlParts.push(`tags ${comparator} ?`)
          params.push(value)
        }
      } else if (keyType === SearchExperimentsUtils._PARAM_IDENTIFIER) {
        const jsonCol = `json_extract(static_params, '$.${key}')`
        if (comparator === 'ILIKE') {
          sqlParts.push(`UPPER(${jsonCol}) LIKE UPPER(?)`)
          params.push(value)
        } else {
          sqlParts.push(`${jsonCol} ${comparator} ?`)
          params.push(value)
        }
      } else if (keyType === SearchExperimentsUtils._METRIC_IDENTIFIER) {
        const jsonCol = `json_extract(dynamic_params, '$.${key}')`
        sqlParts.push(`${jsonCol} ${comparator} ?`)
        params.push(value)
      }
    }

    return [sqlParts.join(' '), params]
  }

  private static _buildSqlOrderBy(orderByList: string[]): string {
    if (!orderByList.length) return ''
    const parts: string[] = []
    for (const orderByStr of orderByList) {
      const [keyType, key, isAscending] = SearchExperimentsUtils.parseOrderBy(orderByStr)
      const direction = isAscending ? 'ASC' : 'DESC'
      if (keyType === SearchExperimentsUtils._ATTRIBUTE_IDENTIFIER) {
        parts.push(`${key} ${direction}`)
      } else if (keyType === SearchExperimentsUtils._PARAM_IDENTIFIER) {
        parts.push(`json_extract(static_params, '$.${key}') ${direction}`)
      } else if (keyType === SearchExperimentsUtils._METRIC_IDENTIFIER) {
        parts.push(`json_extract(dynamic_params, '$.${key}') ${direction}`)
      } else {
        throw new LumlFilterError(`Invalid order_by entity type '${keyType}'`)
      }
    }
    return 'ORDER BY ' + parts.join(', ')
  }

  static validateFilterString(filterString: string | null | undefined): void {
    SearchExperimentsUtils.parseSearchFilter(filterString)
  }

  static toSql(
    filterString: string | null | undefined,
    orderByList?: string[],
  ): [string, string, unknown[]] {
    const parsedFilters = SearchExperimentsUtils.parseSearchFilter(filterString)
    const [whereClause, params] = SearchExperimentsUtils._buildSqlFilter(parsedFilters)
    const orderByClause = SearchExperimentsUtils._buildSqlOrderBy(orderByList ?? [])
    return [whereClause, orderByClause, params]
  }
}

// ─── SearchEvalsUtils ─────────────────────────────────────────────────────────

export class SearchEvalsUtils extends SearchUtils {
  static readonly VALID_SEARCH_ATTRIBUTE_KEYS = new Set([
    'id',
    'dataset_id',
    'created_at',
    'updated_at',
  ])
  static readonly DATE_ATTRIBUTES = new Set(['created_at', 'updated_at'])
  static readonly STRING_ATTRIBUTES = new Set(['id', 'dataset_id'])
  static readonly JSON_COLUMNS = new Set(['inputs', 'outputs', 'refs', 'scores', 'metadata'])
  static readonly ANNOTATION_PREFIX = 'annotations'
  static readonly ANNOTATION_KINDS = new Set(['feedback', 'expectation', 'expectations'])

  private static readonly _JSON_IDENTIFIER = 'json'
  private static readonly _ATTRIBUTE_IDENTIFIER = 'attribute'
  private static readonly _ANNOTATION_IDENTIFIER = 'annotation'

  static readonly VALID_STRING_ATTRIBUTE_COMPARATORS = new Set([
    '=',
    '!=',
    'LIKE',
    'ILIKE',
    'IN',
    'NOT IN',
  ])
  static readonly VALID_DATE_COMPARATORS = new Set(['=', '!=', '>', '>=', '<', '<='])
  static readonly VALID_JSON_COMPARATORS = new Set([
    '=',
    '!=',
    '>',
    '>=',
    '<',
    '<=',
    'LIKE',
    'ILIKE',
    'IN',
    'NOT IN',
  ])
  static readonly VALID_ANNOTATION_COMPARATORS = SearchEvalsUtils.VALID_JSON_COMPARATORS

  protected static override _getIdentifier(
    identifierStr: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _validAttributes: Set<string>,
  ): Record<string, unknown> {
    identifierStr = SearchEvalsUtils.trimBackticks(identifierStr.trim())
    const dotIdx = identifierStr.indexOf('.')

    if (dotIdx === -1) {
      const key = SearchEvalsUtils.trimBackticks(SearchEvalsUtils.stripQuotes(identifierStr))
      if (!SearchEvalsUtils.VALID_SEARCH_ATTRIBUTE_KEYS.has(key)) {
        throw new LumlFilterError(
          `Invalid attribute '${key}'. ` +
            `Valid attributes: ${[...SearchEvalsUtils.VALID_SEARCH_ATTRIBUTE_KEYS].sort()}. ` +
            `For JSON fields use: <column>.<key> where column is one of ` +
            `${[...SearchEvalsUtils.JSON_COLUMNS].sort()}.`,
        )
      }
      return { type: SearchEvalsUtils._ATTRIBUTE_IDENTIFIER, key }
    }

    const prefix = identifierStr.slice(0, dotIdx)
    const rawKey = identifierStr.slice(dotIdx + 1)
    const prefixLower = prefix.toLowerCase()

    // annotations.<name>  OR  annotations.<kind>.<name>
    if (prefixLower === SearchEvalsUtils.ANNOTATION_PREFIX) {
      const kindDot = rawKey.indexOf('.')
      if (kindDot !== -1) {
        const kindStr = rawKey.slice(0, kindDot).toLowerCase()
        if (SearchEvalsUtils.ANNOTATION_KINDS.has(kindStr)) {
          const kind = kindStr === 'expectations' ? 'expectation' : kindStr
          const annName = SearchEvalsUtils.trimBackticks(
            SearchEvalsUtils.stripQuotes(rawKey.slice(kindDot + 1)),
          )
          return {
            type: SearchEvalsUtils._ANNOTATION_IDENTIFIER,
            kind,
            key: annName,
          }
        }
      }
      const annName = SearchEvalsUtils.trimBackticks(SearchEvalsUtils.stripQuotes(rawKey))
      return { type: SearchEvalsUtils._ANNOTATION_IDENTIFIER, kind: null, key: annName }
    }

    // annotations_feedback.<name>
    if (prefixLower === 'annotations_feedback') {
      const annName = SearchEvalsUtils.trimBackticks(SearchEvalsUtils.stripQuotes(rawKey))
      return { type: SearchEvalsUtils._ANNOTATION_IDENTIFIER, kind: 'feedback', key: annName }
    }

    // annotations_expectation.<name>  /  annotations_expectations.<name>
    if (prefixLower === 'annotations_expectation' || prefixLower === 'annotations_expectations') {
      const annName = SearchEvalsUtils.trimBackticks(SearchEvalsUtils.stripQuotes(rawKey))
      return {
        type: SearchEvalsUtils._ANNOTATION_IDENTIFIER,
        kind: 'expectation',
        key: annName,
      }
    }

    const key = SearchEvalsUtils.trimBackticks(SearchEvalsUtils.stripQuotes(rawKey))
    if (!SearchEvalsUtils.JSON_COLUMNS.has(prefixLower)) {
      throw new LumlFilterError(
        `Invalid field prefix '${prefix}'. ` +
          `Valid JSON columns: ${[...SearchEvalsUtils.JSON_COLUMNS].sort()}. ` +
          `Valid bare attributes: ${[...SearchEvalsUtils.VALID_SEARCH_ATTRIBUTE_KEYS].sort()}. ` +
          `Use '${SearchEvalsUtils.ANNOTATION_PREFIX}.<name>' to filter by annotation.`,
      )
    }
    return { type: SearchEvalsUtils._JSON_IDENTIFIER, column: prefixLower, key }
  }

  /** Build SQL expression for comparing annotation `value` column. */
  private static _buildAnnotationValueExpr(
    comparator: string,
    value: unknown,
  ): [string, unknown[]] {
    const numericComparators = new Set(['>', '>=', '<', '<='])
    if (numericComparators.has(comparator)) {
      return [`CAST(value AS REAL) ${comparator} ?`, [value]]
    }
    if (comparator === 'ILIKE') {
      return ['UPPER(value) LIKE UPPER(?)', [value]]
    }
    if (comparator === 'IN') {
      const vals = value as unknown[]
      return [`value IN (${vals.map(() => '?').join(',')})`, vals]
    }
    if (comparator === 'NOT IN') {
      const vals = value as unknown[]
      return [`value NOT IN (${vals.map(() => '?').join(',')})`, vals]
    }
    // = / != : numeric → text, with bool aliases for 1/0
    if (typeof value === 'number') {
      const strVal = Number.isInteger(value) ? String(value) : String(value)
      if (value === 1) {
        return comparator === '='
          ? ["(value = ? OR value = 'true')", [strVal]]
          : ["(value != ? AND value != 'true')", [strVal]]
      }
      if (value === 0) {
        return comparator === '='
          ? ["(value = ? OR value = 'false')", [strVal]]
          : ["(value != ? AND value != 'false')", [strVal]]
      }
      return [`value ${comparator} ?`, [strVal]]
    }
    return [`value ${comparator} ?`, [value]]
  }

  protected static override _getValue(
    identifierType: string,
    key: string,
    parsedValue: ParsedValue,
  ): unknown {
    if (
      identifierType === SearchEvalsUtils._ANNOTATION_IDENTIFIER ||
      identifierType === SearchEvalsUtils._JSON_IDENTIFIER
    ) {
      if (parsedValue.kind === 'number') return parseFloat(parsedValue.raw)
      if (parsedValue.kind === 'string') {
        return SearchEvalsUtils.stripQuotes(parsedValue.raw, true)
      }
      if (parsedValue.kind === 'list') return parsedValue.items
      if (parsedValue.kind === 'bool') return parsedValue.raw === 'TRUE'
      throw new LumlFilterError(
        `Expected string or numeric value for JSON field '${key}'. ` +
          `Got ${JSON.stringify(parsedValue)}`,
      )
    }

    // attribute
    if (SearchEvalsUtils.DATE_ATTRIBUTES.has(key)) {
      if (parsedValue.kind === 'string') {
        const dateStr = SearchEvalsUtils.stripQuotes(parsedValue.raw, true)
        SearchEvalsUtils.validateDateString(dateStr, key)
        return dateStr
      }
      if (parsedValue.kind === 'number') return parsedValue.raw
      throw new LumlFilterError(
        `Expected ISO date string for '${key}'. Got ${JSON.stringify(parsedValue)}`,
      )
    }
    if (parsedValue.kind === 'string') {
      return SearchEvalsUtils.stripQuotes(parsedValue.raw, true)
    }
    if (parsedValue.kind === 'list') return parsedValue.items
    throw new LumlFilterError(
      `Expected string value for attribute '${key}'. Got ${JSON.stringify(parsedValue)}`,
    )
  }

  protected static override _getComparison(raw: RawComparison): ComparisonDict {
    const comp = SearchEvalsUtils._getIdentifier(
      raw.identifierStr,
      SearchEvalsUtils.VALID_SEARCH_ATTRIBUTE_KEYS,
    ) as unknown as ComparisonDict
    const comparator = raw.comparator.toUpperCase()

    let validComparators: Set<string>
    if (comp.type === SearchEvalsUtils._ANNOTATION_IDENTIFIER) {
      validComparators = SearchEvalsUtils.VALID_ANNOTATION_COMPARATORS
    } else if (comp.type === SearchEvalsUtils._JSON_IDENTIFIER) {
      validComparators = SearchEvalsUtils.VALID_JSON_COMPARATORS
    } else if (SearchEvalsUtils.DATE_ATTRIBUTES.has(comp.key)) {
      validComparators = SearchEvalsUtils.VALID_DATE_COMPARATORS
    } else {
      validComparators = SearchEvalsUtils.VALID_STRING_ATTRIBUTE_COMPARATORS
    }

    if (!validComparators.has(comparator)) {
      let field: string
      if (comp.type === SearchEvalsUtils._ANNOTATION_IDENTIFIER) {
        field = comp.kind ? `annotations.${comp.kind}.${comp.key}` : `annotations.${comp.key}`
      } else if (comp.type === SearchEvalsUtils._JSON_IDENTIFIER) {
        field = `${comp.column ?? ''}.${comp.key}`
      } else {
        field = comp.key
      }
      throw new LumlFilterError(
        `Invalid comparator '${comparator}' for '${field}'. ` +
          `Valid comparators: ${[...validComparators].sort()}`,
      )
    }

    comp.comparator = comparator
    comp.value = SearchEvalsUtils._getValue(comp.type, comp.key, raw.parsedValue)
    return comp
  }

  private static _buildSqlFilter(parsedFilters: FilterNode[]): [string, unknown[]] {
    const sqlParts: string[] = []
    const params: unknown[] = []

    for (const item of parsedFilters) {
      if ('operator' in item) {
        sqlParts.push(item.operator)
        continue
      }
      if ('group' in item) {
        const [subSql, subParams] = SearchEvalsUtils._buildSqlFilter(item.group)
        sqlParts.push(`(${subSql})`)
        params.push(...subParams)
        continue
      }

      const { type: keyType, key, value, comparator } = item

      if (keyType === SearchEvalsUtils._ANNOTATION_IDENTIFIER) {
        const kind = (item as ComparisonDict).kind
        const kindClause = kind ? ` AND annotation_kind = '${kind}'` : ''
        const [valueExpr, valueParams] = SearchEvalsUtils._buildAnnotationValueExpr(
          comparator,
          value,
        )
        sqlParts.push(
          `EXISTS (SELECT 1 FROM eval_annotations` +
            ` WHERE eval_id = evals.id AND name = ?${kindClause} AND ${valueExpr})`,
        )
        params.push(key)
        params.push(...valueParams)
      } else if (keyType === SearchEvalsUtils._JSON_IDENTIFIER) {
        const col = (item as ComparisonDict).column!
        const expr = `json_extract(${col}, '$.${key}')`
        if (comparator === 'ILIKE') {
          sqlParts.push(`UPPER(${expr}) LIKE UPPER(?)`)
          params.push(value)
        } else if (comparator === 'IN') {
          sqlParts.push(`${expr} IN (${(value as unknown[]).map(() => '?').join(',')})`)
          params.push(...(value as unknown[]))
        } else if (comparator === 'NOT IN') {
          sqlParts.push(`${expr} NOT IN (${(value as unknown[]).map(() => '?').join(',')})`)
          params.push(...(value as unknown[]))
        } else {
          sqlParts.push(`${expr} ${comparator} ?`)
          params.push(value)
        }
      } else {
        if (comparator === 'ILIKE') {
          sqlParts.push(`UPPER(${key}) LIKE UPPER(?)`)
          params.push(value)
        } else if (comparator === 'IN') {
          sqlParts.push(`${key} IN (${(value as unknown[]).map(() => '?').join(',')})`)
          params.push(...(value as unknown[]))
        } else if (comparator === 'NOT IN') {
          sqlParts.push(`${key} NOT IN (${(value as unknown[]).map(() => '?').join(',')})`)
          params.push(...(value as unknown[]))
        } else {
          sqlParts.push(`${key} ${comparator} ?`)
          params.push(value)
        }
      }
    }

    return [sqlParts.join(' '), params]
  }

  static override parseSearchFilter(filterString: string | null | undefined): FilterNode[] {
    if (!filterString) return []
    const preprocessed = SearchEvalsUtils.preprocessFilter(filterString)
    try {
      return SearchEvalsUtils._parseFilter(preprocessed)
    } catch (e) {
      if (e instanceof LumlFilterError) throw e
      throw new LumlFilterError(`Error on parsing filter '${filterString}'`)
    }
  }

  static validateFilterString(filterString: string | null | undefined): void {
    SearchEvalsUtils.parseSearchFilter(filterString)
  }

  static toSql(filterString: string | null | undefined): [string, unknown[]] {
    const parsed = SearchEvalsUtils.parseSearchFilter(filterString)
    return SearchEvalsUtils._buildSqlFilter(parsed)
  }
}

// ─── SearchTracesUtils ────────────────────────────────────────────────────────

export class SearchTracesUtils extends SearchUtils {
  static readonly VALID_SEARCH_ATTRIBUTE_KEYS: Set<string> = new Set()
  static readonly ATTRIBUTES_PREFIX = 'attributes'
  static readonly ANNOTATION_PREFIX = 'annotations'
  static readonly ANNOTATION_KINDS = new Set(['feedback', 'expectation', 'expectations'])
  static readonly EVALS_COLUMN = 'evals'
  static readonly STATE_COLUMN = 'state'

  static readonly TRACE_COLUMNS = new Set([
    'trace_id',
    'id',
    'execution_time',
    'span_count',
    'created_at',
    'state',
  ])
  static readonly NUMERIC_TRACE_COLUMNS = new Set(['execution_time', 'span_count'])
  static readonly DATE_TRACE_COLUMNS = new Set(['created_at'])

  static readonly STATE_NAME_MAP: Record<string, number> = {
    ok: 1,
    error: 2,
    in_progress: 3,
    state_unspecified: 0,
    unspecified: 0,
  }

  private static readonly _SPAN_ATTR_IDENTIFIER = 'span_attribute'
  private static readonly _ANNOTATION_IDENTIFIER = 'annotation'
  private static readonly _TRACE_COLUMN_IDENTIFIER = 'trace_column'
  private static readonly _EVALS_IDENTIFIER = 'evals'

  static readonly VALID_COMPARATORS = new Set([
    '=',
    '!=',
    '>',
    '>=',
    '<',
    '<=',
    'LIKE',
    'ILIKE',
    'IN',
    'NOT IN',
  ])
  static readonly VALID_NUMERIC_COMPARATORS = new Set(['=', '!=', '>', '>=', '<', '<='])
  static readonly VALID_STRING_COMPARATORS = new Set(['=', '!=', 'LIKE', 'ILIKE', 'IN', 'NOT IN'])
  static readonly VALID_DATE_COMPARATORS = new Set(['=', '!=', '>', '>=', '<', '<='])
  static readonly VALID_STATE_COMPARATORS = new Set(['=', '!=', 'IN', 'NOT IN'])

  private static _resolveStateValue(raw: unknown): number {
    if (typeof raw === 'string') {
      const mapped = SearchTracesUtils.STATE_NAME_MAP[raw.toLowerCase()]
      if (mapped === undefined) {
        throw new LumlFilterError(
          `Invalid state value '${raw}'. ` +
            `Valid values: ${Object.keys(SearchTracesUtils.STATE_NAME_MAP).sort()} or integer 0-3.`,
        )
      }
      return mapped
    }
    return Number(raw)
  }

  protected static override _getIdentifier(
    identifierStr: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _validAttributes: Set<string>,
  ): Record<string, unknown> {
    identifierStr = SearchTracesUtils.trimBackticks(identifierStr.trim())
    const dotIdx = identifierStr.indexOf('.')

    // Bare attribute — trace columns or evals
    if (dotIdx === -1) {
      const key = SearchTracesUtils.trimBackticks(
        SearchTracesUtils.stripQuotes(identifierStr),
      ).toLowerCase()
      if (SearchTracesUtils.TRACE_COLUMNS.has(key)) {
        return { type: SearchTracesUtils._TRACE_COLUMN_IDENTIFIER, key }
      }
      if (key === SearchTracesUtils.EVALS_COLUMN) {
        return { type: SearchTracesUtils._EVALS_IDENTIFIER, key }
      }
      throw new LumlFilterError(
        `Invalid field '${identifierStr}'. ` +
          `Bare fields: ${[...SearchTracesUtils.TRACE_COLUMNS, SearchTracesUtils.EVALS_COLUMN].sort()}. ` +
          `For span attributes use: attributes.<key>. ` +
          `For annotations use: annotations.<name>.`,
      )
    }

    const prefix = identifierStr.slice(0, dotIdx)
    const rawKey = identifierStr.slice(dotIdx + 1)
    const prefixLower = prefix.toLowerCase()

    // annotations.<name>  OR  annotations.<kind>.<name>
    if (prefixLower === SearchTracesUtils.ANNOTATION_PREFIX) {
      const kindDot = rawKey.indexOf('.')
      if (kindDot !== -1) {
        const kindStr = rawKey.slice(0, kindDot).toLowerCase()
        if (SearchTracesUtils.ANNOTATION_KINDS.has(kindStr)) {
          const kind = kindStr === 'expectations' ? 'expectation' : kindStr
          const annName = SearchTracesUtils.trimBackticks(
            SearchTracesUtils.stripQuotes(rawKey.slice(kindDot + 1)),
          )
          return { type: SearchTracesUtils._ANNOTATION_IDENTIFIER, kind, key: annName }
        }
      }
      const annName = SearchTracesUtils.trimBackticks(SearchTracesUtils.stripQuotes(rawKey))
      return { type: SearchTracesUtils._ANNOTATION_IDENTIFIER, kind: null, key: annName }
    }

    // annotations_feedback.<name>
    if (prefixLower === 'annotations_feedback') {
      const annName = SearchTracesUtils.trimBackticks(SearchTracesUtils.stripQuotes(rawKey))
      return {
        type: SearchTracesUtils._ANNOTATION_IDENTIFIER,
        kind: 'feedback',
        key: annName,
      }
    }

    // annotations_expectation.<name>  /  annotations_expectations.<name>
    if (prefixLower === 'annotations_expectation' || prefixLower === 'annotations_expectations') {
      const annName = SearchTracesUtils.trimBackticks(SearchTracesUtils.stripQuotes(rawKey))
      return {
        type: SearchTracesUtils._ANNOTATION_IDENTIFIER,
        kind: 'expectation',
        key: annName,
      }
    }

    // attributes.<key>
    if (prefixLower === SearchTracesUtils.ATTRIBUTES_PREFIX) {
      const key = SearchTracesUtils.trimBackticks(SearchTracesUtils.stripQuotes(rawKey))
      return { type: SearchTracesUtils._SPAN_ATTR_IDENTIFIER, key }
    }

    throw new LumlFilterError(
      `Invalid field prefix '${prefix}'. ` +
        `Bare fields: ${[...SearchTracesUtils.TRACE_COLUMNS, SearchTracesUtils.EVALS_COLUMN].sort()}. ` +
        `For span attributes use: attributes.<key>. ` +
        `For annotations use: annotations.<name>.`,
    )
  }

  protected static override _getValue(
    identifierType: string,
    key: string,
    parsedValue: ParsedValue,
  ): unknown {
    if (
      identifierType === SearchTracesUtils._TRACE_COLUMN_IDENTIFIER &&
      key === SearchTracesUtils.STATE_COLUMN
    ) {
      if (parsedValue.kind === 'number') return Math.round(parseFloat(parsedValue.raw))
      if (parsedValue.kind === 'string') {
        return SearchTracesUtils._resolveStateValue(
          SearchTracesUtils.stripQuotes(parsedValue.raw, true),
        )
      }
      if (parsedValue.kind === 'list') {
        return parsedValue.items.map((v) => SearchTracesUtils._resolveStateValue(v))
      }
      throw new LumlFilterError(
        `Expected state name or integer for 'state'. Got ${JSON.stringify(parsedValue)}`,
      )
    }

    if (
      identifierType === SearchTracesUtils._TRACE_COLUMN_IDENTIFIER &&
      SearchTracesUtils.DATE_TRACE_COLUMNS.has(key)
    ) {
      if (parsedValue.kind === 'string') {
        const dateStr = SearchTracesUtils.stripQuotes(parsedValue.raw, true)
        SearchTracesUtils.validateDateString(dateStr, key)
        return dateStr
      }
      if (parsedValue.kind === 'number') return parsedValue.raw
      throw new LumlFilterError(
        `Expected ISO date string for '${key}'. Got ${JSON.stringify(parsedValue)}`,
      )
    }

    if (parsedValue.kind === 'number') return parseFloat(parsedValue.raw)
    if (parsedValue.kind === 'string') {
      return SearchTracesUtils.stripQuotes(parsedValue.raw, true)
    }
    if (parsedValue.kind === 'list') return parsedValue.items
    if (parsedValue.kind === 'bool') return parsedValue.raw === 'TRUE'
    throw new LumlFilterError(
      `Expected string or numeric value for '${key}'. Got ${JSON.stringify(parsedValue)}`,
    )
  }

  protected static override _getComparison(raw: RawComparison): ComparisonDict {
    const comp = SearchTracesUtils._getIdentifier(
      raw.identifierStr,
      SearchTracesUtils.VALID_SEARCH_ATTRIBUTE_KEYS,
    ) as unknown as ComparisonDict
    const comparator = raw.comparator.toUpperCase()

    let validComparators: Set<string>
    if (comp.type === SearchTracesUtils._TRACE_COLUMN_IDENTIFIER) {
      const key = comp.key
      if (SearchTracesUtils.NUMERIC_TRACE_COLUMNS.has(key)) {
        validComparators = SearchTracesUtils.VALID_NUMERIC_COMPARATORS
      } else if (SearchTracesUtils.DATE_TRACE_COLUMNS.has(key)) {
        validComparators = SearchTracesUtils.VALID_DATE_COMPARATORS
      } else if (key === SearchTracesUtils.STATE_COLUMN) {
        validComparators = SearchTracesUtils.VALID_STATE_COMPARATORS
      } else {
        validComparators = SearchTracesUtils.VALID_STRING_COMPARATORS
      }
    } else if (comp.type === SearchTracesUtils._EVALS_IDENTIFIER) {
      validComparators = SearchTracesUtils.VALID_STRING_COMPARATORS
    } else {
      validComparators = SearchTracesUtils.VALID_COMPARATORS
    }

    if (!validComparators.has(comparator)) {
      throw new LumlFilterError(
        `Invalid comparator '${comparator}' for '${comp.key}'. ` +
          `Valid comparators: ${[...validComparators].sort()}`,
      )
    }

    comp.comparator = comparator
    comp.value = SearchTracesUtils._getValue(comp.type, comp.key, raw.parsedValue)
    return comp
  }

  /** Build SQL expression for comparing annotation `value` column. */
  private static _buildAnnotationValueExpr(
    comparator: string,
    value: unknown,
  ): [string, unknown[]] {
    const numericComparators = new Set(['>', '>=', '<', '<='])
    if (numericComparators.has(comparator)) {
      return [`CAST(value AS REAL) ${comparator} ?`, [value]]
    }
    if (comparator === 'ILIKE') {
      return ['UPPER(value) LIKE UPPER(?)', [value]]
    }
    if (comparator === 'IN') {
      const vals = value as unknown[]
      return [`value IN (${vals.map(() => '?').join(',')})`, vals]
    }
    if (comparator === 'NOT IN') {
      const vals = value as unknown[]
      return [`value NOT IN (${vals.map(() => '?').join(',')})`, vals]
    }
    if (typeof value === 'number') {
      const strVal = String(Number.isInteger(value) ? value : value)
      if (value === 1) {
        return comparator === '='
          ? ["(value = ? OR value = 'true')", [strVal]]
          : ["(value != ? AND value != 'true')", [strVal]]
      }
      if (value === 0) {
        return comparator === '='
          ? ["(value = ? OR value = 'false')", [strVal]]
          : ["(value != ? AND value != 'false')", [strVal]]
      }
      return [`value ${comparator} ?`, [strVal]]
    }
    return [`value ${comparator} ?`, [value]]
  }

  private static _buildSql(parsedFilters: FilterNode[]): [string, unknown[]] {
    const sqlParts: string[] = []
    const params: unknown[] = []

    for (const item of parsedFilters) {
      if ('operator' in item) {
        sqlParts.push(item.operator)
        continue
      }
      if ('group' in item) {
        const [subSql, subParams] = SearchTracesUtils._buildSql(item.group)
        sqlParts.push(`(${subSql})`)
        params.push(...subParams)
        continue
      }

      const { type: itemType, key, value, comparator } = item

      if (itemType === SearchTracesUtils._TRACE_COLUMN_IDENTIFIER) {
        const col = key === 'id' ? 'trace_id' : key
        if (key === 'execution_time') {
          sqlParts.push(`${col} ${comparator} ?`)
          params.push(Math.round(Number(value)))
        } else if (key === SearchTracesUtils.STATE_COLUMN) {
          if (comparator === 'IN') {
            sqlParts.push(`${col} IN (${(value as unknown[]).map(() => '?').join(',')})`)
            params.push(...(value as unknown[]))
          } else if (comparator === 'NOT IN') {
            sqlParts.push(`${col} NOT IN (${(value as unknown[]).map(() => '?').join(',')})`)
            params.push(...(value as unknown[]))
          } else {
            sqlParts.push(`${col} ${comparator} ?`)
            params.push(value)
          }
        } else if (key === 'trace_id' || key === 'id') {
          if (comparator === 'ILIKE') {
            sqlParts.push('UPPER(trace_id) LIKE UPPER(?)')
            params.push(value)
          } else if (comparator === 'IN') {
            sqlParts.push(`trace_id IN (${(value as unknown[]).map(() => '?').join(',')})`)
            params.push(...(value as unknown[]))
          } else if (comparator === 'NOT IN') {
            sqlParts.push(`trace_id NOT IN (${(value as unknown[]).map(() => '?').join(',')})`)
            params.push(...(value as unknown[]))
          } else {
            sqlParts.push(`trace_id ${comparator} ?`)
            params.push(value)
          }
        } else {
          sqlParts.push(`${col} ${comparator} ?`)
          params.push(value)
        }
      } else if (itemType === SearchTracesUtils._EVALS_IDENTIFIER) {
        if (comparator === '!=') {
          sqlParts.push(
            'trace_id NOT IN (SELECT DISTINCT trace_id FROM eval_traces_bridge WHERE eval_id = ?)',
          )
          params.push(value)
        } else if (comparator === 'ILIKE') {
          sqlParts.push(
            'trace_id IN (SELECT DISTINCT trace_id FROM eval_traces_bridge' +
              ' WHERE UPPER(eval_id) LIKE UPPER(?))',
          )
          params.push(value)
        } else if (comparator === 'LIKE') {
          sqlParts.push(
            'trace_id IN (SELECT DISTINCT trace_id FROM eval_traces_bridge WHERE eval_id LIKE ?)',
          )
          params.push(value)
        } else if (comparator === 'IN') {
          const vals = value as unknown[]
          sqlParts.push(
            `trace_id IN (SELECT DISTINCT trace_id FROM eval_traces_bridge` +
              ` WHERE eval_id IN (${vals.map(() => '?').join(',')}))`,
          )
          params.push(...vals)
        } else if (comparator === 'NOT IN') {
          const vals = value as unknown[]
          sqlParts.push(
            `trace_id NOT IN (SELECT DISTINCT trace_id FROM eval_traces_bridge` +
              ` WHERE eval_id IN (${vals.map(() => '?').join(',')}))`,
          )
          params.push(...vals)
        } else {
          sqlParts.push(
            'trace_id IN (SELECT DISTINCT trace_id FROM eval_traces_bridge WHERE eval_id = ?)',
          )
          params.push(value)
        }
      } else if (itemType === SearchTracesUtils._ANNOTATION_IDENTIFIER) {
        const kind = (item as ComparisonDict).kind
        const kindClause = kind ? ` AND annotation_kind = '${kind}'` : ''
        const [valueExpr, valueParams] = SearchTracesUtils._buildAnnotationValueExpr(
          comparator,
          value,
        )
        sqlParts.push(
          `trace_id IN (SELECT DISTINCT trace_id FROM span_annotations` +
            ` WHERE name = ?${kindClause} AND ${valueExpr})`,
        )
        params.push(key)
        params.push(...valueParams)
      } else {
        // _SPAN_ATTR_IDENTIFIER
        const expr = `json_extract(attributes, '$."${key}"')`
        if (comparator === 'ILIKE') {
          sqlParts.push(
            `trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE UPPER(${expr}) LIKE UPPER(?))`,
          )
          params.push(value)
        } else if (comparator === 'IN') {
          const vals = value as unknown[]
          sqlParts.push(
            `trace_id IN (SELECT DISTINCT trace_id FROM spans` +
              ` WHERE ${expr} IN (${vals.map(() => '?').join(',')}))`,
          )
          params.push(...vals)
        } else if (comparator === 'NOT IN') {
          const vals = value as unknown[]
          sqlParts.push(
            `trace_id IN (SELECT DISTINCT trace_id FROM spans` +
              ` WHERE ${expr} NOT IN (${vals.map(() => '?').join(',')}))`,
          )
          params.push(...vals)
        } else {
          sqlParts.push(
            `trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE ${expr} ${comparator} ?)`,
          )
          params.push(value)
        }
      }
    }

    return [sqlParts.join(' '), params]
  }

  static override parseSearchFilter(filterString: string | null | undefined): FilterNode[] {
    if (!filterString) return []
    const preprocessed = SearchTracesUtils.preprocessFilter(filterString)
    try {
      return SearchTracesUtils._parseFilter(preprocessed)
    } catch (e) {
      if (e instanceof LumlFilterError) throw e
      throw new LumlFilterError(`Error on parsing filter '${filterString}'`)
    }
  }

  static validateFilterString(filterString: string | null | undefined): void {
    SearchTracesUtils.parseSearchFilter(filterString)
  }

  static toSql(filterString: string | null | undefined): [string, unknown[]] {
    const parsed = SearchTracesUtils.parseSearchFilter(filterString)
    if (!parsed.length) return ['', []]
    return SearchTracesUtils._buildSql(parsed)
  }
}
