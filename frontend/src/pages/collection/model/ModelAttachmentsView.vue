<template>
  <div class="attachments-wrapper">
    <UiPageLoader v-if="loading"></UiPageLoader>
    <template v-else-if="isEmpty">
      <div class="empty-state">
        <p>This attachment is empty.</p>
      </div>
    </template>
    <template v-else>
      <FileTree :tree="tree" :selected="selectedFile" @select="handleSelect" />
      <FilePreview
        :file="selectedFile"
        :file-index="attachmentsIndex"
        :organization-id="organizationId"
        :orbit-id="orbitId"
        :collection-id="collectionId"
        :model-id="modelId"
      />
    </template>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useModelsStore } from '@/stores/models'
import FileTree from '../../../components/orbits/tabs/registry/collection/model/modell-attachments/FileTree.vue'
import FilePreview from '../../../components/orbits/tabs/registry/collection/model/modell-attachments/FilePreview.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
interface AttachmentNode {
  name: string
  path?: string
  type: 'file' | 'folder'
  size?: number
  children?: AttachmentNode[]
}
const props = defineProps<{ model: any }>()
const route = useRoute()
const modelsStore = useModelsStore()
const organizationId = route.params.organizationId as string
const orbitId = route.params.id as string
const collectionId = route.params.collectionId as string
const modelId = route.params.modelId as string
const tree = ref<AttachmentNode[]>([])
const selectedFile = ref<AttachmentNode | null>(null)
const attachmentsIndex = ref<Record<string, [number, number]>>({})
const loading = ref(true)
const error = ref<string | null>(null)
const isEmpty = computed(() => {
  return !loading.value && tree.value.length === 0
})

async function fetchFileBlob(url: string, offset: number, length: number): Promise<Blob> {
  const end = offset + length - 1
  const response = await fetch(url, {
    headers: { Range: `bytes=${offset}-${end}` },
  })
  if (!response.ok) {
    throw new Error(`HTTP Error: ${response.status}`)
  }
  return response.blob()
}

async function loadAttachmentsData() {
  try {
    loading.value = true
    error.value = null
    const downloadUrl = await modelsStore.getDownloadUrl(modelId)
    const indexPath = Object.keys(props.model.file_index).find((path) =>
      path.includes('attachments.index.json'),
    )

    if (!indexPath) {
      return
    }

    const indexRange = props.model.file_index[indexPath]
    if (!indexRange) {
      return
    }
    const [indexOffset, indexLength] = indexRange
    const indexBlob = await fetchFileBlob(downloadUrl, indexOffset, indexLength)
    const indexText = await indexBlob.text()
    const index = JSON.parse(indexText) as Record<string, [number, number]>

    const tarPath = Object.keys(props.model.file_index).find((path) =>
      path.includes('attachments.tar'),
    )

    if (!tarPath) {
      return
    }

    const tarRange = props.model.file_index[tarPath]
    if (!tarRange) {
      return
    }
    const [tarOffset] = tarRange
    attachmentsIndex.value = index
    ;(window as any).__tarOffset = tarOffset
    ;(window as any).__modelDownloadUrl = downloadUrl
    tree.value = buildTreeFromIndex(index)
  } catch (e) {
    console.error('Failed to load attachments:', e)
  } finally {
    loading.value = false
  }
}

function buildTreeFromIndex(index: Record<string, [number, number]>): AttachmentNode[] {
  const root: Record<string, any> = {}
  const filePaths = Object.entries(index)
    .filter(([path, [, size]]) => size > 0)
    .map(([path]) => path)

  filePaths.forEach((fullPath) => {
    const path = fullPath.replace(/^attachments\//, '')
    const parts = path.split('/')
    const [, size] = index[fullPath]

    let current = root

    parts.forEach((part, idx) => {
      if (idx === parts.length - 1) {
        current[part] = {
          type: 'file',
          path: fullPath,
          size,
        }
      } else {
        if (!current[part]) {
          current[part] = {
            type: 'folder',
            children: {},
          }
        }
        current = current[part].children
      }
    })
  })

  function convertToArray(obj: any): AttachmentNode[] {
    return Object.entries(obj).map(([name, data]: [string, any]) => {
      if (data.type === 'file') {
        return {
          name,
          path: data.path,
          type: 'file',
          size: data.size,
        }
      } else {
        return {
          name,
          type: 'folder',
          children: convertToArray(data.children),
        }
      }
    })
  }

  return convertToArray(root)
}

function handleSelect(node: AttachmentNode) {
  if (node.type === 'file') {
    selectedFile.value = node
  }
}

onMounted(() => {
  if (props.model?.file_index) {
    loadAttachmentsData()
  }
})
</script>
<style scoped>
.attachments-wrapper {
  display: flex;
  gap: 16px;
  height: calc(100vh - 320px);
}
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-form-field-float-label-color);
}
</style>
