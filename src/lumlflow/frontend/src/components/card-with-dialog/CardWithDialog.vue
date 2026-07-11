<template>
  <Card class="group cursor-pointer" @click="openDialog">
    <template #title>
      <div class="flex items-center gap-2">
        <component :is="icon" :size="16" color="var(--p-primary-color)" />
        <span class="transition-colors duration-200 group-hover:text-primary">
          {{ title }}
        </span>
      </div>
    </template>
    <template #content>
      <p class="text-muted-color leading-6">{{ description }}</p>
    </template>
  </Card>
  <Dialog
    v-model:visible="visible"
    modal
    :header="title"
    :style="{ maxWidth: 'calc(100vw - 32px)', width: '938px', height: 'calc(100vh - 115px)' }"
    :draggable="false"
  >
    <div v-html="html" class="markdown-body"></div>
  </Dialog>
</template>

<script setup lang="ts">
import type { LucideIcon } from 'lucide-vue-next'
import { Card, Dialog } from 'primevue'
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import 'github-markdown-css/github-markdown.css'

interface Props {
  title: string
  description: string
  icon: LucideIcon
  content: string
}

const props = defineProps<Props>()

const visible = ref(false)

const html = computed(() => {
  const result = marked.parse(props.content)
  return DOMPurify.sanitize(result as string)
})

function openDialog() {
  visible.value = true
}
</script>

<style scoped>
.markdown-body {
  background-color: transparent;
  color: var(--p-text-color);
}

.markdown-body :deep(tr) {
  background-color: transparent !important;
}

.markdown-body :deep(th:empty) {
  display: none !important;
}
</style>

<style>
.markdown-body pre,
.markdown-body code {
  background-color: var(--p-inputnumber-button-hover-background) !important;
  color: var(--p-text-color) !important;
}
</style>
