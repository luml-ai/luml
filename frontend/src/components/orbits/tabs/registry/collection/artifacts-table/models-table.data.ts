import type { ColumnPassThroughOptions, DataTablePassThroughOptions } from 'primevue'
import { ArtifactStatusEnum, ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { CircuitBoard, FileChartColumn, FlaskConical } from 'lucide-vue-next'

export const TABLE_PT: DataTablePassThroughOptions = {
  root: {
    style: 'font-size: 14px;',
  },
  emptyMessageCell: {
    style: 'padding: 25px 16px;',
  },
}

export const STATUS_TAGS_CONFIG = {
  [ArtifactStatusEnum.deletion_failed]: {
    severity: 'danger',
    text: 'Deletion failed',
  },
  [ArtifactStatusEnum.pending_deletion]: {
    severity: 'warn',
    text: 'Pending deletions',
  },
  [ArtifactStatusEnum.pending_upload]: {
    severity: 'warn',
    text: 'Pending upload',
  },
  [ArtifactStatusEnum.upload_failed]: {
    severity: 'danger',
    text: 'Upload failed',
  },
  [ArtifactStatusEnum.uploaded]: {
    severity: 'success',
    text: 'Uploaded',
  },
}

export const TYPE_COLUMN_PT: ColumnPassThroughOptions = {
  columnHeaderContent: { style: 'width: 100px' },
  filterRuleList: { style: 'display: none' },
  filterButtonbar: { style: 'display: none' },
}

export const columnBodyStyle = 'white-space: nowrap; overflow:hidden; text-overflow: ellipsis;'

export const ARTIFACT_TYPE_TAGS_CONFIG = {
  [ArtifactTypeEnum.model]: {
    severity: 'secondary',
    text: 'Model',
    icon: CircuitBoard,
  },
  [ArtifactTypeEnum.experiment]: {
    severity: 'info',
    text: 'Experiment',
    icon: FlaskConical,
  },
  [ArtifactTypeEnum.dataset]: {
    severity: 'warn',
    text: 'Dataset',
    icon: FileChartColumn,
  },
}

export const ARTIFACT_TYPE_OPTIONS = [
  {
    label: 'Model',
    value: ArtifactTypeEnum.model,
    icon: CircuitBoard,
    color: 'var(--p-tag-primary-color)',
  },
  {
    label: 'Experiment',
    value: ArtifactTypeEnum.experiment,
    icon: FlaskConical,
    color: 'var(--p-tag-secondary-color)',
  },
  {
    label: 'Dataset',
    value: ArtifactTypeEnum.dataset,
    icon: FileChartColumn,
    color: 'var(--p-tag-info-color)',
  },
]
