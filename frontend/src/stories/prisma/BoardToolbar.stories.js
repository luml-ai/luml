import { ref } from 'vue';
import BoardToolbar from '@/components/prisma/board/BoardToolbar.vue';
import { mockRepositories } from './_fixtures';
import './_mockApi';
const meta = {
    title: 'Prisma/Board/BoardToolbar',
    component: BoardToolbar,
    tags: ['autodocs'],
    parameters: {
        layout: 'padded',
        docs: {
            description: {
                component: 'Toolbar at the top of the Prisma board. Lets the user filter the columns by repository.',
            },
        },
    },
};
export default meta;
export const AllRepositories = {
    render: (args) => ({
        components: { BoardToolbar },
        setup() {
            const filter = ref(null);
            return { args, filter };
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
};
export const FilteredByRepo = {
    render: (args) => ({
        components: { BoardToolbar },
        setup() {
            const filter = ref('repo-1');
            return { args, filter };
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
};
export const NoRepositories = {
    render: (args) => ({
        components: { BoardToolbar },
        setup() {
            const filter = ref(null);
            return { args, filter };
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
};
