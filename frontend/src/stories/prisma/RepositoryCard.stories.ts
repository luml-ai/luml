import type { Meta, StoryObj } from '@storybook/vue3'
import RepositoryCard from '@/components/prisma/RepositoryCard.vue'
import { mockRepositories } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof RepositoryCard> = {
  title: 'Prisma/RepositoryCard',
  component: RepositoryCard,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Card shown in the Prisma repository list. Has two modes: `default` (shows repo name, path, delete button) and `create` (a placeholder with a + button).',
      },
    },
  },
  argTypes: {
    type: { control: 'select', options: ['default', 'create'] },
  },
  decorators: [
    (story) => ({
      components: { story },
      template: '<div style="width: 320px;"><story /></div>',
    }),
  ],
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { type: 'default', data: mockRepositories[0] },
}

export const LongPath: Story = {
  args: { type: 'default', data: mockRepositories[2] },
  parameters: {
    docs: {
      description: {
        story: 'Repository with a long path — the path is middle-truncated.',
      },
    },
  },
}

export const CreatePlaceholder: Story = {
  args: { type: 'create' },
}
