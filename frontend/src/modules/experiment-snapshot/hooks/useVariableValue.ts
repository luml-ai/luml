import { computed, onMounted, ref } from 'vue'

export const useVariableValue = (rootSelector = 'body') => {
  const rootStyle = ref<CSSStyleDeclaration | null>(null)

  const getRootStyle = computed(() => {
    if (!rootStyle.value) throw new Error('Root style was not found')
    return rootStyle.value
  })

  function getVariablesValues(variable: string[]) {
    const formattedVariables = variable.map((variable) =>
      variable.replace('var(', '').replace(')', ''),
    )
    return formattedVariables.map((variable) => getRootStyle.value.getPropertyValue(variable))
  }

  function setRootStyle() {
    const rootElement = document.querySelector(rootSelector)
    if (!rootElement) return
    rootStyle.value = getComputedStyle(rootElement)
  }

  onMounted(() => {
    setRootStyle()
  })

  return { getVariablesValues }
}
