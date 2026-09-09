<template>
  <div>
    <Button variant="text" class="px-2.5!" @click="openDialog">
      <Plus :size="14" />
      <span>New lane</span>
    </Button>
    <Dialog
      v-model:visible="visible"
      header="CREATE NEW LANE"
      modal
      dismissable-mask
      :draggable="false"
      :pt="DIALOG_PT"
      @update:visible="onVisibleChange"
    >
      <Form
        id="create-lane-form"
        :resolver="resolver"
        :initial-values="initialValues"
        :validate-on-value-update="false"
        @submit="submit"
      >
        <FormField v-slot="$field" name="name">
          <label for="name" class="inline-block mb-2 required">Name</label>
          <InputText v-model="initialValues.name" id="name" fluid placeholder="Name your lane" />
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
          form="create-lane-form"
          fluid
          rounded
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Button, Dialog, InputText, Message } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { ref } from 'vue'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import z from 'zod'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { isValidGitBranchName, LANE_NAME_INVALID_MESSAGE } from './lanes.const'

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

const visible = ref(false)

const loading = ref(false)

function openDialog() {
  visible.value = true
}

function onVisibleChange(visible: boolean) {
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
    await flowStore.createLane(name)
    resetForm()
    visible.value = false
    toast.add(successToast('Lane created successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped></style>
