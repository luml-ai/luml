<template>
  <header class="header">
    <div class="info">
      <h3 class="title">Organization Orbits</h3>
      <p v-if="!createAvailable" class="text">
        To create a new Orbit, please contact your organization’s owner or admin.
      </p>
    </div>
    <Button v-if="createAvailable" @click="$emit('createNew')">
      <Plus :size="14" />
      <span>New orbit</span>
    </Button>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'

type Props = {
  createAvailable: boolean
}

type Emits = {
  createNew: []
}

defineEmits<Emits>()
defineProps<Props>()
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  gap: 40px;
  align-items: center;
}
.info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.title {
  font-size: 24px;
  font-weight: 500;
  line-height: 1.25;
}
.text {
  line-height: 1.5;
}
</style>
