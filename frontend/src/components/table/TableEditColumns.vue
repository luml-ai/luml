<template>
  <OverlayBadge v-if="hideColumnsCount" :value="hideColumnsCount">
    <Button severity="secondary" :rounded="roundedButton" variant="outlined" @click="togglePopover">
      <span class="button-label">Edit columns</span>
      <component :is="buttonIcon" :size="14" />
    </Button>
  </OverlayBadge>
  <Button
    v-else
    severity="secondary"
    :rounded="roundedButton"
    variant="outlined"
    @click="togglePopover"
  >
    <span class="button-label">Edit columns</span>
    <component :is="buttonIcon" :size="14" />
  </Button>
  <Popover ref="popover">
    <div class="popover-wrapper">
      <div class="main">
        <InputText placeholder="Column" v-model="searchValue" />
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
        <div class="flex items-center gap-2">
          <Checkbox
            :modelValue="isShowAll"
            inputId="showAll"
            binary
            @update:modelValue="onShowAllUpdate($event)"
          />
          <label for="showAll"> show all </label>
        </div>
        <Button label="apply" severity="secondary" @click="apply" />
      </div>
    </div>
  </Popover>
</template>

<script setup lang="ts">
import { Target, type LucideIcon } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { OverlayBadge, Button, Popover, InputText, ToggleSwitch, Divider, Checkbox } from 'primevue'

type Column = {
  selected: boolean
  name: string
}
type Props = {
  target?: string
  columns: string[]
  selectedColumns: string[]
  roundedButton: boolean
  buttonIcon: LucideIcon
}
type Emits = {
  (event: 'edit', list: string[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const popover = ref()
const searchValue = ref('')
const selectedColumnsCurrent = ref<Column[]>(
  fillSelectedColumns(props.columns, props.selectedColumns),
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
const hideColumnsCount = computed(() => {
  if (!props.selectedColumns.length) return 0

  return props.columns.length - props.selectedColumns.length
})

function fillSelectedColumns(allColumns: string[], selectedColumns: string[]) {
  return allColumns.map((column) => ({
    name: column,
    selected: !selectedColumns.length ? true : selectedColumns.includes(column),
  }))
}

function togglePopover(event: any) {
  popover.value.toggle(event)
}

function apply() {
  const newSelectedColumns = selectedColumnsCurrent.value
    .filter((column) => column.selected)
    .map((column) => column.name)
  emit('edit', JSON.parse(JSON.stringify(newSelectedColumns)))
  popover.value.toggle()
}

function onShowAllUpdate(value: boolean) {
  if (value) selectedColumnsCurrent.value = fillSelectedColumns(props.columns, [])
  else
    selectedColumnsCurrent.value = fillSelectedColumns(
      props.columns,
      props.columns.filter((column) => column === props.target),
    )
}
</script>

<style scoped>
.popover-wrapper {
  padding: 1.5rem;
  width: 21.875rem;
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

@media (max-width: 768px) {
  .button-label {
    display: none;
  }
}
</style>
