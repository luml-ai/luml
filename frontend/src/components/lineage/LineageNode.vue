<template>
  <div
    class="node"
    :class="{ [variant]: true, [artifactType]: true }"
    :data-lineage-state="isDeleted ? 'deleted' : variant === 'main' ? 'focal' : 'live'"
  >
    <div class="node__header">
      <div class="node__type-icon">
        <component
          :is="artifactTypeData.icon"
          :size="14"
          :color="artifactTypeData.color"
          class="node__icon"
        />
        <span v-if="isDeleted" class="node__deleted-badge">Deleted</span>
      </div>
      <div class="node__title">{{ title }}</div>
      <Button
        v-if="variant !== 'main'"
        variant="text"
        severity="secondary"
        class="node__options-button"
        aria-label="Artifact actions"
        @click.stop="toggle"
      >
        <template #icon>
          <Ellipsis :size="14" />
        </template>
      </Button>
      <Menu ref="menu" :model="menuItems" :popup="true" class="node-menu" />
    </div>
    <div class="node__collection">
      <Folders :size="14" class="node__collection-icon" />
      <div class="node__collection-name">{{ collectionName ?? 'Unknown collection' }}</div>
    </div>
    <div v-if="showIconsBlock" class="node__icons">
      <span v-if="deployments.length" class="node__count" title="Deployments">
        <Rocket :size="14" class="node__icon" />
        {{ deployments.length }}
      </span>
      <span v-if="tracks.length" class="node__count" title="Tracks">
        <TrainTrack :size="14" class="node__icon" />
        {{ tracks.length }}
      </span>
    </div>
    <Handle :position="Position.Left" type="target" :connectable="!isDeleted" />
    <Handle :position="Position.Right" type="source" :connectable="!isDeleted" />
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
  collectionName: string | null
  variant: LineageNodeVariant
  isDeleted: boolean
  deployments: Deployment[]
  tracks: ArtifactTrack[]
  actionsDisabled?: boolean
}

interface Emits {
  replace: []
  unlink: []
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const menu = ref()

const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'Replace',
    disabled: props.actionsDisabled,
    command: () => {
      emit('replace')
    },
  },
  {
    label: 'Unlink',
    disabled: props.actionsDisabled,
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
.node.disabled {
  opacity: 0.65;
}
.node__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.node__type-icon {
  position: relative;
  display: flex;
  flex: 0 0 auto;
}
.node__deleted-badge {
  position: absolute;
  left: -5px;
  bottom: calc(100% + 4px);
  padding: 1px 5px;
  border-radius: 999px;
  color: var(--p-text-muted-color);
  background: var(--p-surface-100);
  border: 1px solid var(--p-content-border-color);
  font-size: 9px;
  line-height: 12px;
  white-space: nowrap;
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
.node__count {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--p-tabs-tab-color);
  font-size: 12px;
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
