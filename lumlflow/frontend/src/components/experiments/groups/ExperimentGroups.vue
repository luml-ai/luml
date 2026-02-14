<template>
  <div class="flex flex-col gap-6 h-[calc(100vh-92px)] overflow-hidden">
    <div class="grid grid-cols-4 gap-6 flex-0">
      <Card v-for="(card, index) in TOP_CARDS" :key="index">
        <template #title>{{ card.title }}</template>
        <template #content>{{ card.description }}</template>
      </Card>
    </div>
    <div class="flex-1 flex flex-col gap-6 overflow-hidden">
      <h2 class="text-2xl font-medium">Experiments group</h2>
      <Card class="flex-1 overflow-hidden" :pt="tableCardPt">
        <template #content>
          <ExperimentsGroupsToolbar class="flex-0" />
          <ExperimentsGroupsTable class="flex-1 overflow-hidden" />
        </template>
      </Card>
    </div>
  </div>
  <ExperimentsGroupEdit />
</template>

<script setup lang="ts">
import { Card, type CardPassThroughOptions } from 'primevue'
import { TOP_CARDS } from './data'
import ExperimentsGroupsToolbar from '@/components/experiments/groups/ExperimentsGroupsToolbar.vue'
import ExperimentsGroupsTable from './ExperimentsGroupsTable.vue'
import ExperimentsGroupEdit from './ExperimentsGroupEdit.vue'

const tableCardPt: CardPassThroughOptions = {
  body: {
    class: 'h-full overflow-hidden',
  },
  content: {
    class: 'h-full overflow-hidden flex flex-col',
  },
}
</script>

<style scoped></style>
