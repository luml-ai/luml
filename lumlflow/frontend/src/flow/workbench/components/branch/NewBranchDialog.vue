<template>
  <Dialog v-model:visible="visible" modal header="New lane" :style="{ width: '26rem' }">
    <div class="flex flex-col gap-3">
      <p class="text-sm text-muted-color">
        starts a lane from the newest version of
        <code class="font-mono">{{ from }}</code
        >. no file and no value is copied. nothing here reaches back into it.
      </p>
      <InputText
        ref="nameInput"
        v-model="name"
        aria-label="lane name"
        placeholder="exp/lr-sweep"
        :invalid="Boolean(refusal)"
        @keyup.enter="confirm"
      />
      <p v-if="refusal" class="text-sm text-(--p-message-error-color)">{{ refusal }}</p>
      <div class="flex justify-end gap-2">
        <Button text severity="secondary" label="cancel" @click="visible = false" />
        <Button label="create lane" :disabled="!name.trim() || busy" @click="confirm" />
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef, watch } from 'vue'
import { Button, Dialog, InputText } from 'primevue'

/**
 * Naming a fork. The parent is stated rather than chosen: a branch is forked
 * from the one being viewed, which is the branch every other surface on the
 * screen is already scoped to — a second picker here would let the two disagree.
 */
const props = defineProps<{
  /** The branch this forks off — the viewed one. */
  from: string
  /** The daemon's refusal, when it named one (a name already taken). */
  refusal?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{ create: [name: string] }>()

const visible = defineModel<boolean>('visible', { required: true })

const name = ref('')
const nameInput = useTemplateRef<{ $el: HTMLElement }>('nameInput')

watch(visible, async (open) => {
  if (!open) return
  name.value = ''
  await nextTick()
  nameInput.value?.$el.focus()
})

function confirm(): void {
  const wanted = name.value.trim()
  if (!wanted || props.busy) return
  emit('create', wanted)
}
</script>
