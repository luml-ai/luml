<template>
  <div class="attachments-wrapper">
    <FileTree :tree="tree" :selected="selectedFile" @select="handleSelect" />
    <FilePreview
      :file="selectedFile"
      :file-index="attachmentsIndex"
      :organization-id="organizationId"
      :orbit-id="orbitId"
      :collection-id="collectionId"
      :model-id="modelId"
    />
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useModelsStore } from '@/stores/models'
import FileTree from '../../../components/orbits/tabs/registry/collection/model/modell-attachments/FileTree.vue'
import FilePreview from '../../../components/orbits/tabs/registry/collection/model/modell-attachments/FilePreview.vue'
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

    const tarPath = Object.keys(props.model.file_index).find((path) =>
      path.includes('attachments.tar'),
    )

    if (!tarPath) {
      return
    }

    const [indexOffset, indexLength] = props.model.file_index[indexPath]
    const indexBlob = await fetchFileBlob(downloadUrl, indexOffset, indexLength)
    const indexText = await indexBlob.text()
    const index = JSON.parse(indexText) as Record<string, [number, number]>

    const [tarOffset, tarLength] = props.model.file_index[tarPath]
    const tarBlob = await fetchFileBlob(downloadUrl, tarOffset, tarLength)
    const tarUrl = URL.createObjectURL(tarBlob)

    const adjustedIndex: Record<string, [number, number]> = {}
    Object.entries(index).forEach(([path, [offset, length]]) => {
      adjustedIndex[path] = [offset, length]
    })

    attachmentsIndex.value = adjustedIndex
    ;(window as any).__tarBlobUrl = tarUrl

    tree.value = buildTreeFromIndex(index)
  } catch (e) {
    console.error('Failed to load attachments:', e)
  } finally {
    loading.value = false
  }
}

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
</style>
