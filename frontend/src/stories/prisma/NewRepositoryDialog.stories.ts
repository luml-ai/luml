import type { Meta, StoryObj } from '@storybook/vue3'
import NewRepositoryDialog from '@/components/prisma/NewRepositoryDialog.vue'
import './_mockApi'

const meta: Meta<typeof NewRepositoryDialog> = {
  title: 'Prisma/NewRepositoryDialog',
  component: NewRepositoryDialog,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Modal to register a new repository. Name + FolderPicker (which drives `api.dataAgent.browsePath`).',
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Open: Story = {
  args: { visible: true },
}
