<template>
  <Button
    severity="warn"
    variant="outlined"
    :disabled="isOnlyOrganization"
    v-tooltip.top="deleteButtonTooltip"
    @click="visible = true"
    >Delete organization</Button
  >
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Delete this organization?"
    :style="{ width: '350px' }"
  >
    <div>
      <p v-if="otherMembersCount" class="text">
        Remove the other
        {{ otherMembersCount === 1 ? 'member' : `${otherMembersCount} members` }} from
        <span class="name">{{ organizationStore.currentOrganization?.name }}</span> before deleting
        it.
      </p>
      <p v-else class="text">
        This will permanently remove
        <span class="name">{{ organizationStore.currentOrganization?.name }}</span> with all its
        orbits and data. This action is final and cannot be undone.
      </p>
      <div class="flex items-center gap-2">
        <Checkbox v-model="accept" inputId="deleteAccept" binary :disabled="!!otherMembersCount" />
        <label for="deleteAccept"> Yes, delete this organization. </label>
      </div>
    </div>
    <template #footer>
      <Button @click="visible = false" :disabled="loading">Cancel</Button>
      <Button
        severity="warn"
        outlined
        :disabled="!accept || !!otherMembersCount"
        :loading="loading"
        @click="deleteOrganization"
        >Delete</Button
      >
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/helpers/helpers'
import { computed, ref } from 'vue'
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
const otherMembersCount = computed(() =>
  Math.max((organizationStore.organizationDetails?.members.length ?? 1) - 1, 0),
)
const isOnlyOrganization = computed(() => organizationStore.availableOrganizations.length <= 1)
const deleteButtonTooltip = computed(() =>
  isOnlyOrganization.value
    ? 'This is your only organization. Create another one first, or delete your account instead.'
    : null,
)

async function deleteOrganization() {
  const organizationId = organizationStore.currentOrganization?.id
  if (!organizationId) return
  loading.value = true
  try {
    await organizationStore.deleteOrganization(organizationId)
  } catch (e: unknown) {
    const deleted = !organizationStore.availableOrganizations.some(
      (organization) => organization.id === organizationId,
    )
    if (!deleted) {
      toast.add(simpleErrorToast(getErrorMessage(e, 'Could not delete organization')))
      return
    }
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not load the next organization')))
  } finally {
    loading.value = false
  }
  router.replace({ name: 'home' })
  toast.add(
    simpleSuccessToast('The organization and all associated data have been permanently removed.'),
  )
}
</script>

<style scoped>
.text {
  margin-bottom: 14px;
}
.name {
  font-weight: 600;
}
</style>
