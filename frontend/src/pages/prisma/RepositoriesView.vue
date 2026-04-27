<script setup lang="ts">
import { computed, onMounted, inject, type Ref } from 'vue'
import { useConfirm } from 'primevue'
import { api } from '@/lib/api'
import { usePrismaStore } from '@/stores/prisma'
import { deleteRepositoryConfirmOptions } from '@/lib/primevue/data/confirm'
import RepositoryCard from '@/components/prisma/RepositoryCard.vue'

const store = usePrismaStore()
const confirm = useConfirm()
const repositories = computed(() => store.repositories)

const showNewRepository = inject<Ref<boolean>>('showNewRepository')!

async function refresh() {
  store.repositories = await api.dataAgent.listRepositories()
}

function openNewRepository() {
  showNewRepository.value = true
}

function onDeleteRepository(repositoryId: string, repositoryName: string) {
  confirm.require(
    deleteRepositoryConfirmOptions(async () => {
      await api.dataAgent.deleteRepository(repositoryId)
      await refresh()
    }, repositoryName),
  )
}

onMounted(() => {
  refresh()
})
</script>

<template>
  <div class="repositories-workspace">
    <div class="repositories-grid">
      <RepositoryCard
        v-for="repo in repositories"
        :key="repo.id"
        type="default"
        :data="repo"
        @delete="onDeleteRepository"
      />
      <RepositoryCard
        v-if="repositories.length === 0"
        type="create"
        @create-new="openNewRepository"
      />
    </div>
  </div>
</template>

<style scoped>
.repositories-workspace {
  flex: 1;
  overflow-y: auto;
  margin-top: 16px;
  padding: 0 4px;
}

.repositories-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
</style>
