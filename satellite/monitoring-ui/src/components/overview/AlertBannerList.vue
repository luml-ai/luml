<template>
  <div class="alert-banners card" :class="{ critical: hasCritical }" data-testid="alert-banners">
    <!-- Ten rows is where a list stops being a summary and starts being a wall. -->
    <div class="scroll" :class="{ scrollable }">
      <component
        :is="inspectable ? 'button' : 'div'"
        v-for="(banner, index) in banners"
        :key="`${banner.group}:${banner.metric}:${banner.feature ?? ''}`"
        class="banner"
        :class="{ divided: index > 0, clickable: inspectable }"
        :type="inspectable ? 'button' : undefined"
        :aria-label="inspectable ? `Inspect ${banner.metric}` : undefined"
        data-testid="alert-banner"
        @click="inspectable && (selected = banner)"
      >
        <TriangleAlert :size="17" class="icon" :class="`sev-${banner.severity}`" />
        <div class="body">
          <span class="title">{{ bannerTitle(banner) }}</span>
          <span v-if="banner.feature" class="subject mono">{{ banner.feature }}</span>
          <span class="message">{{ banner.message }}</span>
          <span
            v-if="banner.state === 'acknowledged'"
            class="ack"
            data-testid="banner-acknowledged"
          >
            seen
          </span>
        </div>
      </component>
    </div>

    <DetailDrawer
      :open="selected !== null"
      :feature="selected ? alertSubject(selected) : null"
      :kind="selected?.label ?? null"
      :caption="drawerCaption"
      eyebrow="Alert"
      testid="alert-drawer"
      @close="selected = null"
    >
      <template #status>
        <SeverityTag v-if="selected" :severity="selected.severity" />
      </template>
      <AlertDetailPanel
        v-if="selected"
        :alert="selected"
        @show-feature="showFeature"
        @acknowledge="$emit('acknowledge', $event)"
      />
    </DetailDrawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'
import { Severity, type AlertBanner } from '@/api/types'
import { severityLabel } from '@/lib/format'
import { alertSubject, groupLabel } from '@/lib/alerts'
import DetailDrawer from '@/components/DetailDrawer.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import AlertDetailPanel from '@/components/alerts/AlertDetailPanel.vue'

/** Past this many rows the panel scrolls instead of pushing the section off the page. */
const VISIBLE_ROWS = 10

const props = withDefaults(defineProps<{ banners: AlertBanner[]; inspectable?: boolean }>(), {
  inspectable: false,
})
const emit = defineEmits<{ 'show-feature': [AlertBanner]; acknowledge: [AlertBanner] }>()

const hasCritical = computed(() => props.banners.some((b) => b.severity === Severity.CRITICAL))
const scrollable = computed(() => props.banners.length > VISIBLE_ROWS)

const selected = ref<AlertBanner | null>(null)

const drawerCaption = computed(() =>
  selected.value ? `${groupLabel(selected.value.group)} · ${selected.value.state ?? 'open'}` : null,
)

function showFeature(alert: AlertBanner): void {
  emit('show-feature', alert)
  selected.value = null
}

// A panel describing one alert must not outlive it: a reload may have resolved it.
watch(
  () => props.banners,
  (banners) => {
    if (!selected.value) return
    const key = selected.value.metric
    selected.value = banners.find((banner) => banner.metric === key) ?? null
  },
)

// The feature name is rendered next to the title, not inside it: the title is prose and
// gets capitalized, while a feature is an identifier and must survive verbatim.
function bannerTitle(banner: AlertBanner): string {
  return `${groupLabel(banner.group)} ${severityLabel(banner.severity).toLowerCase()}`
}
</script>

<style scoped>
.alert-banners {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-3);
  padding: 16px 18px;
}
.alert-banners.critical {
  border-color: var(--luml-danger-tint-bg);
}
.scroll {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-3);
}
.scroll.scrollable {
  /* ten rows and the nine gaps between them; a row is one line of text */
  max-height: calc(10 * 18px + 9 * var(--luml-space-3));
  overflow-y: auto;
  padding-right: 6px;
}
.banner {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  width: 100%;
  text-align: left;
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  padding: 0;
}
.banner.clickable {
  cursor: pointer;
}
.banner.clickable:hover .title {
  text-decoration: underline;
}
.banner.divided {
  border-top: 1px solid var(--luml-surface-100);
  padding-top: var(--luml-space-3);
}
.icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.icon.sev-critical {
  color: var(--luml-danger);
}
.icon.sev-warning {
  color: var(--luml-warn);
}
.icon.sev-ok {
  color: var(--luml-success);
}
.title {
  font-weight: 600;
  color: var(--luml-fg-strong);
  font-size: 13.5px;
  text-transform: capitalize;
}
.subject {
  margin-left: 6px;
  font-size: 13px;
  color: var(--luml-fg-strong);
}
.message {
  font-size: 13px;
  color: var(--luml-fg-muted);
  margin-left: 8px;
}
</style>
