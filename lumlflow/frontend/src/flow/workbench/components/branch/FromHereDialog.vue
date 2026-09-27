<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="`${branch} stands at step ${headStep}`"
    :style="{ width: '28rem' }"
  >
    <div class="flex flex-col gap-3">
      <!--
        The choice names what each way costs, and nothing else: a change from
        here moves the lane on from this step, so the later steps stop being
        where it would go next. A new lane keeps them as they were.
      -->
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

/**
 * Asked once, at the first change on a lane that stands behind its newest
 * step. The lane was rewound and stayed there on purpose; what the reader is
 * about to do moves it on, and the one thing worth asking is whether they
 * want that on this lane or on a new one started from here.
 */
const props = defineProps<{
  branch: string
  headStep: number
  newestStep: number
  /** The daemon's refusal of the lane name, when it named one. */
  refusal?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{
  /** Start a lane from where the branch stands, and land the change there. */
  'new-lane': [name: string]
  /** Land the change on this lane, moving it on from where it stands. */
  continue: []
}>()

const visible = defineModel<boolean>('visible', { required: true })

const name = ref('')
const nameInput = useTemplateRef<{ $el: HTMLElement }>('nameInput')

// Immediate: the dialog is mounted open, at the gesture that asked for it.
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
