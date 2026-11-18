import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { churnBreadcrumbs } from '@/fixtures/experiments-pages'
import { churnFeaturesTable } from '../WorkspacesPage/sample'
import AttachmentsView from './AttachmentsView.vue'

const meta = {
  title: 'Proposals/UIP-002/AttachmentsView',
  component: AttachmentsView,
  args: {
    breadcrumbs: churnBreadcrumbs,
    tree: [
      {
        name: 'data',
        path: 'data',
        expanded: true,
        children: [{ name: 'churn_features.parquet', path: 'data/churn_features.parquet' }],
      },
      { name: 'src', path: 'src', children: [{ name: 'train.py', path: 'src/train.py' }] },
    ],
  },
  parameters: { base: 'Pages/Experiments & evals/AttachmentsView' },
} satisfies Meta<typeof AttachmentsView>

export default meta
type Story = StoryObj<typeof meta>

export const AttachParquet: Story = {
  name: 'table file (.parquet)',
  args: {
    selected: { name: 'churn_features.parquet', path: 'data/churn_features.parquet', size: '4.2 MB' },
    table: churnFeaturesTable,
  },
  parameters: { frame: { width: 1440, height: 1000 } },
}
