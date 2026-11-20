<template>
  <div v-if="!inspection || inspection.kind === 'unknown'" class="archive-state" role="status">
    {{ error || (inspection ? 'No preview for this file type' : 'Loading preview…') }}
  </div>
  <div v-else class="luml-preview">
    <p v-if="error" role="alert">{{ error }}</p>
    <div class="overview-hint">
      <span>For full overview</span>
      <div class="actions">
        <Button
          v-if="inspection.kind === 'experiment'"
          as="router-link"
          :to="{ name: ROUTE_NAMES.WORKSPACE_EXPERIMENT, query: { file: file.path } }"
          label="Open in Experiments"
          severity="secondary"
          size="small"
        >
          <template #icon><FlaskConical :size="14" /></template>
        </Button>
        <UploadButton
          :artifact-kind="inspection.kind"
          :default-name="
            typeof inspection.manifest?.name === 'string' ? inspection.manifest.name : file.name
          "
          :publish="(target) => workspaceApi.publishFile(file.path, target)"
        />
      </div>
    </div>

    <section v-if="inspection.kind === 'dataset'" class="section">
      <h3>Data</h3>
      <Tabs v-if="inspection.splits?.length" v-model:value="activeSplit" class="mb-3">
        <TabList>
          <Tab v-for="(item, index) in inspection.splits" :key="index" :value="index">
            {{ item.subset }} / {{ item.name }}
          </Tab>
        </TabList>
      </Tabs>
      <FilePreview
        v-if="chunk && split"
        dataset-split
        :key="`${revision}-${activeSplit}`"
        :file-name="`data.${split.format}`"
        :file-size="chunk.size"
        supports-partial-preview
        :source="chunkSource"
        :total-rows="split.num_rows ?? -1"
        class="chunk-preview"
      />
      <p v-else class="text-muted-color">No data to display</p>
    </section>

    <section class="section">
      <h3>Manifest</h3>
      <UiCodeEditor
        class="manifest"
        :model-value="manifestYaml"
        language="yaml"
        aria-label="Archive manifest"
        max-height="320px"
        readonly
      />
    </section>

    <section class="section">
      <h3>Contents</h3>
      <ul class="contents">
        <li v-for="entry in contents" :key="entry.name">
          <div v-if="entry.size === null" class="contents-row">
            <span class="contents-name"><Folder :size="14" />{{ entry.name }}</span>
          </div>
          <button v-else class="contents-row" @click="selected = entry">
            <span class="contents-name"><File :size="14" />{{ entry.name }}</span>
            <span class="text-muted-color shrink-0">{{ getSizeText(entry.size, ' ') }}</span>
          </button>
        </li>
      </ul>
    </section>
    <Dialog
      :visible="!!selected"
      :header="selected?.name"
      modal
      class="w-[min(90vw,960px)]"
      @update:visible="selected = undefined"
    >
      <FilePreview
        v-if="selected"
        :key="revision"
        :file-name="selected.name"
        :file-size="selected.size"
        supports-partial-preview
        :source="selectedSource"
      />
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { Button, Dialog, Tab, TabList, Tabs } from 'primevue'
import { File, FlaskConical, Folder } from 'lucide-vue-next'
import { stringify } from 'yaml'
import { FilePreview } from '@luml/attachments'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type {
  ArchiveFile,
  ArchiveInspection,
  WorkspaceFile,
} from '@/api/slices/workspace/workspace.interface'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'
import UploadButton from '@/components/upload/UploadButton.vue'
import { getErrorMessage } from '@/helpers/errors'
import { getSizeText } from '@/helpers/string'
import { ROUTE_NAMES } from '@/router/router.const'

const props = defineProps<{ file: WorkspaceFile; refreshKey: number }>()
const inspection = shallowRef<ArchiveInspection>()
const error = ref('')
const selected = ref<ArchiveFile>()
const activeSplit = ref(0)
const revision = ref(0)
const split = computed(() => inspection.value?.splits?.[activeSplit.value])
const chunk = computed(() =>
  inspection.value?.files.find((entry) => entry.name === split.value?.files[0]),
)
function memberSource(entry: ArchiveFile | undefined) {
  const path = props.file.path
  return () => workspaceApi.fileUrl(path, entry!.name)
}
const chunkSource = computed(() => memberSource(chunk.value))
const selectedSource = computed(() => memberSource(selected.value))
const manifestYaml = computed(() => stringify(inspection.value?.manifest))
const contents = computed(() => {
  const rows: (ArchiveFile | { name: string; size: null })[] = []
  const folders = new Set<string>()
  for (const file of inspection.value?.files ?? []) {
    const folder = file.name.slice(0, file.name.indexOf('/') + 1)
    if (folder && !folders.has(folder)) {
      rows.push({ name: folder, size: null })
      folders.add(folder)
    }
    rows.push(file)
  }
  return rows
})

watch(
  [() => props.file.path, () => props.refreshKey],
  async ([path], _, onCleanup) => {
    let active = true
    onCleanup(() => {
      active = false
    })
    try {
      const result = await workspaceApi.inspectFile(path)
      if (!active) return
      inspection.value = result
      if (!result.splits?.[activeSplit.value]) activeSplit.value = 0
      if (selected.value)
        selected.value = result.files.find((entry) => entry.name === selected.value?.name)
      revision.value++
      error.value = ''
    } catch (failure) {
      if (active) error.value = getErrorMessage(failure)
    }
  },
  { immediate: true },
)
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
.overview-hint,
.archive-state {
  border: 1px dashed var(--p-content-border-color);
  border-radius: 8px;
  color: var(--p-text-muted-color);
}
.archive-state {
  flex: 1;
  display: grid;
  place-items: center;
}
.overview-hint,
.actions,
.contents-row,
.contents-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.overview-hint {
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}
.section {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
}
h3 {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
}
.manifest :deep(.cm-editor) {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-content-background);
  font-size: 13px;
}
.manifest :deep(.cm-gutters) {
  display: none;
}
.manifest :deep(.cm-scroller) {
  line-height: 1.5;
}
.manifest :deep(.cm-content) {
  padding: 12px;
}
.chunk-preview {
  padding: 0;
}
.contents {
  margin: 0;
  padding: 0;
  list-style: none;
}
.contents-row {
  width: 100%;
  justify-content: space-between;
  padding: 0.3125rem 0;
  text-align: left;
  font-size: 0.8125rem;
}
button.contents-row {
  cursor: pointer;
}
button.contents-row:hover .contents-name {
  text-decoration: underline;
}
.contents-name {
  font-family: monospace;
  overflow-wrap: anywhere;
}
.contents-name svg {
  flex-shrink: 0;
  color: var(--p-text-muted-color);
}
</style>
