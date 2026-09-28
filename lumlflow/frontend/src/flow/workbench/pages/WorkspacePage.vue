<template>
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-8 pb-16">
    <header>
      <h3 class="text-2xl font-medium">Workspace</h3>
      <p v-if="connected" class="mt-1 truncate font-mono text-sm text-muted-color">
        {{ directory || 'resolving the launch directory…' }}
      </p>
    </header>

    <NotConnectedNotice v-if="!connected" />
    <DaemonDownBanner v-else-if="unreachable" detail="nothing to list" />
    <p v-if="refusal" class="text-base text-(--p-message-error-color)">{{ refusal }}</p>

    <div
      v-if="!offline || flows.length"
      class="divide-y divide-surface-200 rounded-lg border border-surface-200 bg-surface-0 dark:divide-surface-700 dark:border-surface-700 dark:bg-surface-900"
    >
      <RouterLink
        v-for="flow in flows"
        :key="flow.path"
        :to="{ path: flowPath(flow.path), query: { directory } }"
        class="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-50 dark:hover:bg-surface-800"
      >
        <FileCode2 :size="16" class="shrink-0 text-primary-500" />
        <span class="min-w-0 flex-1 truncate font-mono text-base" :title="flow.path">
          {{ flow.relative_path }}
        </span>
        <span class="whitespace-nowrap text-sm text-muted-color">flow</span>
        <ArrowRight :size="14" class="shrink-0 text-muted-color" />
      </RouterLink>

      <p v-if="!offline && !flows.length" class="px-4 py-3 text-base text-muted-color">
        no flows here yet
      </p>
    </div>

    <div v-if="connected" class="flex flex-col gap-2">
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
          :disabled="offline || !newFlow.trim() || !directory"
        />
        <Button text severity="secondary" label="cancel" @click="creating = false" />
        <span class="font-mono text-sm text-muted-color">
          {{ newFlow.trim() || 'churn' }}.flow
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
import { RouterLink, useRoute } from 'vue-router'
import { Button, InputText } from 'primevue'
import { ArrowRight, FileCode2, Plus } from 'lucide-vue-next'

import { DaemonUnreachable, FlowApi } from '@/flow/api/client'
import type { WorkspaceListing } from '@/flow/api/client'
import { browserToken, tokenRejected } from '@/flow/api/token'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import NotConnectedNotice from '../components/session/NotConnectedNotice.vue'
import { flowPath } from '../model/routes'

const route = useRoute()
const launchDirectory = queryString(route.query.directory)
const token = browserToken()
const api = token === null ? null : new FlowApi({ token })

const listing = shallowRef<WorkspaceListing | null>(null)
const connected = computed(() => api !== null && !tokenRejected.value)
const unreachable = ref(false)
const offline = computed(() => !connected.value || unreachable.value)
const refusal = ref<string | null>(null)
const newFlow = ref('')
const creating = ref(false)
const initializing = ref(false)
const warnings = ref<string[]>([])

const directory = computed(() => listing.value?.directory ?? launchDirectory ?? '')
const flows = computed(() => listing.value?.flows ?? [])

async function load(): Promise<void> {
  if (api === null) return
  try {
    listing.value = await api.call(
      'workspace.list',
      launchDirectory === null ? {} : { directory: launchDirectory },
    )
    unreachable.value = false
    refusal.value = null
  } catch (failure) {
    reportFailure(failure)
  }
}

async function initHere(): Promise<void> {
  const name = newFlow.value.trim()
  if (api === null || !name || !directory.value || initializing.value) return
  initializing.value = true
  refusal.value = null
  warnings.value = []
  let scaffolded = false
  let failure: unknown = null
  try {
    const created = await api.call('flow.init', { name, directory: directory.value })
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
  if (scaffolded) await load()
  if (failure !== null) reportFailure(failure)
  initializing.value = false
}

function reportFailure(failure: unknown): void {
  if (failure instanceof DaemonUnreachable) {
    unreachable.value = true
    return
  }
  unreachable.value = false
  refusal.value = tokenRejected.value
    ? null
    : failure instanceof Error
      ? failure.message
      : String(failure)
}

function queryString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

void load()
</script>
