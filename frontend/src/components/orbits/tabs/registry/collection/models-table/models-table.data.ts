import type { DataTablePassThroughOptions } from 'primevue'
import { MlModelStatusEnum } from '@/lib/api/orbit-ml-models/interfaces'

export const TABLE_PT: DataTablePassThroughOptions = {
  root: {
    style: 'font-size: 14px;',
  },
  emptyMessageCell: {
    style: 'padding: 25px 16px;',
  },
}

export const STATUS_TAGS_CONFIG = {
  [MlModelStatusEnum.deletion_failed]: {
    severity: 'danger',
    text: 'Deletion failed',
  },
  [MlModelStatusEnum.pending_deletion]: {
    severity: 'warn',
    text: 'Pending deletions',
  },
  [MlModelStatusEnum.pending_upload]: {
    severity: 'warn',
    text: 'Pending upload',
  },
  [MlModelStatusEnum.upload_failed]: {
    severity: 'danger',
    text: 'Upload failed',
  },
  [MlModelStatusEnum.uploaded]: {
    severity: 'success',
    text: 'Uploaded',
  },
}

export const columnBodyStyle = 'white-space: nowrap; overflow:hidden; text-overflow: ellipsis;'
