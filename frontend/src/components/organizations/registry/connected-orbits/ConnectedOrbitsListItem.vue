<template>
  <div class="orbit">
    <OrbitIcon :size="24" color="var(--p-primary-color)" class="orbit-icon" />
    <div class="orbit-name">{{ orbit.name }}</div>
    <div class="orbit-id">
      <span class="orbit-id-label">Id: </span>
      <span class="orbit-id-value">{{ cutStringOnMiddle(orbit.id, 8) }}</span>
    </div>
    <UiCopyButton :text="orbit.id"></UiCopyButton>
  </div>
</template>

<script setup lang="ts">
import type { Orbit } from '@/lib/api/api.interfaces'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { Orbit as OrbitIcon } from 'lucide-vue-next'
import UiCopyButton from '@/components/ui/UiCopyButton.vue'

type Props = {
  orbit: Pick<Orbit, 'id' | 'name'>
}

const props = defineProps<Props>()
</script>

<style scoped>
.orbit {
  display: grid;
  grid-template-columns: 30px 1fr 90px 20px;
  align-items: center;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  white-space: nowrap;
  overflow: hidden;
}
.orbit-icon {
  flex: 0 0 auto;
  padding-right: 6px;
}
.orbit-name {
  font-weight: 500;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 12px;
}
.orbit-id {
  flex: 0 0 auto;
  padding-right: 4px;
  font-size: 12px;
}
.orbit-id-label {
  color: var(--p-text-muted-color);
}
.orbit-copy-btn {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border-radius: 4px;
}
.orbit-copy-icon {
  flex: 0 0 14px;
}
</style>
