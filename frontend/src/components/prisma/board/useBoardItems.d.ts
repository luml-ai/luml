import { type Ref } from 'vue';
import type { AgentTask, Run } from '@/lib/api/prisma/prisma.interfaces';
export declare function useBoardItems(tasks: Ref<AgentTask[]>, runs: Ref<Run[]>, repositoryFilter?: Ref<string | null>): {
    columns: any;
    allItems: any;
};
