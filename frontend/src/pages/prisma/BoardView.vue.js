/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch, onMounted, onUnmounted, inject } from 'vue';
import { useRouter } from 'vue-router';
import { useConfirm } from 'primevue';
import { api } from '@/lib/api';
import { usePrismaStore } from '@/stores/prisma';
import { useBoardItems } from '@/components/prisma/board/useBoardItems';
import { COLUMN_DEFS, FAIL_STATUSES, } from '@/components/prisma/board/board.types';
import BoardToolbar from '@/components/prisma/board/BoardToolbar.vue';
import BoardColumn from '@/components/prisma/board/BoardColumn.vue';
const store = usePrismaStore();
const router = useRouter();
const confirm = useConfirm();
const tasks = ref([]);
const runs = ref([]);
const repositoryFilter = ref(null);
const { columns } = useBoardItems(tasks, runs, repositoryFilter);
const failCounts = computed(() => {
    const counts = {};
    for (const col of COLUMN_DEFS) {
        counts[col.key] = (columns.value[col.key] ?? []).filter((item) => FAIL_STATUSES.has(item.data.status)).length;
    }
    return counts;
});
const newItemType = inject('newItemType');
const boardRefreshTrigger = inject('boardRefreshTrigger');
watch(boardRefreshTrigger, () => refresh());
function openCreate() {
    newItemType.value = 'workflow';
}
let refreshInterval = null;
async function refresh() {
    const repoId = repositoryFilter.value ?? undefined;
    const [taskList, runList, repoList] = await Promise.all([
        api.dataAgent.listTasks(repoId),
        api.dataAgent.listRuns(repoId),
        api.dataAgent.listRepositories(),
    ]);
    tasks.value = taskList;
    runs.value = runList;
    store.tasks = taskList;
    store.setRuns(runList);
    store.repositories = repoList;
}
function onSelect(item) {
    if (item.kind === 'task') {
        router.push({ name: 'prisma-task', params: { taskId: item.data.id } });
    }
    else {
        router.push({ name: 'prisma-run', params: { runId: item.data.id } });
    }
}
async function onStart(item) {
    if (item.kind === 'run') {
        await api.dataAgent.startRun(item.data.id);
    }
    else {
        await api.dataAgent.openTerminal(item.data.id);
    }
    await refresh();
}
function onDelete(item) {
    const label = item.kind === 'task' ? 'task' : 'workflow';
    confirm.require({
        header: `Delete this ${label}?`,
        message: `This will permanently delete the ${label} "${item.data.name}". This action cannot be undone.`,
        acceptProps: {
            label: 'Delete',
            severity: 'danger',
        },
        rejectProps: {
            label: 'Cancel',
            outlined: true,
        },
        accept: async () => {
            if (item.kind === 'task') {
                await api.dataAgent.deleteTask(item.data.id);
            }
            else {
                await api.dataAgent.deleteRun(item.data.id);
            }
            await refresh();
        },
    });
}
async function onReorder(orderedItems) {
    const taskPositions = [];
    const runPositions = [];
    orderedItems.forEach((item, index) => {
        if (item.kind === 'task') {
            taskPositions.push({ id: item.data.id, position: index });
        }
        else {
            runPositions.push({ id: item.data.id, position: index });
        }
    });
    // Optimistic update
    for (const tp of taskPositions) {
        const task = tasks.value.find((t) => t.id === tp.id);
        if (task)
            task.position = tp.position;
    }
    for (const rp of runPositions) {
        const run = runs.value.find((r) => r.id === rp.id);
        if (run)
            run.position = rp.position;
    }
    try {
        const promises = [];
        if (taskPositions.length > 0)
            promises.push(api.dataAgent.reorderTasks(taskPositions));
        if (runPositions.length > 0)
            promises.push(api.dataAgent.reorderRuns(runPositions));
        await Promise.all(promises);
    }
    catch {
        await refresh();
    }
}
onMounted(() => {
    refresh();
    refreshInterval = setInterval(refresh, 5000);
});
onUnmounted(() => {
    if (refreshInterval)
        clearInterval(refreshInterval);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "board-view" },
});
/** @type {__VLS_StyleScopedClasses['board-view']} */ ;
const __VLS_0 = BoardToolbar;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:repositoryFilter': {} },
    repositories: (__VLS_ctx.store.repositories),
    repositoryFilter: (__VLS_ctx.repositoryFilter),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:repositoryFilter': {} },
    repositories: (__VLS_ctx.store.repositories),
    repositoryFilter: (__VLS_ctx.repositoryFilter),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:repositoryFilter': {} },
    { 'onUpdate:repositoryFilter': (...[$event]) => {
            __VLS_ctx.repositoryFilter = $event;
            // @ts-ignore
            [store, repositoryFilter, repositoryFilter,];
        } });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "board-columns" },
});
/** @type {__VLS_StyleScopedClasses['board-columns']} */ ;
for (const [col] of __VLS_vFor((__VLS_ctx.COLUMN_DEFS))) {
    const __VLS_7 = BoardColumn;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        ...{ 'onSelect': {} },
        ...{ 'onStart': {} },
        ...{ 'onDelete': {} },
        ...{ 'onCreate': {} },
        ...{ 'onReorder': {} },
        key: (col.key),
        title: (col.label),
        severity: (col.severity),
        items: (__VLS_ctx.columns[col.key]),
        failCount: (__VLS_ctx.failCounts[col.key]),
        repositories: (__VLS_ctx.store.repositories),
        showCreate: (col.key === 'pending'),
    }));
    const __VLS_9 = __VLS_8({
        ...{ 'onSelect': {} },
        ...{ 'onStart': {} },
        ...{ 'onDelete': {} },
        ...{ 'onCreate': {} },
        ...{ 'onReorder': {} },
        key: (col.key),
        title: (col.label),
        severity: (col.severity),
        items: (__VLS_ctx.columns[col.key]),
        failCount: (__VLS_ctx.failCounts[col.key]),
        repositories: (__VLS_ctx.store.repositories),
        showCreate: (col.key === 'pending'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    let __VLS_12;
    const __VLS_13 = ({ select: {} },
        { onSelect: (__VLS_ctx.onSelect) });
    const __VLS_14 = ({ start: {} },
        { onStart: (__VLS_ctx.onStart) });
    const __VLS_15 = ({ delete: {} },
        { onDelete: (__VLS_ctx.onDelete) });
    const __VLS_16 = ({ create: {} },
        { onCreate: (__VLS_ctx.openCreate) });
    const __VLS_17 = ({ reorder: {} },
        { onReorder: (__VLS_ctx.onReorder) });
    var __VLS_10;
    var __VLS_11;
    // @ts-ignore
    [store, COLUMN_DEFS, columns, failCounts, onSelect, onStart, onDelete, openCreate, onReorder,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
