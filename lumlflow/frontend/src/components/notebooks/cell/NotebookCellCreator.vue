<template>
  <div>
    <Button variant="text" @click="openDialog">
      <Plus :size="14" />
      New cell
    </Button>
    <Dialog
      v-model:visible="visible"
      header="CREATE NEW CELL"
      modal
      dismissable-mask
      :draggable="false"
      :pt="DIALOG_PT"
      @update:visible="onVisibleChange"
    >
      <Form
        id="create-cell-form"
        :resolver="resolver"
        :initial-values="initialValues"
        :validate-on-value-update="submitAttempted"
        @submit="submit"
      >
        <FormField v-slot="$field" name="name">
          <label for="name" class="inline-block mb-2 required">Name</label>
          <InputText
            v-model="initialValues.name"
            id="name"
            fluid
            placeholder="my_cell"
            class="mb-2"
          />
          <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
            {{ $field.error?.message }}
          </Message>
          <Message v-else severity="secondary" size="small" variant="simple">
            {{ CELL_NAME_HINT }}
          </Message>
        </FormField>
      </Form>
      <template #footer>
        <Button
          type="submit"
          label="Create cell"
          :loading="loading"
          :disabled="!initialValues.name || loading"
          form="create-cell-form"
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
import { CELL_NAME_HINT, getCellNameError } from './cell.const'

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
      .max(255)
      .superRefine((name, ctx) => {
        const error = getCellNameError(
          name.trim(),
          flowStore.cells.map((cell) => cell.slug),
        )
        if (error) ctx.addIssue({ code: 'custom', message: error })
      }),
  }) as never,
)

const visible = ref(false)

const loading = ref(false)

const submitAttempted = ref(false)

function openDialog() {
  if (!flowStore.ensureOnLaneHead()) return
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
  submitAttempted.value = false
}

function submit(event: FormSubmitEvent) {
  submitAttempted.value = true
  if (!event.valid) return

  const values = event.values as typeof initialValues.value
  createCell(values.name.trim())
}

async function createCell(name: string) {
  loading.value = true
  try {
    const slug = await flowStore.createCell(name)
    flowStore.selectCell(slug)
    resetForm()
    visible.value = false
    toast.add(successToast('Cell created successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped></style>
