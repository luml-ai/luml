export interface FilterItem {
  id: string
  field: string
  operator: FilterOperatorEnum
  value: string
}

export enum FilterOperatorEnum {
  equal = 'equal',
  notEqual = 'notEqual',
  gt = 'gt',
  gte = 'gte',
  lt = 'lt',
  lte = 'lte',
}

export interface FilterItemProps {
  fields: string[]
}

export interface FilterProps {
  fields: string[]
  disabled?: boolean
}

export interface FilterEmits {
  (e: 'apply', filters: FilterItem[]): void
}

export interface FilterItemEmits {
  (e: 'remove'): void
}
