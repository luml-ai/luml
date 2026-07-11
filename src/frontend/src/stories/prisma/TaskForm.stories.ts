import type { Meta, StoryObj } from '@storybook/vue3'
import TaskForm from '@/components/prisma/TaskForm.vue'
import { mockRepositories } from './_fixtures'
import { installPrismaApiStubs } from './_mockApi'

const meta: Meta<typeof TaskForm> = {
  title: 'Prisma/TaskForm',
  component: TaskForm,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Form used inside the New Item dialog when creating a one-shot task. Loads available agents via `api.dataAgent.listAvailableAgents()` and branch options via `api.dataAgent.listBranches(repoPath)` when a repository is selected.',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="width: 480px;"><story /></div>',
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
}

export const BranchFetchSlow: Story = {
  args: { repositories: mockRepositories, loading: false },
  play: async () => {
    installPrismaApiStubs({
      listBranches: async () => {
        await new Promise((r) => setTimeout(r, 2000))
        return ['main', 'develop']
      },
    })
  },
  parameters: {
    docs: {
      description: {
        story:
          'Simulates a slow `listBranches` call — the base branch Select shows its loading state for ~2s after selecting a repository.',
      },
    },
  },
}
