<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="popup-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>satellite settings</span>
      </h2>
    </template>
    <div class="dialog-content">
      <Form
        id="satellitesEditForm"
        :initial-values
        :resolver="satellitesResolver"
        @submit="onSubmit"
      >
        <div class="fields">
          <div class="field">
            <label for="name" class="label">Name</label>
            <InputText
              v-model="initialValues.name"
              id="name"
              name="name"
              type="text"
              placeholder="Name your satellite"
              fluid
            />
          </div>
          <div class="field">
            <label for="description" class="label">Description</label>
            <Textarea
              v-model="initialValues.description"
              id="description"
              name="description"
              placeholder="Describe your satellite"
              fluid
              class="textarea"
            ></Textarea>
          </div>
        </div>
      </Form>
    </div>
    <template #footer>
      <Button
        severity="warn"
        variant="outlined"
        :disabled="loading"
        @click="deleteDialogVisible = true"
      >
        unpair satellite
      </Button>
      <Button type="submit" :disabled="loading" form="satellitesEditForm">save changes</Button>
    </template>
  </Dialog>
  <SatelliteDelete
    v-model:visible="deleteDialogVisible"
    :organization-id="organizationId"
    :orbit-id="orbitId"
    :satellite-id="props.data.id"
    :name="props.data.name"
  />
</template>

<script setup lang="ts">
import type { Satellite } from '@/lib/api/satellites/interfaces'
import { Dialog, InputText, Textarea, Button, useToast } from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { satellitesResolver } from '@/utils/forms/resolvers'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useSatellitesStore } from '@/stores/satellites'
import { useRoute } from 'vue-router'
import SatelliteDelete from './SatelliteDelete.vue'

type Props = {
  data: Satellite
}

const props = defineProps<Props>()

const toast = useToast()
const route = useRoute()
const satellitesStore = useSatellitesStore()

const dialogPT = {
  footer: {
    class: 'organization-edit-footer',
  },
}

const visible = defineModel<boolean>('visible')
const deleteDialogVisible = ref(false)
const loading = ref(false)
const initialValues = ref({
  name: '',
  description: '',
})

const organizationId = computed(() => {
  const id = route.params.organizationId
  if (!id || Array.isArray(id)) throw new Error('Current organization was not found')
  return id
})
const orbitId = computed(() => {
  const id = route.params.id
  if (!id || Array.isArray(id)) throw new Error('Current orbit was not found')
  return id
})

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    loading.value = true
    await satellitesStore.updateSatellite(
      organizationId.value,
      orbitId.value,
      props.data.id,
      initialValues.value,
    )
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || 'Failed to update satellite'))
  } finally {
    toast.add(simpleSuccessToast(`${props.data.name} updated successfully.`))
    loading.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    initialValues.value.name = props.data.name
    initialValues.value.description = props.data.description
  }
})
</script>

<style scoped>
.fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 28px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.textarea {
  height: 72px;
  resize: none;
}

.popup-title {
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 16px;
  font-weight: 500;
}
</style>
