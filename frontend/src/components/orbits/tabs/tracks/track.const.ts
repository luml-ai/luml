import type { DialogPassThroughOptions, MultiSelectPassThroughOptions } from 'primevue'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { CircuitBoard, FileChartColumn, FlaskConical } from 'lucide-vue-next'

export const TRACK_CREATOR_DIALOG_PT: DialogPassThroughOptions = {
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

export const TRACK_TYPE_SELECT_PT: MultiSelectPassThroughOptions = {
  root: {
    style: 'width: 230px;',
  },
  header: {
    style: 'display: none;',
  },
}

export const TRACK_TYPE_OPTIONS = [
  { label: 'Model', value: ArtifactTypeEnum.model, disabled: false },
  { label: 'Dataset', value: ArtifactTypeEnum.dataset, disabled: false },
  { label: 'Experiment', value: ArtifactTypeEnum.experiment, disabled: false },
]

export const TRACK_TYPE_CONFIG: Record<
  string,
  { label: string; icon: typeof CircuitBoard }
> = {
  [ArtifactTypeEnum.model]: {
    label: 'Model',
    icon: CircuitBoard,
  },
  [ArtifactTypeEnum.dataset]: {
    label: 'Dataset',
    icon: FileChartColumn,
  },
  [ArtifactTypeEnum.experiment]: {
    label: 'Experiment',
    icon: FlaskConical,
  },
}
