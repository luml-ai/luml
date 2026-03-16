<template>
  <div class="toolbar">
    <div class="left">
      <IconField class="icon-field">
        <InputIcon class="search-icon">
          <Search :size="12" />
        </InputIcon>
        <InputText
          v-model="searchModel"
          placeholder="Search evals"
          size="small"
          fluid
          class="search-input"
        />
      </IconField>
    </div>
    <div class="right">
      <TableFilter :fields="visibleColumns" disabled @apply="(filters) => $emit('filter-change', filters)" />
      <TableEditColumns
        :button-icon="Bolt"
        :columns="columns"
        :rounded-button="false"
        :selected-columns="selectedColumns"
        :disabled-columns="['id']"
        @edit="(data) => $emit('edit', data)"
      ></TableEditColumns>
      <Button severity="secondary" variant="outlined" size="small" disabled @click="$emit('export')">
        <span>Export CSV</span>
        <Download :size="14"></Download>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolbarEmits, ToolbarProps } from './traces.interface'
import { computed } from 'vue'
import { Button, IconField, InputIcon, InputText } from 'primevue'
import { Bolt, Download, Search } from 'lucide-vue-next'
import TableEditColumns from '../table/TableEditColumns.vue'
import TableFilter from '../table/filter/TableFilter.vue'

const props = defineProps<ToolbarProps>()
defineEmits<ToolbarEmits>()

const searchModel = defineModel<string>('search', { default: '' })

const visibleColumns = computed(() => {
  return props.selectedColumns.length ? props.selectedColumns : props.columns
})
</script>

<style scoped>
.toolbar {
  padding: 0 0 12px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.left {
  flex: 1 1;
}

.right {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.icon-field {
  max-width: 280px;
  width: 100%;
}

.search-input {
  padding-left: 30px !important;
}

.search-icon {
  inset-inline-start: 9px !important;
}
</style>
