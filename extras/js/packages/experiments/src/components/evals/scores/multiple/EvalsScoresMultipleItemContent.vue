<template>
  <UiCard :title="title">
    <template #header-right>
      <Button severity="secondary" variant="text" @click="scaled = true">
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </template>
    <UiScalable v-model="scaled" :title="title">
      <slot></slot>
      <template #scaled>
        <slot name="scaled"></slot>
      </template>
    </UiScalable>
  </UiCard>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import { Button } from 'primevue'
import UiCard from '../../../ui/UiCard.vue'
import UiScalable from '../../../ui/UiScalable.vue'

type Props = {
  title: string
}

type Emits = {
  scale: []
}

defineProps<Props>()
const emits = defineEmits<Emits>()

const scaled = ref(false)

watch(scaled, (val) => {
  if (val) emits('scale')
})
</script>

<style scoped></style>
