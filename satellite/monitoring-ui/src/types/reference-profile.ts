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

export interface ReferenceStatItem {
  label: string
  value: string
}

export interface ReferenceProbabilityItem {
  label: string
  value: string
  width: string
}

export interface ReferenceNote {
  severity: 'info' | 'warn'
  title: string
  detail: string
}
