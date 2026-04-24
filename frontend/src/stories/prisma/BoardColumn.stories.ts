import type { Meta, StoryObj } from '@storybook/vue3'
import BoardColumn from '@/components/prisma/board/BoardColumn.vue'
import { toBoardItem } from '@/components/prisma/board/board.types'
import { mockRepositories, mockTasks, mockRuns } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof BoardColumn> = {
  title: 'Prisma/Board/BoardColumn',
  component: BoardColumn,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'A single column of the Prisma board. Renders a header (title + count badge, optional fail count), an optional "New" button, and a draggable list of BoardCards.',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="width: 280px; height: 500px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

const pendingItems = [
  toBoardItem('task', mockTasks.find((t) => t.status === 'pending')!),
]

const runningItems = [
  toBoardItem('task', mockTasks.find((t) => t.status === 'running')!),
  toBoardItem('task', mockTasks.find((t) => t.status === 'waiting_input')!),
  toBoardItem('run', mockRuns.find((r) => r.status === 'running')!),
]

const completedItems = [
  toBoardItem('task', mockTasks.find((t) => t.status === 'succeeded')!),
  toBoardItem('task', mockTasks.find((t) => t.status === 'failed')!),
  toBoardItem('run', mockRuns.find((r) => r.status === 'succeeded')!),
]

const mergedItems = [toBoardItem('task', mockTasks.find((t) => t.status === 'merged')!)]

export const Pending: Story = {
  args: {
    title: 'Pending',
    severity: 'warn',
    items: pendingItems,
    repositories: mockRepositories,
    showCreate: true,
  },
}

export const Running: Story = {
  args: {
    title: 'Running',
    severity: 'info',
    items: runningItems,
    repositories: mockRepositories,
  },
}

export const Completed: Story = {
  args: {
    title: 'Completed',
    severity: 'success',
    items: completedItems,
    repositories: mockRepositories,
    failCount: 1,
  },
  parameters: {
    docs: {
      description: {
        story: 'Completed column showing a separate danger count badge for failed items.',
      },
    },
  },
}

export const Merged: Story = {
  args: {
    title: 'Merged',
    severity: 'info',
    items: mergedItems,
    repositories: mockRepositories,
  },
}

export const Empty: Story = {
  args: {
    title: 'Pending',
    severity: 'warn',
    items: [],
    repositories: mockRepositories,
  },
  parameters: {
    docs: {
      description: { story: 'Empty column renders "No items" when `showCreate` is false.' },
    },
  },
}
