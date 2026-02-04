<template>
  <ConfirmDialog group="delete" class="w-full max-w-md" @update:visible="resetState">
    <template #container="slotProps">
      <div class="flex flex-col gap-4 p-4">
        <header class="flex items-center justify-between uppercase">
          <h3 class="text-lg font-medium">{{ slotProps.message.header }}</h3>
          <Button variant="text" severity="secondary" @click="slotProps.closeCallback">
            <template #icon>
              <X :size="16" />
            </template>
          </Button>
        </header>
        <div class="text-sm text-gray-500 flex flex-col gap-2">
          <p>{{ slotProps.message.message }}</p>
          <p>Please type "delete" to confirm</p>
        </div>
        <InputText v-model="input" placeholder="delete" fluid size="small" />
        <footer class="flex items-center justify-end gap-2">
          <Button
            v-bind:attrs="slotProps.message.rejectProps"
            :label="slotProps.message.rejectProps?.label || 'cancel'"
            @click="onReject(slotProps.rejectCallback)"
          />
          <Button
            variant="outlined"
            severity="warn"
            v-bind:attrs="slotProps.message.acceptProps"
            :label="slotProps.message.acceptProps?.label || 'delete'"
            :disabled="confirmDisabled"
            @click="onAccept(slotProps.acceptCallback)"
          />
        </footer>
      </div>
    </template>
  </ConfirmDialog>
</template>

<script setup lang="ts">
import { ConfirmDialog, Button, InputText } from 'primevue'
import { X } from 'lucide-vue-next'
import { computed, ref } from 'vue'

const input = ref('')

const confirmDisabled = computed(() => {
  return input.value !== 'delete'
})

function resetState() {
  input.value = ''
}

function onReject(callback: () => void) {
  resetState()
  callback()
}

function onAccept(callback: () => void) {
  resetState()
  callback()
}
</script>

<style scoped></style>
