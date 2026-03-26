<template>
  <Dialog
    v-model:visible="visible"
    header="Connect a new satellite"
    :pt="dialogPt"
    modal
    :draggable="false"
  >
    <Form :resolver="satellitesResolver" :initialValues="initialValues" @submit="onSubmit">
      <div class="fields">
        <div class="field">
          <label for="name" class="label required">Name</label>
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
      <Button label="Create" fluid rounded type="submit"></Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { CreateSatelliteResponse } from '@/lib/api/satellites/interfaces'
import { Dialog, InputText, Button, Textarea, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { ref, watch } from 'vue'
import { useSatellitesStore } from '@/stores/satellites'
import { useRoute } from 'vue-router'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { satellitesResolver } from '@/utils/forms/resolvers'

type Emits = {
  create: [CreateSatelliteResponse]
}

const emits = defineEmits<Emits>()

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const visible = defineModel<boolean>('visible')

const satellitesStore = useSatellitesStore()
const route = useRoute()
const toast = useToast()

const initialValues = ref({
  name: '',
  description: '',
})
const loading = ref(false)

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  const organizationIdParam = route.params.organizationId
  const orbitIdParam = route.params.id

  const organizationId =
    typeof organizationIdParam === 'string' ? organizationIdParam : organizationIdParam?.[0]
  const orbitId = typeof orbitIdParam === 'string' ? orbitIdParam : orbitIdParam?.[0]

  try {
    if (!organizationId) {
      throw new Error('Current organization was not found')
    }
    if (!orbitId) {
      throw new Error('Current orbit was not found')
    }
    loading.value = true
    const data = await satellitesStore.createSatellite(organizationId, orbitId, initialValues.value)
    emits('create', data)
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.detail?.message || e?.message || 'Failed to create satellite'),
    )
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  if (!val) {
    initialValues.value.name = ''
    initialValues.value.description = ''
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
</style>
