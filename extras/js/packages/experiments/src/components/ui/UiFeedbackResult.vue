<template>
  <div class="wrapper">
    <ProgressBar
      v-if="!positive"
      :value="percentage"
      :show-value="false"
      :pt="{
        root: {
          class: 'progressbar',
        },
        value: {
          class: 'progressbar-value-error',
        },
      }"
    ></ProgressBar>
    <div class="main">
      <component :is="icon" :size="14" :color="color" />
      <span class="title">{{ title }}</span>
      <span class="secondary-text">{{ secondaryText }}</span>
    </div>
    <ProgressBar
      v-if="positive"
      :value="percentage"
      :show-value="false"
      :pt="{
        root: {
          class: 'progressbar',
        },
        value: {
          class: 'progressbar-value-success',
        },
      }"
    ></ProgressBar>
  </div>
</template>

<script setup lang="ts">
import { ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { computed } from 'vue'
import { ProgressBar } from 'primevue'

interface Props {
  positive: boolean
  count?: number
  percentage?: number
}

const props = defineProps<Props>()

const showProgress = computed(() => props.percentage !== undefined)

const color = computed(() => (props.positive ? 'var(--p-green-500)' : 'var(--p-red-500)'))

const icon = computed(() => (props.positive ? ThumbsUp : ThumbsDown))

const title = computed(() => (props.positive ? 'True' : 'False'))

const secondaryText = computed(() => {
  if (showProgress.value) {
    return `${props.percentage}%`
  }
  return `(${props.count})`
})
</script>

<style scoped>
.wrapper {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
}

.main {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
}

.secondary-text {
  color: var(--p-text-muted-color);
  font-size: 12px;
  font-weight: 400;
}

.progressbar {
  height: 4px;
  background: transparent;
  border-radius: 0;
  width: 107px;
}

:deep(.progressbar-value-error) {
  background-color: var(--p-red-500);
  border-radius: 0 4px 4px 0;
}

:deep(.progressbar-value-success) {
  background-color: var(--p-green-500);
  border-radius: 0 4px 4px 0;
}
</style>
