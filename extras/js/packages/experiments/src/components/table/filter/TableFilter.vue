<template>
  <div>
    <Button severity="secondary" variant="outlined" size="small" @click.stop="togglePopover">
      <Filter :size="14" />
      <span>Filters</span>
      <component :is="isOpen ? ChevronUp : ChevronDown" :size="14" />
    </Button>
    <Popover
      ref="popover"
      :pt="{
        root: { class: 'table-filter-popover' },
        content: { class: 'table-filter-popover-content' },
      }"
      @hide="isOpen = false"
      @show="isOpen = true"
    >
      <div class="content">
        <div v-if="items.length" class="items">
          <template v-for="(item, i) in items" :key="item.id">
            <TableFilterItem v-model="items[i]!" :fields="fields" @remove="removeFilter(item.id)" />
          </template>
        </div>
        <div v-else class="empty">Filters list is empty</div>
        <div>
          <Button severity="secondary" variant="outlined" @click="addFilterItem">
            <Plus :size="14" />
            <span>Add filter</span>
          </Button>
        </div>
      </div>
      <div class="footer">
        <Button severity="secondary" @click="apply">Apply</Button>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import {
  type FilterEmits,
  FilterOperatorEnum,
  type FilterItem,
  type FilterProps,
} from './filter.interface'
import { onBeforeMount, ref } from 'vue'
import { Button, Popover } from 'primevue'
import { Filter, ChevronDown, ChevronUp, Plus } from 'lucide-vue-next'
import { v4 as uuidv4 } from 'uuid'
import TableFilterItem from './TableFilterItem.vue'

defineProps<FilterProps>()

const emit = defineEmits<FilterEmits>()

const popover = ref()

const isOpen = ref(false)

const items = ref<FilterItem[]>([])

function togglePopover(event: any) {
  popover.value.toggle(event)
}

function apply(event: any) {
  emit('apply', items.value)
  popover.value.toggle(event)
}

function addFilterItem() {
  items.value.push({
    id: uuidv4(),
    field: '',
    operator: FilterOperatorEnum.equal,
    value: '',
  })
}

function removeFilter(id: string) {
  items.value = items.value.filter((item) => item.id !== id)
}

onBeforeMount(() => {
  addFilterItem()
})
</script>

<style scoped>
:global(.table-filter-popover) {
  margin-top: 3px !important;
}

:global(.table-filter-popover::before),
:global(.table-filter-popover::after) {
  display: none;
}

:global(.table-filter-popover-content) {
  padding: 16px 12px !important;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
  width: 514px;
}

.empty {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.footer {
  display: flex;
  justify-content: flex-end;
}
</style>
