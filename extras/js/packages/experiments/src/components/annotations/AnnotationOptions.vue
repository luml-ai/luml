<template>
  <div>
    <button class="options" @click.stop.prevent="toggle">
      <EllipsisVertical :size="14" color="var(--p-button-text-secondary-color)" />
    </button>
    <Menu ref="menu" id="overlay_menu" :model="items" :popup="true" :pt="PT">
      <template #item="{ item }">
        <div class="menu-item" :class="item.class">
          {{ item.label }}
        </div>
      </template>
    </Menu>
  </div>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import { ref } from 'vue'
import { EllipsisVertical } from 'lucide-vue-next'
import { Menu, type MenuPassThroughOptions } from 'primevue'

const PT: MenuPassThroughOptions = {
  root: {
    style: 'background-color: var(--p-card-background);',
  },
}

interface Emits {
  (event: 'edit'): void
  (event: 'delete'): void
}

const emit = defineEmits<Emits>()

const menu = ref<InstanceType<typeof Menu> | null>(null)

const items = ref<MenuItem[]>([
  {
    label: 'Edit',
    command: () => {
      emit('edit')
    },
  },
  {
    label: 'Delete',
    class: 'danger',
    command: () => {
      emit('delete')
    },
  },
])

const toggle = (event: MouseEvent) => {
  menu.value?.toggle(event)
}
</script>

<style scoped>
.options {
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
}

.danger {
  color: var(--p-button-outlined-warn-color);
}

.menu-item {
  padding: 8px 12px;
  cursor: pointer;
}

.menu-item:not(:last-child) {
  border-bottom: 1px solid var(--p-divider-border-color);
}
</style>
