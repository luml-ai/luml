import type { ValidateResponseItem } from '@experiments/interfaces/interfaces'

export interface FilterItem {
  id: string
  field: string | null
  operator: FilterOperatorEnum | null
  value: string | number | null
}

export enum FilterOperatorEnum {
  equal = '=',
  notEqual = '!=',
  gt = '>',
  gte = '>=',
  lt = '<',
  lte = '<=',
  like = 'LIKE',
  ilike = 'ILIKE',
  in = 'IN',
  notIn = 'NOT IN',
  contains = 'CONTAINS',
}

export interface FilterItemProps {
  fields: { name: string; type: 'string' | 'number' | 'boolean' | 'unknown' }[]
  errors?: { [key: string]: string } & { global?: string }
}

export interface FilterProps {
  fields: { name: string; type: 'string' | 'number' | 'boolean' | 'unknown' }[]
  disabled?: boolean
  errors?: FilterItemsErrors
  asyncValidateCallback?: (filters: FilterItem[]) => Promise<ValidateResponseItem[]>
}

export interface FilterEmits {
  (e: 'apply', filters: FilterItem[]): void
}

export interface FilterItemEmits {
  (e: 'remove'): void
  (e: 'clear-errors'): void
}

export type FilterItemsErrors = { [key: string]: string }[]
