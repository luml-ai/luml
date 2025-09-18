<template>
  <Dialog v-model:visible="visible" header="Create a new secret" modal :draggable="false" :pt="dialogPt">
    <Form :initial-values="formData" :resolver="createSecretResolver" @submit="onSubmit" class="form">
      <div class="form-item">
          <label for="name" class="label required">Name</label>
          <InputText v-model="formData.name" id="name" name="name" placeholder="Name your secret key" fluid />
        </div>

        <div class="form-item">
          <label for="value" class="label required">Secret key</label>
          <Password v-model="formData.value" id="value" name="value" :feedback="false" placeholder="Enter secret key"
            toggleMask fluid />
        </div>

        <div class="form-item">
          <label for="tags" class="label">Tags</label>
          <AutoComplete v-model="formData.tags" id="tags" name="tags" fluid multiple placeholder="Type to add tags"
            :suggestions="autocompleteItems" @complete="searchTags" />
        </div>
      <Button type="submit" fluid rounded :loading="loading">
        Create
      </Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions, AutoCompleteCompleteEvent } from 'primevue'
import { Dialog, Button, InputText, AutoComplete, Password, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { ref, computed } from 'vue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useSecretsStore } from '@/stores/orbit-secrets'
import type { CreateSecretPayload } from '@/lib/api/orbit-secrets/interfaces'
import { createSecretResolver } from '@/utils/forms/resolvers'
import { useOrbitsStore } from '@/stores/orbits'

type Props = {
  organizationId?: number
  orbitId?: number
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible')

const dialogPt: DialogPassThroughOptions = {
  root: { style: 'max-width: 500px; width: 100%;' },
  header: { style: 'padding: 28px; text-transform: uppercase; font-size: 20px;' },
  content: { style: 'padding: 0 28px 28px;' },
}

const secretsStore = useSecretsStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const loading = ref(false)

const getInitialFormData = (): CreateSecretPayload => ({
  name: '',
  value: '',
  tags: [],
})

const formData = ref<CreateSecretPayload>(getInitialFormData())

const existingTags = computed(() => secretsStore.existingTags)
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = [
    event.query,
    ...existingTags.value.filter((tag) =>
      tag.toLowerCase().includes(event.query.toLowerCase()),
    ),
  ]
}

function getRequestInfo() {
  if (props.organizationId && props.orbitId) {
    return { organizationId: props.organizationId, orbitId: props.orbitId }
  }
  const orbit = orbitsStore.currentOrbitDetails
  if (orbit?.organization_id && orbit?.id) {
    return { organizationId: orbit.organization_id, orbitId: orbit.id }
  }
}

function resetForm() {
  formData.value = getInitialFormData()
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    loading.value = true
    const req = getRequestInfo()
    if (!req) throw new Error('Orbit info is missing')

    await secretsStore.addSecret(req.organizationId, req.orbitId, { ...formData.value })
    visible.value = false
    resetForm()
    toast.add(simpleSuccessToast('Secret created successfully'))
  } catch (e: any) {
    toast.add(
      simpleErrorToast(
        e?.response?.data?.detail || e.message || 'Failed to create secret',
      ),
    )
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>

.form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.label {
  font-weight: 400;
  align-self: flex-start;
}

.form-item:last-of-type input,
.form-item:last-of-type .p-password,
.form-item:last-of-type .p-autocomplete {
  margin-bottom: 29px;
}

</style>
