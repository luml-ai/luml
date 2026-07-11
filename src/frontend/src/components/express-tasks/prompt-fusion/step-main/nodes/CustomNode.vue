<template>
  <div ref="nodeRef" class="node-body">
    <header class="header">
      <div class="header-left">
        <component :is="icon" width="15" height="15" :color="data.iconColor"></component>
        <h3 class="header-title">{{ data.label }}</h3>
      </div>
      <template v-if="data.showMenu">
        <d-button
          ref="toggleMenuButton"
          severity="secondary"
          variant="text"
          rounded
          class="button"
          @click.stop="toggleMenu"
        >
          <template #icon>
            <ellipsis width="20" height="20" />
          </template>
        </d-button>
        <on-click-outside
          v-if="isMenuOpen"
          :options="{ ignore: [toggleMenuButton] }"
          class="menu"
          :style="{ left: `${menuPosition.left}px`, top: `${menuPosition.top}px` }"
          @trigger="onMenuOutsideClick"
        >
          <button class="menu-item" @click.stop="onDuplicateClick">Duplicate</button>
          <d-divider :style="{ margin: '2px 0' }" />
          <button class="menu-item" @click.stop="onDeleteClick">Delete</button>
        </on-click-outside>
      </template>
    </header>
    <div class="all-fields" :key="data.fields.length">
      <div v-if="inputFields.length" class="fields input-fields">
        <node-field v-for="field in inputFields" :key="field.id" :field="field" />
      </div>
      <d-divider v-if="inputFields.length && outputFields.length" style="margin: 8px 0" />
      <div v-if="outputFields.length" class="fields output-fields">
        <node-field v-for="field in outputFields" :key="field.id" :field="field" />
      </div>
      <div v-if="conditionFields.length" class="fields condition-fields">
        <node-field
          v-for="(field, index) in conditionFields"
          :index="index + 1"
          :key="field.id"
          :field="field"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { PROMPT_NODES_ICONS, type NodeData } from '../../interfaces'
import { Ellipsis } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { OnClickOutside } from '@vueuse/components'
import NodeField from './NodeField.vue'

type Props = {
  id: string
  data: NodeData
}
type Emits = {
  duplicate: []
  delete: []
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const nodeRef = ref<HTMLDivElement>()
const toggleMenuButton = ref<HTMLButtonElement>()
const isMenuOpen = ref(false)

const icon = computed(() => PROMPT_NODES_ICONS[props.data.icon])
const inputFields = computed(() => props.data.fields.filter((field) => field.variant === 'input'))
const outputFields = computed(() => props.data.fields.filter((field) => field.variant === 'output'))
const conditionFields = computed(() =>
  props.data.fields.filter((field) => field.variant === 'condition'),
)
const menuPosition = computed(() => {
  if (!nodeRef.value) return { left: 0, top: 0 }
  const nodePosition = { left: nodeRef.value.offsetLeft, top: nodeRef.value.offsetTop }
  return { left: nodePosition.left + 48, top: nodePosition.top + 36 }
})

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

function onDuplicateClick() {
  toggleMenu()
  emit('duplicate')
}
function onDeleteClick() {
  emit('delete')
}
function onMenuOutsideClick() {
  if (isMenuOpen.value) toggleMenu()
}
</script>

<style scoped>
.node-body {
  width: 215px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
  height: 40px;
}
.header-left {
  display: flex;
  gap: 4px;
  align-items: center;
}
.header-title {
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 500;
}

.all-fields {
  padding-bottom: 12px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.condition-fields:not(:first-child) {
  padding-top: 16px;
}

.button {
  margin-right: -8px;
}

.menu {
  position: absolute;
  max-width: 175px;
  width: 100%;
  background-color: var(--p-card-background);
  border: 1px solid var(--p-menu-border-color);
  border-radius: var(--p-menu-border-radius);
  padding: 4px;
  box-shadow:
    0px 4px 6px -1px rgba(0, 0, 0, 0.1),
    0px 2px 4px -2px rgba(0, 0, 0, 0.1);
  z-index: 10;
}
.menu-item {
  padding: 8px 12px;
  color: var(--p-menu-item-color);
  width: 100%;
  transition:
    background-color var(--p-menu-transition-duration),
    color var(--p-menu-transition-duration);
  border-radius: var(--p-menu-item-border-radius);
  cursor: pointer;
  text-align: left;
  font-size: 12px;
}
.menu-item:hover {
  background-color: var(--p-menu-item-focus-background);
}
</style>
