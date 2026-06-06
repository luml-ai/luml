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

type Props = {
  organizationId: string
}

const props = defineProps<Props>()

const confirm = useConfirm()
const organizationStore = useOrganizationStore()
const toast = useToast()

function onClick() {
  confirm.require(leaveOrganizationConfirmOptions(leave))
}

async function leave() {
  try {
    await organizationStore.leaveOrganization(props.organizationId)
    toast.add(simpleSuccessToast('You’ve successfully left the organization.'))
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to log out of the organization')))
  }
}
</script>

<style scoped>
.button {
  flex-shrink: 0;
}
</style>
