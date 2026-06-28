import type { DialogPassThroughOptions } from 'primevue'

export const ARTIFACT_DETAILS_MODAL_PT: DialogPassThroughOptions = {
  root: {
    style: 'margin-top: 80px; height: 86%; width: 100%; max-width: 580px;',
  },
  mask: {
    style: 'background-color: transparent !important;',
  },
  footer: {
    style: 'display: flex; justify-content: flex-end; width: 100%; margin-top: auto;',
  },
}
