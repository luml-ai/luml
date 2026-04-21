<template>
  <div class="header">
    <div class="header-left">
      <Pencil :size="16" color="var(--p-primary-color)" />
      <span>Annotations ({{ props.count }})</span>
    </div>
    <Button severity="secondary" variant="outlined" @click="$emit('close')">
      <template #icon>
        <EyeOff :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Pencil, EyeOff } from 'lucide-vue-next'
import { Button } from 'primevue'

interface Emits {
  (event: 'close'): void
}

interface Props {
  count: number
}

const props = defineProps<Props>()

defineEmits<Emits>()
</script>

<style scoped>
.header {
  padding: 2px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  flex: 0 0 auto;
  margin-bottom: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}
</style>
