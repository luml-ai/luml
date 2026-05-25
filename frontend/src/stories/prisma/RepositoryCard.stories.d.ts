import type { Meta, StoryObj } from '@storybook/vue3';
import RepositoryCard from '@/components/prisma/RepositoryCard.vue';
import './_mockApi';
declare const meta: Meta<typeof RepositoryCard>;
export default meta;
type Story = StoryObj<typeof meta>;
export declare const Default: Story;
export declare const LongPath: Story;
export declare const CreatePlaceholder: Story;
