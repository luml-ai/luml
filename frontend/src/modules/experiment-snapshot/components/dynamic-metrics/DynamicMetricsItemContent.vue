<template>
  <UiCard :title="title">
    <template #header-left>
      <div class="header-left">
        <h3 class="card__title">{{ title }}</h3>
        <CircleAlert
          v-if="aggregated"
          :size="14"
          v-tooltip="'Contains aggregated data'"
          color="var(--p-badge-warn-background)"
        />
      </div>
    </template>
    <template #header-right>
      <Button v-if="!loading" severity="secondary" variant="text" @click="scaled = true">
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </template>
    <div v-if="loading" class="loading-wrapper">
      <ProgressSpinner style="width: 100px; height: 100px"></ProgressSpinner>
    </div>
    <UiScalable v-else v-model="scaled" :title="title">
      <slot></slot>
      <template #scaled>
        <slot name="scaled"></slot>
      </template>
    </UiScalable>
  </UiCard>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { CircleAlert, Maximize2 } from 'lucide-vue-next'
import { Button, ProgressSpinner } from 'primevue'
import UiCard from '../ui/UiCard.vue'
import UiScalable from '../ui/UiScalable.vue'

type Props = {
  title: string
  loading: boolean
  aggregated: boolean
}

type Emits = {
  scale: []
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const scaled = ref(false)

watch(scaled, (val) => {
  val && emits('scale')
})
</script>

<style scoped>
.loading-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  width: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 39px;
}

.card__title {
  font-size: 20px;
}
</style>
