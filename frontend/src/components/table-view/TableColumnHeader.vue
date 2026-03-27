<template>
  <div class="column-header">
    <div class="column-header-title">
      <span>{{ column }}</span>
      <div class="column-header-icons">
        <component
          :is="currentColumnTypeIcon"
          width="16"
          height="16"
          color="var(--p-icon-muted-color)"
        />
        <Target
          v-if="target && column === target"
          width="16"
          height="16"
          color="var(--p-message-error-color)"
        />
        <Blocks
          v-if="group && group.includes(column)"
          width="16"
          height="16"
          color="var(--p-primary-color)"
        />
        <template v-if="inputsOutputsColumns">
          <component
            v-if="inputsOutputsColumns.find((c) => c.name === column)?.variant === 'input'"
            :is="PROMPT_NODES_ICONS.input"
            :size="16"
            color="var(--p-primary-color)"
          ></component>
          <component
            v-if="inputsOutputsColumns.find((c) => c.name === column)?.variant === 'output'"
            :is="PROMPT_NODES_ICONS.output"
            :size="16"
            color="var(--p-primary-color)"
          ></component>
        </template>
      </div>
    </div>
    <d-button
      v-if="showMenu"
      severity="secondary"
      rounded
      variant="text"
      aria-haspopup="true"
      aria-controls="overlay_menu"
      @click="toggleMenu"
      :style="{ width: '30px', height: '31px' }"
    >
      <template #icon>
        <EllipsisVertical :size="14" />
      </template>
    </d-button>
    <Menu :model="menuItems" :popup="true" ref="menu">
      <template #itemicon="{ item }">
        <component
          :is="item.iconComponent"
          width="14"
          height="14"
          :color="getCurrentMenuIconColor(item.iconComponent)"
        />
      </template>
    </Menu>
  </div>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import type { LucideIcon } from 'lucide-vue-next'
import { PROMPT_NODES_ICONS } from '@/components/express-tasks/prompt-fusion/interfaces'
import { Blocks, CalendarFold, CaseUpper, Hash, Target, EllipsisVertical } from 'lucide-vue-next'
import { Menu } from 'primevue'
import { computed, ref } from 'vue'
import type { ColumnType, PromptFusionColumn } from '@/hooks/useDataTable'

type Props = {
  values: object[]
  column: string
  target?: string
  group?: string[]
  columnType: ColumnType
  showMenu: boolean
  inputsOutputsColumns?: PromptFusionColumn[]
}
type Emits = {
  (event: 'setTarget', column: string): void
  (event: 'changeGroup', column: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const menu = ref()
const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    {
      label: 'Set as group',
      iconComponent: Blocks,
      disabled: true,
      command() {
        emit('changeGroup', props.column)
      },
    },
  ]

  if (props.column !== props.target) {
    items.push({
      label: 'Set as target',
      iconComponent: Target,
      command() {
        emit('setTarget', props.column)
      },
    })
  }

  return items
})

const getCurrentMenuIconColor = computed(() => (icon: LucideIcon) => {
  if (icon === Target) return 'var(--p-message-error-color)'
  if (icon === Blocks) return 'var(--p-primary-color)'
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
