import type { Meta, StoryObj } from '@storybook/vue3'
import NewItemDialog from '@/components/prisma/NewItemDialog.vue'
import { mockRepositories } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof NewItemDialog> = {
  title: 'Prisma/NewItemDialog',
  component: NewItemDialog,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Modal to create a new task or workflow. The SelectButton at the top toggles between TaskForm and WorkflowForm; the default is Workflow.',
      },
    },
  },
  argTypes: {
    initialType: { control: 'select', options: ['task', 'workflow'] },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const WorkflowFirst: Story = {
  args: {
    visible: true,
    initialType: 'workflow',
    repositories: mockRepositories,
  },
  parameters: {
    docs: {
      description: {
        story: 'Default entry point — Workflow tab is selected first.',
      },
    },
  },
}

export const TaskTab: Story = {
  args: {
    visible: true,
    initialType: 'task',
    repositories: mockRepositories,
  },
}

export const NoRepositories: Story = {
  args: {
    visible: true,
    initialType: 'workflow',
    repositories: [],
  },
}
