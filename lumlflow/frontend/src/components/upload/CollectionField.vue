<template>
  <FormField :name="fieldName" class="flex flex-col gap-2">
    <label for="collection">
      Collection <span class="text-(--p-badge-warn-background)">*</span>
    </label>
    <Select
      :options="accepting"
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
          <template v-if="collections.length">
            None of this orbit's collections take {{ kindsLine }}. One typed {{ kindsLine }} or
            mixed would; create it in
          </template>
          <template v-else>
            There are no collections in this orbit yet. Create your first collection in
          </template>
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
import { computed, watch } from 'vue'
import { Select, type SelectChangeEvent } from 'primevue'
import { FormField } from '@primevue/forms'
import { collectionAccepts } from './collectionTypes'

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

/** Only the collections LUML would accept this upload into; the rest would answer 400. */
const accepting = computed(() =>
  collections.value.filter((collection) => collectionAccepts(collection.type, props.requiredKinds)),
)

const kindsLine = computed(() => props.requiredKinds.join(' + '))

function resetValue() {
  props.formRef?.setFieldValue(props.fieldName, null)
  emits('change-collection', undefined)
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

// Switching Auto / Model / Experiment can make the chosen collection wrong for
// what will now be sent; drop it rather than let the request find out.
watch(
  () => props.requiredKinds,
  (kinds) => {
    const chosen = props.formRef?.states[props.fieldName]?.value
    if (!chosen) return
    const collection = collections.value.find((c) => c.id === chosen)
    if (collection && !collectionAccepts(collection.type, kinds)) resetValue()
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
