<template>
  <div class="luml-preview">
    <div class="overview-hint">
      <span>For full overview</span>
      <div class="actions">
        <Button
          v-for="action in ACTIONS[luml.kind]"
          :key="action.label"
          :label="action.label"
          severity="secondary"
          size="small"
        >
          <template #icon>
            <component :is="action.icon" :size="14" />
          </template>
        </Button>
      </div>
    </div>

    <!-- product:PROP-004 B-11: a dataset shows its data first, one tab per subset and split. -->
    <section v-if="luml.kind === 'dataset' && luml.data" class="section">
      <h3 class="section-title">Data</h3>
      <Tabs :value="luml.data.activeTab" class="data-tabs">
        <TabList>
          <Tab v-for="tab in luml.data.tabs" :key="tab" :value="tab">{{ tab }}</Tab>
        </TabList>
      </Tabs>
      <div class="data-table">
        <AttachmentsPreviewDataTable
          :value="luml.data.table.rows"
          :paginator="true"
          :rows="10"
          :rows-per-page-options="[10, 20, 50]"
          :total-records="luml.data.table.rowsCount"
          size="small"
        >
          <Column v-for="column in luml.data.table.headers" :key="column" :field="column" :header="column"></Column>
        </AttachmentsPreviewDataTable>
      </div>
    </section>

    <section class="section">
      <h3 class="section-title">Manifest</h3>
      <!-- eslint-disable-next-line vue/no-v-html -- highlight.ts escapes the text first -->
      <pre class="manifest"><code v-html="highlight(luml.manifestYaml, 'yaml')"></code></pre>
    </section>

    <section class="section">
      <h3 class="section-title">Contents</h3>
      <ul class="contents">
        <li v-for="entry in luml.contents" :key="entry.path" class="contents-row">
          <span class="contents-name">
            <component :is="entry.folder ? Folder : File" :size="14" class="contents-icon" />
            {{ entry.path }}
          </span>
          <span class="contents-size">{{ entry.size ?? '' }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { CloudUpload, File, FlaskConical, Folder } from 'lucide-vue-next'
import { Button, Column, Tab, TabList, Tabs } from '@/ui'
import AttachmentsPreviewDataTable from '@/ui/AttachmentsPreviewDataTable.vue'
import { highlight } from './highlight'

/** product:PROP-004 B-09 – B-11; the kind comes from `artifact_type` in manifest.json. */
export type LumlPackage = {
  kind: 'experiment' | 'model' | 'dataset'
  /** manifest.json shown as YAML. */
  manifestYaml: string
  contents: { path: string; size?: string; folder?: boolean }[]
  /** Datasets only (B-11): the rows of one subset / split per tab. */
  data?: {
    tabs: string[]
    activeTab: string
    table: { headers: string[]; rows: Record<string, string>[]; rowsCount: number }
  }
}

type Action = { label: string; icon: typeof CloudUpload }

// B-09: an experiment has two actions; B-10, B-11: models and datasets upload only.
const ACTIONS: Record<LumlPackage['kind'], Action[]> = {
  experiment: [
    { label: 'Open in Experiments', icon: FlaskConical },
    { label: 'Upload experiment to LUML', icon: CloudUpload },
  ],
  model: [{ label: 'Upload model to LUML', icon: CloudUpload }],
  dataset: [{ label: 'Upload dataset to LUML', icon: CloudUpload }],
}

defineProps<{ luml: LumlPackage }>()
</script>

<style scoped>
.luml-preview {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
}

.section-title {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.data-tabs {
  margin-bottom: 0.75rem;
}

.data-table {
  overflow: auto;
}

.manifest {
  margin: 0;
  max-height: 320px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background-color: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  font-size: 13px;
  line-height: 1.5;
  color: var(--p-text-color);
  --hl-comment: #6b7280;
  --hl-string: #15803d;
  --hl-keyword: #7c3aed;
  --hl-number: #b45309;
  --hl-key: #1d4ed8;
}

.manifest :deep(.hl-comment) {
  color: var(--hl-comment);
}

.manifest :deep(.hl-string) {
  color: var(--hl-string);
}

.manifest :deep(.hl-keyword) {
  color: var(--hl-keyword);
}

.manifest :deep(.hl-number) {
  color: var(--hl-number);
}

.manifest :deep(.hl-key) {
  color: var(--hl-key);
}

.contents {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 0.8125rem;
}

.contents-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.3125rem 0;
}

.contents-name {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-family: monospace;
}

.contents-icon {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.contents-size {
  color: var(--p-text-muted-color);
}

.overview-hint {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  border: 1px dashed var(--p-content-border-color);
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
