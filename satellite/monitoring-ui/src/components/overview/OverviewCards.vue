<template>
  <div class="cards">
    <MCard
      v-for="card in cards"
      :key="card.key"
      :label="card.label"
      :content="formatCardValue(card)"
      :severity="getCardSeverity(card)"
    >
      <template v-if="card.key === 'active_alerts'" #footer>
        <span>{{ card.critical_count ?? 0 }} critical</span>
      </template>
      <template v-else-if="card.key === 'drifted_features'" #footer>
        <MTags v-if="card.feature_names?.length" :tags="card.feature_names" />
        <span v-else>none</span>
      </template>
      <template v-else-if="formatCardDelta(card)" #footer>
        <span>{{ formatCardDelta(card) }}</span>
      </template>
    </MCard>
  </div>
</template>

<script setup lang="ts">
import MCard from '@/components/MCard.vue'
import MTags from '@/components/MTags.vue'
import type { Card } from '@/api/monitoring/interfaces'
import { formatCardDelta, formatCardValue, getCardSeverity } from '@/utils/cards'

interface Props {
  cards: Card[]
}

withDefaults(defineProps<Props>(), {
  cards: () => [],
})
</script>

<style scoped>
.cards {
  --cards-gap: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: var(--cards-gap);
}

.cards > * {
  flex: 1 1 max(130px, (100% - 5 * var(--cards-gap)) / 6);
}
</style>
