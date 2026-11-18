export enum ReferenceProfileView {
  STRUCTURE = 'structure',
  RAW_JSON = 'raw-json',
}

export interface ReferenceProfileSummaryItem {
  label: string
  value: string
}

export enum JsonValueKind {
  NUMBER = 'number',
  STRING = 'string',
  MUTED = 'muted',
}

export interface JsonEntry {
  key: string
  value: unknown
}
