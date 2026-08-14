<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-6 pb-16">
    <header class="flex flex-col gap-2">
      <h3 class="text-2xl font-medium">Comparing {{ fixture.branches.length }} lanes</h3>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <BranchTag
          v-for="column in fixture.branches"
          :key="column.branch"
          :name="column.branch"
          :checked-out="column.branch === target"
        />
      </div>
    </header>

    <Accordion v-model:value="open" multiple lazy>
      <AccordionPanel value="results">
        <AccordionHeader><span class="text-lg">Results</span></AccordionHeader>
        <AccordionContent>
          <!-- Integrity warnings render inline at the top of the columns. -->
          <ResultColumns :compare="fixture" />
        </AccordionContent>
      </AccordionPanel>

      <AccordionPanel value="divergence">
        <AccordionHeader><span class="text-lg">Divergence</span></AccordionHeader>
        <AccordionContent>
          <div class="flex flex-col gap-4">
            <DivergencePointCard
              v-for="divergence in fixture.definitionDivergences"
              :key="divergence.slug"
              :divergence="divergence"
            />
            <MaterializationRows :rows="fixture.materializationRows" />
            <Accordion v-model:value="allDifferences" multiple lazy>
              <AccordionPanel value="all">
                <AccordionHeader>
                  <span class="text-base">
                    all differences
                    <span class="text-muted-color">
                      {{ fixture.shapelessDifferences.length }}
                    </span>
                  </span>
                </AccordionHeader>
                <AccordionContent>
                  <ShapelessTable :differences="fixture.shapelessDifferences" />
                </AccordionContent>
              </AccordionPanel>
            </Accordion>
          </div>
        </AccordionContent>
      </AccordionPanel>

      <AccordionPanel value="artifacts">
        <AccordionHeader><span class="text-lg">Links</span></AccordionHeader>
        <AccordionContent>
          <ArtifactLinks :artifacts="fixture.artifacts" />
        </AccordionContent>
      </AccordionPanel>
    </Accordion>

    <AdoptBar
      :winner="winner"
      :asset="adoptAsset"
      :target="target"
      @adopt="onAdopt"
      @export="onExport"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import { useToast } from 'primevue/usetoast'
import AdoptBar from '../components/compare/AdoptBar.vue'
import ArtifactLinks from '../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../components/compare/DivergencePointCard.vue'
import MaterializationRows from '../components/compare/MaterializationRows.vue'
import ResultColumns from '../components/compare/ResultColumns.vue'
import ShapelessTable from '../components/compare/ShapelessTable.vue'
import { sweepCompare } from '../fixtures/compare'
import BranchTag from '../ui/BranchTag.vue'

/**
 * The comparison on the fixture: the design's own sweep, where the metrics
 * declare which way they read and a winner can therefore be named. A live one
 * has no such declaration and names none.
 */
const fixture = sweepCompare
const target = 'main'
const adoptAsset = 'train_model'

const toast = useToast()

// Results and divergence are why the page exists; the artifact links are a
// follow-up action and the shapeless table is a long tail.
const open = ref<string[]>(['results', 'divergence'])
const allDifferences = ref<string[]>([])

const winner = computed(() => {
  const [first, ...rest] = fixture.branches
  return rest.reduce((best, column) => {
    if (!column.headlineMetric || !best.headlineMetric) return best
    const better = column.headlineMetric.higherIsBetter
      ? column.headlineMetric.value > best.headlineMetric.value
      : column.headlineMetric.value < best.headlineMetric.value
    return better ? column : best
  }, first).branch
})

function onAdopt(): void {
  toast.add({
    severity: 'info',
    summary: 'Adopt',
    detail: `would adopt ${adoptAsset} from ${winner.value} onto ${target}. a three-way check on the definition runs first.`,
    life: 4000,
  })
}

function onExport(): void {
  toast.add({
    severity: 'info',
    summary: 'Export flow file',
    detail: 'would export the chosen slice as a flow file. a file export, not a platform upload.',
    life: 4000,
  })
}
</script>
