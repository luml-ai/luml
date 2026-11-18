import type { Meta, StoryObj } from '@storybook/vue3-vite'
import { openFlows } from '@/fixtures/workspaces'
import { filesListed } from '../WorkspacesPage/sample'
import WorkspaceFolder from './WorkspaceFolder.vue'

const meta = {
  title: 'Proposals/UIP-002/WorkspaceFolder',
  component: WorkspaceFolder,
  args: { items: filesListed, openFlows },
  parameters: {
    app: 'lumlflow',
    base: 'Blocks/WorkspaceFolder',
    canvas: {
      rows: [
        { label: 'Listing', stories: ['WithFiles', 'FileSelected', 'Empty'] },
        { label: 'File operations', stories: ['FileMenuOpen', 'FolderRenaming'] },
      ],
    },
  },
} satisfies Meta<typeof WorkspaceFolder>

export default meta
type Story = StoryObj<typeof meta>

export const WithFiles: Story = { name: 'notebooks, folders and files' }

export const FileSelected: Story = {
  name: 'file selected',
  args: { selectedId: '/home/ml/projects/churn-model/train.py' },
}

export const FileMenuOpen: Story = {
  name: 'file row menu open',
  args: { menuOpenId: '/home/ml/projects/churn-model/train.py' },
}

export const FolderRenaming: Story = {
  name: 'renaming a folder',
  args: { renamingId: '/home/ml/projects/churn-model/reports', renameValue: 'reports-2026' },
}

export const Empty: Story = { name: 'empty directory', args: { items: [], openFlows: [] } }
