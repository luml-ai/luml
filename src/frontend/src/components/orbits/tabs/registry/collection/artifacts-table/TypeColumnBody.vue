<template>
  <Tag :severity="ARTIFACT_TYPE_TAGS_CONFIG[data.type]?.severity ?? 'info'">
    <component
      v-if="ARTIFACT_TYPE_TAGS_CONFIG[data.type]"
      :is="ARTIFACT_TYPE_TAGS_CONFIG[data.type]?.icon"
      :size="12"
    />
    {{ ARTIFACT_TYPE_TAGS_CONFIG[data.type]?.text ?? 'Unknown type' }}
  </Tag>
</template>

<script setup lang="ts">
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { Tag } from 'primevue'
import { ARTIFACT_TYPE_TAGS_CONFIG } from './models-table.data'

interface Props {
  data: Artifact
}

defineProps<Props>()
</script>

<style scoped></style>
