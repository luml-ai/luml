<template>
  <div style="width: 150px">
    <Tag :severity="STATUS_TAGS_CONFIG[status]?.severity ?? 'info'" class="tag">
      {{ STATUS_TAGS_CONFIG[status]?.text ?? 'Unknown status' }}
    </Tag>
  </div>
</template>

<script setup lang="ts">
import type { ArtifactStatusEnum } from '@/lib/api/artifacts/interfaces'
import { STATUS_TAGS_CONFIG } from './models-table.data'
import { Tag } from 'primevue'

type Props = {
  status: ArtifactStatusEnum
}

const props = defineProps<Props>()
</script>

<style scoped>
.tag {
  font-weight: 400;
}
</style>
