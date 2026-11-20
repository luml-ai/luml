<template>
  <RouterLink
    class="self-start mb-3 text-primary"
    :to="{ name: ROUTE_NAMES.WORKSPACES, query: { directory: parentDirectory(path), file: path } }"
    >Back to Workspace</RouterLink
  >
  <Message severity="info" class="mb-4">Read-only experiment from {{ baseName(path) }}</Message>
  <p v-if="error" role="alert">{{ error }}</p>
  <Skeleton v-else-if="!archive" height="16rem" />
  <template v-else>
    <h1 class="text-2xl font-medium mb-3">{{ name }}</h1>
    <Tabs v-model:value="tab" class="mb-4">
      <TabList :pt="TABLIST_PT">
        <Tab v-for="(icon, label) in tabs" :key="label" :value="label">
          <component :is="icon" :size="14" /> {{ label }}
        </Tab>
      </TabList>
    </Tabs>
    <div v-if="tab === 'Overview'" class="grid grid-cols-2 gap-6">
      <ParametersCard :parameters="parameters" />
      <div>
        <h3 class="text-lg mb-4">About this experiment</h3>
        <Card>
          <template #content>
            <dl class="grid grid-cols-[auto_1fr] gap-4">
              <template v-for="(value, field) in metadata" :key="field">
                <dt>{{ field }}</dt>
                <dd>{{ value }}</dd>
              </template>
            </dl>
          </template>
        </Card>
      </div>
    </div>
    <template v-else-if="tab === 'Metrics'">
      <DynamicMetrics
        v-if="metrics.length"
        :metrics-names="metrics"
        :models-info="modelsInfo"
        :show-title="false"
      />
      <p v-else class="text-muted-color">No metrics found in this experiment</p>
    </template>
    <TracesWrapper v-else-if="tab === 'Traces'" :artifact-id="path" />
    <EvalsDatasetsList
      v-else-if="tab === 'Evals'"
      :models-info="modelsInfo"
      loader-height="calc(100vh - 250px)"
      empty-message="No evals found in this experiment"
    />
    <ArchiveAttachments v-else :key="path" :path="path" :files="archive.files" />
    <TracesDialog
      :visible="!!evals.currentEvalData"
      :models-info="modelsInfo"
      @update:visible="evals.resetCurrentEvalData"
    />
    <TraceDialog
      v-if="evals.selectedTrace"
      visible
      :tree="evals.selectedTrace.tree"
      :count="evals.selectedTrace.count"
      :min-span-time="evals.selectedTrace.minTime"
      :max-span-time="evals.selectedTrace.maxTime"
      :artifact-id="path"
      :trace-id="evals.selectedTrace.traceId"
      @update:visible="evals.resetSelectedTrace"
    />
  </template>
</template>

<script setup lang="ts">
import { computed, markRaw, onUnmounted, provide, ref, shallowRef, toRef, watch } from 'vue'
import { Card, Message, Skeleton, Tab, TabList, Tabs } from 'primevue'
import { Braces, LayoutDashboard, ListTree, Paperclip, Table2 } from 'lucide-vue-next'
import {
  DynamicMetrics,
  MarkdownRendererKey,
  EvalsDatasetsList,
  ExperimentSnapshotWorkerProxy,
  provideTheme,
  TraceDialog,
  TracesDialog,
  TracesWrapper,
  useAnnotationsStore,
  useEvalsStore,
} from '@luml/experiments'
import { renderMarkdown } from '@luml/attachments'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { ArchiveInspection } from '@/api/slices/workspace/workspace.interface'
import ArchiveAttachments from '@/components/workspace/ArchiveAttachments.vue'
import { TABLIST_PT } from '@/components/experiments/details/details.const'
import { getErrorMessage } from '@/helpers/errors'
import { baseName, parentDirectory } from '@/helpers/path'
import { ROUTE_NAMES } from '@/router/router.const'
import { useThemeStore } from '@/store/theme'
import ParametersCard from '@/table-cards/ParametersCard.vue'

const props = defineProps<{ path: string }>()
const tabs = {
  Overview: LayoutDashboard,
  Metrics: Table2,
  Traces: ListTree,
  Evals: Braces,
  Attachments: Paperclip,
}
const tab = ref('Overview')
const evals = useEvalsStore()
const annotations = useAnnotationsStore()
provideTheme(toRef(useThemeStore(), 'theme'))
provide(MarkdownRendererKey, renderMarkdown)
const archive = shallowRef<ArchiveInspection>()
const parameters = shallowRef<{ name: string; value: string }[]>([])
const metrics = ref<string[]>([])
const error = ref('')
const name = computed(() =>
  typeof archive.value?.manifest?.name === 'string'
    ? archive.value.manifest.name
    : baseName(props.path),
)
const modelsInfo = computed(() => ({
  [props.path]: { name: name.value, color: 'var(--p-primary-color)' },
}))
const metadata = computed(() => {
  const payload = archive.value?.manifest?.payload
  const fields: Record<string, string> = {}
  if (payload && typeof payload === 'object') {
    if ('local_experiment_id' in payload && typeof payload.local_experiment_id === 'string')
      fields['Experiment ID'] = payload.local_experiment_id
    if ('status' in payload && typeof payload.status === 'string') fields.Status = payload.status
    if ('group' in payload && typeof payload.group === 'string') fields.Group = payload.group
    if ('tags' in payload && Array.isArray(payload.tags))
      fields.Tags = payload.tags.filter((tag) => typeof tag === 'string').join(', ')
  }
  return fields
})

// Child tabs reset their cursors during unmount and still need the provider then.
onUnmounted(() => evals.resetProvider())

watch(
  () => props.path,
  async (path, _, onCleanup) => {
    const controller = new AbortController()
    let provider: ExperimentSnapshotWorkerProxy | undefined
    onCleanup(() => {
      controller.abort()
      provider?.terminate()
      evals.reset()
    })
    annotations.disallowEdit()
    archive.value = undefined
    tab.value = 'Overview'
    error.value = ''
    try {
      if (!path) throw new Error('An experiment archive path is required.')
      const result = await workspaceApi.inspectFile(path)
      if (controller.signal.aborted) return
      if (result.kind !== 'experiment') throw new Error('This file is not an experiment archive.')
      const response = await fetch(await workspaceApi.fileUrl(path, 'exp.db.zip'), {
        signal: controller.signal,
      })
      if (!response.ok)
        throw new Error(`Could not read the experiment database (${response.status})`)
      const buffer = await response.arrayBuffer()
      if (controller.signal.aborted) return
      provider = markRaw(
        new ExperimentSnapshotWorkerProxy(
          new Worker(
            new URL('../../../../../extras/js/experimentSnapshotWorker.ts', import.meta.url),
            { type: 'module' },
          ),
        ),
      )
      await provider.init([{ modelId: path, buffer }], controller.signal)
      const [params, names] = await Promise.all([
        provider.getLoggedParameters(path, controller.signal),
        provider.getDynamicMetricsNames(),
      ])
      if (controller.signal.aborted) return
      parameters.value = params
      metrics.value = names
      evals.setProvider(provider)
      archive.value = result
    } catch (failure) {
      provider?.terminate()
      if (!controller.signal.aborted) error.value = getErrorMessage(failure)
    }
  },
  { immediate: true },
)
</script>
