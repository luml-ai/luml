<template>
  <div class="attachments-wrapper">
    <FileTree :tree="tree" :selected="selectedFile" @select="handleSelect" />
    <FilePreview
      :file="selectedFile"
      :file-index="model?.file_index || {}"
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
const organizationId = route.params.organizationId as string
const orbitId = route.params.id as string
const collectionId = route.params.collectionId as string
const modelId = route.params.modelId as string
const tree = ref<AttachmentNode[]>([])
const selectedFile = ref<AttachmentNode | null>(null)
function buildVariantArtifactsTree(fileIndex: Record<string, [number, number]>): AttachmentNode[] {
  const root: Record<string, any> = {}
  Object.keys(fileIndex)
    .filter((p) => p.startsWith('variant_artifacts/extra_files'))
    .forEach((path) => {
      const parts = path.split('/')
      let curr = root
      parts.forEach((part, idx) => {
        if (!curr[part]) {
          curr[part] =
            idx === parts.length - 1
              ? { type: 'file', path, size: fileIndex[path][1] }
              : { type: 'folder', children: {} }
        }
        curr = curr[part].children || {}
      })
    })
  function convert(obj: any): AttachmentNode[] {
    return Object.entries(obj).map(([name, data]: [string, any]) => {
      return data.type === 'file'
        ? { name, path: data.path, type: 'file', size: data.size }
        : { name, type: 'folder', children: convert(data.children) }
    })
  }
  return convert(root)
}
onMounted(() => {
  if (props.model?.file_index) {
    tree.value = buildVariantArtifactsTree(props.model.file_index)
  }
})
function handleSelect(node: AttachmentNode) {
  if (node.type === 'file') {
    selectedFile.value = node
  }
}
</script>
<style scoped>
.attachments-wrapper {
  display: flex;
  gap: 16px;
  height: calc(100vh - 320px);
}
</style>
