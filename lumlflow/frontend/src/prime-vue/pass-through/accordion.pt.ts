import type {
  AccordionContentPassThroughOptions,
  AccordionHeaderPassThroughOptions,
  AccordionPanelPassThroughOptions,
  AccordionPassThroughOptions,
} from 'primevue'

export const ACCORDION_PT: AccordionPassThroughOptions = {
  root: {
    class:
      'bg-(--p-card-background) border border-surface rounded-lg shadow-(--p-card-shadow) overflow-hidden',
  },
}

export const ACCORDION_PANEL_PT: AccordionPanelPassThroughOptions = {
  root: {
    class: 'border-l-0! border-t-0! border-r-0! last:border-b-0! border-surface',
  },
}

export const ACCORDION_HEADER_PT: AccordionHeaderPassThroughOptions = {
  root: {
    class: 'bg-transparent! pr-5!',
  },
  toggleicon: {
    class: 'w-3! h-3!',
  },
}

export const ACCORDION_CONTENT_PT: AccordionContentPassThroughOptions = {
  contentWrapper: {
    class: 'overflow-hidden',
  },
  content: {
    class: 'bg-transparent!',
  },
}
