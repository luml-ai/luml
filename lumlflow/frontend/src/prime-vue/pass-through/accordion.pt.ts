import type {
  AccordionContentPassThroughOptions,
  AccordionHeaderPassThroughOptions,
} from 'primevue'

export const ACCORDION_HEADER_PT: AccordionHeaderPassThroughOptions = {
  root: {
    class: 'bg-transparent pr-5!',
  },
}

export const ACCORDION_CONTENT_PT: AccordionContentPassThroughOptions = {
  content: {
    class: 'bg-transparent!',
  },
}
