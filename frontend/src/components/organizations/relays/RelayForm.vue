<template>
  <form :id="formId" class="form" @submit.prevent="emit('submit')">
    <div class="field">
      <label :for="`${formId}-label`" class="label required">Label</label>
      <InputText
        :id="`${formId}-label`"
        v-model="model.label"
        name="label"
        placeholder="Lab relay"
        required
        fluid
      />
    </div>
    <div class="field">
      <label :for="`${formId}-base-domain`" class="label required">Base domain</label>
      <InputText
        :id="`${formId}-base-domain`"
        v-model="model.base_domain"
        name="base_domain"
        placeholder="sessions.example.com"
        required
        fluid
      />
      <div class="hint">Hostname only. No scheme, port or trailing dot.</div>
    </div>
    <div class="field">
      <label :for="`${formId}-agent-url`" class="label required">Connection address</label>
      <InputText
        :id="`${formId}-agent-url`"
        v-model="model.agent_url"
        name="agent_url"
        placeholder="wss://relay.example.com/connect"
        required
        fluid
      />
      <div class="hint">A ws:// or wss:// address.</div>
    </div>
  </form>
</template>

<script setup lang="ts">
import type { RelayCreatePayload } from '@/lib/api/relays/interfaces'
import { InputText } from 'primevue'

type Props = {
  formId: string
}

defineProps<Props>()
const emit = defineEmits<{ submit: [] }>()
const model = defineModel<RelayCreatePayload>({ required: true })
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.label {
  font-size: 14px;
  line-height: 1.5;
}
.hint {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
