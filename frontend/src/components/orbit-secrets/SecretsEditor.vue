<template>
  <Dialog :visible="props.visible" @update:visible="emit('update:visible', $event)" position="topright"
    :draggable="false" style="margin-top: 80px; height: 86%; width: 420px" :pt="dialogPt">
    <template #header>
      <h2 class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>Secret settings</span>
      </h2>
    </template>
    <Form id="secret-edit-form" :initial-values="formData" :resolver="updateSecretResolver" @submit="onSubmit"
      class="form" validate-on-submit>
      <div class="form-item">
        <label for="name" class="label">Name</label>
        <InputText v-model="formData.name" id="name" name="name" fluid />
      </div>

      <div class="form-item">
        <label for="value" class="label">Secret key</label>
        <Password v-model="formData.value" id="value" name="value" :feedback="false" toggleMask fluid
          :key="props.secret?.id" />
      </div>

      <div class="form-item">
        <label for="tags" class="label">Tags</label>
        <AutoComplete v-model="formData.tags" id="tags" name="tags" placeholder="Type to add tags" fluid multiple
          :suggestions="autocompleteItems" @complete="searchTags" />
      </div>
    </Form>
    <template #footer>
      <div class="footer-actions">
        <Button outlined severity="warn" :loading="deleteLoading" @click="onComponentDelete">
          delete key
        </Button>
        <Button type="submit" form="secret-edit-form" :loading="updateLoading">
          save changes
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, Button, InputText, AutoComplete, Password, useToast, useConfirm } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { Bolt } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { updateSecretResolver } from '@/utils/forms/resolvers'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useOrbitsStore } from '@/stores/orbits'
import type { OrbitSecret, UpdateSecretPayload } from '@/lib/api/orbit-secrets/interfaces'
import type { AutoCompleteCompleteEvent } from 'primevue'
import { deleteSecretConfirmation } from "@/lib/primevue/data/confirm"

interface Props {
  visible: boolean
  secret?: OrbitSecret | null
}

const props = defineProps<Props>()
const emit = defineEmits(['update:visible'])

const secretsStore = useSecretsStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()

const dialogPt = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

const formData = ref<UpdateSecretPayload>({
  id: props.secret?.id || 0,
  name: props.secret?.name || '',
  value: '',
  tags: props.secret?.tags ? [...props.secret.tags] : [],
})

async function loadSecretDetails() {
  if (!props.secret?.id) return

  const orbit = orbitsStore.currentOrbitDetails
  if (!orbit?.organization_id || !orbit?.id) return

  try {
    const fullSecret = await secretsStore.getSecretById(
      orbit.organization_id,
      orbit.id,
      props.secret.id
    )

    if (fullSecret) {
      formData.value = {
        id: fullSecret.id,
        name: fullSecret.name || '',
        value: fullSecret.value || '',
        tags: fullSecret.tags ? [...fullSecret.tags] : [],
      }
    }
  } catch (error) {
    toast.add(
      simpleErrorToast('Failed to load secret details'
      )
    )
  }
}

watch(
  () => props.secret,
  async (secret) => {
    if (secret?.id) {
      await loadSecretDetails()
    } else {
      formData.value = {
        id: 0,
        name: '',
        value: '',
        tags: [],
      }
    }
  },
  { immediate: true }
)

watch(
  () => props.visible,
  async (visible) => {
    if (visible && props.secret?.id) {
      await loadSecretDetails()
    }
  }
)

const updateLoading = ref(false)
const deleteLoading = ref(false)

const existingTags = computed(() => secretsStore.existingTags)
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = [
    event.query,
    ...existingTags.value.filter((tag) =>
      tag.toLowerCase().includes(event.query.toLowerCase())
    ),
  ]
}

function getRequestInfo() {
  const orbit = orbitsStore.currentOrbitDetails
  if (orbit?.organization_id && orbit?.id) {
    return { organizationId: orbit.organization_id, orbitId: orbit.id }
  }
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid || !props.secret) return
  try {
    updateLoading.value = true
    const req = getRequestInfo()
    if (!req) throw new Error('Orbit info is missing')

    const updatePayload: UpdateSecretPayload = {
      id: props.secret.id,
      name: formData.value.name?.trim() || props.secret.name || '',
      tags: formData.value.tags,
    }

    if (formData.value.value?.trim()) {
      updatePayload.value = formData.value.value.trim()
    }

    await secretsStore.updateSecret(req.organizationId, req.orbitId, updatePayload)
    toast.add(simpleSuccessToast('Secret updated successfully'))
    emit('update:visible', false)
  } catch (e: any) {
    toast.add(
      simpleErrorToast(
        e?.response?.data?.detail || e.message || 'Failed to update secret'
      )
    )
  } finally {
    updateLoading.value = false
  }
}

const confirm = useConfirm()

function onComponentDelete() {
  confirm.require({
    ...deleteSecretConfirmation,
    accept: async () => {
      await onDelete()
    }
  })
}

async function onDelete() {
  if (!props.secret) return
  try {
    deleteLoading.value = true
    const req = getRequestInfo()
    if (!req) throw new Error('Orbit info is missing')

    await secretsStore.deleteSecret(req.organizationId, req.orbitId, props.secret.id)
    toast.add(simpleSuccessToast('Secret deleted successfully'))
    emit('update:visible', false)
  } catch (e: any) {
    const errorMessage = e?.response?.data?.detail || e.message || 'Failed to delete secret'
    
    if (errorMessage.includes('used') || errorMessage.includes('deployment') || errorMessage.includes('active')) {
      toast.add(simpleErrorToast('The secret is currently used by active deployments'))
    } else {
      toast.add(simpleErrorToast(errorMessage))
    }
  } finally {
    deleteLoading.value = false
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.footer-actions {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.dialog-title {
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 16px;
  font-weight: 500;
}
</style>