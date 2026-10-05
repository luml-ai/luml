<template>
  <div @click.stop>
    <Button
      v-tooltip.top="'Mark as point'"
      variant="outlined"
      severity="secondary"
      class="point-button"
      aria-label="Mark as point"
      @click="toggle"
    >
      <template #icon>
        <Flag :size="14" />
      </template>
    </Button>
    <Popover ref="popoverRef" :pt="POPOVER_WITHOUT_ARROW_PT" class="w-80" @hide="resetForm">
      <Form
        :resolver="resolver"
        :initial-values="initialValues"
        :validate-on-value-update="false"
        class="form"
        @submit="submit"
      >
        <FormField v-slot="$field" name="name">
          <label for="point-name" class="inline-block mb-2 required">Name</label>
          <InputText
            v-model="initialValues.name"
            id="point-name"
            fluid
            placeholder="Name this point"
          />
          <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
            {{ $field.error?.message }}
          </Message>
        </FormField>
        <Button
          type="submit"
          label="Create Point"
          :loading="loading"
          :disabled="!initialValues.name.trim() || loading"
          fluid
          rounded
        />
      </Form>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { Button, InputText, Message, Popover } from 'primevue'
import { Flag } from 'lucide-vue-next'
import { ref } from 'vue'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import z from 'zod'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { POPOVER_WITHOUT_ARROW_PT } from '@/prime-vue/pass-through/popover.pt'

const props = defineProps<{ step: number }>()

const toast = useToast()

const flowStore = useFlowStore()

const popoverRef = ref<InstanceType<typeof Popover>>()

const initialValues = ref({
  name: '',
})

const resolver: ReturnType<typeof zodResolver> = zodResolver(
  z.object({
    name: z.string().trim().min(1).max(255),
  }) as never,
)

const loading = ref(false)

function toggle(event: Event) {
  popoverRef.value?.toggle(event)
}

function resetForm() {
  initialValues.value = {
    name: '',
  }
}

function submit(event: FormSubmitEvent) {
  if (!event.valid) return

  const values = event.values as typeof initialValues.value
  createPoint(values.name.trim())
}

async function createPoint(name: string) {
  loading.value = true
  try {
    await flowStore.createPoint(name, props.step)
    popoverRef.value?.hide()
    toast.add(successToast('Point created successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.form {
  @apply flex flex-col gap-4;
}
.point-button {
  @apply w-8 h-8 p-0 text-primary! border-(--p-highlight-color)! bg-(--p-content-background)!;
}
</style>
