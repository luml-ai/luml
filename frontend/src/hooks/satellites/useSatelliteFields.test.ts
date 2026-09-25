import { describe, expect, it } from 'vitest'
import conditionCases from '../../../../backend/tests/satellite_field_condition_cases.json'
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import {
  SatelliteFieldTypeEnum,
  type ConditionsObject,
  type Satellite,
} from '@/lib/api/satellites/interfaces'
import { useSatelliteFields } from './useSatelliteFields'

interface ConditionCase {
  name: string
  conditions: ConditionsObject[]
  current_values: Record<string, unknown>
  manifest: {
    producer_tags: string[]
    version: string
    variant: string
  }
  expected: boolean
}

describe('useSatelliteFields', () => {
  it.each(conditionCases as ConditionCase[])(
    'matches the shared condition case: $name',
    ({ conditions, current_values: currentValues, manifest, expected }) => {
      const satellite = {
        capabilities: {
          deploy: {
            version: 1,
            api_versions: [1],
            facets: ['satellite', 'deployment'],
            supported_variants: [manifest.variant],
            supported_tags_combinations: null,
            extra_fields_form_spec: [
              {
                name: 'tested',
                type: SatelliteFieldTypeEnum.text,
                values: null,
                required: false,
                validators: [],
                conditions,
              },
            ],
          },
        },
      } as unknown as Satellite
      const model = { manifest } as ModelArtifact
      const { fields, setFields } = useSatelliteFields()

      setFields(satellite, model, currentValues)

      expect(fields.value.some((field) => field.name === 'tested')).toBe(expected)
    },
  )
})
