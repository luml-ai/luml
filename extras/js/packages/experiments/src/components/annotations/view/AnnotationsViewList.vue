<template>
  <div class="list">
    <AnnotationItem
      v-for="item in items"
      :key="item.id"
      :item="item"
      :is-editable="true"
      @edit="onEdit(item)"
      @delete="onDelete(item)"
    />
  </div>

  <AnnotationEditDialog v-model:visible="editDialogVisible" :data="{}" />
</template>

<script setup lang="ts">
import { useConfirm } from 'primevue/useconfirm'
import { deleteAnnotationConfirmOptions } from '@/lib/primevue/data/confirm'
import { ref } from 'vue'
import AnnotationItem from '../AnnotationItem.vue'
import AnnotationEditDialog from '../AnnotationEditDialog.vue'

interface Props {
  items: any[]
}

defineProps<Props>()

const confirm = useConfirm()

const editDialogVisible = ref(false)

function onEdit(item: any) {
  console.log('edit', item)
  editDialogVisible.value = true
}

function onDelete(item: any) {
  confirm.require(deleteAnnotationConfirmOptions('AnnoName 3', () => deleteAnnotation(item)))
}

function deleteAnnotation(item: any) {
  console.log(item)
}
</script>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1 1 auto;
  overflow-y: auto;
}
</style>
