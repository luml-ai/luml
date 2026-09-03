<template>
  <div class="px-1">
    <Button variant="text" @click="openDialog">
      <Plus :size="16" />
      <span> New flow</span>
    </Button>
    <Dialog
      v-model:visible="visible"
      header="CREATE NEW FLOW"
      modal
      dismissable-mask
      :draggable="false"
      :pt="DIALOG_PT"
      @update:visible="onVisibleChange"
    >
      <Form
        id="create-flow-form"
        :resolver="resolver"
        :initial-values="initialValues"
        :validate-on-value-update="false"
        @submit="submit"
      >
        <FormField v-slot="$field" name="name">
          <label for="name" class="inline-block mb-2 required">Name</label>
          <InputText
            v-model="initialValues.name"
            id="name"
            fluid
            :placeholder="`Name your flow ${FLOW_FILE_EXTENSION}`"
          />
          <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
            {{ $field.error?.message }}
          </Message>
        </FormField>
      </Form>
      <template #footer>
        <Button
          type="submit"
          label="Create flow"
          :loading="loading"
          :disabled="!initialValues.name || loading"
          form="create-flow-form"
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
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { useWorkspaceStore } from '@/store/workspace'

interface Props {
  existingNames?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  existingNames: () => [],
})

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

const workspaceStore = useWorkspaceStore()

const initialValues = ref({
  name: '',
})

const resolver: ReturnType<typeof zodResolver> = zodResolver(
  z.object({
    name: z
      .string()
      .min(1)
      .max(255)
      .refine((name) => name.endsWith(FLOW_FILE_EXTENSION), {
        message: `Name must end with ${FLOW_FILE_EXTENSION}`,
      })
      .superRefine((name, ctx) => {
        if (props.existingNames.includes(name)) {
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
  console.log(event)
  if (!event.valid) return

  const values = event.values as typeof initialValues.value
  createFlow(values.name)
}

async function createFlow(name: string) {
  loading.value = true
  try {
    await new Promise((resolve) => setTimeout(resolve, 1000))
    workspaceStore.createFlow(name)
    resetForm()
    visible.value = false
    toast.add(successToast('Flow created successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped></style>
