import type { GetAttachmentsResponseItem } from '@/api/slices/attachments/attachments.interface'
import type { FileNode, ModelAttachmentsProvider } from '@luml/attachments'
import { ref } from 'vue'
import { apiService } from '@/api/api.service'

export function useAttachmentsProvider(experimentId: string) {
  const provider = ref<ModelAttachmentsProvider | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function init() {
    try {
      loading.value = true
      error.value = null
      const attachments = await apiService.getAttachments(experimentId)
      const tree = await createTree(attachments)
      provider.value = {
        getTree: () => tree,
        getAttachmentContent: async (path: string) => {
          const blob = await apiService.getAttachmentContent(experimentId, {
            file_path: path,
          })
          return { blob, size: blob.size }
        },
        isEmpty: () => tree.length === 0,
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  async function createTree(attachments: GetAttachmentsResponseItem[]): Promise<FileNode[]> {
    const promises = attachments.map(async (attachment) => {
      if (attachment.type === 'folder') {
        const attachmentPath = typeof attachment.path === 'string' ? attachment.path.trim() : ''
        if (!attachmentPath) {
          return {
            ...attachment,
            size: attachment.size,
            children: [],
          }
        }
        const childrenList = await apiService.getAttachments(experimentId, {
          parent_path: attachmentPath,
        })
        const children = await createTree(childrenList)
        return {
          ...attachment,
          size: attachment.size,
          children,
        }
      }
      return { ...attachment, size: attachment.size }
    })
    return Promise.all(promises)
  }

  return {
    provider,
    loading,
    error,
    init,
  }
}
