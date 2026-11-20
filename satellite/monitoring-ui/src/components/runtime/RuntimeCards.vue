<template>
  <div class="cards">
    <MCard
      v-for="card in cards"
      :key="card.key"
      :label="card.label"
      :content="formatCardValue(card)"
      :severity="getCardSeverity(card)"
    >
      <template v-if="formatCardDelta(card)" #footer>
        <span>{{ formatCardDelta(card) }}</span>
      </template>
    </MCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RuntimeResponse } from '@/api/monitoring/interfaces'
import MCard from '@/components/MCard.vue'
import { useFiltersStore } from '@/store/filters'
import { formatCardDelta, formatCardValue, getCardSeverity } from '@/utils/cards'
import { getRuntimeCards } from '@/utils/runtime'

interface Props {
  data: RuntimeResponse
}

const props = defineProps<Props>()

const filtersStore = useFiltersStore()

const cards = computed(() => getRuntimeCards(props.data, filtersStore.compare))
</script>

<style scoped>
.cards {
  --cards-column-gap: 16px;
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(max(260px, (100% - 3 * var(--cards-column-gap)) / 4), 1fr)
  );
  gap: 20px var(--cards-column-gap);
}
</style>
