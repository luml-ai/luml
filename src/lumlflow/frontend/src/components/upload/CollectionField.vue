<template>
  <FormField :name="fieldName" class="flex flex-col gap-2">
    <label for="collection">
      Collection <span class="text-(--p-badge-warn-background)">*</span>
    </label>
    <Select
      :options="collections"
      option-label="name"
      option-value="id"
      :disabled="!orbitId"
      :placeholder="orbitId ? 'Select collection' : 'Select orbit first'"
      fluid
      :virtualScrollerOptions="
        collections.length < 10 ? undefined : { itemSize: 35, lazy: true, onLazyLoad: onLazyLoad }
      "
      @change="handleChange"
    >
      <template #empty>
        <div class="max-w-[423px] w-full">
          There are no collections in this orbit yet. Create your first collection in
          <a target="_blank" :href="lmlUrl" class="text-primary font-medium hover:underline">
            LUML.
          </a>
        </div>
      </template></Select
    >
  </FormField>
</template>

<script setup lang="ts">
import type { CollectionFieldProps, CollectionInfo, CollectionFieldEmits } from './upload.interface'
import type { GetLumlCollectionsParams } from '@/api/api.interface'
import { apiService } from '@/api/api.service'
import { usePagination } from '@/hooks/usePagination'
import { watch } from 'vue'
import { Select, type SelectChangeEvent } from 'primevue'
import { FormField } from '@primevue/forms'

const lmlUrl = import.meta.env.VITE_LUML_URL

const props = defineProps<CollectionFieldProps>()

const emits = defineEmits<CollectionFieldEmits>()

const {
  data: collections,
  getInitialPage,
  setParams,
  onLazyLoad,
  getParams,
  reset: resetList,
} = usePagination<CollectionInfo, GetLumlCollectionsParams>(apiService.getLumlCollections)

function resetValue() {
  props.formRef?.setFieldValue(props.fieldName, null)
}

function handleChange(event: SelectChangeEvent) {
  const collectionId = event.value
  const collection = collections.value.find((c) => c.id === collectionId)
  emits('change-collection', collection)
}

watch(
  () => props.organizationId,
  (value) => {
    if (value) {
      setParams({ ...getParams(), organization_id: value })
    }
  },
)

watch(
  () => props.orbitId,
  async (value) => {
    if (value) {
      setParams({ ...getParams(), orbit_id: value })
      await getInitialPage()
    } else {
      resetList()
      resetValue()
    }
  },
)
</script>

<style scoped></style>
