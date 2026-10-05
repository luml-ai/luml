<template>
  <Dialog
    :visible="visible"
    header="CREATE NEW LANE"
    modal
    dismissable-mask
    :draggable="false"
    :pt="DIALOG_PT"
    @update:visible="onVisibleChange"
  >
    <Message v-if="forkRequired" severity="info" size="small" class="mt-1 mb-4">
      <template v-if="isFromLaneOnScreen">
        You are on step {{ flowStore.currentHeadStep }} of this lane, not its latest step. Create a
        new lane from here to make changes.
      </template>
      <template v-else>
        Lane {{ fromLane?.branch }} is on step {{ fromLane?.head_step }}, not its latest step.
        Create a new lane from there to save your changes.
      </template>
    </Message>
    <Form
      :id="formId"
      :resolver="resolver"
      :initial-values="initialValues"
      :validate-on-value-update="false"
      @submit="submit"
    >
      <FormField v-slot="$field" name="name">
        <label :for="inputId" class="inline-block mb-2 required">Name</label>
        <InputText v-model="initialValues.name" :id="inputId" fluid placeholder="Name your lane" />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{ $field.error?.message }}
        </Message>
      </FormField>
    </Form>
    <template #footer>
      <Button
        type="submit"
        label="Create lane"
        :loading="loading"
        :disabled="!initialValues.name || loading"
        :form="formId"
        fluid
        rounded
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Button, Dialog, InputText, Message } from 'primevue'
import { computed, ref, useId } from 'vue'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import z from 'zod'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { isValidGitBranchName, LANE_NAME_INVALID_MESSAGE } from './lanes.const'

const props = defineProps<{
  visible: boolean
  /** Opened because a change was attempted behind the lane's latest step. */
  forkRequired?: boolean
  /** The lane to fork. The lane on screen when not given. */
  from?: string
}>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  created: [lane: string]
}>()

const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    class: 'w-[600px] rounded-lg!',
  },
  header: {
    class: 'text-xl uppercase',
  },
  content: {
    class: 'pb-7',
  },
}

const toast = useToast()

const flowStore = useFlowStore()

const formId = useId()
const inputId = useId()

const initialValues = ref({
  name: '',
})

const resolver: ReturnType<typeof zodResolver> = zodResolver(
  z.object({
    name: z
      .string()
      .min(1)
      .max(255)
      .refine((name) => isValidGitBranchName(name), {
        message: LANE_NAME_INVALID_MESSAGE,
      })
      .superRefine((name, ctx) => {
        if (flowStore.branches.some((branch) => branch.branch === name)) {
          ctx.addIssue({
            code: 'custom',
            message: `"${name}" already exists`,
          })
        }
      }),
  }) as never,
)

const loading = ref(false)

const isFromLaneOnScreen = computed(
  () => props.from === undefined || props.from === flowStore.currentBranch?.branch,
)
const fromLane = computed(() => flowStore.branches.find((branch) => branch.branch === props.from))

function onVisibleChange(visible: boolean) {
  emit('update:visible', visible)
  if (visible) return
  resetForm()
}

function resetForm() {
  initialValues.value = {
    name: '',
  }
}

function submit(event: FormSubmitEvent) {
  if (!event.valid) return

  const values = event.values as typeof initialValues.value
  createLane(values.name)
}

async function createLane(name: string) {
  loading.value = true
  try {
    // A fork forced by the lane on screen standing behind its head moves the
    // screen with it; a fork of a lane off screen leaves the screen alone.
    const created = await flowStore.createLane(name, {
      from: props.from,
      switchTo: props.forkRequired && isFromLaneOnScreen.value,
    })
    resetForm()
    emit('update:visible', false)
    emit('created', created)
    toast.add(successToast('Lane created successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>
