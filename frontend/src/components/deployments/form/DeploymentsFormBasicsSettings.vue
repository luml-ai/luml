<template>
  <div class="column">
    <h4 v-if="showTitle" class="column-title">Basics</h4>
    <div class="fields">
      <div class="field">
        <label for="name" class="label required">Name</label>
        <InputText v-model="name" id="name" name="name" placeholder="Name your deployment" fluid />
      </div>
      <div class="field">
        <label for="tags" class="label">Tags</label>
        <AutoComplete
          v-model="tags"
          id="tags"
          name="tags"
          placeholder="Type to add tags for deployment"
          fluid
          multiple
          :suggestions="autocompleteItems"
          @complete="searchTags"
        ></AutoComplete>
      </div>
      <div class="field">
        <label for="description" class="label">Description</label>
        <Textarea
          v-model="description"
          id="description"
          name="description"
          placeholder="Describe your deployment"
          fluid
          class="textarea"
        ></Textarea>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent } from 'primevue'
import { useDeploymentsStore } from '@/stores/deployments'
import { computed, ref } from 'vue'
import { InputText, AutoComplete, Textarea } from 'primevue'

type Props = {
  showTitle?: boolean
}

withDefaults(defineProps<Props>(), {
  showTitle: true,
})

const name = defineModel<string | null>('name')
const tags = defineModel<string[]>('tags')
const description = defineModel<string | null>('description')

const deploymentsStore = useDeploymentsStore()

const existingTags = computed(() => {
  const tagsSet = deploymentsStore.deployments.reduce((acc: Set<string>, item) => {
    item.tags?.map((tag) => {
      acc.add(tag)
    })
    return acc
  }, new Set<string>())
  return Array.from(tagsSet)
})
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = [
    event.query,
    ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
  ]
}
</script>

<style scoped>
.column {
  padding: 20px;
  overflow-y: auto;
  height: 100%;
  border-right: 1px solid var(--p-divider-border-color);
}

.column-title {
  font-weight: 500;
  margin-bottom: 20px;
}

.fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.textarea {
  resize: none;
  height: 72px;
}

@media (max-width: 992px) {
  .column {
    border-right: none;
    border-bottom: 1px solid var(--p-divider-border-color);
  }
}
</style>
