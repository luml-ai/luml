import { computed, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutationObserver } from '@vueuse/core'

export function useCssVariables<T extends string>(variables: MaybeRefOrGetter<Record<T, string>>) {
  const themeVersion = ref(0)

  useMutationObserver(
    document.documentElement,
    () => {
      themeVersion.value += 1
    },
    { attributes: true, attributeFilter: ['data-theme', 'class'] },
  )

  const values = computed(() => {
    void themeVersion.value
    const styles = getComputedStyle(document.body)
    return Object.fromEntries(
      Object.entries<string>(toValue(variables)).map(([key, variable]) => [
        key,
        styles.getPropertyValue(variable).trim(),
      ]),
    ) as Record<T, string>
  })

  const isDark = computed(() => {
    void themeVersion.value
    return document.documentElement.getAttribute('data-theme') === 'dark'
  })

  return { values, isDark }
}
