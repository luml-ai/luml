import { api } from '@/api/client'
import type {
  GetAttachmentContentParams,
  GetAttachmentsParams,
  GetAttachmentsResponseItem,
} from './attachments.interface'

export const attachmentsApi = {
  getAttachments: async (experimentId: string, params: GetAttachmentsParams = {}) => {
    const { data } = await api.get<GetAttachmentsResponseItem[]>(
      `/experiments/${experimentId}/attachments`,
      { params },
    )
    return data
  },

  getAttachmentContent: async (experimentId: string, params: GetAttachmentContentParams) => {
    const { data } = await api.get<Blob>(`/experiments/${experimentId}/attachments/content`, {
      params,
      responseType: 'blob',
    })
    return data
  },
}
