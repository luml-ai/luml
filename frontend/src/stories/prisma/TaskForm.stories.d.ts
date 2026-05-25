import type { Meta, StoryObj } from '@storybook/vue3';
import TaskForm from '@/components/prisma/TaskForm.vue';
declare const meta: Meta<typeof TaskForm>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Default: Story;
export declare const Loading: Story;
export declare const NoRepositories: Story;
export declare const BranchFetchSlow: Story;
