import type { DialogPassThroughOptions, MultiSelectPassThroughOptions } from 'primevue'
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import { CircuitBoard, FileChartColumn, FlaskConical, Package } from 'lucide-vue-next'

export const COLLECTION_CREATOR_DIALOG_PT: DialogPassThroughOptions = {
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

export const COLLECTION_TYPE_SELECT_PT: MultiSelectPassThroughOptions = {
  root: {
    style: 'width: 230px;',
  },
  header: {
    style: 'display: none;',
  },
}

export const COLLECTION_TYPE_OPTIONS = [
  { label: 'Model', value: OrbitCollectionTypeEnum.model, disabled: false },
  { label: 'Dataset', value: OrbitCollectionTypeEnum.dataset, disabled: true },
  { label: 'Experiment', value: OrbitCollectionTypeEnum.experiment, disabled: true },
  { label: 'Mixed', value: OrbitCollectionTypeEnum.mixed, disabled: true },
]

export const COLLECTION_TYPE_CONFIG = {
  [OrbitCollectionTypeEnum.model]: {
    label: 'Model',
    icon: CircuitBoard,
  },
  [OrbitCollectionTypeEnum.dataset]: {
    label: 'Dataset',
    icon: FileChartColumn,
  },
  [OrbitCollectionTypeEnum.experiment]: {
    label: 'Experiment',
    icon: FlaskConical,
  },
  [OrbitCollectionTypeEnum.mixed]: {
    label: 'Mixed',
    icon: Package,
  },
}
