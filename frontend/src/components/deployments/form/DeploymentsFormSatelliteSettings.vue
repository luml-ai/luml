<template>
  <div class="column">
    <h4 class="column-title">Satellite</h4>
    <div class="fields">
      <div class="field">
        <label for="satelliteId" class="label required">Satellite</label>
        <Select
          v-model="satelliteId"
          id="satelliteId"
          name="satelliteId"
          placeholder="Select satellite"
          fluid
          :options="satellitesGroups"
          option-label="name"
          option-value="id"
          option-disabled="disabled"
          option-group-label="label"
          option-group-children="items"
        >
          <template #option="{ option }">
            <div class="option">
              <div class="option-text">
                {{ option.name }}
              </div>
              <div class="option-icons">
                <Rocket
                  v-if="option.capabilities.deploy"
                  :size="16"
                  color="var(--p-icon-muted-color)"
                ></Rocket>
              </div>
              <div v-if="option.errorMessage" class="option-message">
                <Info :size="12" class="option-message-icon" /> {{ option.errorMessage }}
              </div>
            </div>
          </template>
        </Select>
      </div>
      <div v-if="fields?.length" class="custom-variables">
        <div class="custom-variables__content">
          <FormField
            v-for="(field, index) in fields"
            :key="field.key"
            :name="`satelliteFields.${index}.value`"
            class="field"
          >
            <label class="label" :class="{ required: field.required }">{{ field.label }}</label>
            <template v-if="field.type === SatelliteFieldTypeEnum.boolean">
              <ToggleButton
                v-model="field.value as unknown as boolean"
                size="small"
                @change="updateFields"
              ></ToggleButton>
            </template>
            <template v-else-if="field.type === SatelliteFieldTypeEnum.dropdown">
              <Select
                v-model="field.value"
                :options="field.values || []"
                :required="field.required"
                size="small"
                option-label="label"
                option-value="value"
                placeholder="Select value"
                @change="updateFields"
              ></Select>
            </template>
            <template v-else-if="field.type === SatelliteFieldTypeEnum.number">
              <InputNumber
                v-model="field.value as unknown as number"
                placeholder="Enter value"
                size="small"
                :required="field.required"
                @change="updateFields"
              ></InputNumber>
            </template>
            <template v-else>
              <InputText
                v-model="field.value as string"
                placeholder="Enter value"
                size="small"
                :required="field.required"
                @change="updateFields"
              ></InputText>
            </template>
          </FormField>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldInfo } from '../deployments.interfaces'
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { SatelliteFieldTypeEnum, type SatelliteField } from '@/lib/api/satellites/interfaces'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useSatellitesStore } from '@/stores/satellites'
import { Select, useToast, InputText, InputNumber, ToggleButton } from 'primevue'
import { computed, nextTick, onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { FormField } from '@primevue/forms'
import { Rocket, Info } from 'lucide-vue-next'
import { useSatelliteFields } from '@/hooks/satellites/useSatelliteFields'
import { watch } from 'vue'

type Props = {
  selectedModel: MlModel | null
}

const props = defineProps<Props>()

const satellitesStore = useSatellitesStore()
const route = useRoute()
const toast = useToast()
const { fields: fieldsForShowing, setFields } = useSatelliteFields()

const satelliteId = defineModel<string | null>('satelliteId')
const fields = defineModel<FieldInfo<string | number | boolean>[]>('fields')

const ignoreWatch = ref(false)

const filteredSatellites = computed(() => {
  const model = props.selectedModel
  if (!model) return []
  return satellitesStore.satellitesList.filter((satellite) => !!satellite.capabilities.deploy)
})

const satellitesOptions = computed(() => {
  const model = props.selectedModel
  if (!model) return []
  return filteredSatellites.value.map((satellite) => {
    const variantValid = !!satellite.capabilities.deploy?.supported_variants?.includes(
      model.manifest.variant,
    )
    const supportedTagsEmpty = !satellite.capabilities.deploy?.supported_tags_combinations
    const tagsSupported = !!satellite.capabilities.deploy?.supported_tags_combinations?.find(
      (combination) => {
        return combination.every((tag) => model.manifest.producer_tags.includes(tag))
      },
    )
    const tagsValid = supportedTagsEmpty || tagsSupported
    return {
      ...satellite,
      disabled: !variantValid || !tagsValid,
      errorMessage: getSatelliteErrorMessage(variantValid, tagsValid),
    }
  })
})

const satellitesGroups = computed(() => {
  const disabled = satellitesOptions.value.filter((satellite) => satellite.disabled)
  const enabled = satellitesOptions.value.filter((satellite) => !satellite.disabled)
  const groups = []
  if (enabled.length > 0) {
    groups.push({
      label: 'Available satellites',
      items: enabled,
    })
  }
  if (disabled.length > 0) {
    groups.push({
      label: 'Incompatible satellites',
      items: disabled,
    })
  }
  return groups
})

function getSatelliteErrorMessage(variantValid: boolean, tagsValid: boolean) {
  if (!variantValid) return 'The satellite does not support this model variant'
  if (!tagsValid)
    return 'The model does not contain a combination of tags required by the satellite'
  return null
}

async function getSatellites() {
  try {
    const organizationIdParam = route.params.organizationId
    const orbitIdParam = route.params.id

    const organizationId =
      typeof organizationIdParam === 'string' ? organizationIdParam : organizationIdParam[0]

    const orbitId = typeof orbitIdParam === 'string' ? orbitIdParam : orbitIdParam[0]

    const list = await satellitesStore.loadSatellites(organizationId, orbitId)
    satellitesStore.setList(list)
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
  }
}

function updateFields() {
  const satellite =
    satellitesStore.satellitesList.find((satellite) => satellite.id === satelliteId.value) || null
  setFields(
    satellite,
    props.selectedModel,
    fields.value?.reduce(
      (acc, field) => {
        acc[field.key] = field.value
        return acc
      },
      {} as Record<string, any>,
    ) || {},
  )
}

function getFieldInfo(data: SatelliteField) {
  return {
    key: data.name,
    value: null,
    label: data.name,
    required: data.required,
    validators: data.validators,
    values: data.values,
    type: data.type,
  }
}

function removeOldFields(currentFields: string[]) {
  const updatedFields = fields.value?.filter((field) => {
    return currentFields.includes(field.key)
  })
  fields.value = updatedFields
}

function addNewFields(newFields: SatelliteField[]) {
  const notExistingFields = newFields.filter((field) => {
    return !fields.value?.some((f) => f.key === field.name)
  })
  fields.value = [...(fields.value || []), ...notExistingFields.map(getFieldInfo)]
}

watch(
  [() => props.selectedModel, () => satelliteId.value, () => fields.value],
  (values, prevValues) => {
    const isModelChanged = values[0] !== prevValues[0]
    const isSatelliteChanged = values[1] !== prevValues[1]
    const isFieldsChanged = JSON.stringify(values[2]) !== JSON.stringify(prevValues[2])
    const someDataChanged = isModelChanged || isSatelliteChanged || isFieldsChanged
    if (ignoreWatch.value || !someDataChanged) return
    updateFields()
  },
  { deep: true },
)

watch(fieldsForShowing, (newFields) => {
  ignoreWatch.value = true
  removeOldFields(newFields.map((field) => field.name))
  nextTick(() => {
    addNewFields(newFields)
    ignoreWatch.value = false
  })
})

onBeforeMount(() => {
  getSatellites()
})
</script>

<style scoped>
.column {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
}

.column-title {
  font-weight: 500;
  margin-bottom: 20px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.textarea {
  resize: none;
  height: 72px;
}

:deep(.p-disabled .p-select-dropdown) {
  display: none;
}

.custom-variables {
  padding: 12px;
  border-radius: var(--p-border-radius-lg);
  background-color: var(--p-badge-secondary-background);
}

.custom-variables .label {
  font-size: 12px;
}

.custom-variables__content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dropdown-title {
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: var(--p-select-option-group-font-weight);
  color: var(--p-select-option-group-color);
}

.option {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  column-gap: 15px;
}

.option-icons {
  flex: 0 0 auto;
  display: flex;
  gap: 6px;
}

.option-message {
  grid-column: span 2;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 2px;
}

.option-message-icon {
  flex: 0 0 auto;
}
</style>
