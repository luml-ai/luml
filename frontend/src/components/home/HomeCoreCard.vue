<template>
  <section class="core">
    <div class="overview">
      <div class="product">
        <img :src="coreImage" alt="" width="72" height="72" />
        <div class="product-details">
          <h3 class="name">Core</h3>
          <p class="text">Take models from experiments to production.</p>
        </div>
      </div>
      <div class="divider"></div>
      <div class="capabilities">
        <div v-for="capability in capabilities" :key="capability.title" class="capability">
          <div class="capability-title">
            <component :is="capability.icon" :size="16" />
            <span>{{ capability.title }}</span>
          </div>
          <p class="text">{{ capability.text }}</p>
        </div>
      </div>
    </div>
    <div class="steps">
      <template v-for="(step, index) in steps" :key="step.id">
        <ArrowRight v-if="index" :size="16" class="arrow" />
        <d-button
          v-if="step.active"
          variant="link"
          class="step active"
          @click="emit('run-step', step.id)"
        >
          <component :is="step.icon" :size="16" />
          <span>{{ step.label }}</span>
        </d-button>
        <div v-else class="step">
          <component :is="step.icon" :size="16" />
          <span>{{ step.label }}</span>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { Activity, ArrowRight, Folders, Rocket } from 'lucide-vue-next'
import type { QuickStartStep, QuickStartStepEnum } from '@/hooks/useQuickStart'
import coreImage from '@/assets/img/home/core.svg'

defineProps<{ steps: QuickStartStep[] }>()

const emit = defineEmits<{ 'run-step': [stepId: QuickStartStepEnum] }>()

const capabilities = [
  { title: 'Registry', icon: Folders, text: 'Version, organize, and share your model artifacts.' },
  { title: 'Deployments', icon: Rocket, text: 'Serve models on your own infrastructure.' },
  { title: 'Monitoring', icon: Activity, text: 'Track model health, data quality, and drift.' },
]
</script>

<style scoped>
.core {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
}

.overview {
  display: flex;
  gap: 16px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--p-content-border-color);
}

.product {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.product-details {
  width: 182px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.name {
  font-size: 20px;
  font-weight: 500;
  line-height: 24px;
  color: var(--p-text-color);
}

.text {
  font-size: 14px;
  line-height: 20px;
  color: var(--p-text-muted-color);
}

.divider {
  height: auto;
  width: 1px;
  flex: 0 0 auto;
  background-color: var(--p-divider-border-color);
}

.capabilities {
  flex: 1 1 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.capability {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.capability-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  line-height: 24px;
  color: var(--p-text-color);
}

.steps {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  line-height: 24px;
  color: var(--p-text-color);
}

.step.active {
  padding: 0;
  font-weight: 500;
  color: var(--p-primary-color);
}

.arrow {
  flex: 0 0 auto;
  color: var(--p-text-muted-color);
}

@media (max-width: 1024px) {
  .overview {
    flex-direction: column;
    align-items: stretch;
  }

  .divider {
    width: auto;
    height: 1px;
  }

  .arrow {
    display: none;
  }
}

@media (max-width: 768px) {
  .capabilities {
    grid-template-columns: 1fr;
  }

  .steps {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
