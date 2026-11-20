import type { GetAttachmentsResponseItem } from '@/api/slices/attachments/attachments.interface'
import {
  getFileExtension,
  getFileType,
  urlPreviewBytes,
  type FileNode,
  type ModelAttachmentsProvider,
} from '@luml/attachments'
import { api } from '@/api/client'
import { getSessionToken } from '@/api/session'
import { ref } from 'vue'
import { apiService } from '@/api/api.service'

function supportsPartialPreview(path: string) {
  const type = getFileType(path)
  return (
    type === 'audio' || type === 'video' || type === 'pdf' || getFileExtension(path) === 'parquet'
  )
}

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
        getAttachmentContent,
        supportsPartialPreview,
        async getPreviewSource(path) {
          if (!supportsPartialPreview(path)) {
            return (await getAttachmentContent(path)).blob
          }
          const base = `/experiments/${encodeURIComponent(experimentId)}/attachments`
          if (getFileExtension(path) === 'parquet') {
            const url = api.getUri({ url: `${base}/content`, params: { file_path: path } })
            const token = getSessionToken()
            return urlPreviewBytes(url, undefined, {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            })
          }
          const { data } = await api.post<{ expires: number; signature: string; size: number }>(
            `${base}/preview`,
            null,
            { params: { file_path: path } },
          )
          if (!data.size) return new Blob([])
          return api.getUri({
            url: '/experiments/preview/content',
            params: {
              experiment_id: experimentId,
              file_path: path,
              expires: data.expires,
              signature: data.signature,
            },
          })
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

  async function getAttachmentContent(path: string) {
    const blob = await apiService.getAttachmentContent(experimentId, { file_path: path })
    return { blob, size: blob.size }
  }

  async function createTree(attachments: GetAttachmentsResponseItem[]): Promise<FileNode[]> {
    const promises = attachments.map(async (attachment) => {
      if (attachment.type === 'folder') {
        const attachmentPath = typeof attachment.path === 'string' ? attachment.path.trim() : ''
        if (!attachmentPath) {
          return {
            ...attachment,
            size: attachment.size ?? undefined,
            children: [],
          }
        }
        const childrenList = await apiService.getAttachments(experimentId, {
          parent_path: attachmentPath,
        })
        const children = await createTree(childrenList)
        return {
          ...attachment,
          size: attachment.size ?? undefined,
          children,
        }
      }
      return { ...attachment, size: attachment.size ?? undefined }
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
