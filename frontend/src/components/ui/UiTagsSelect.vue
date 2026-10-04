<template>
  <div class="wrapper" @keydown.capture="onKeydown">
    <AutoComplete
      ref="elementRef"
      :name="name"
      v-model="modelValue"
      multiple
      fluid
      :inputId="id"
      :suggestions="suggestions"
      :placeholder="placeholder"
      :disabled="disabled"
      @complete="search"
      @focus="onFocus"
    >
      <template #chip="{ value, removeCallback }">
        <Chip v-tooltip="getTooltip(value)" :label="value" :removable="!disabled">
          <template #removeicon>
            <CircleX
              :size="14"
              class="remove-icon"
              :class="{ 'remove-icon-disabled': disabledValues.includes(value) }"
              @click.stop="!disabledValues.includes(value) && removeCallback($event)"
            />
          </template>
        </Chip>
      </template>
    </AutoComplete>
    <ChevronDown :size="16" class="arrow" color="var(--p-multiselect-dropdown-color)" />
  </div>
</template>

<script setup lang="ts">
import { AutoComplete, Chip, type AutoCompleteCompleteEvent } from 'primevue'
import { ref, useTemplateRef, watch } from 'vue'
import { ChevronDown, CircleX } from 'lucide-vue-next'

interface Props {
  id: string
  items: string[]
  placeholder: string
  name: string
  itemsTooltips?: Record<string, string>
  disabledValues?: string[]
  disabled?: boolean
}

type AutoCompleteInstance = InstanceType<typeof AutoComplete> & { show: () => void }

const props = withDefaults(defineProps<Props>(), {
  itemsTooltips: () => ({}),
  disabledValues: () => [],
  disabled: false,
})

const modelValue = defineModel<string[]>('modelValue', { default: [] })

const elementRef = useTemplateRef<AutoCompleteInstance>('elementRef')

const suggestions = ref([...props.items.filter((item) => !modelValue.value.includes(item))])

function search(event: AutoCompleteCompleteEvent) {
  const selected = new Set(modelValue.value)
  const filtered = props.items.filter((item) => !selected.has(item))
  suggestions.value = event.query ? Array.from(new Set([...filtered, event.query])) : filtered
}

function onFocus() {
  elementRef.value?.show()
}

function onKeydown(event: KeyboardEvent) {
  if (event.code !== 'Backspace') return

  const target = event.target as HTMLElement
  const value =
    target instanceof HTMLInputElement
      ? target.value
        ? undefined
        : modelValue.value.at(-1)
      : Array.from(target.children)
          .find((option) => option.id === target.getAttribute('aria-activedescendant'))
          ?.getAttribute('aria-label')

  if (value && props.disabledValues.includes(value)) {
    event.preventDefault()
    event.stopPropagation()
  }
}

function getTooltip(value: string) {
  return props.itemsTooltips[value]
}

watch(modelValue, (value) => {
  const selected = new Set(value)
  suggestions.value = props.items.filter((item) => !selected.has(item))
})
</script>

<style scoped>
.wrapper {
  position: relative;
  width: 100%;
}
.arrow {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
}
:deep(.p-chip) {
  padding-block-start: calc(var(--p-autocomplete-padding-y) / 2);
  padding-block-end: calc(var(--p-autocomplete-padding-y) / 2);
  border-radius: var(--p-autocomplete-chip-border-radius);
  padding-inline-end: var(--p-chip-padding-y);
}
.remove-icon {
  cursor: pointer;
}
.remove-icon-disabled {
  opacity: 0.6;
}
:deep(.p-autocomplete:has(.p-autocomplete-chip-item) .p-autocomplete-input-chip) {
  display: none;
}
:deep(.p-autocomplete.p-focus .p-autocomplete-input-chip) {
  display: inline-block;
}
</style>
