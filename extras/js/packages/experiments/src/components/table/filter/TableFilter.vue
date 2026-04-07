<template>
  <div>
    <Button
      severity="secondary"
      variant="outlined"
      size="small"
      :disabled="!!disabled"
      @click.stop="togglePopover"
    >
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
            <TableFilterItem
              v-model="items[i]!"
              :fields="filteredFields"
              :errors="itemsErrors[i]"
              @remove="removeFilter(item.id)"
              @clear-errors="clearItemErrors(i)"
            />
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
        <Button severity="secondary" variant="outlined" @click="clear">
          <FilterX :size="14" />
          Clear all
        </Button>
        <Button severity="secondary" @click="apply">Apply</Button>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import {
  type FilterEmits,
  type FilterItem,
  type FilterItemsErrors,
  type FilterProps,
} from './filter.interface'
import type { ValidateResponseItem } from '@/interfaces/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { Button, Popover, useToast } from 'primevue'
import { Filter, ChevronDown, ChevronUp, Plus, FilterX } from 'lucide-vue-next'
import { v4 as uuidv4 } from 'uuid'
import { formSchema } from './filter.const'
import { mapZodErrors } from '@/helpers/forms'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import TableFilterItem from './TableFilterItem.vue'

const toast = useToast()

const props = defineProps<FilterProps>()

const emit = defineEmits<FilterEmits>()

const popover = ref()

const isOpen = ref(false)

const items = ref<FilterItem[]>([])

const itemsErrors = ref<FilterItemsErrors>([])

const filteredFields = computed(() => {
  return props.fields.filter((field) => field.type !== 'unknown')
})

function togglePopover(event: any) {
  popover.value.toggle(event)
}

async function apply(event: any) {
  const isValid = await validate()
  if (!isValid) return
  emit('apply', items.value)
  popover.value.toggle(event)
}

function addFilterItem() {
  items.value.push({
    id: uuidv4(),
    field: '',
    operator: null,
    value: '',
  })
}

function removeFilter(id: string) {
  items.value = items.value.filter((item) => item.id !== id)
}

function clearItemsErrors() {
  itemsErrors.value = []
}

function clearItemErrors(index: number) {
  itemsErrors.value[index] = {}
}

function setItemsErrors(errors: Record<string, string>) {
  const errorsEntries = Object.entries(errors)
  errorsEntries.forEach(([key, errorMessage]) => {
    const [, index, field] = key.split('.')
    const itemIndex = parseInt(index!)
    const itemErrors = itemsErrors.value[itemIndex] || {}
    itemErrors[field!] = errorMessage
    itemsErrors.value[itemIndex] = itemErrors
  })
}

function setGlobalErrors(results: ValidateResponseItem[]) {
  results.forEach((result, index) => {
    if (result.valid || !result.error) return
    const itemErrors = itemsErrors.value[index] || {}
    itemErrors.global = result.error
    itemsErrors.value[index] = itemErrors
  })
}

async function validate() {
  clearItemsErrors()
  const result = formSchema.safeParse({ items: items.value })
  if (result.success) return asyncValidate()
  const errors = mapZodErrors(result.error)
  setItemsErrors(errors)
  return false
}

async function asyncValidate() {
  if (!props.asyncValidateCallback) return true
  try {
    const results = await props.asyncValidateCallback(items.value)
    const hasErrors = results.some((result) => !result.valid)
    if (!hasErrors) return true
    setGlobalErrors(results)
    return false
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to validate filters')))
    return false
  }
}

function clear(event: any) {
  items.value = []
  emit('apply', [])
  popover.value.toggle(event)
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
  gap: 7px;
}
</style>
