import { computed, onMounted, ref } from 'vue'

export const useVariableValue = (rootSelector = 'body') => {
  const rootStyle = ref<CSSStyleDeclaration | null>(null)

  const getRootStyle = computed(() => {
    if (!rootStyle.value) throw new Error('Root style was not found')
    return rootStyle.value
  })

  function getVariablesValues(variables: string[]) {
    return variables.map((variable) => {
      const isVariable = variable.startsWith('var')
      if (isVariable) {
        const variableValue = variable.replace('var(', '').replace(')', '')
        return getRootStyle.value.getPropertyValue(variableValue)
      } else {
        return variable
      }
    })
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
