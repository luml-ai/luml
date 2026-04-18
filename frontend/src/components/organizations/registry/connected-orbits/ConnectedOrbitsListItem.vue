<template>
  <div class="orbit">
    <OrbitIcon :size="24" color="var(--p-primary-color)" class="orbit-icon" />
    <div class="orbit-name">{{ orbit.name }}</div>
    <div class="orbit-id">
      <span class="orbit-id-label">Id: </span>
      <span class="orbit-id-value">{{ cutStringOnMiddle(orbit.id, 8) }}</span>
    </div>
    <Button
      variant="text"
      severity="secondary"
      size="small"
      class="orbit-copy-btn"
      @click="onCopyClick"
    >
      <component :is="isCopied ? CopyCheck : Copy" :size="14" class="orbit-copy-icon" />
    </Button>
  </div>
</template>

<script setup lang="ts">
import type { Orbit } from '@/lib/api/api.interfaces'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { Orbit as OrbitIcon, Copy, CopyCheck } from 'lucide-vue-next'
import { Button } from 'primevue'
import { ref } from 'vue'

type Props = {
  orbit: Pick<Orbit, 'id' | 'name'>
}

const props = defineProps<Props>()

const isCopied = ref(false)

function onCopyClick() {
  navigator.clipboard.writeText(props.orbit.id)
  isCopied.value = true
  setTimeout(() => {
    isCopied.value = false
  }, 2000)
}
</script>

<style scoped>
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
