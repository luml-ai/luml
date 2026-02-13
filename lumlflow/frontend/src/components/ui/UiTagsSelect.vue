<template>
  <div class="relative">
    <AutoComplete
      ref="elementRef"
      v-model="modelValue"
      multiple
      fluid
      :inputId="id"
      :suggestions="suggestions"
      :placeholder="placeholder"
      @complete="search"
      @focus="onFocus"
    >
    </AutoComplete>
    <ChevronDown
      :size="16"
      class="absolute right-2.5 top-1/2 -translate-y-1/2"
      color="var(--p-multiselect-dropdown-color)"
    />
  </div>
</template>

<script setup lang="ts">
import { AutoComplete, type AutoCompleteCompleteEvent } from 'primevue'
import { ref, useTemplateRef } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

interface Props {
  id: string
  items: string[]
  placeholder: string
}

type AutoCompleteInstance = InstanceType<typeof AutoComplete> & { show: () => void }

const props = defineProps<Props>()

const modelValue = defineModel<string[]>('modelValue', { default: [] })

const elementRef = useTemplateRef<AutoCompleteInstance>('elementRef')

const suggestions = ref([...props.items])

function search(event: AutoCompleteCompleteEvent) {
  suggestions.value = [...props.items, event.query]
}

function onFocus() {
  elementRef.value?.show()
}
</script>

<style scoped></style>
