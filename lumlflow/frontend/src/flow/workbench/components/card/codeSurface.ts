/**
 * The house code slab. Read-only source and the editor's own placeholder share
 * it so the two cannot drift apart while one of them is being swapped out.
 *
 * No border: the card already frames it, and a bordered block inside a bordered
 * section inside a bordered card is three levels of the same line.
 */
export const CODE_SURFACE_CLASS =
  'font-mono text-sm leading-relaxed rounded-lg ' +
  'bg-surface-50 dark:bg-surface-800 p-3 overflow-auto'
