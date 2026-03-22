import { FilterOperatorEnum } from './filter.interface'

export const FILTER_OPERATORS = [
  {
    label: '=',
    value: FilterOperatorEnum.equal,
  },
  {
    label: '!=',
    value: FilterOperatorEnum.notEqual,
  },
  {
    label: '>',
    value: FilterOperatorEnum.gt,
  },
  {
    label: '>=',
    value: FilterOperatorEnum.gte,
  },
  {
    label: '<',
    value: FilterOperatorEnum.lt,
  },
  {
    label: '<=',
    value: FilterOperatorEnum.lte,
  },
]
