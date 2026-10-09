<template>
  <div class="popover-wrapper" :class="`popover-wrapper-${size}`">
    <div class="main">
      <InputText :placeholder="placeholder" v-model="searchValue" :size="size" />
      <div class="list">
        <label v-for="column in visibleColumns" :key="column.name" class="column">
          <ToggleSwitch v-model="column.selected" :disabled="column.name === target" />
          <div class="item-title">
            <span class="label">{{ cutStringOnMiddle(column.name, 24) }}</span>
            <Target
              v-if="column.name === target"
              width="16"
              height="16"
              color="var(--p-message-error-color)"
            />
          </div>
        </label>
      </div>
    </div>
    <Divider class="divider" />
    <div class="popover-footer">
      <div>
        <div v-if="showAllAvailable" class="flex items-center gap-2">
          <Checkbox
            :modelValue="isShowAll"
            inputId="showAll"
            binary
            @update:modelValue="onShowAllUpdate($event)"
          />
          <label for="showAll"> show all </label>
        </div>
      </div>
      <Button label="Apply" severity="secondary" @click="apply" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Target } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { InputText, ToggleSwitch, Checkbox, Button, Divider } from 'primevue'
import { cutStringOnMiddle } from '@/helpers/helpers'

type Column = {
  selected: boolean
  name: string
}
type Props = {
  target?: string
  options: string[]
  selectedOptions: string[]
  selectedByDefault?: boolean
  size?: 'small' | 'medium' | 'large'
  placeholder?: string
  showAllAvailable?: boolean
}
type Emits = {
  (event: 'edit', list: string[]): void
}

const props = withDefaults(defineProps<Props>(), {
  selectedByDefault: true,
  size: 'medium',
  showAllAvailable: true,
})
const emit = defineEmits<Emits>()

const searchValue = ref('')
const selectedColumnsCurrent = ref<Column[]>(
  fillSelectedOptions(props.options, props.selectedOptions),
)

const isShowAll = computed(() => {
  return selectedColumnsCurrent.value.every((column) => column.selected)
})
const visibleColumns = computed(() => {
  if (searchValue.value)
    return selectedColumnsCurrent.value.filter((column) =>
      column.name.includes(searchValue.value.trim()),
    )
  return selectedColumnsCurrent.value
})

function fillSelectedOptions(allColumns: string[], selectedColumns: string[]) {
  return allColumns.map((column) => ({
    name: column,
    selected: !selectedColumns.length ? props.selectedByDefault : selectedColumns.includes(column),
  }))
}

function apply() {
  const newSelectedColumns = selectedColumnsCurrent.value
    .filter((column) => column.selected)
    .map((column) => column.name)
  emit('edit', JSON.parse(JSON.stringify(newSelectedColumns)))
}

function onShowAllUpdate(value: boolean) {
  if (value) selectedColumnsCurrent.value = fillSelectedOptions(props.options, [])
  else
    selectedColumnsCurrent.value = fillSelectedOptions(
      props.options,
      props.options.filter((option) => option === props.target),
    )
}
</script>

<style scoped>
.popover-wrapper {
  padding: 1.5rem;
  width: 21.875rem;
}

.popover-wrapper-small {
  width: 320px;
}

.popover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.main {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 10.875rem;
  overflow-y: auto;
  padding: 1rem 0.5rem;
}

.column {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.item-title {
  display: flex;
  align-items: center;
  gap: 4px;
}

.label {
  font-weight: 600;
  font-size: 14px;
  margin-right: 4px;
}

.divider {
  margin-top: 0;
}
</style>
