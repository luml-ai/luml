<template>
  <div class="flex flex-col">
    <div
      v-for="artifact in artifacts"
      :key="artifact.slug + artifact.output"
      class="flex flex-col gap-1.5 border-t border-surface-200 py-3 first:border-t-0 first:pt-0 last:pb-0 dark:border-surface-700"
    >
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <KindBadge :kind="artifact.kind" icon-only />
        <a v-if="artifact.href" class="link text-base" :href="artifact.href">{{
          artifact.label
        }}</a>
        <span v-else class="text-base">{{ artifact.label }}</span>
        <span class="font-mono text-sm text-muted-color">
          {{ artifact.slug }}.{{ artifact.output }}
        </span>
        <span class="ml-auto text-sm text-muted-color">{{ destination(artifact) }}</span>
      </div>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="(reference, branch) in artifact.byBranch"
          :key="branch"
          v-tooltip.top="branch"
          class="inline-flex items-center gap-1.5 rounded-lg border border-surface-200 px-1.5 py-0.5 font-mono text-sm dark:border-surface-700"
        >
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :style="{ background: branchColor(String(branch)) }"
          />
          {{ reference }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CompareArtifactLink } from '../../model/types'
import KindBadge from '../../ui/KindBadge.vue'
import { branchColor } from '../../ui/kinds'

defineProps<{ artifacts: CompareArtifactLink[] }>()

/** The fallback chain: experiment → tracker, model → model card, dataset → view, else → metric. */
function destination(artifact: CompareArtifactLink): string {
  // Nothing to open is a state of its own: naming a screen that does not answer
  // reads as a broken link rather than as an artifact still on its way.
  if (!artifact.href) return 'no screen'
  switch (artifact.kind) {
    case 'experiment':
      return 'tracker'
    case 'model':
      return 'model card'
    case 'dataset':
      return 'dataset view'
    default:
      return 'no screen'
  }
}
</script>
