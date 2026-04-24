import type { Meta, StoryObj } from '@storybook/vue3'
import { ref } from 'vue'
import BoardToolbar from '@/components/prisma/board/BoardToolbar.vue'
import { mockRepositories } from './_fixtures'
import './_mockApi'

const meta: Meta<typeof BoardToolbar> = {
  title: 'Prisma/Board/BoardToolbar',
  component: BoardToolbar,
  tags: ['autodocs'],
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Toolbar at the top of the Prisma board. Lets the user filter the columns by repository.',
      },
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const AllRepositories: Story = {
  render: (args) => ({
    components: { BoardToolbar },
    setup() {
      const filter = ref<string | null>(null)
      return { args, filter }
    },
    template: `
      <BoardToolbar
        v-bind="args"
        :repository-filter="filter"
        @update:repositoryFilter="filter = $event"
      />
    `,
  }),
  args: { repositories: mockRepositories },
}

export const FilteredByRepo: Story = {
  render: (args) => ({
    components: { BoardToolbar },
    setup() {
      const filter = ref<string | null>('repo-1')
      return { args, filter }
    },
    template: `
      <BoardToolbar
        v-bind="args"
        :repository-filter="filter"
        @update:repositoryFilter="filter = $event"
      />
    `,
  }),
  args: { repositories: mockRepositories },
}

export const NoRepositories: Story = {
  render: (args) => ({
    components: { BoardToolbar },
    setup() {
      const filter = ref<string | null>(null)
      return { args, filter }
    },
    template: `
      <BoardToolbar
        v-bind="args"
        :repository-filter="filter"
        @update:repositoryFilter="filter = $event"
      />
    `,
  }),
  args: { repositories: [] },
}
