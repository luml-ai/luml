import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

/** True while the element is within `rootMargin` of the viewport; always true without IntersectionObserver. */
export function useInView(
  element: Ref<HTMLElement | null>,
  enabled: boolean,
  rootMargin = '200px',
): Ref<boolean> {
  const inView = ref(!enabled || typeof IntersectionObserver === 'undefined')
  if (inView.value) return inView

  const observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[entries.length - 1]
      if (entry) inView.value = entry.isIntersecting
    },
    { rootMargin },
  )
  watch(
    element,
    (current, previous) => {
      if (previous) observer.unobserve(previous)
      if (current) observer.observe(current)
    },
    { immediate: true },
  )
  onBeforeUnmount(() => observer.disconnect())
  return inView
}
