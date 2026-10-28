import type { ObjectDirective } from 'vue'
import { Tooltip } from 'primevue'

const tooltip = Tooltip as ObjectDirective<HTMLElement>

function skipUnlessOverflowing(event: Event) {
  const el = event.currentTarget as HTMLElement
  if (el.scrollWidth <= el.clientWidth) event.stopImmediatePropagation()
}

export const overflowTooltip: ObjectDirective<HTMLElement> = {
  ...tooltip,
  beforeMount(el, ...rest) {
    el.addEventListener('mouseenter', skipUnlessOverflowing, true)
    tooltip.beforeMount?.(el, ...rest)
  },
  unmounted(el, ...rest) {
    el.removeEventListener('mouseenter', skipUnlessOverflowing, true)
    tooltip.unmounted?.(el, ...rest)
  },
}
