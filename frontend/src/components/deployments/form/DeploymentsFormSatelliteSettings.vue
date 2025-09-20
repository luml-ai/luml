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
          :options="satellitesStore.satellitesList"
          option-label="name"
          option-value="id"
        >
          <template #header>
            <div class="dropdown-title">Available satellites</div>
          </template>
          <template #option="{ option }">
            <div class="option">
              <div class="option-text">{{ option.name }}</div>
              <div class="option-icons">
                <Rocket
                  v-if="option.capabilities.deploy"
                  :size="16"
                  color="var(--p-icon-muted-color)"
                ></Rocket>
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
            <label class="label">{{ field.label }}</label>
            <InputText v-model="field.value" placeholder="Enter value" size="small"></InputText>
          </FormField>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldInfo } from '../deployments.interfaces'
import type { Satellite } from '@/lib/api/satellites/interfaces'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useSatellitesStore } from '@/stores/satellites'
import { Select, useToast, InputText } from 'primevue'
import { computed, onBeforeMount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FormField } from '@primevue/forms'
import { Rocket } from 'lucide-vue-next'

const satellitesStore = useSatellitesStore()
const route = useRoute()
const toast = useToast()

const satelliteId = defineModel<number | null>('satelliteId')
const fields = defineModel<FieldInfo[]>('fields')

const currentSatellite = computed(() => {
  if (!satelliteId.value) return null
  const satellite = satellitesStore.satellitesList.find(
    (satellite) => satellite.id === satelliteId.value,
  )
  return satellite || null
})

async function getSatellites() {
  try {
    const organizationId = +route.params.organizationId
    const orbitId = +route.params.id
    if (!organizationId) {
      throw new Error('Current organization was not found')
    }
    if (!orbitId) {
      throw new Error('Current orbit was not found')
    }
    const list = await satellitesStore.loadSatellites(organizationId, orbitId)
    satellitesStore.setList(list)
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
  }
}

function onSatelliteChange(satellite: Satellite | null) {
  if (satellite) {
    const inputs = satellite.capabilities.deploy?.inputs
    fields.value = inputs?.map((input) => getFieldFromInput(input)) || []
  } else {
    fields.value = []
  }
}

function getFieldFromInput(input: string) {
  return { key: input, label: input, value: '' }
}

watch(currentSatellite, onSatelliteChange)

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
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
}

.option-icons {
  flex: 0 0 auto;
  display: flex;
  gap: 6px;
}
</style>
