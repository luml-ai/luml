<template>
  <WorkspacePath
    class="mb-3"
    :path="path"
    @navigate="router.push({ name: ROUTE_NAMES.WORKSPACES, query: { directory: $event } })"
  />
  <!-- Message draws its border as an outline outside its box; main clips anything past its edges. -->
  <Message severity="info" class="mx-(--p-message-border-width) mb-4"
    >Read-only experiment from {{ baseName(path) }}</Message
  >
  <p v-if="error" role="alert">{{ error }}</p>
  <Skeleton v-else-if="!archive" height="16rem" />
  <template v-else>
    <h1 class="text-2xl font-medium mb-3">{{ name }}</h1>
    <DetailsTabs v-model="tab" class="mb-4" />
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
      <ExperimentStatusNotices :statuses="dynamicMetrics.statuses" :models-info="modelsInfo" />
      <DynamicMetrics :models-info="modelsInfo" :show-title="false" />
      <p v-if="metricsEmpty" class="text-muted-color">No metrics found in this experiment</p>
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
import { useRouter } from 'vue-router'
import { Card, Message, Skeleton } from 'primevue'
import {
  DynamicMetrics,
  MarkdownRendererKey,
  EvalsDatasetsList,
  ExperimentSnapshotWorkerProxy,
  ExperimentStatusNotices,
  provideTheme,
  TraceDialog,
  TracesDialog,
  TracesWrapper,
  useAnnotationsStore,
  useDynamicMetricsStore,
  useEvalsStore,
} from '@luml/experiments'
import { renderMarkdown } from '@luml/attachments'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { ArchiveInspection } from '@/api/slices/workspace/workspace.interface'
import ArchiveAttachments from '@/components/workspace/ArchiveAttachments.vue'
import WorkspacePath from '@/components/workspace/WorkspacePath.vue'
import DetailsTabs from '@/components/experiments/details/DetailsTabs.vue'
import { getErrorMessage } from '@/helpers/errors'
import { findSnapshotMember, loadSnapshotSource } from '@/helpers/experimentSnapshot'
import { baseName } from '@/helpers/path'
import { ROUTE_NAMES } from '@/router/router.const'
import { useThemeStore } from '@/store/theme'
import ParametersCard from '@/table-cards/ParametersCard.vue'

const props = defineProps<{ path: string }>()
const router = useRouter()
const tab = ref('Overview')
const evals = useEvalsStore()
const annotations = useAnnotationsStore()
const dynamicMetrics = useDynamicMetricsStore()
provideTheme(toRef(useThemeStore(), 'theme'))
provide(MarkdownRendererKey, renderMarkdown)
const archive = shallowRef<ArchiveInspection>()
const parameters = shallowRef<{ name: string; value: string }[]>([])
const error = ref('')
// The catalog, not `dynamic_params`, says which metrics exist: it is read with the charts.
const metricsEmpty = computed(
  () =>
    !dynamicMetrics.loading &&
    dynamicMetrics.catalogs !== null &&
    dynamicMetrics.catalogs.errors.size === 0 &&
    dynamicMetrics.metricsNames.length === 0,
)
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
      const member = findSnapshotMember(result.files)
      if (!member) throw new Error('The experiment database is missing from this archive.')
      const source = await loadSnapshotSource(path, member, controller.signal)
      if (controller.signal.aborted) return
      const renewUrl = () => workspaceApi.fileUrl(path, member.name)
      provider = markRaw(
        new ExperimentSnapshotWorkerProxy(
          new Worker(
            new URL('../../../../../extras/js/experimentSnapshotWorker.ts', import.meta.url),
            { type: 'module' },
          ),
          { sourceUrls: { get: renewUrl, renew: renewUrl } },
        ),
      )
      await provider.init([{ modelId: path, source }], controller.signal)
      const [status] = await provider.getExperimentStatuses(controller.signal)
      if (status?.error) throw new Error(status.error.message)
      const params = await provider.getLoggedParameters(path, controller.signal)
      if (controller.signal.aborted) return
      parameters.value = params
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
