<template>
  <article class="card">
    <div class="main">
      <div class="details">
        <Tag :value="product.tag" rounded class="tag" />
        <h3 class="name">{{ product.name }}</h3>
        <p class="description">{{ product.description }}</p>
        <d-button
          as="a"
          :href="product.learnMoreLink"
          target="_blank"
          rel="noopener noreferrer"
          label="Learn more"
          variant="link"
          class="learn-more"
        />
      </div>
      <img :src="product.image" alt="" width="120" height="120" class="image" />
    </div>
    <div class="divider"></div>
    <ul class="features">
      <li v-for="feature in product.features" :key="feature.label" class="feature">
        <component :is="feature.icon" :size="16" />
        <span>{{ feature.label }}</span>
      </li>
    </ul>
  </article>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { Tag } from 'primevue'

export type HomeProduct = {
  tag: string
  name: string
  description: string
  learnMoreLink: string
  image: string
  features: { label: string; icon: Component }[]
}

defineProps<{ product: HomeProduct }>()
</script>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
}

.main {
  display: flex;
  align-items: center;
  gap: 16px;
}

.details {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.tag {
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 400;
}

.name {
  font-size: 20px;
  font-weight: 500;
  line-height: 24px;
  color: var(--p-text-color);
}

.description {
  font-size: 14px;
  line-height: 20px;
  color: var(--p-text-muted-color);
}

.learn-more {
  padding-left: 0;
  padding-right: 0;
  text-decoration: none;
}

.image {
  flex: 0 0 auto;
}

.divider {
  height: 1px;
  background-color: var(--p-divider-border-color);
}

.features {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  list-style: none;
}

.feature {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  color: var(--p-text-color);
}

@media (max-width: 768px) {
  .image {
    width: 80px;
    height: 80px;
  }

  .features {
    flex-direction: column;
  }
}
</style>
