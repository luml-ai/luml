<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-6 pb-12">
    <header class="flex flex-col gap-2">
      <h3 class="text-2xl font-medium">
        {{ compared.length >= 2 ? `Comparing ${compared.length} lanes` : 'Comparing lanes' }}
      </h3>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <BranchTag
          v-for="name in compared"
          :key="name"
          :name="name"
          :checked-out="name === session.brief.value?.branch"
        />
        <Button
          v-if="compared.length >= 2"
          class="ml-auto"
          size="small"
          text
          severity="secondary"
          label="Explain this diff"
          @click="onExplainDiff"
        >
          <template #icon><Send :size="14" /></template>
        </Button>
        <RouterLink class="link text-sm" :to="back">back to the workbench</RouterLink>
      </div>

      <!--
        Fewer than two is not an empty comparison, it is one nobody has chosen
        yet: the selection is the lane map's, and this route only renders it.
      -->
      <p v-if="compared.length < 2" class="text-base text-muted-color">
        Selection happens in the lane map. Pick 2–5 lanes there and land here.
      </p>
      <p v-else-if="area.error.value" class="text-base text-(--p-message-error-color)">
        {{ area.error.value }}
      </p>
      <p v-else-if="area.loading.value" class="text-base text-muted-color">reading the lanes…</p>
      <p v-else-if="!area.assets.value.length" class="text-base text-muted-color">
        these lanes hold the same cells and the same results
      </p>

      <label v-if="area.assets.value.length > 1" class="flex items-center gap-2 text-sm">
        <span class="text-muted-color">leading with</span>
        <Select
          v-model="focus"
          size="small"
          :options="area.assets.value"
          aria-label="asset the comparison leads with"
        />
      </label>
    </header>

    <Accordion v-model:value="open" multiple lazy>
      <AccordionPanel v-if="area.ready.value" value="results">
        <AccordionHeader>
          <span class="text-lg">Results · {{ area.focused.value }}</span>
        </AccordionHeader>
        <AccordionContent>
          <!-- Integrity warnings render inline at the top of the columns. -->
          <ResultColumns :compare="compare" />
        </AccordionContent>
      </AccordionPanel>

      <AccordionPanel v-if="area.assets.value.length" value="divergence">
        <AccordionHeader><span class="text-lg">Divergence</span></AccordionHeader>
        <AccordionContent>
          <div class="flex flex-col gap-4">
            <DivergencePointCard
              v-for="divergence in compare.definitionDivergences"
              :key="divergence.slug"
              :divergence="divergence"
            />
            <MaterializationRows
              v-if="compare.materializationRows.length"
              :rows="compare.materializationRows"
            />
            <Accordion
              v-if="compare.shapelessDifferences.length"
              v-model:value="allDifferences"
              multiple
              lazy
            >
              <AccordionPanel value="all">
                <AccordionHeader>
                  <span class="text-base">
                    all differences
                    <span class="text-muted-color">
                      {{ compare.shapelessDifferences.length }}
                    </span>
                  </span>
                </AccordionHeader>
                <AccordionContent>
                  <ShapelessTable :differences="compare.shapelessDifferences" />
                </AccordionContent>
              </AccordionPanel>
            </Accordion>
          </div>
        </AccordionContent>
      </AccordionPanel>

      <AccordionPanel v-if="compare.artifacts.length" value="artifacts">
        <AccordionHeader><span class="text-lg">Links</span></AccordionHeader>
        <AccordionContent>
          <ArtifactLinks :artifacts="compare.artifacts" />
        </AccordionContent>
      </AccordionPanel>
    </Accordion>

    <div v-if="area.focused.value" class="flex flex-col gap-3">
      <!--
        No winner is computed here. Nothing the runtime records says which way a
        metric reads, so the reader names the branch that won and the bar carries
        the adopt out under their choice.
      -->
      <label class="flex items-center gap-2 text-sm">
        <span class="text-muted-color">adopt from</span>
        <Select v-model="from" size="small" :options="sources" aria-label="lane to adopt from" />
      </label>

      <Message v-if="conflict" severity="warn" size="small">
        <template #icon><TriangleAlert :size="14" class="shrink-0" /></template>
        <div class="flex w-full flex-wrap items-center gap-3">
          <span class="min-w-40 flex-1 text-base">{{ conflict }}. nothing changed.</span>
          <div class="flex shrink-0 items-center gap-2">
            <Button severity="warn" :label="`take ${from}'s version`" @click="onAdopt(true)" />
            <Button
              text
              severity="secondary"
              :label="`keep ${target}'s`"
              @click="conflict = null"
            />
          </div>
        </div>
      </Message>

      <AdoptBar
        :winner="from"
        :asset="area.focused.value"
        :target="target"
        @adopt="onAdopt(false)"
        @export="onExport"
      />
    </div>

    <HandoffDialog
      v-model:visible="handoffOpen"
      gesture="diff"
      :payload="handoffPayload"
      :pending="handoffPending"
      :refusal="handoffRefusal"
      @hand-off="onHandOff"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionPanel,
  Button,
  Message,
  Select,
} from 'primevue'
import { useToast } from 'primevue/usetoast'
import { Send, TriangleAlert } from 'lucide-vue-next'

import { FlowApiError } from '@/flow/api/client'
import AdoptBar from '../components/compare/AdoptBar.vue'
import HandoffDialog from '../components/handoff/HandoffDialog.vue'
import ArtifactLinks from '../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../components/compare/DivergencePointCard.vue'
import MaterializationRows from '../components/compare/MaterializationRows.vue'
import ResultColumns from '../components/compare/ResultColumns.vue'
import ShapelessTable from '../components/compare/ShapelessTable.vue'
import { useCompare } from '../live/useCompare'
import { useFlowOps } from '../live/useFlowOps'
import type { FlowSessionHandle } from '../live/useFlowSession'
import { useSelection } from '../live/useSelection'
import BranchTag from '../ui/BranchTag.vue'

/**
 * 2–5 branches side by side, off the daemon's comparison.
 *
 * The two divergence kinds are the daemon's verdict and render as what they
 * are: an edit is the branching point everything below it inherits, and
 * everything below it is one row per asset rather than a fan of identical-code
 * nodes. Above both, comparability is checked rather than assumed — where
 * pin-at-fork stopped holding, the warning says so before the numbers do.
 *
 * The two closing verbs are the point of the screen: adopt the version that
 * won onto another branch, and export the slice that produced it.
 */
const props = defineProps<{ session: FlowSessionHandle }>()

const route = useRoute()
const toast = useToast()
const session = props.session
const ops = useFlowOps(session)

const selection = useSelection(route, {
  session,
  defaultBranch: computed(() => session.brief.value?.branch ?? 'main'),
})

const compared = computed(() => selection.compared.value)
const area = useCompare(session, compared, selection.selectedSlug)
const compare = computed(() => area.compare.value)

// Landing on a comparison is itself the focus change: the daemon learns what
// its human is looking at from these reports and from nowhere else, and an open
// comparison is the one an agent's brief most needs to know about.
void selection.reportFocus()

const open = ref<string[]>(['results', 'divergence'])
const allDifferences = ref<string[]>([])
const conflict = ref<string | null>(null)
const handoffOpen = ref(false)
const handoffPayload = ref<string | null>(null)
const handoffPending = ref(false)
const handoffRefusal = ref<string | null>(null)

/** The branch the adopt lands on: the one this comparison was entered from. */
const target = computed(() => selection.viewedBranch.value)

const sources = computed(() => compared.value.filter((name) => name !== target.value))
const from = ref('')

watch(
  sources,
  (names) => {
    if (!names.includes(from.value)) from.value = names[0] ?? ''
  },
  { immediate: true },
)

/** Picking the asset moves the URL, so the comparison stays a link. */
const focus = computed<string | null>({
  get: () => area.focused.value,
  set: (slug) => {
    selection.selectedSlug.value = slug
  },
})

const back = computed(() => ({
  path: route.path.replace(/\/compare$/, ''),
  query: { ...route.query, branch: target.value },
}))

function refused(failure: unknown): void {
  toast.add({
    severity: 'warn',
    summary: 'lumlflow refused this',
    detail: failure instanceof Error ? failure.message : String(failure),
    life: 4000,
  })
}

/**
 * Per-asset cherry-pick. A conflict is not a failure to report and move past:
 * both sides edited the cell since they forked, nothing is written, and the
 * choice is the reader's to make.
 */
async function onAdopt(force: boolean): Promise<void> {
  const slug = area.focused.value
  if (!slug || !from.value) return
  try {
    const adopted = await ops.adopt(slug, from.value, { branch: target.value, force })
    conflict.value = null
    await area.refresh()
    toast.add({
      severity: 'secondary',
      summary: `Adopted ${slug} onto ${target.value}`,
      detail: adopted.rebound.length
        ? `${adopted.rebound.join(', ')} re-accepted under ${target.value}'s names`
        : `from ${from.value}. its consumers on ${target.value} turn stale.`,
      life: 4000,
    })
  } catch (failure) {
    if (failure instanceof FlowApiError && failure.kind === 'AdoptConflict') {
      conflict.value = failure.message
      return
    }
    refused(failure)
  }
}

/**
 * The comparison's own handoff. The daemon builds it off the same `diff` the
 * columns are drawn from, so what the agent is told diverged is what is on
 * screen — a payload assembled here would be a second opinion about it.
 */
async function onExplainDiff(): Promise<void> {
  handoffPayload.value = null
  handoffRefusal.value = null
  handoffPending.value = true
  handoffOpen.value = true
  try {
    const built = await ops.handoff('diff', {
      branch: target.value,
      branches: compared.value,
    })
    handoffPayload.value = built.text
  } catch (failure) {
    handoffRefusal.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    handoffPending.value = false
  }
}

function onHandOff(payload: string): void {
  void navigator.clipboard?.writeText?.(payload)
  handoffOpen.value = false
  toast.add({
    severity: 'secondary',
    summary: 'Copied for your agent',
    detail: 'paste it into the session you paired',
    life: 4000,
  })
}

/** A file export of the chosen branch's slice — not a platform upload. */
async function onExport(): Promise<void> {
  if (!from.value) return
  try {
    const exported = await session.request('export', {
      flow: session.brief.value?.path,
      branch: from.value,
    })
    saveFile(`${exported.flow}-${exported.branch}.py`, exported.source)
    toast.add({
      severity: 'secondary',
      summary: `Exported ${from.value}`,
      detail: `${exported.cells.length} cells as one file. a file export, not a platform upload.`,
      life: 4000,
    })
  } catch (failure) {
    refused(failure)
  }
}

function saveFile(name: string, source: string): void {
  if (typeof URL.createObjectURL !== 'function') return
  const url = URL.createObjectURL(new Blob([source], { type: 'text/x-python' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>
