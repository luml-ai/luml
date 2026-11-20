<template>
  <Dialog
    v-model:visible="visible"
    modal
    block-scroll
    dismissable-mask
    :draggable="false"
    :style="dialogStyle"
    :pt="dialogPt"
  >
    <template #header>
      <div class="header">
        <h3 class="title">{{ REFERENCE_PROFILE_FILE_NAME }}</h3>
        <span class="subtitle">{{ subtitle }}</span>
      </div>
    </template>
    <MCode class="code" :code="code" copy-label="reference profile JSON" />
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Dialog } from 'primevue'
import {
  REFERENCE_PROFILE_DIALOG_GAP,
  REFERENCE_PROFILE_FILE_NAME,
} from '@/constants/reference-profile'
import {
  formatCharactersCount,
  formatLinesCount,
  formatReferenceDocument,
} from '@/utils/reference-profile'
import MCode from '@/components/MCode.vue'

interface Props {
  document: Record<string, unknown>
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible', { required: true })

const dialogStyle = {
  width: `calc(100vw - ${2 * REFERENCE_PROFILE_DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * REFERENCE_PROFILE_DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}

const dialogPt = {
  mask: { style: { '--px-mask-background': 'transparent' } },
  content: { class: 'reference-profile-dialog-content' },
}

const code = computed(() => formatReferenceDocument(props.document))

const subtitle = computed(
  () => `${formatLinesCount(code.value)} · ${formatCharactersCount(code.value)}`,
)
</script>

<style scoped>
.header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subtitle {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.code {
  height: 100%;
}
</style>

<style>
.reference-profile-dialog-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
</style>
