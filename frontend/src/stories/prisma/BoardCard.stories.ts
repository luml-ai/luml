import type { Meta, StoryObj } from '@storybook/vue3'
import BoardCard from '@/components/prisma/board/BoardCard.vue'
import { toBoardItem } from '@/components/prisma/board/board.types'
import { mockTasks, mockRuns } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof BoardCard> = {
  title: 'Prisma/Board/BoardCard',
  component: BoardCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Card shown in each column of the Prisma board. Displays a task or run with its name, repository, status tag, relative updated time and contextual action buttons (Start shown only when status is `pending`).',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="width: 280px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

const pendingTask = mockTasks.find((t) => t.status === 'pending')!
const runningTask = mockTasks.find((t) => t.status === 'running')!
const waitingTask = mockTasks.find((t) => t.status === 'waiting_input')!
const succeededTask = mockTasks.find((t) => t.status === 'succeeded')!
const failedTask = mockTasks.find((t) => t.status === 'failed')!
const mergedTask = mockTasks.find((t) => t.status === 'merged')!

export const TaskPending: Story = {
  args: {
    item: toBoardItem('task', pendingTask),
    repositoryName: 'ml-experiments',
  },
  parameters: {
    docs: {
      description: { story: 'Pending task — shows the Start button.' },
    },
  },
}

export const TaskRunning: Story = {
  args: {
    item: toBoardItem('task', runningTask),
    repositoryName: 'ml-experiments',
  },
}

export const TaskWaitingInput: Story = {
  args: {
    item: toBoardItem('task', waitingTask),
    repositoryName: 'nlp-benchmarks',
  },
  parameters: {
    docs: {
      description: {
        story: 'Task waiting for input — status label reads "waiting for input" with a warn tag.',
      },
    },
  },
}

export const TaskSucceeded: Story = {
  args: {
    item: toBoardItem('task', succeededTask),
    repositoryName: 'ml-experiments',
  },
}

export const TaskFailed: Story = {
  args: {
    item: toBoardItem('task', failedTask),
    repositoryName: 'nlp-benchmarks',
  },
}

export const TaskMerged: Story = {
  args: {
    item: toBoardItem('task', mergedTask),
    repositoryName: 'ml-experiments',
  },
}

export const Workflow: Story = {
  args: {
    item: toBoardItem('run', mockRuns[0]),
    repositoryName: 'ml-experiments',
  },
  parameters: {
    docs: {
      description: { story: 'Workflow (run) uses the Waypoints icon instead of ListTodo.' },
    },
  },
}
