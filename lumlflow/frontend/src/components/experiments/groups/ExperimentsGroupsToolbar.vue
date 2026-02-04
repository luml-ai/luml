<template>
  <div class="flex justify-between items-center gap-10 pb-2.5">
    <div class="flex items-center gap-8">
      <div>{{ groupsStore.selectedGroups.length }} Selected</div>
      <ExperimentsGroupButtons />
    </div>
    <div class="max-w-sm w-full">
      <InputGroup>
        <InputText v-model="search" placeholder="Serch experiment by name or tags" size="small" />
        <InputGroupAddon>
          <Button severity="secondary" class="h-full" size="small" fluid @click="onSearch">
            <template #icon>
              <Search :size="12" />
            </template>
          </Button>
        </InputGroupAddon>
      </InputGroup>
    </div>
  </div>
</template>

<script setup lang="ts">
import { InputGroup, InputGroupAddon, InputText, Button } from 'primevue'
import { Search } from 'lucide-vue-next'
import { ref } from 'vue'
import { useGroupsStore } from '@/store/groups'
import ExperimentsGroupButtons from './ExperimentsGroupButtons.vue'

const groupsStore = useGroupsStore()

const search = ref('')

function onSearch() {
  console.log(search.value)
}
</script>

<style scoped></style>
