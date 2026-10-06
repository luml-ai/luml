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
        <RouterLink class="link text-sm" :to="back">back to the workbench</RouterLink>
      </div>

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

      <AccordionPanel v-if="compare.trackerLinks.length" value="experiments">
        <AccordionHeader><span class="text-lg">Experiments</span></AccordionHeader>
        <AccordionContent>
          <ArtifactLinks :links="compare.trackerLinks" />
        </AccordionContent>
      </AccordionPanel>
    </Accordion>

    <div v-if="area.focused.value" class="flex flex-col gap-3">
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
import { TriangleAlert } from 'lucide-vue-next'

import { FlowApiError } from '@/flow/api/client'
import AdoptBar from '../components/compare/AdoptBar.vue'
import ArtifactLinks from '../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../components/compare/DivergencePointCard.vue'
import MaterializationRows from '../components/compare/MaterializationRows.vue'
import ResultColumns from '../components/compare/ResultColumns.vue'
import ShapelessTable from '../components/compare/ShapelessTable.vue'
import { useCompare } from '../live/useCompare'
import { MoveCancelled, useFlowOps } from '../live/useFlowOps'
import type { FlowSessionHandle } from '../live/useFlowSession'
import { useSelection } from '../live/useSelection'
import BranchTag from '../ui/BranchTag.vue'

const props = defineProps<{ session: FlowSessionHandle }>()

const route = useRoute()
const toast = useToast()
const session = props.session
const ops = useFlowOps(session)

const selection = useSelection(route, {
  defaultBranch: computed(() => session.brief.value?.branch ?? 'main'),
})

const compared = computed(() => selection.compared.value)
const area = useCompare(session, compared, selection.selectedSlug)
const compare = computed(() => area.compare.value)

const open = ref<string[]>(['results', 'divergence'])
const allDifferences = ref<string[]>([])
const conflict = ref<string | null>(null)

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
    if (failure instanceof MoveCancelled) return
    if (failure instanceof FlowApiError && failure.kind === 'AdoptConflict') {
      conflict.value = failure.message
      return
    }
    refused(failure)
  }
}

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
