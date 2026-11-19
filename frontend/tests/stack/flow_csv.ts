// Reads the CSV files the traces and evals tables export (RFC 4180: quoted fields may hold
// commas, quotes doubled, and line breaks).

/** The header and the rows of a CSV text, each row as a record by column name. */
export function parseCsv(text: string): { header: string[]; rows: Record<string, string>[] } {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let quoted = false
  for (let index = 0; index < text.length; index++) {
    const char = text[index]!
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"'
        index++
      } else if (char === '"') quoted = false
      else field += char
    } else if (char === '"') quoted = true
    else if (char === ',') {
      record.push(field)
      field = ''
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[index + 1] === '\n') index++
      record.push(field)
      records.push(record)
      record = []
      field = ''
    } else field += char
  }
  if (field || record.length) {
    record.push(field)
    records.push(record)
  }
  const [header = [], ...rows] = records
  return {
    header,
    rows: rows.map((values) => Object.fromEntries(header.map((name, i) => [name, values[i]!]))),
  }
}
