<template>
  <d-dialog
    :visible="modelValue"
    modal
    style="width: 100%; max-width: 604px; margin: 0 15px"
    dismissable-mask
    @update:visible="(value: boolean) => $emit('update:modelValue', value)"
  >
    <template #header>
      <h2 class="dialog-title">PROMPT OPTIMIZATION</h2>
    </template>
    <div class="dialog-sub-title">Select a prompt optimization strategy to continue.</div>
    <ul class="prompt-menu">
      <li class="prompt-menu-item">
        <h3 class="prompt-menu-item-title">Free-form Optimization</h3>
        <p class="prompt-menu-item-description">
          Zero-shot prompt optimization based on the pipeline structure and the task description.
        </p>
        <d-button asChild severity="secondary" v-slot="slotProps">
          <router-link
            :to="{ name: 'prompt-fusion' }"
            class="prompt-menu-item-button"
            :class="slotProps.class"
            @click="() => onLinkClick('free_form')"
            >Select option</router-link
          >
        </d-button>
      </li>
      <li class="prompt-menu-item">
        <h3 class="prompt-menu-item-title">Data-Driven Optimization</h3>
        <p class="prompt-menu-item-description">
          Multi-iteration prompt optimization incorporating both the pipeline structure and the
          labelled data.
        </p>
        <d-button asChild severity="secondary" v-slot="slotProps">
          <router-link
            :to="{ name: 'prompt-fusion', params: { mode: 'data-driven' } }"
            class="prompt-menu-item-button"
            :class="slotProps.class"
            @click="() => onLinkClick('data_driven')"
            >Select option</router-link
          >
        </d-button>
      </li>
    </ul>
  </d-dialog>
</template>

<script setup lang="ts">
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'

type Props = {
  modelValue: boolean
}
type Emits = {
  'update:modelValue': [boolean]
}

defineProps<Props>()
defineEmits<Emits>()

function onLinkClick(option: string) {
  AnalyticsService.track(AnalyticsTrackKeysEnum.select_prompt_optimization, { option })
}
</script>

<style scoped>
.dialog-title {
  font-size: 20px;
  font-weight: 600;
}
.dialog-sub-title {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.prompt-menu {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.prompt-menu-item {
  background-color: var(--p-content-background);
  border-radius: 4px;
  padding: 12px;
  display: flex;
  flex-direction: column;
}
.prompt-menu-item-title {
  margin-bottom: 8px;
  font-weight: 500;
  font-size: 16px;
}
.prompt-menu-item-description {
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--p-text-muted-color);
}
.prompt-menu-item-button {
  align-self: flex-end;
}
.button-disabled {
  opacity: 0.7;
  pointer-events: none;
}
</style>
