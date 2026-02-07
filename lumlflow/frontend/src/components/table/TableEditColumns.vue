<template>
  <OverlayBadge v-if="hideColumnsCount" :value="hideColumnsCount">
    <Button
      severity="secondary"
      variant="outlined"
      size="small"
      class="h-full"
      @click="togglePopover"
    >
      <span>Edit columns</span>
      <PenLine :size="14" />
    </Button>
  </OverlayBadge>
  <Button v-else severity="secondary" variant="outlined" size="small" @click="togglePopover">
    <span>Edit columns</span>
    <PenLine :size="14" />
  </Button>
  <Popover ref="popover">
    <div class="w-[250px]">
      <div>
        <InputText placeholder="Column" size="small" v-model="searchValue" class="mb-4" fluid />
        <div class="flex flex-col gap-4 max-h-[180px] overflow-y-auto pb-4">
          <label
            v-for="column in visibleColumns"
            :key="column.name"
            class="flex gap-4 items-center"
          >
            <ToggleSwitch v-model="column.selected" />
            <span>{{ cutStringOnMiddle(column.name, 24) }}</span>
          </label>
        </div>
      </div>
      <Divider :pt="{ root: { class: 'mt-0!' } }" />
      <div class="flex items-center justify-between gap-4">
        <div>
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
import { PenLine } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { OverlayBadge, Button, Popover, InputText, ToggleSwitch, Divider, Checkbox } from 'primevue'
import { cutStringOnMiddle } from '@/helpers/string'

type Column = {
  selected: boolean
  name: string
}

type Props = {
  columns: string[]
  selectedColumns: string[]
}

type Emits = {
  (event: 'edit', list: string[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const popover = ref()
const searchValue = ref('')
const selectedColumnsCurrent = ref<Column[]>([])

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

function togglePopover(event: Event) {
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
  else selectedColumnsCurrent.value = fillSelectedColumns(props.columns, props.columns)
}

watch(
  () => props.columns,
  (newColumns) => {
    selectedColumnsCurrent.value = fillSelectedColumns(newColumns, props.selectedColumns)
  },
)
</script>

<style scoped></style>
