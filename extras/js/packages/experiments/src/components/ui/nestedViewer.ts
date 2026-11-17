import { inject, onMounted, onUnmounted, provide, ref, type InjectionKey, type Ref } from 'vue'

const OPEN_NESTED_VIEWERS: InjectionKey<Ref<number>> = Symbol('openNestedViewers')

/**
 * PrimeVue closes every open dialog on Escape. A dialog that hosts value viewers
 * uses this to keep itself open while one of them is open.
 */
export function provideNestedViewers(): Readonly<Ref<number>> {
  const openViewers = ref(0)
  provide(OPEN_NESTED_VIEWERS, openViewers)
  return openViewers
}

export function registerNestedViewer(): void {
  const openViewers = inject(OPEN_NESTED_VIEWERS, null)
  if (!openViewers) return
  onMounted(() => openViewers.value++)
  onUnmounted(() => openViewers.value--)
}
