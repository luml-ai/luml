import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { CircuitBoard, FlaskConical, FileChartColumn } from 'lucide-vue-next'
import type { DialogPassThroughOptions } from 'primevue'

/**
 * Identifier of the Vue Flow instance shared by the lineage store, the canvas
 * and the toolbar. Vue Flow shares an instance across components only through
 * an explicit id; without it every mount of the canvas would create its own
 * instance and the store's edits would never reach it.
 */
export const LINEAGE_FLOW_ID = 'lineage'

export const LINEAGE_NODE_ICONS = {
  [ArtifactTypeEnum.model]: {
    icon: CircuitBoard,
    color: 'var(--p-badge-secondary-color)',
  },
  [ArtifactTypeEnum.experiment]: {
    icon: FlaskConical,
    color: 'var(--p-badge-info-background)',
  },
  [ArtifactTypeEnum.dataset]: {
    icon: FileChartColumn,
    color: '#F97316',
  },
}

export const LINK_CREATOR_DIALOG_PT: DialogPassThroughOptions = {
  root: {
    style: 'width: 100%; max-width: 500px; height: 737px;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}
