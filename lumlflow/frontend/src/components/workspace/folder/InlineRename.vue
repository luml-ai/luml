<template>
  <form
    ref="form"
    class="min-w-0"
    @submit.prevent="emit('save', name)"
    @keydown.esc.prevent="cancel"
  >
    <div class="flex items-center gap-2">
      <InputText
        v-model="name"
        aria-label="New name"
        :disabled="busy"
        class="min-w-0 max-w-50 max-h-6.5 rounded-none! shadow-none! border-x-0! border-t-0! px-0!"
      />
      <Button
        label="Save"
        type="submit"
        size="small"
        severity="secondary"
        class="max-h-7"
        :loading="busy"
      />
    </div>
    <p v-if="item.type === 'file'" class="text-xs text-muted-color mt-1">
      {{ FILE_PATH_NOTE }}
    </p>
  </form>
</template>

<script setup lang="ts">
import { onMounted, ref, useTemplateRef } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Button, InputText } from 'primevue'
import type { IWorkspaceFolderItem } from './interface'
import { FILE_PATH_NOTE } from './operations'

const props = defineProps<{ item: IWorkspaceFolderItem; busy?: boolean }>()
const emit = defineEmits<{ save: [name: string]; cancel: [] }>()
const form = useTemplateRef('form')
const name = ref(props.item.entryName ?? props.item.name)

function cancel() {
  if (!props.busy) emit('cancel')
}
onClickOutside(form, cancel)
onMounted(() => {
  const input = form.value?.querySelector('input')
  input?.focus()
  input?.select()
})
</script>
