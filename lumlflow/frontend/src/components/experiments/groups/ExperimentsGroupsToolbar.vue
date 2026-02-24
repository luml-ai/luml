<template>
  <div class="flex justify-between items-center gap-10 pb-2.5">
    <div class="flex items-center gap-8">
      <div class="tabular-nums">{{ groupsStore.selectedGroups.length }} Selected</div>
      <ExperimentsGroupButtons />
    </div>
    <div class="max-w-sm w-full">
      <IconField>
        <InputText
          v-model="search"
          placeholder="Serch experiment by name or tags"
          size="small"
          fluid
        />
        <InputIcon>
          <Search :size="12" />
        </InputIcon>
      </IconField>
    </div>
  </div>
</template>

<script setup lang="ts">
import { InputText, IconField, InputIcon } from 'primevue'
import { Search } from 'lucide-vue-next'
import { ref, watch } from 'vue'
import { useGroupsStore } from '@/store/groups'
import ExperimentsGroupButtons from './ExperimentsGroupButtons.vue'

const groupsStore = useGroupsStore()

const search = ref(groupsStore.queryParams.search || '')

function onSearch() {
  groupsStore.setQueryParams({ ...groupsStore.queryParams, search: search.value })
}

watch(search, onSearch)
</script>

<style scoped></style>
