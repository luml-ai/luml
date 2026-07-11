import { FilterOperatorEnum } from './filter.interface'
import { z } from 'zod'

export const FILTER_OPERATORS = [
  {
    label: '=',
    value: FilterOperatorEnum.equal,
    availableTypes: ['string', 'number', 'boolean'],
  },
  {
    label: '!=',
    value: FilterOperatorEnum.notEqual,
    availableTypes: ['string', 'number', 'boolean'],
  },
  {
    label: '>',
    value: FilterOperatorEnum.gt,
    availableTypes: ['number'],
  },
  {
    label: '>=',
    value: FilterOperatorEnum.gte,
    availableTypes: ['number'],
  },
  {
    label: '<',
    value: FilterOperatorEnum.lt,
    availableTypes: ['number'],
  },
  {
    label: '<=',
    value: FilterOperatorEnum.lte,
    availableTypes: ['number'],
  },
  {
    label: 'LIKE',
    value: FilterOperatorEnum.like,
    availableTypes: ['string'],
  },
  {
    label: 'ILIKE',
    value: FilterOperatorEnum.ilike,
    availableTypes: ['string'],
  },
  {
    label: 'IN',
    value: FilterOperatorEnum.in,
    availableTypes: ['string'],
  },
  {
    label: 'NOT IN',
    value: FilterOperatorEnum.notIn,
    availableTypes: ['string'],
  },
  {
    label: 'CONTAINS',
    value: FilterOperatorEnum.contains,
    availableTypes: ['string'],
  },
]

export const filterItemSchema = z.object({
  field: z.string().min(1, 'Field is required'),
  operator: z.string().min(1, 'Operator is required'),
  value: z.any().refine((v) => v !== null && v !== '', 'Value is required'),
})

export const formSchema = z.object({
  items: z.array(filterItemSchema).min(1, 'Add at least one filter'),
})
