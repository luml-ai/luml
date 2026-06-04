<template>
  <div class="wrapper">
    <div class="headings">
      <h1 class="main-title">Upload your data for model training</h1>
      <p class="sub-title">Select a file to upload, or try our sample dataset to get started.</p>
    </div>
    <div class="area">
      <file-input
        id="table"
        :file
        :error="hasError"
        :accept="['text/csv']"
        accept-text="Supports CSV file format"
        upload-text="upload CSV"
        @select-file="(e) => $emit('selectFile', e)"
        @remove-file="$emit('removeFile')"
      />
      <div class="info">
        <h3 class="info-title">File Requirements</h3>
        <ul class="info-list">
          <li class="info-item">
            <div class="info-item-body">
              <span>File Size: Up to 50 MB</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.size" />
                <check width="20" height="20" class="success" v-if="!errors.size" />
              </template>
            </div>
          </li>
          <li class="info-item">
            <div class="info-item-body">
              <span>Columns: At least {{ minColumnsCount }}</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.columns" />
                <check width="20" height="20" class="success" v-if="!errors.columns" />
              </template>
            </div>
          </li>
          <li class="info-item">
            <div class="info-item-body">
              <span>Rows: At least {{ minRowsCount }}</span>
              <template v-if="isTableExist">
                <x width="20" height="20" class="danger" v-if="errors.rows" />
                <check width="20" height="20" class="success" v-if="!errors.rows" />
              </template>
            </div>
          </li>
        </ul>
      </div>
      <span class="middle-divider">or</span>
      <span class="empty"></span>
      <div class="sample">
        <div class="sample-title">
          <img :src="CSVIcon" alt="CSV File" />
          <span>Sample Dataset</span>
        </div>
        <div class="sample-text">Use our sample dataset to explore how the model training.</div>
        <d-button label="use sample" @click="selectSample" />
      </div>
      <div class="info">
        <h3 class="info-title">Useful Resources:</h3>
        <ul class="info-list">
          <li v-for="resource in resources" :key="resource.link" class="info-item">
            <a :href="resource.link" target="_blank" class="info-item-body link">
              <span>{{ resource.label }}</span>
              <external-link width="14" height="14" class="link-icon" />
            </a>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ExternalLink, X, Check } from 'lucide-vue-next'
import CSVIcon from '@/assets/img/icons/csv.svg'
import FileInput from '@/components/ui/FileInput.vue'

type Props = {
  isTableExist: boolean
  errors: {
    size: boolean
    columns: boolean
    rows: boolean
  }
  file: {
    name?: string
    size?: number
  }
  minColumnsCount: number
  minRowsCount: number
  resources: { label: string; link: string }[]
  sampleFileName: string
}

type Emits = {
  selectFile: [File]
  removeFile: []
}

const emit = defineEmits<Emits>()
const props = defineProps<Props>()

const hasError = computed(() => {
  const errors = props.errors
  if (!errors) return false
  for (const key in errors) {
    if (errors[key as keyof typeof errors]) return true
  }
  return false
})

async function selectSample() {
  const fileUrl = `/data/${props.sampleFileName}`
  const response = await fetch(fileUrl)
  const text = await response.text()
  const file = new File([text], props.sampleFileName, { type: 'text/csv' })
  if (file) emit('selectFile', file)
}
</script>

<style scoped>
.wrapper {
  padding-top: 32px;
  padding-bottom: 32px;
}

.headings {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.area {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  padding: 36px;
  gap: 16px;
  display: grid;
  grid-template-columns: 1fr 227px;
}

.middle-divider {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-weight: 500;
  &::before,
  &::after {
    content: '';
    height: 1px;
    background-color: var(--p-divider-border-color);
  }
}

.info {
  font-weight: 500;
  padding: 16px;
}

.info-title {
  margin-bottom: 16px;
  font-size: 16px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  line-height: 1.7;
}

.info-item-body {
  display: flex;
  align-items: center;
  font-size: 14px;
  gap: 7px;
  justify-content: space-between;
  color: var(--p-text-muted-color);
  font-weight: 500;
  max-width: 200px;
}

.link-icon {
  flex: 0 0 auto;
}

.sample {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  padding: 24px;
}

.sample-title {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.sample-text {
  margin-bottom: 16px;
  color: var(--p-text-hover-muted-color);
  font-size: 14px;
  line-height: 1.7;
}

.danger {
  color: var(--p-badge-danger-background);
}

.success {
  color: var(--p-badge-success-background);
}

@media (max-width: 968px) {
  .area {
    grid-template-columns: 1fr;
  }

  .info {
    order: 3;
  }
}

@media (max-width: 768px) {
  .wrapper {
    padding-top: 16px;
    padding-bottom: 40px;
  }
  .info {
    padding: 8px;
  }
  .area {
    padding: 16px;
  }
}
</style>
