import { computed } from 'vue';
import { toBoardItem } from './board.types';
function hasPosition(item) {
    return item.data.position != null;
}
function sortItems(a, b) {
    const aHas = hasPosition(a);
    const bHas = hasPosition(b);
    if (aHas && bHas)
        return a.data.position - b.data.position;
    if (aHas && !bHas)
        return -1;
    if (!aHas && bHas)
        return 1;
    return new Date(b.data.updated_at).getTime() - new Date(a.data.updated_at).getTime();
}
export function useBoardItems(tasks, runs, repositoryFilter) {
    const allItems = computed(() => {
        const repoId = repositoryFilter?.value ?? null;
        const filteredTasks = repoId != null ? tasks.value.filter((t) => t.repository_id === repoId) : tasks.value;
        const filteredRuns = repoId != null ? runs.value.filter((r) => r.repository_id === repoId) : runs.value;
        const items = [
            ...filteredTasks.map((t) => toBoardItem('task', t)),
            ...filteredRuns.map((r) => toBoardItem('run', r)),
        ];
        items.sort(sortItems);
        return items;
    });
    const columns = computed(() => {
        const result = {
            pending: [],
            running: [],
            completed: [],
            merged: [],
        };
        for (const item of allItems.value) {
            result[item.column].push(item);
        }
        return result;
    });
    return { columns, allItems };
}
