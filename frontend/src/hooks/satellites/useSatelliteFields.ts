import type {
  ConditionsObject,
  FieldConditionObject,
  FieldOperator,
  ModelConditionObject,
  ModelTagsOperator,
  ModelVariantOperator,
  ModelVersionOperator,
  Satellite,
  SatelliteField,
} from '@/lib/api/satellites/interfaces'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { ref } from 'vue'

export const useSatelliteFields = () => {
  const fields = ref<SatelliteField[]>([])

  function compareValues(a: any, operator: FieldOperator, b: any): boolean {
    switch (operator) {
      case 'equal':
        return a === b
      case 'notEqual':
        return a !== b
      case 'gt':
        return a > b
      case 'gte':
        return a >= b
      case 'lt':
        return a < b
      case 'lte':
        return a <= b
      default:
        return false
    }
  }

  function checkModelVersion(
    modelVersion: string,
    operator: ModelVersionOperator,
    value: any,
  ): boolean {
    switch (operator) {
      case 'eq':
        return modelVersion === value
      case 'neq':
        return modelVersion !== value
    }
  }

  function checkModelTags(modelTags: string[], operator: ModelTagsOperator, value: any): boolean {
    if (!Array.isArray(value)) return true
    switch (operator) {
      case 'includes':
        return value.some(
          (pair) => Array.isArray(pair) && pair.every((tag) => modelTags.includes(tag)),
        )
      case 'notIncludes':
        return value.every(
          (pair) => Array.isArray(pair) && !pair.every((tag) => modelTags.includes(tag)),
        )
    }
  }

  function checkModelVariant(
    modelVariant: string,
    operator: ModelVariantOperator,
    value: any,
  ): boolean {
    switch (operator) {
      case 'includes':
        return value.includes(modelVariant)
      case 'notIncludes':
        return !value.includes(modelVariant)
      case 'eq':
        return value === modelVariant
      case 'neq':
        return value !== modelVariant
    }
  }

  function shouldDisplayField(
    conditions: ConditionsObject[] = [],
    currentValues: Record<string, any>,
    modelTags: string[],
    modelVersion: string,
    modelVariant: string,
  ): boolean {
    if (!conditions.length) return true

    return conditions.every((condition) => {
      const { type, body } = condition

      if (Array.isArray(body)) {
        return shouldDisplayField(body, currentValues, modelTags, modelVersion, modelVariant)
      }

      if (type === 'field') {
        const { field, operator, value } = body as FieldConditionObject
        if (operator === 'includes') {
          return field in currentValues
        } else if (operator === 'notIncludes') {
          return !(field in currentValues)
        } else {
          const currentValue = currentValues[field]
          return compareValues(currentValue, operator, value)
        }
      }

      if (type === 'model') {
        const { field, operator, value } = body as ModelConditionObject
        if (field === 'tags') {
          return checkModelTags(modelTags, operator, value)
        }
        if (field === 'version') {
          return checkModelVersion(modelVersion, operator, value)
        }
        if (field === 'variant') {
          return checkModelVariant(modelVariant, operator, value)
        }
        return false
      }

      return true
    })
  }

  function setFields(
    satellite: Satellite | null,
    model: MlModel | null,
    currentValues: Record<string, any>,
  ) {
    if (!satellite || !model) {
      fields.value = []
      return
    }

    const fieldsList = satellite.capabilities.deploy?.extra_fields_form_spec
    if (!fieldsList) {
      fields.value = []
      return
    }

    fields.value = fieldsList.filter((field) => {
      return shouldDisplayField(
        field.conditions,
        currentValues,
        model.manifest.producer_tags,
        model.manifest.version || '',
        model.manifest.variant || '',
      )
    })
  }

  return {
    fields,
    setFields,
  }
}
