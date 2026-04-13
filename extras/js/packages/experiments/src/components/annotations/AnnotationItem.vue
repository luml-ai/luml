<template>
  <div class="wrapper" :class="{ expanded: isExpanded }">
    <div class="main" @click="toggle">
      <ChevronDown :size="16" class="chevron" color="var(--p-datatable-row-toggle-button-color)" />
      <div class="content">
        <div class="header-row">
          <div class="name">
            <component :is="mainIcon.icon" :size="16" :color="mainIcon.color" class="icon" />
            {{ data.name }}
          </div>
          <AnnotationOptions v-if="isEditable" @edit="$emit('edit')" @delete="$emit('delete')" />
        </div>
        <div class="row">
          <span class="username">{{ data.user }}</span>
          <span class="date">{{ lastUpdateText }}</span>
        </div>
      </div>
    </div>
    <div class="secondary-info">
      <div class="row">
        <span class="value-type">{{ valueTypeText }}:</span>
        <span
          v-if="data.value_type === AnnotationValueType.BOOL"
          class="result"
          :class="{ positive: data.value }"
        >
          <component :is="data.value ? ThumbsUp : ThumbsDown" :size="16" />
          {{ data.value ? 'True' : 'False' }}
        </span>
        <span v-else>
          {{ data.value }}
        </span>
      </div>
      <div class="description">
        {{ data.rationale }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { AnnotationKind, AnnotationValueType, type Annotation } from './annotations.interface'
import { computed, ref } from 'vue'
import { ChevronDown, Target, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import AnnotationOptions from './AnnotationOptions.vue'
import { getLastUpdateText } from '@experiments/helpers/helpers'

interface Props {
  isEditable: boolean
  data: Annotation
}

interface Emits {
  (event: 'edit'): void
  (event: 'delete'): void
}

const props = defineProps<Props>()
defineEmits<Emits>()

const isExpanded = ref(false)

const valueTypeText = computed(() => {
  switch (props.data.value_type) {
    case AnnotationValueType.BOOL:
      return 'Boolean'
    case AnnotationValueType.STRING:
      return 'String'
    case AnnotationValueType.INT:
      return 'Number'
    default:
      return 'Unknown'
  }
})

const mainIcon = computed(() => {
  if (props.data.annotation_kind === AnnotationKind.EXPECTATION) {
    return {
      icon: Target,
      color: 'var(--p-primary-color)',
    }
  }
  if (props.data.value === true) {
    return {
      icon: ThumbsUp,
      color: 'var(--p-green-500)',
    }
  }
  return {
    icon: ThumbsDown,
    color: 'var(--p-red-500)',
  }
})

const lastUpdateText = computed(() => {
  return getLastUpdateText(new Date(props.data.created_at))
})

function toggle() {
  isExpanded.value = !isExpanded.value
}
</script>

<style scoped>
.wrapper {
  border-radius: var(--p-card-border-radius);
  padding: 8px 12px;
  border: 1px solid transparent;
  font-size: 14px;
}

.expanded {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  box-shadow: var(--p-card-shadow);
}

.main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
}

.chevron {
  flex: 0 0 auto;
  margin: 6px 0;
}

.expanded .chevron {
  transform: rotate(180deg);
}

.content {
  flex: 1 1 auto;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.name {
  min-height: 26px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  margin-bottom: 4px;
}

.icon {
  flex: 0 0 auto;
}

.row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: space-between;
}

.username {
  color: var(--p-text-link-color);
  font-size: 12px;
}

.date {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.secondary-info {
  display: none;
  padding: 12px 0 0 22px;
}

.expanded .secondary-info {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.result {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--p-red-500);
}

.result.positive {
  color: var(--p-green-500);
}

.value-type {
  flex: 0 0 auto;
}

.description {
}
</style>
