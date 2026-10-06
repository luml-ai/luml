<template>
  <article
    class="rounded-lg border bg-surface-0 dark:bg-surface-900 flex flex-col min-w-0"
    :class="[
      loudError
        ? 'border-(--p-message-error-border-color)'
        : 'border-surface-200 dark:border-surface-700',
      selected ? 'ring-2 ring-primary-500' : '',
    ]"
  >
    <header class="flex flex-col gap-1.5" :class="headerPad">
      <div class="flex items-start gap-2.5 min-w-0">
        <div class="flex items-center gap-x-2.5 gap-y-1 flex-wrap min-w-0 flex-1">
          <h3 v-if="unnamed" class="min-w-0">
            <Button
              v-tooltip.top="cell.flag!.message"
              text
              severity="secondary"
              :aria-label="`name this cell. ${cell.slug} is a placeholder.`"
              :pt="NAME_PT"
              @click="emit('rename')"
            >
              <span class="font-mono font-semibold italic" :class="titleSize">{{ cell.slug }}</span>
              <Pencil :size="14" class="shrink-0" />
            </Button>
          </h3>
          <h3
            v-else
            class="font-mono font-semibold transition-colors duration-500"
            :class="[titleSize, cell.renamedFrom ? 'text-primary-600 dark:text-primary-400' : '']"
          >
            {{ cell.slug }}
          </h3>
          <span
            v-if="cell.renamedFrom"
            class="text-sm text-muted-color transition-opacity duration-500"
          >
            renamed from <code class="font-mono">{{ cell.renamedFrom }}</code>
          </span>
          <KindBadge v-if="primary" :kind="primary.kind" icon-only :icon-size="14" />
          <StatusChip
            v-if="cell.status !== 'materialized'"
            :status="cell.status"
            :stale="cell.stale"
          />
          <MetaBadge v-if="cell.externalInput" variant="external" />
        </div>
        <div v-if="timingLine" class="shrink-0 pt-0.5 text-right text-sm text-muted-color">
          {{ timingLine }}
        </div>
      </div>
      <p
        v-if="cell.doc && !selectedOutput && activeTab !== 'code'"
        class="text-sm text-muted-color"
      >
        {{ cell.doc }}
      </p>
    </header>

    <div class="flex flex-col" :class="bodyPad">
      <Message v-if="loudFlag" severity="warn" size="small">
        <template #icon><TriangleAlert :size="14" class="shrink-0" /></template>
        <div class="flex w-full flex-wrap items-center gap-2">
          <span class="min-w-40 flex-1 text-sm" v-html="flagHtml" />
          <Button
            v-if="cell.flag!.didYouMean"
            text
            severity="warn"
            label="apply suggestion"
            :disabled="!detailLoaded"
            @click="applySuggestion"
          />
        </div>
      </Message>
      <p v-else-if="quietFlag" class="text-sm text-muted-color" v-html="flagHtml" />

      <p v-if="autoLine" class="flex items-start gap-1.5 text-sm text-muted-color">
        <ZapOff :size="14" class="mt-0.5 shrink-0" />
        <span>{{ autoLine }}</span>
      </p>

      <p
        v-if="cell.sdkVersionWarning"
        class="flex items-start gap-1.5 text-sm text-(--p-message-warn-color)"
      >
        <TriangleAlert :size="14" class="mt-0.5 shrink-0" />
        <span>{{ cell.sdkVersionWarning }}</span>
      </p>

      <ConflictMenu v-if="cell.conflict" @resolve="emit('resolve-conflict', $event)" />

      <Message v-if="loudError" severity="error" size="small">
        <template #icon><CircleAlert :size="14" class="shrink-0" /></template>
        <code class="font-mono text-sm">{{ cell.error!.summary }}</code>
      </Message>

      <CellTabStrip :tabs="tabs" :selected="activeTab" @select="selectedTab = $event" />

      <div class="min-w-0">
        <template v-if="selectedOutput">
          <div
            v-if="cell.status === 'unmaterialized'"
            class="rounded-lg border border-dashed border-surface-200 dark:border-surface-700 px-3 py-6 text-center text-sm text-muted-color"
          >
            not materialized on this lane
          </div>
          <div v-else class="overflow-auto" :class="density === 'canvas' ? 'max-h-72' : 'max-h-80'">
            <RendererHost
              :preview="selectedOutput.preview"
              :density="density"
              :download-url="selectedOutput.downloadUrl"
            />
          </div>
          <div
            v-if="publishModel && selectedOutput.declared === 'model' && selectedOutput.downloadUrl"
            class="mt-2 flex justify-end"
          >
            <ModelUploadLink
              :publish="(target) => publishModel!(selectedOutput!.name, target)"
              :default-name="`${cell.slug}.${selectedOutput.name}`"
            />
          </div>
        </template>
        <CodeView
          v-else-if="activeTab === 'code'"
          v-model:editing="editing"
          v-model:draft="editorDraft"
          :cell="cell"
          :density="density"
          :disabled="!detailLoaded"
          @edit="emit('edit', $event)"
          @edit-start="emit('edit-start')"
        />
        <ConsoleView v-else-if="activeTab === 'console'" :lines="cell.console ?? []" />
        <LogsView
          v-else-if="activeTab === 'logs'"
          :logs="cell.logs"
          :error="cell.error"
          :tracker="cell.tracker"
        />

        <p
          v-if="quietError && activeTab === 'code'"
          class="mt-2 border-l-2 border-(--p-message-error-border-color) pl-2 font-mono text-sm text-muted-color"
        >
          {{ cell.error!.summary }}
        </p>

        <div
          v-if="density === 'notebook' && activeTab === 'code' && primary && !cell.isNote"
          class="mt-3 max-h-64 overflow-auto border-t border-surface-200 pt-2.5 dark:border-surface-700"
        >
          <RendererHost
            :preview="primary.preview"
            density="notebook"
            :download-url="primary.downloadUrl"
          />
        </div>
      </div>
    </div>

    <footer class="flex flex-wrap items-center justify-between gap-3" :class="footerPad">
      <ProvenanceLine
        v-if="cell.provenance"
        :provenance="cell.provenance"
        :repaired-attempts="cell.error?.repairedAttempts"
        class="flex-1 min-w-0"
      />
      <span v-else class="flex-1" />
      <CellOpRow
        :cell="cell"
        :density="density"
        :awaiters="awaiters"
        :preflight="preflight"
        :can-move-up="canMoveUp"
        :can-move-down="canMoveDown"
        @run="emit('run', $event)"
        @preflight="emit('preflight')"
        @stop="emit('stop')"
        @expand="emit('expand')"
        @copy-context="emit('copy-context')"
        @rename="emit('rename')"
        @delete="emit('delete')"
        @duplicate="emit('duplicate')"
        @add-downstream="emit('add-downstream')"
        @move-up="emit('move-up')"
        @move-down="emit('move-down')"
        @eager="emit('eager', $event)"
      />
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Message } from 'primevue'
import { CircleAlert, Pencil, TriangleAlert, ZapOff } from 'lucide-vue-next'
import { formatCost } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, Preflight } from '../../model/types'
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StatusChip from '../../ui/StatusChip.vue'
import RendererHost from '../../renderers/RendererHost.vue'
import ModelUploadLink from '../../ui/ModelUploadLink.vue'
import type { PublishTarget } from '@/components/upload/upload.interface'
import CellOpRow from './CellOpRow.vue'
import CellTabStrip, { type CellTab } from './CellTabStrip.vue'
import CodeView from './CodeView.vue'
import ConflictMenu from './ConflictMenu.vue'
import ConsoleView from './ConsoleView.vue'
import LogsView from './LogsView.vue'
import ProvenanceLine from './ProvenanceLine.vue'
import { inlineCodeHtml } from './inlineCode'

const props = withDefaults(
  defineProps<{
    cell: FlowCell
    density: 'canvas' | 'notebook'
    selected?: boolean
    awaiters?: number
    preflight?: Preflight | null
    canMoveUp?: boolean
    canMoveDown?: boolean
    detailLoaded?: boolean
    publishModel?: (output: string, target: PublishTarget) => Promise<{ job_id: string }>
  }>(),
  { detailLoaded: true },
)

const emit = defineEmits<{
  tab: [id: string]
  expand: []
  run: [payload: { force: boolean }]
  preflight: []
  stop: []
  rename: []
  delete: []
  duplicate: []
  'add-downstream': []
  'move-up': []
  'move-down': []
  eager: [on: boolean]
  'copy-context': []
  'resolve-conflict': [choice: 'overwrite' | 'fork']
  edit: [payload: { source: string }]
  'edit-start': []
}>()

const editing = defineModel<boolean>('editing', { default: false })
const editorDraft = defineModel<string>('draft', { default: '' })

const titleSize = computed(() => (props.density === 'canvas' ? 'text-lg' : 'text-base'))

const NAME_PT = { root: { class: 'gap-1.5 p-0 text-muted-color hover:bg-transparent!' } }

const headerPad = computed(() => (props.density === 'canvas' ? 'px-4 pt-4' : 'px-4 pt-3.5'))
const bodyPad = computed(() =>
  props.density === 'canvas' ? 'px-4 pb-4 pt-3 gap-3.5' : 'px-4 pb-3.5 pt-2.5 gap-3',
)
const footerPad = computed(() => (props.density === 'canvas' ? 'px-4 py-2.5' : 'px-4 py-2'))

const primary = computed(() => primaryOutput(props.cell))

const timingLine = computed(() => {
  const timing = props.cell.timing
  if (!timing) return ''
  const parts: string[] = []
  if (timing.costSeconds !== undefined) {
    parts.push(`${props.cell.status === 'running' ? '~' : ''}${formatCost(timing.costSeconds)}`)
  }
  if (timing.cached) parts.push('cached')
  if (timing.olderEnv) parts.push('older env')
  if (timing.finishedAgo) parts.push(timing.finishedAgo)
  return parts.join(' · ')
})

const autoLine = computed(() => {
  const declined = props.cell.autoDeclined
  if (!declined) return ''
  if (props.cell.status === 'unmaterialized' && declined.reason === 'never-timed') {
    return 'never run yet — run it once to enable auto-refresh'
  }
  if (declined.reason === 'blocked') {
    return (
      declined.detail ??
      'blocked by a failed cell above it. edit that failed cell to unblock auto-refresh.'
    )
  }
  if (declined.reason === 'never-timed') {
    return 'never run here, so its cost is unknown. run it once and it keeps itself fresh.'
  }
  if (declined.reason === 'refresh-failed') {
    return declined.detail ?? 'could not refresh. repair the cause or run it explicitly to retry.'
  }
  if (declined.reason === 'unresolvable-reference') {
    return declined.detail ?? 'one of its inputs is not available on this lane.'
  }
  if (declined.reason === 'dangling-experiment') {
    return (
      declined.detail ??
      'an experiment above it is no longer available. run it by hand to record it again.'
    )
  }
  return `too expensive to refresh on its own (~${formatCost(declined.estimateSeconds)}). run it when you want it.`
})

const loudError = computed(() => props.cell.error?.author === 'user')
const quietError = computed(
  () => props.cell.error?.author === 'agent' && props.density === 'notebook',
)

const unnamed = computed(() => props.cell.flag?.code === 'placeholder_slug')

const quietFlag = computed(() => props.cell.flag?.code === 'hygiene')

const loudFlag = computed(() => Boolean(props.cell.flag) && !unnamed.value && !quietFlag.value)

const flagHtml = computed(() => {
  const flag = props.cell.flag
  if (!flag) return ''
  const suffix = flag.didYouMean ? `. did you mean \`${flag.didYouMean}\`?` : ''
  return inlineCodeHtml(flag.message + suffix)
})

function applySuggestion(): void {
  if (!props.detailLoaded) return
  const flag = props.cell.flag
  if (!flag?.didYouMean) return
  const broken = flag.message.match(/`([^`]+)`/)?.[1]
  const source = broken ? props.cell.source.split(broken).join(flag.didYouMean) : props.cell.source
  emit('edit', { source })
}

const tabs = computed<CellTab[]>(() => {
  const list: CellTab[] = props.cell.outputs.map((output) => ({
    id: `out:${output.name}`,
    label: output.name,
    kind: output.kind,
  }))
  list.push({ id: 'code', label: 'code', icon: 'code' })
  if (props.cell.status === 'running')
    list.push({ id: 'console', label: 'console', icon: 'console', live: true })
  if (!props.cell.isNote) list.push({ id: 'logs', label: 'logs', icon: 'logs' })
  return list
})

function defaultTab(): string {
  if (props.cell.status === 'running') return 'console'
  const first = primary.value
  if (props.density === 'notebook' && first?.kind !== 'note') return 'code'
  return first ? `out:${first.name}` : 'code'
}

const selectedTab = ref(defaultTab())

watch(
  () => [props.cell.slug, props.cell.status, props.density] as const,
  ([, status], [, previousStatus]) => {
    if (status === 'running' && previousStatus !== 'running' && !editing.value) {
      selectedTab.value = 'console'
    }
  },
)

const activeTab = computed(() =>
  tabs.value.some((tab) => tab.id === selectedTab.value) ? selectedTab.value : defaultTab(),
)

watch(activeTab, (id) => emit('tab', id), { immediate: true })

const selectedOutput = computed(() => {
  if (!activeTab.value.startsWith('out:')) return undefined
  const name = activeTab.value.slice(4)
  return props.cell.outputs.find((output) => output.name === name)
})
</script>
