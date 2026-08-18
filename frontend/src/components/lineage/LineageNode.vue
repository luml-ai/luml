<template>
  <div class="node" :class="{ [variant]: true, [artifactType]: true }">
    <div class="node__header">
      <component
        :is="artifactTypeData.icon"
        :size="14"
        :color="artifactTypeData.color"
        class="node__icon"
      />
      <div class="node__title">{{ title }}</div>
      <Button
        v-if="variant === 'default'"
        variant="text"
        severity="secondary"
        class="node__options-button"
        @click="toggle"
      >
        <template #icon>
          <Ellipsis :size="14" />
        </template>
      </Button>
      <Menu ref="menu" :model="menuItems" :popup="true" class="node-menu" />
    </div>
    <div class="node__collection">
      <Folders :size="14" class="node__collection-icon" />
      <div class="node__collection-name">{{ collectionName }}</div>
    </div>
    <div v-if="showIconsBlock" class="node__icons">
      <Rocket v-if="deployments.length" :size="14" class="node__icon" />
      <TrainTrack v-if="tracks.length" :size="14" class="node__icon" />
    </div>
    <Handle :position="Position.Left" type="source" />
    <Handle :position="Position.Right" type="target" />
  </div>
</template>

<script setup lang="ts">
import type { LineageNodeVariant } from './lineage.interface'
import { ArtifactTypeEnum, type ArtifactTrack } from '@/lib/api/artifacts/interfaces'
import { Ellipsis, Folders, Rocket, TrainTrack } from 'lucide-vue-next'
import { Button, Menu } from 'primevue'
import { computed, ref } from 'vue'
import { LINEAGE_NODE_ICONS } from './lineage.data'
import { Handle, Position } from '@vue-flow/core'
import type { MenuItem } from 'primevue/menuitem'
import type { Deployment } from '@/lib/api/deployments/interfaces'

interface Props {
  artifactType: ArtifactTypeEnum
  title: string
  collectionName: string
  variant: LineageNodeVariant
  deployments: Deployment[]
  tracks: ArtifactTrack[]
}

interface Emits {
  replace: []
  unlink: []
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const menu = ref()

const menuItems = ref<MenuItem[]>([
  {
    label: 'Replace',
    command: () => {
      emit('replace')
    },
  },
  {
    label: 'Unlink',
    command: () => {
      emit('unlink')
    },
  },
])

const artifactTypeData = computed(() => {
  const option = LINEAGE_NODE_ICONS[props.artifactType]
  if (!option) {
    throw new Error(`Invalid artifact type: ${props.artifactType}`)
  }
  return option
})

const showIconsBlock = computed(() => {
  return props.deployments.length || props.tracks.length
})

const toggle = (event: MouseEvent) => {
  menu.value.toggle(event)
}
</script>

<style scoped>
.node {
  width: 220px;
  padding: 12px;
}
.node__header {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  margin-bottom: 8px;
}
.node__icon {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
}
.node__title {
  font-size: 14px;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node__options-button {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  outline: none !important;
}
.node__collection {
  display: flex;
  align-items: flex-start;
  gap: 4px;
}
.node__collection-icon {
  width: 14px;
  height: 14px;
  flex: 0 0 auto;
  color: var(--p-tabs-tab-color);
}
.node__collection-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node__icons {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
}
.node__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--p-tabs-tab-color);
}
</style>

<style>
.node-menu {
  background-color: var(--p-card-background) !important;
}
.node-menu .p-menu-item:not(:last-child) {
  position: relative;
  margin-bottom: 1px;
}
.node-menu .p-menu-item:not(:last-child)::after {
  content: '';
  display: block;
  position: absolute;
  top: calc(100% + 1px);
  height: 1px;
  width: 100%;
  background-color: var(--p-content-border-color);
}
</style>
