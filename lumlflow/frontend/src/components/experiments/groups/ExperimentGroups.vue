<template>
  <div class="flex flex-col gap-6 h-[calc(100vh-92px)] overflow-hidden">
    <div class="grid grid-cols-4 gap-6 flex-0">
      <CardWithDialog
        v-for="(card, index) in TOP_CARDS"
        :key="index"
        :title="card.title"
        :description="card.description"
        :icon="card.icon"
        :content="card.mdRaw"
      />
    </div>
    <div class="flex-1 flex flex-col gap-6 overflow-hidden">
      <h2 class="text-2xl font-medium">Experiment groups</h2>
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
import CardWithDialog from '@/components/card-with-dialog/CardWithDialog.vue'

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
