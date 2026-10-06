<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="`${branch} stands at step ${headStep}`"
    :style="{ width: '28rem' }"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-muted-color">
        behind its newest step {{ newestStep }}. a change from here moves
        <code class="font-mono">{{ branch }}</code> on from step {{ headStep }}; the later steps
        stay in its history. a new lane starts from this step and leaves
        <code class="font-mono">{{ branch }}</code> as it is.
      </p>
      <InputText
        ref="nameInput"
        v-model="name"
        aria-label="lane name"
        placeholder="exp/from-here"
        :invalid="Boolean(refusal)"
        @keyup.enter="confirm"
      />
      <p v-if="refusal" class="text-sm text-(--p-message-error-color)">{{ refusal }}</p>
      <div class="flex flex-wrap justify-end gap-2">
        <Button text severity="secondary" label="cancel" @click="visible = false" />
        <Button
          text
          severity="secondary"
          :label="`continue on ${branch}`"
          :disabled="busy"
          @click="emit('continue')"
        />
        <Button label="new lane from here" :disabled="!name.trim() || busy" @click="confirm" />
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef, watch } from 'vue'
import { Button, Dialog, InputText } from 'primevue'

const props = defineProps<{
  branch: string
  headStep: number
  newestStep: number
  refusal?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{
  'new-lane': [name: string]
  continue: []
}>()

const visible = defineModel<boolean>('visible', { required: true })

const name = ref('')
const nameInput = useTemplateRef<{ $el: HTMLElement }>('nameInput')

watch(
  visible,
  async (open) => {
    if (!open) return
    name.value = `${props.branch}-at-${props.headStep}`
    await nextTick()
    nameInput.value?.$el.focus()
  },
  { immediate: true },
)

function confirm(): void {
  const wanted = name.value.trim()
  if (!wanted || props.busy) return
  emit('new-lane', wanted)
}
</script>
