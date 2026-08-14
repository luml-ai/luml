<template>
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-8 pb-16">
    <header>
      <h3 class="text-2xl font-medium">Workspace</h3>
      <p v-if="connected" class="mt-1 truncate font-mono text-sm text-muted-color">
        {{ listing?.root ?? 'resolving the launch directory…' }}
      </p>
    </header>

    <NotConnectedNotice v-if="!connected" />
    <DaemonDownBanner v-else-if="unreachable" detail="nothing to list" />

    <!--
      Up is a first-class direction: the launch directory is where browsing
      starts, not where it ends, so a flow a neighbouring project holds is a
      few clicks away rather than a reason to stop lumlflow and start it again.
    -->
    <nav v-if="connected" class="flex flex-wrap items-center gap-1 text-base">
      <Button
        v-if="parent !== null"
        v-tooltip.top="'up one directory'"
        text
        rounded
        severity="secondary"
        size="small"
        aria-label="up one directory"
        @click="up()"
      >
        <template #icon><ArrowUp :size="14" /></template>
      </Button>

      <Breadcrumb v-if="!outside" :model="trail" :pt="BREADCRUMB_PT">
        <template #item="{ item }">
          <Button
            link
            :label="String(item.label)"
            :pt="item.path === here ? CRUMB_CURRENT_PT : CRUMB_PT"
            @click="browse(item.path as string)"
          />
        </template>
      </Breadcrumb>

      <!--
        Above the launch directory there is no root-relative trail to draw, so
        the address is shown whole and `workspace` is the way back to it.
      -->
      <template v-else>
        <span class="px-1.5 py-0.5 font-mono text-base font-medium">{{ here }}</span>
        <Button
          class="ml-2"
          link
          severity="secondary"
          label="back to workspace"
          :pt="CRUMB_PT"
          @click="browse('')"
        />
      </template>
    </nav>

    <p v-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>

    <!-- An empty frame under a notice claims a listing nobody has; last-known entries stay. -->
    <div
      v-if="!offline || entries.length"
      class="divide-y divide-surface-200 rounded-lg border border-surface-200 bg-surface-0 dark:divide-surface-700 dark:border-surface-700 dark:bg-surface-900"
    >
      <!--
        A flow is one entry and one gesture: open it. There is no chevron and no
        expansion, because its cells and its store are not files of this
        workspace — they are the document's insides.
      -->
      <RouterLink
        v-for="entry in flows"
        :key="entry.path"
        :to="flowPath(entry.path)"
        class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-50 dark:hover:bg-surface-800"
      >
        <FileCode2 :size="16" class="shrink-0 text-primary-500" />
        <span class="min-w-0 flex-1 truncate font-mono text-base">{{ entry.name }}</span>
        <span class="whitespace-nowrap text-sm text-muted-color">flow</span>
        <ArrowRight :size="14" class="shrink-0 text-muted-color" />
      </RouterLink>

      <Button
        v-for="entry in directories"
        :key="entry.path"
        text
        severity="secondary"
        :pt="ROW_PT"
        @click="browse(entry.path)"
      >
        <Folder :size="16" class="shrink-0 text-muted-color" />
        <span class="min-w-0 flex-1 truncate font-mono text-base font-normal">{{
          entry.name
        }}</span>
        <ChevronRight :size="14" class="shrink-0 text-muted-color" />
      </Button>

      <!-- Context, not content: workspace files are listed and never opened. -->
      <div
        v-for="entry in files"
        :key="entry.path"
        class="flex w-full items-center gap-3 px-4 py-3 text-muted-color"
      >
        <FileText :size="16" class="shrink-0" />
        <span class="min-w-0 flex-1 truncate font-mono text-base">{{ entry.name }}</span>
        <span v-if="entry.size !== null" class="whitespace-nowrap text-sm">
          {{ formatBytes(entry.size) }}
        </span>
      </div>

      <!-- "below" is the init field, which only the workspace has. -->
      <p v-if="!offline && !entries.length" class="px-4 py-3 text-base text-muted-color">
        {{ outside ? 'nothing here' : 'nothing here yet' }}
      </p>
    </div>

    <!-- A flow is created in the workspace, and above it "here" is not one. -->
    <p v-if="connected && outside" class="text-sm text-muted-color">
      flows are created in <span class="font-mono">{{ listing?.root }}</span>
    </p>

    <!-- A once-per-project gesture does not hold a permanent block. -->
    <div v-if="connected && !outside" class="flex flex-col gap-2">
      <Button v-if="!creating" class="self-start" text label="New flow" @click="creating = true">
        <template #icon><Plus :size="14" /></template>
      </Button>
      <form v-else class="flex flex-wrap items-center gap-2" @submit.prevent="initHere">
        <InputText
          v-model="newFlow"
          size="small"
          placeholder="churn"
          aria-label="new flow name"
          :disabled="offline"
        />
        <Button
          type="submit"
          label="init"
          :loading="initializing"
          :disabled="offline || !newFlow.trim()"
        />
        <Button text severity="secondary" label="cancel" @click="creating = false" />
        <span class="font-mono text-sm text-muted-color">
          {{ here ? `${here}/` : '' }}{{ newFlow.trim() || 'churn' }}.flow
        </span>
      </form>
      <p v-for="warning in warnings" :key="warning" class="text-sm text-(--p-message-warn-color)">
        {{ warning }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { RouterLink } from 'vue-router'
import { Breadcrumb, Button, InputText } from 'primevue'
import {
  ArrowRight,
  ArrowUp,
  ChevronRight,
  FileCode2,
  FileText,
  Folder,
  Plus,
} from 'lucide-vue-next'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import type { WorkspaceEntry, WorkspaceListing } from '@/flow/api/client'
import { browserToken, tokenRejected } from '@/flow/api/token'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import NotConnectedNotice from '../components/session/NotConnectedNotice.vue'
import { formatBytes } from '../model/format'
import { flowPath } from '../model/routes'

/**
 * The launch surface: the directory lumlflow was started in, and the ones above it.
 *
 * Flows are documents here. A `.flow` directory renders as one entry with one
 * gesture — open it — and never as a folder to walk into, the same way a
 * notebook is a file rather than a tree of cells. The server enforces the same
 * rule (a listing inside a flow is a refusal), so the two cannot drift.
 *
 * Browsing goes up as well as down, because the launch directory is a place the
 * user started from rather than a boundary they chose: a flow in a neighbouring
 * project is reached by climbing to it and opened where it is. What does not
 * move is the workspace — one venv, one set of helpers, one `AGENTS.md` — so
 * everything above it renders as context, and creating a flow stays inside.
 *
 * Everything else is context too: the helpers and data files a cell reaches
 * through `ctx.workspace_dir` are listed so the workspace is legible, and
 * nothing here opens one — viewers are not v1, and a file the store never
 * versions has no business looking editable.
 */

const token = browserToken()
const api = token === null ? null : new FlowApi({ token })

const listing = shallowRef<WorkspaceListing | null>(null)
const here = ref('')
// Two separate facts, and folding them together would report a healthy server
// as a stopped one: a tab with no token never asked — or asked with a token a
// restarted server refused — and only a round-trip nobody answered is the
// not-running state.
const connected = computed(() => api !== null && !tokenRejected.value)
const unreachable = ref(false)
const offline = computed(() => !connected.value || unreachable.value)
const refusal = ref<string | null>(null)
const newFlow = ref('')
const creating = ref(false)
const initializing = ref(false)
const warnings = ref<string[]>([])

// Where the listing sits relative to the launch directory, and what is above
// it — both the daemon's to say, so the page never parses a path to find out.
const outside = computed(() => listing.value?.outside ?? false)
const parent = computed(() => listing.value?.parent ?? null)

const entries = computed<WorkspaceEntry[]>(() => listing.value?.entries ?? [])
const flows = computed(() => entries.value.filter((entry) => entry.kind === 'flow'))
const directories = computed(() => entries.value.filter((entry) => entry.kind === 'dir'))
const files = computed(() => entries.value.filter((entry) => entry.kind === 'file'))

// A trail of root-relative crumbs, which only the workspace has: above it every
// path is absolute, and a crumb built from one would address the wrong place.
const BREADCRUMB_PT = { root: { class: 'bg-transparent p-0' } }
const CRUMB_PT = { root: { class: 'px-1.5 py-0.5 font-mono text-base font-normal' } }
const CRUMB_CURRENT_PT = { root: { class: 'px-1.5 py-0.5 font-mono text-base font-medium' } }
const ROW_PT = { root: { class: 'w-full justify-start gap-3 rounded-none px-4 py-3 text-left' } }

const crumbs = computed(() =>
  outside.value
    ? []
    : here.value
        .split('/')
        .filter(Boolean)
        .map((name, index, parts) => ({ name, path: parts.slice(0, index + 1).join('/') })),
)

/** The root plus the trail under it — one model for a real `Breadcrumb`. */
const trail = computed(() => [
  { label: 'workspace', path: '' },
  ...crumbs.value.map((crumb) => ({ label: crumb.name, path: crumb.path })),
])

async function load(path: string): Promise<void> {
  if (api === null) return
  try {
    const answer = await api.call('workspace.list', { path })
    listing.value = answer
    here.value = answer.path
    unreachable.value = false
    refusal.value = null
  } catch (failure) {
    reportFailure(failure)
  }
}

function browse(path: string): void {
  void load(path)
}

/** One directory up, wherever that is — including out of the workspace. */
function up(): void {
  if (parent.value !== null) void load(parent.value)
}

/**
 * `flow init` scaffolds unbound; the checkout is what makes the directory a
 * worktree on `main`. Both, in that order, is what the browser's door owes —
 * the same pair the CLI's `init` performs.
 */
async function initHere(): Promise<void> {
  const name = newFlow.value.trim()
  if (api === null || !name || initializing.value) return
  initializing.value = true
  refusal.value = null
  warnings.value = []
  // The scaffold lands before the checkout does, so a checkout that refuses
  // leaves a real flow on disk. Re-reading the listing is owed to it either
  // way — a directory on disk that the browser does not show is a flow the user
  // can neither open nor create again ("already exists").
  let scaffolded = false
  let failure: unknown = null
  try {
    const created = await api.call('flow.init', {
      name: here.value ? `${here.value}/${name}` : name,
    })
    scaffolded = true
    warnings.value = created.warnings
    newFlow.value = ''
    creating.value = false
    await api.call('flow.checkout', {
      flow: created.path,
      branch: 'main',
      intent: `init flow ${created.flow}`,
    })
  } catch (caught) {
    failure = caught
  }
  // A fresh listing clears the last refusal, so this one is reported after it.
  if (scaffolded) await load(here.value)
  if (failure !== null) reportFailure(failure)
  initializing.value = false
}

/**
 * A refusal names something about the request, which is proof somebody
 * answered; only nobody answering is the not-running state.
 */
function reportFailure(failure: unknown): void {
  if (failure instanceof DaemonUnreachable) {
    unreachable.value = true
    return
  }
  unreachable.value = false
  // A refused token has the notice above; its sentence repeated underneath
  // would ask twice for the one thing the reader is already being sent to do.
  if (tokenRejected.value) {
    refusal.value = null
    return
  }
  refusal.value = failure instanceof Error ? failure.message : String(failure)
}

void load('')
</script>
