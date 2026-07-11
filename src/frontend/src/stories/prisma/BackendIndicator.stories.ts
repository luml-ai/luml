import type { Meta, StoryObj } from '@storybook/vue3'
import BackendIndicator from '@/components/prisma/BackendIndicator.vue'
import { installPrismaApiStubs } from './_mockApi'

const meta: Meta<typeof BackendIndicator> = {
  title: 'Prisma/BackendIndicator',
  component: BackendIndicator,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Small pill button in the Prisma page header that shows the backend host and opens a popover to edit the backend URL. Persists via `api.dataAgent.setBackendUrl`.',
      },
    },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="padding: 40px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

export const Localhost: Story = {
  play: async () => {
    installPrismaApiStubs({ getBackendUrl: () => 'http://localhost:8420' })
  },
}

export const RemoteHost: Story = {
  play: async () => {
    installPrismaApiStubs({ getBackendUrl: () => 'https://prisma.staging.example.com:8420' })
  },
  parameters: {
    docs: {
      description: {
        story: 'Indicator with a non-localhost URL — only the host is shown in the pill.',
      },
    },
  },
}
