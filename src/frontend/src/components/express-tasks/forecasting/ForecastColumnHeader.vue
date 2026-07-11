<template>
  <div class="column-header" :data-testid="`forecast-header-${column}`">
    <div class="column-header-title">
      <span
        v-tooltip.top="
          column !== cutStringOnMiddle(column) ? { value: column, showDelay: 400 } : undefined
        "
      >
        {{ cutStringOnMiddle(column) }}
      </span>
      <div class="column-header-icons">
        <component
          :is="currentColumnTypeIcon"
          width="16"
          height="16"
          color="var(--p-icon-muted-color)"
        />
        <component
          v-if="roleBadge"
          :is="roleBadge.icon"
          v-tooltip.top="roleBadge.label"
          :data-testid="`role-badge-${roleBadge.testId}`"
          width="16"
          height="16"
          :color="roleBadge.color"
        />
      </div>
    </div>
    <d-button
      v-if="menuItems.length"
      severity="secondary"
      rounded
      variant="text"
      aria-haspopup="true"
      aria-controls="overlay_menu"
      :data-testid="`forecast-menu-${column}`"
      :style="{ width: '30px', height: '31px' }"
      @click="toggleMenu"
    >
      <template #icon>
        <EllipsisVertical :size="14" />
      </template>
    </d-button>
    <Menu ref="menu" :model="menuItems" :popup="true">
      <template #itemicon="{ item }">
        <component :is="item.iconComponent" width="14" height="14" :color="item.iconColor" />
      </template>
    </Menu>
  </div>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import {
  CalendarCheck,
  CalendarClock,
  CalendarFold,
  CaseUpper,
  EllipsisVertical,
  Hash,
  Layers,
  Target,
} from 'lucide-vue-next'
import { Menu } from 'primevue'
import { computed, ref } from 'vue'
import type { ColumnType } from '@/hooks/useDataTable'
import type { ForecastColumnRole } from '@/hooks/useForecastSetup'
import { cutStringOnMiddle } from '@/helpers/helpers'

type Props = {
  column: string
  columnType: ColumnType
  role: ForecastColumnRole
}
type Emits = {
  setDate: [column: string]
  setTarget: [column: string]
  toggleAux: [column: string]
  toggleKnownFuture: [column: string]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const DATE_COLOR = 'var(--p-primary-color)'
const TARGET_COLOR = 'var(--p-message-error-color)'
const AUX_COLOR = 'var(--p-primary-color)'

const menu = ref()

const roleBadge = computed(() => {
  switch (props.role) {
    case 'date':
      return { icon: CalendarCheck, color: DATE_COLOR, label: 'Date column', testId: 'date' }
    case 'target':
      return { icon: Target, color: TARGET_COLOR, label: 'Target', testId: 'target' }
    case 'aux':
      return { icon: Layers, color: AUX_COLOR, label: 'Auxiliary', testId: 'aux' }
    case 'known_future':
      return {
        icon: CalendarClock,
        color: AUX_COLOR,
        label: 'Known future',
        testId: 'known-future',
      }
    default:
      return null
  }
})

const menuItems = computed<MenuItem[]>(() => {
  const { role } = props
  const items: MenuItem[] = []

  // The date and target columns offer the opposite role, which swaps the two
  // (see useForecastSetup): without it these roles could only be moved by
  // reassigning them from some other column's menu.
  if (role === 'date') {
    items.push({
      label: 'Set as target',
      iconComponent: Target,
      iconColor: TARGET_COLOR,
      command: () => emit('setTarget', props.column),
    })
  } else if (role === 'target') {
    items.push({
      label: 'Set as date column',
      iconComponent: CalendarCheck,
      iconColor: DATE_COLOR,
      command: () => emit('setDate', props.column),
    })
  } else {
    items.push({
      label: 'Set as date column',
      iconComponent: CalendarCheck,
      iconColor: DATE_COLOR,
      command: () => emit('setDate', props.column),
    })
    items.push({
      label: 'Set as target',
      iconComponent: Target,
      iconColor: TARGET_COLOR,
      command: () => emit('setTarget', props.column),
    })
    items.push({
      label: role === null ? 'Set as auxiliary' : 'Remove auxiliary',
      iconComponent: Layers,
      iconColor: AUX_COLOR,
      command: () => emit('toggleAux', props.column),
    })
  }
  if (role === 'aux' || role === 'known_future') {
    items.push({
      label: role === 'aux' ? 'Mark as known-future' : 'Unmark known-future',
      iconComponent: CalendarClock,
      iconColor: AUX_COLOR,
      command: () => emit('toggleKnownFuture', props.column),
    })
  }

  return items
})

const currentColumnTypeIcon = computed(() => {
  if (props.columnType === 'number') return Hash
  else if (props.columnType === 'date') return CalendarFold
  else return CaseUpper
})

function toggleMenu(event: Event) {
  menu.value.toggle(event)
}
</script>

<style scoped>
.column-header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.column-header-title {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--p-datatable-header-color);
  font-weight: var(--p-datatable-column-title-font-weight);
}

.column-header-icons {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
