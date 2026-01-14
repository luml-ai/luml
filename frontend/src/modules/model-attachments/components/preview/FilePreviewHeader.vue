<template>
  <div class="preview-header" v-if="fileName">
    <div class="file-info-wrapper">
      <div class="file-info">
        <span class="font-bold text-lg">{{ fileName }}</span>
        <span v-if="fileSize" class="file-size">
          {{ formatFileSize(fileSize) }}
        </span>
      </div>
      <div class="file-path-row">
        <span class="file-path">{{ filePath }}</span>
        <div class="file-path-actions">
          <span class="icon-wrapper" v-tooltip.top="'Copy path'" @click="$emit('copy-path')">
            <Copy class="icon-btn" />
          </span>
          <span class="icon-wrapper" v-tooltip.top="'Download'" @click="$emit('download')">
            <Download class="icon-btn" />
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Copy, Download } from 'lucide-vue-next'
import { formatFileSize } from '../../utils/fileTypes'

import type { FilePreviewHeaderProps, FilePreviewHeaderEmits } from '../../interfaces/interfaces'

const props = defineProps<FilePreviewHeaderProps>()
const emit = defineEmits<FilePreviewHeaderEmits>()
</script>

<style scoped>
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid var(--surface-200);
  background: var(--surface-50);
}

.file-info {
  display: flex;
  align-items: center;
}

.file-info-wrapper {
  display: flex;
  flex-direction: column;
}

.file-size {
  margin-left: 10px;
  color: var(--p-form-field-float-label-color);
}

.file-path-row {
  margin-top: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.file-path {
  color: var(--p-form-field-float-label-color);
  word-break: break-all;
}

.file-path-actions {
  display: flex;
  gap: 10px;
}
.icon-btn:hover {
  color: var(--primary-color);
}

.icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.icon-btn {
  width: 20px;
  height: 20px;
  color: var(--p-form-field-float-label-color);
}

.icon-wrapper:hover .icon-btn {
  color: var(--primary-color);
}
</style>
