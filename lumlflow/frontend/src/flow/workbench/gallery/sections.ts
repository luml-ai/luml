import type { Component } from 'vue'
import { defineAsyncComponent } from 'vue'

export interface GallerySection {
  id: string
  label: string
  group: 'Foundations' | 'Components' | 'Pages'
  component: Component
}

export const sections: GallerySection[] = [
  {
    id: 'foundations',
    label: 'Foundations',
    group: 'Foundations',
    component: defineAsyncComponent(() => import('./sections/FoundationsSection.vue')),
  },
  {
    id: 'renderers',
    label: 'Renderers',
    group: 'Foundations',
    component: defineAsyncComponent(() => import('./sections/RenderersSection.vue')),
  },
  {
    id: 'cell-card',
    label: 'Cell card',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/CellCardSection.vue')),
  },
  {
    id: 'run-controls',
    label: 'Run controls',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/RunControlsSection.vue')),
  },
  {
    id: 'errors',
    label: 'Errors & recovery',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/ErrorsSection.vue')),
  },
  {
    id: 'left-panel',
    label: 'Left panel',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/LeftPanelSection.vue')),
  },
  {
    id: 'branch-graph',
    label: 'Lane map',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/BranchGraphSection.vue')),
  },
  {
    id: 'session',
    label: 'Session & pairing',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/SessionSection.vue')),
  },
  {
    id: 'compare',
    label: 'Compare',
    group: 'Components',
    component: defineAsyncComponent(() => import('./sections/CompareSection.vue')),
  },
  {
    id: 'pages',
    label: 'Pages',
    group: 'Pages',
    component: defineAsyncComponent(() => import('./sections/PagesSection.vue')),
  },
]

export const sectionGroups = ['Foundations', 'Components', 'Pages'] as const

export function sectionById(id: string | undefined): GallerySection {
  return sections.find((section) => section.id === id) ?? sections[0]
}
