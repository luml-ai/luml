<template>
  <section class="onboarding">
    <div class="content">
      <div class="heading">
        <h2 class="title">Onboard your agent to LUML</h2>
        <p class="text">
          Paste this into your coding agent or chat assistant.<br />
          It'll get to know your work and show where LUML can help.
        </p>
      </div>
      <div class="prompt">
        <p class="prompt-text">{{ ONBOARDING_PROMPT }}</p>
        <UiCopyButton class="copy" :text="ONBOARDING_PROMPT" :icon-size="16" />
      </div>
    </div>
    <div class="actions">
      <d-button
        v-for="action in actions"
        :key="action.label"
        as="a"
        :href="action.href"
        target="_blank"
        rel="noopener noreferrer"
        severity="secondary"
        variant="outlined"
        class="action"
      >
        <span>{{ action.label }}</span>
        <ArrowUpRight :size="14" />
      </d-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
import UiCopyButton from '@/components/ui/UiCopyButton.vue'

const ONBOARDING_PROMPT =
  'Read https://raw.githubusercontent.com/luml-ai/luml/main/.agents-onboarding/index.md\nand help me understand how LUML could fit my work.'

const encodedPrompt = encodeURIComponent(ONBOARDING_PROMPT)

const actions = [
  { label: 'Open in Claude', href: `https://claude.ai/new?q=${encodedPrompt}` },
  { label: 'Open in ChatGPT', href: `https://chatgpt.com/?q=${encodedPrompt}` },
  { label: 'Open in Cursor', href: `https://cursor.com/link/prompt?text=${encodedPrompt}` },
]
</script>

<style scoped>
.onboarding {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
}

.content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--p-text-color);
}

.title {
  font-size: 20px;
  font-weight: 500;
  line-height: 24px;
}

.text {
  font-size: 16px;
  line-height: 24px;
}

.prompt {
  position: relative;
  padding: 8px 32px 8px 8px;
  border: 1px solid var(--p-listbox-border-color);
  border-radius: 8px;
  background-color: var(--p-listbox-option-focus-background);
}

.prompt-text {
  font-family: Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 16px;
  line-height: normal;
  color: var(--p-text-color);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.copy {
  position: absolute;
  top: 6px;
  right: 6px;
}

.actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.action {
  gap: 7px;
  padding-left: 12px;
  padding-right: 12px;
  text-decoration: none;
  white-space: nowrap;
}

.action svg {
  flex-shrink: 0;
}

@media (max-width: 1024px) {
  .actions {
    grid-template-columns: 1fr;
  }
}
</style>
