import { useId, type Ref } from 'vue'
import { useEventListener } from '@vueuse/core'
import { blockBodyScroll } from 'primevue/utils'

const DIALOG_MASK_SELECTOR = '.p-dialog-mask'

export function useNestedDialog(visible: Ref<boolean>) {
  const maskClass = `nested-dialog-mask-${useId()}`

  useEventListener(
    window,
    'keydown',
    (event: KeyboardEvent) => {
      if (!visible.value || event.key !== 'Escape' || event.isComposing) return
      event.stopPropagation()
      visible.value = false
    },
    { capture: true },
  )

  function restoreScrollLock() {
    const masks = document.querySelectorAll<HTMLElement>(DIALOG_MASK_SELECTOR)
    const hasOtherDialog = Array.from(masks).some((mask) => !mask.classList.contains(maskClass))
    if (hasOtherDialog) blockBodyScroll()
  }

  return { maskClass, restoreScrollLock }
}
