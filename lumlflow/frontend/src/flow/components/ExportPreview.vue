<template>
  <div>
    <div class="flex items-center justify-between gap-4 mb-3">
      <div>
        <h3 class="font-medium">Freeze {{ session.branches[branchId]?.name }} as an artifact</h3>
        <p class="text-sm text-muted-color">
          {{ frozen.length }} assets · {{ leftBehind.length }} left behind
        </p>
      </div>
      <CostChip :cost="cost" />
    </div>

    <div
      v-if="leftBehind.length"
      class="mb-4 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 text-sm"
    >
      <p class="font-medium mb-1">Not included in the artifact</p>
      <ul class="text-muted-color">
        <li v-for="item in leftBehind" :key="item.assetId">{{ item.name }} · {{ item.reason }}</li>
      </ul>
    </div>

    <!--
      The linear document. A frozen slice shipped to a registry needs a rendering
      for its consumers, and a graph screenshot is not it: prose and outputs in
      dependency order, code collapsed, is how a finding is actually read.
    -->
    <article class="space-y-6">
      <section v-for="entry in document" :key="entry.assetId">
        <header class="flex items-baseline gap-2">
          <h4 class="font-medium">{{ entry.name }}</h4>
          <span class="font-mono text-xs text-muted-color">{{ entry.versionTag }}</span>
          <span class="text-xs text-muted-color">{{ entry.kind }}</span>
        </header>
        <p class="text-sm text-muted-color mb-2">{{ entry.doc }}</p>
        <ArtifactView v-if="entry.value" :value="entry.value" />
        <details class="mt-2">
          <summary class="text-xs text-muted-color cursor-pointer">source</summary>
          <pre class="text-xs mt-1 p-2 rounded-lg bg-surface-100 dark:bg-surface-800 overflow-x-auto">{{ entry.source }}</pre>
        </details>
      </section>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ArtifactView from './ArtifactView.vue'
import CostChip from './CostChip.vue'
import { preflightCost, resolveSlice, topoOrder } from '../engine'
import type { ArtifactValue, BranchId, FlowSession } from '../types'

const props = defineProps<{ session: FlowSession; branchId: BranchId }>()

const slice = computed(() => resolveSlice(props.session, props.branchId))
const order = computed(() => topoOrder(props.session, props.branchId))
const cost = computed(() => preflightCost(props.session, props.branchId))

const frozen = computed(() =>
  order.value.filter((assetId) => {
    const version = slice.value[assetId]
    const materialization = props.session.materializations[version.versionId]
    return materialization?.state === 'materialized'
  }),
)

const leftBehind = computed(() =>
  order.value
    .map((assetId) => {
      const version = slice.value[assetId]
      const materialization = props.session.materializations[version.versionId]
      if (materialization?.state === 'materialized') return null
      return {
        assetId,
        name: version.definition.name,
        reason:
          materialization?.state === 'failed'
            ? 'last materialization failed'
            : 'never materialized in this slice',
      }
    })
    .filter((item): item is { assetId: string; name: string; reason: string } => item !== null),
)

const document = computed(() =>
  order.value.map((assetId) => {
    const version = slice.value[assetId]
    const materialization = props.session.materializations[version.versionId]
    const values = Object.values(materialization?.values ?? {})
    return {
      assetId,
      name: version.definition.name,
      versionTag: version.versionId.split('@')[1] ?? version.versionId,
      kind: version.definition.kind,
      doc: version.definition.doc,
      source: version.definition.source,
      value: (values[0] as ArtifactValue | undefined) ?? null,
    }
  }),
)
</script>
