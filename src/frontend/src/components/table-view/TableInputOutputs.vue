<template>
  <d-button severity="secondary" rounded variant="outlined" @click="togglePopover">
    <span class="button-label">Output fields</span>
    <bolt width="14" height="14" />
  </d-button>
  <d-popover ref="popover" style="width: 100%; max-width: 398px" @hide="onPopoverHide">
    <div class="popover-wrapper">
      <div class="main">
        <h4 class="title">Set type for each column</h4>
        <d-input-text placeholder="Find column" v-model="searchValue" fluid class="input" />
        <div class="list">
          <div v-for="column in searchedColumns" :key="column.name" class="column">
            <div class="item-title">
              <span class="label">{{ cutStringOnMiddle(column.name, 24) }}</span>
              <component
                :is="typesIcons[column.type]"
                width="16"
                height="16"
                color="var(--p-icon-muted-color)"
                class="variant-icon"
              ></component>
            </div>
            <ui-custom-radio v-model="column.variant" :options="['input', 'output']" />
          </div>
        </div>
      </div>
      <d-divider class="divider" />
      <div class="popover-footer">
        <d-button label="apply" severity="secondary" @click="apply" />
      </div>
    </div>
  </d-popover>
</template>

<script setup lang="ts">
import type { ColumnType, PromptFusionColumn } from '@/hooks/useDataTable'
import { computed, ref, watch, type FunctionalComponent } from 'vue'
import { Bolt, CalendarFold, Hash, CaseUpper } from 'lucide-vue-next'
import { cutStringOnMiddle } from '@/helpers/helpers'
import UiCustomRadio from '@/components/ui/UiCustomRadio.vue'

const typesIcons: Record<ColumnType, FunctionalComponent> = {
  number: Hash,
  date: CalendarFold,
  string: CaseUpper,
}

type Props = {
  columns: PromptFusionColumn[]
  columnTypes: Record<string, ColumnType>
  selectedColumns: string[]
}

const props = defineProps<Props>()

const popover = ref()
const searchValue = ref('')
const columnsState = ref(fillColumnsState())

const searchedColumns = computed(() =>
  columnsState.value.filter((column) =>
    column.name.toLowerCase().includes(searchValue.value.toLowerCase()),
  ),
)

function togglePopover(event: Event) {
  popover.value.toggle(event)
}
function apply() {
  columnsState.value.map((column) => {
    const currentColumn = props.columns.find((c) => c.name === column.name)
    if (currentColumn) currentColumn.variant = column.variant
  })
  popover.value.toggle()
}
function fillColumnsState() {
  const availableColumns = props.selectedColumns.length
    ? props.columns.filter((column) => props.selectedColumns.includes(column.name))
    : props.columns
  return availableColumns.map((column) => ({
    name: column.name,
    type: props.columnTypes[column.name],
    variant: column.variant,
  }))
}
function onPopoverHide() {
  searchValue.value = ''
  columnsState.value = fillColumnsState()
}

watch(
  () => props.selectedColumns,
  () => {
    columnsState.value = fillColumnsState()
  },
  { deep: true },
)
</script>

<style scoped>
.variant-icon {
  margin-left: 4px;
}
.popover-wrapper {
  padding: 14px;
}
.title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 20px;
}
.input {
  margin-bottom: 20px;
}
.list {
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 205px;
  overflow-y: auto;
}
.column {
  display: flex;
  align-items: center;
  gap: 4px;
}
.item-title {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.label {
  font-size: 14px;
  color: var(--p-datatable-header-cell-color);
  font-weight: var(--p-datatable-column-title-font-weight);
}
.variant-icon {
  flex: 0 0 auto;
}
.divider {
  margin-top: 0;
}
.popover-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
