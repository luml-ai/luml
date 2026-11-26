<template>
  <AlertDialog
    v-model:visible="visible"
    :alert="alert"
    :acknowledging="acknowledging"
    @acknowledge="acknowledge"
    @show="showInTab"
    @hidden="clear"
  />
</template>

<script setup lang="ts">
import type { AlertBanner } from '@/api/monitoring/interfaces'
import { useAlertDialog } from '@/composables/useAlertDialog'
import AlertDialog from '@/components/alerts/AlertDialog.vue'

interface Props {
  alerts: AlertBanner[]
  reload: () => Promise<unknown>
  error: Error | null
}

const props = defineProps<Props>()

const { alert, visible, acknowledging, open, clear, acknowledge, showInTab } = useAlertDialog(
  () => props.alerts,
  () => props.reload(),
  () => props.error,
)

defineExpose({ open })
</script>
