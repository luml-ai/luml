import type { Meta, StoryObj } from '@storybook/vue3';
import BoardToolbar from '@/components/prisma/board/BoardToolbar.vue';
import './_mockApi';
declare const meta: Meta<typeof BoardToolbar>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const AllRepositories: Story;
export declare const FilteredByRepo: Story;
export declare const NoRepositories: Story;
