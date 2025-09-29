<template>
  <div class="item">
    <header class="header">
      <h4 class="title">{{ title }}</h4>
      <div class="right">
        <Select
          v-model="contentType"
          :options="contentTypes"
          option-label="label"
          option-value="value"
          option-disabled="disabled"
          size="small"
          class="select"
        ></Select>
        <Button
          severity="secondary"
          variant="text"
          v-tooltip.left="'Copy'"
          :disabled="copied"
          @click="copy"
        >
          <template #icon>
            <component :is="copied ? CopyCheck : Copy" :size="14"></component>
          </template>
        </Button>
      </div>
    </header>
    <div class="content">
      <div v-if="contentType === ContentTypeEnum.yaml" class="yaml-body">
        <pre>{{ yamlText }}</pre>
      </div>
      <div
        v-else-if="contentType === ContentTypeEnum.markdown"
        v-html="markdownText"
        class="markdown-body"
      ></div>
      <div v-else>{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import 'github-markdown-css/github-markdown.css';
import { computed, ref } from 'vue'
import { Select, Button } from 'primevue'
import { Copy, CopyCheck } from 'lucide-vue-next'
import { marked } from 'marked'
import { isYamlLike, jsonToYaml } from '../../helpers/texts'
import DOMPurify from 'dompurify'

type Props = {
  title: string
  text: any
}

enum ContentTypeEnum {
  yaml = 'yaml',
  markdown = 'markdown',
  raw = 'raw',
}

const props = defineProps<Props>()

const contentType = ref<ContentTypeEnum>(ContentTypeEnum.raw)
const copied = ref(false)

const contentTypes = computed(() => [
  {
    label: 'YAML',
    value: ContentTypeEnum.yaml,
    disabled: !isYamlLike(props.text),
  },
  {
    label: 'Markdown',
    value: ContentTypeEnum.markdown,
  },
  {
    label: 'Raw',
    value: ContentTypeEnum.raw,
  },
])

const markdownText = computed(() => {
  const result = marked.parse(
    typeof props.text === 'object' ? JSON.stringify(props.text) : `${props.text}`,
  )
  return DOMPurify.sanitize(result as string)
})

const yamlText = computed(() => jsonToYaml(props.text))

function copy() {
  navigator.clipboard.writeText(
    typeof props.text === 'object' ? JSON.stringify(props.text) : `${props.text}`,
  )
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 1000)
}
</script>

<style scoped>
.item {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
}

.header {
  margin-bottom: 18px;
  padding-bottom: 4px;
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  overflow: hidden;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.title {
  font-size: 16px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.select {
  width: 120px;
}

.content {
  font-size: 14px;
  overflow-x: auto;
}

.yaml-body {
  white-space: pre;
}

.markdown-body {
  background-color: transparent;
}
</style>
