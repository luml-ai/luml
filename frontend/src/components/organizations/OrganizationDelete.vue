<template>
  <Button severity="warn" variant="outlined" @click="visible = true">delete organization</Button>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Delete this organization?"
    :style="{ width: '350px' }"
  >
    <div>
      <p class="text">
        This will permanently remove all members and work data linked to the organization. This
        action is final and cannot be undone.
      </p>
      <div class="flex items-center gap-2">
        <Checkbox v-model="accept" inputId="deleteAccept" binary />
        <label for="deleteAccept"> Yes, delete this organization. </label>
      </div>
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="!accept"
        :loading="loading"
        @click="deleteOrganization"
        >delete</Button
      >
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/helpers/helpers'
import { ref } from 'vue'
import { Checkbox, Button, Dialog, useToast } from 'primevue'
import { useOrganizationStore } from '@/stores/organization'
import { useRouter } from 'vue-router'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

const organizationStore = useOrganizationStore()
const toast = useToast()
const router = useRouter()

const visible = ref(false)
const accept = ref(false)
const loading = ref(false)

async function deleteOrganization() {
  if (!organizationStore.currentOrganization) return
  try {
    loading.value = true
    await organizationStore.deleteOrganization(organizationStore.currentOrganization.id)
    router.push({ name: 'home' })
    organizationStore.resetCurrentOrganization()
    toast.add(
      simpleSuccessToast('The organization and all associated data have been permanently removed.'),
    )
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not delete organization')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.text {
  margin-bottom: 14px;
}
</style>
