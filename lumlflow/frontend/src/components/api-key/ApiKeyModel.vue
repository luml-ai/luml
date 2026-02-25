<template>
  <Dialog v-model:visible="visible" header="Api key" modal :draggable="false" :pt="DIALOG_PT">
    <div class="mb-6 text-muted-color">
      It looks like you haven't provided your API key yet. You can generate one in your
      <a :href="lmlUrl" target="_blank" class="text-primary underline">LUML account settings</a>
    </div>
    <div>
      <InputText v-model="currentValue" placeholder="Enter api key" fluid :invalid="!!error" />
      <Message v-if="error" severity="error" size="small" variant="simple" class="mt-2">
        {{ error }}
      </Message>
    </div>
    <template #footer>
      <Button label="Add" fluid @click="add" />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog, InputText, Button, Message } from 'primevue'
import { API_KEY_SCHEMA, DIALOG_PT } from './data'
import { ref, watch } from 'vue'
import z from 'zod'

const visible = defineModel<boolean>('visible')
const apiKey = defineModel<string | null>('apiKey', { required: true })

const currentValue = ref<string | null>(null)

const error = ref<string | null>(null)

const lmlUrl = import.meta.env.VITE_LUML_URL

function add() {
  try {
    API_KEY_SCHEMA.parse(currentValue.value)
    error.value = null
    apiKey.value = currentValue.value
    visible.value = false
  } catch (e) {
    if (e instanceof z.ZodError) {
      error.value = e.issues[0].message
    }
  }
}

watch(apiKey, (v) => {
  currentValue.value = v
})

watch(currentValue, () => {
  error.value = null
})

watch(visible, (v) => {
  if (!v) {
    currentValue.value = null
    error.value = null
  }
})
</script>

<style scoped></style>
