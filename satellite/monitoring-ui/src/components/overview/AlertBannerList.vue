<template>
  <div class="alert-banners card" :class="{ critical: hasCritical }" data-testid="alert-banners">
    <div
      v-for="(banner, index) in banners"
      :key="`${banner.group}:${banner.metric}:${banner.feature ?? ''}`"
      class="banner"
      :class="{ divided: index > 0 }"
      data-testid="alert-banner"
    >
      <TriangleAlert :size="17" class="icon" :class="`sev-${banner.severity}`" />
      <div class="body">
        <span class="title">{{ bannerTitle(banner) }}</span>
        <span class="message">{{ banner.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'
import { Severity, type AlertBanner } from '@/api/types'
import { severityLabel } from '@/lib/format'

const props = defineProps<{ banners: AlertBanner[] }>()

const hasCritical = computed(() => props.banners.some((b) => b.severity === Severity.CRITICAL))

function bannerTitle(banner: AlertBanner): string {
  const scope = banner.feature ? ` — ${banner.feature}` : ''
  const group = banner.group.replace(/_/g, ' ')
  return `${group} ${severityLabel(banner.severity).toLowerCase()}${scope}`
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
.banner {
  display: flex;
  align-items: flex-start;
  gap: 11px;
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
.message {
  font-size: 13px;
  color: var(--luml-fg-muted);
  margin-left: 8px;
}
</style>
