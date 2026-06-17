import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { CircuitBoard, FileChartColumn, FlaskConical } from 'lucide-vue-next'
import type {
  DataTablePassThroughOptions,
  DialogPassThroughOptions,
  MultiSelectPassThroughOptions,
} from 'primevue'

export const TRACKS_TYPE_OPTIONS = [
  { label: 'Model', value: ArtifactTypeEnum.model },
  { label: 'Experiment', value: ArtifactTypeEnum.experiment },
  { label: 'Dataset', value: ArtifactTypeEnum.dataset },
]

export const TRACKS_TYPE_SELECT_PT: MultiSelectPassThroughOptions = {
  root: {
    style: 'width: 230px;',
  },
  header: {
    style: 'display: none;',
  },
}

export const TRACKS_CREATOR_DIALOG_PT: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

export const ARTIFACT_TYPE_OPTIONS = [
  { label: 'Model', value: ArtifactTypeEnum.model },
  { label: 'Experiment', value: ArtifactTypeEnum.experiment },
  { label: 'Dataset', value: ArtifactTypeEnum.dataset },
]

export const TRACK_TYPE_CONFIG = {
  [ArtifactTypeEnum.model]: {
    label: 'Model',
    icon: CircuitBoard,
  },
  [ArtifactTypeEnum.experiment]: {
    label: 'Experiment',
    icon: FlaskConical,
  },
  [ArtifactTypeEnum.dataset]: {
    label: 'Dataset',
    icon: FileChartColumn,
  },
}

export const TABLE_PT: DataTablePassThroughOptions = {
  root: {
    style: 'font-size: 14px;',
  },
  emptyMessageCell: {
    style: 'padding: 25px 16px;',
  },
}

export const STAGE_TAG_SEVERITY = {
  Production: 'success',
  'Pre-Production': 'warn',
  Staging: 'warn',
}

export const getStageTagSeverity = (name: string) => {
  return STAGE_TAG_SEVERITY[name as keyof typeof STAGE_TAG_SEVERITY] || 'default'
}
