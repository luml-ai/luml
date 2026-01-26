<template>
  <header class="header">
    <div class="label">
      Trace <span style="color: var(--p-text-muted-color)">({{ itemsCount }} items)</span>
    </div>
    <Button severity="secondary" variant="outlined" @click="open = !open">
      <template #icon>
        <component :is="open ? FoldVertical : UnfoldVertical" :size="14"></component>
      </template>
    </Button>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { FoldVertical, UnfoldVertical } from 'lucide-vue-next'

type Props = {
  itemsCount: number
}

defineProps<Props>()

const open = defineModel<boolean>('open')
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  margin-bottom: 20px;
}
.label {
  font-size: 14px;
  font-weight: 500;
}
</style>
