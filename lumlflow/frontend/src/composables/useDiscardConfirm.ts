import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import { useConfirm } from 'primevue'
import { useFlowStore } from '@/store/flow'
import { discardChangesConfirmOptions } from '@/confirm/confirm'

export function useDiscardConfirm() {
  const confirm = useConfirm()
  const flowStore = useFlowStore()

  function confirmDiscard(): Promise<boolean> {
    return flowStore.shareDiscardConfirmation(
      () => new Promise((resolve) => confirm.require(discardChangesConfirmOptions(resolve))),
    )
  }

  async function confirmLeave(): Promise<boolean> {
    if (!flowStore.hasUnsavedChanges) return true
    if (!(await confirmDiscard())) return false
    flowStore.closeCodeEditors()
    return true
  }

  return { confirmDiscard, confirmLeave }
}

export function useUnsavedChangesGuard() {
  const flowStore = useFlowStore()
  const { confirmLeave } = useDiscardConfirm()

  onBeforeRouteLeave(confirmLeave)
  onBeforeRouteUpdate(confirmLeave)

  useEventListener(window, 'beforeunload', (event: BeforeUnloadEvent) => {
    if (flowStore.hasUnsavedChanges) event.preventDefault()
  })
}
