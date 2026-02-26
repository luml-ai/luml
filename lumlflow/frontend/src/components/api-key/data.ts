import type { DialogPassThroughOptions } from 'primevue'
import z from 'zod'

export const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    class: 'w-[600px]',
  },
  header: {
    class: 'text-xl uppercase',
  },
}

export const API_KEY_SCHEMA = z
  .string('API key cannot be empty')
  .min(1, 'API key cannot be empty')
  .regex(/^[A-Za-z0-9]+$/, 'API key must be alphanumeric')
