import type { Meta, StoryObj } from '@storybook/vue3'
import WorkflowForm from '@/components/prisma/WorkflowForm.vue'
import { mockRepositories } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof WorkflowForm> = {
  title: 'Prisma/WorkflowForm',
  component: WorkflowForm,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Form used inside the New Item dialog when creating a workflow (orchestrated run). Collects the objective, agent, auto-mode, optional LUML collection upload, and an Advanced section with depth/fork/concurrency/timeout knobs.',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="width: 520px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { repositories: mockRepositories, loading: false },
}

export const Loading: Story = {
  args: { repositories: mockRepositories, loading: true },
}

export const NoRepositories: Story = {
  args: { repositories: [], loading: false },
  parameters: {
    docs: {
      description: {
        story: 'No repositories configured — the Repository select is empty.',
      },
    },
  },
}
