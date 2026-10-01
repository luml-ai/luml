<template>
  <Button severity="contrast" variant="text" @click="onClick" class="button">
    <template #icon>
      <LogOut :size="14" />
    </template>
  </Button>
</template>

<script setup lang="ts">
import { Button, useConfirm, useToast } from 'primevue'
import { LogOut } from 'lucide-vue-next'
import { useOrganizationStore } from '@/stores/organization'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { leaveOrganizationConfirmOptions } from '@/lib/primevue/data/confirm'
import { getErrorMessage } from '@/helpers/helpers'
import { useRouter } from 'vue-router'

type Props = {
  organizationId: string
}

const props = defineProps<Props>()

const confirm = useConfirm()
const organizationStore = useOrganizationStore()
const toast = useToast()
const router = useRouter()

function onClick() {
  confirm.require(leaveOrganizationConfirmOptions(leave))
}

async function leave() {
  const organizationId = props.organizationId
  const isCurrentOrganization = organizationStore.currentOrganization?.id === organizationId
  try {
    await organizationStore.leaveOrganization(organizationId)
    toast.add(simpleSuccessToast('You’ve successfully left the organization.'))
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to log out of the organization')))
  } finally {
    if (
      isCurrentOrganization &&
      !organizationStore.availableOrganizations.some(
        (organization) => organization.id === organizationId,
      )
    ) {
      await router.replace({ name: 'setup' })
    }
  }
}
</script>

<style scoped>
.button {
  flex-shrink: 0;
}
</style>
