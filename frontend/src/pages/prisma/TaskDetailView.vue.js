/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Button } from 'primevue';
import { ArrowLeft } from 'lucide-vue-next';
import { api } from '@/lib/api';
import TaskDetail from '@/components/prisma/TaskDetail.vue';
import TerminalTabs from '@/components/prisma/TerminalTabs.vue';
const route = useRoute();
const router = useRouter();
const task = ref(null);
const idleSessions = ref([]);
const taskId = computed(() => String(route.params.taskId || ''));
const activeTasks = computed(() => {
    if (!task.value?.session_id || !task.value.is_alive)
        return [];
    return [task.value];
});
let refreshInterval = null;
async function refresh() {
    try {
        task.value = await api.dataAgent.getTask(taskId.value);
    }
    catch {
        task.value = null;
    }
}
function goBack() {
    router.push({ name: 'prisma-board' });
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
    ...{ class: "task-detail-view" },
});
/** @type {__VLS_StyleScopedClasses['task-detail-view']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "detail-header" },
});
/** @type {__VLS_StyleScopedClasses['detail-header']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.goBack) });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.ArrowLeft} */
    ArrowLeft;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (16),
    }));
    const __VLS_11 = __VLS_10({
        size: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [goBack,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "detail-title" },
});
/** @type {__VLS_StyleScopedClasses['detail-title']} */ ;
if (__VLS_ctx.task) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "detail-content" },
    });
    /** @type {__VLS_StyleScopedClasses['detail-content']} */ ;
    const __VLS_14 = TaskDetail;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        ...{ 'onRefresh': {} },
        task: (__VLS_ctx.task),
    }));
    const __VLS_16 = __VLS_15({
        ...{ 'onRefresh': {} },
        task: (__VLS_ctx.task),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    let __VLS_19;
    const __VLS_20 = ({ refresh: {} },
        { onRefresh: (__VLS_ctx.refresh) });
    var __VLS_17;
    var __VLS_18;
    const __VLS_21 = TerminalTabs;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        ...{ 'onUpdate:idleSessions': {} },
        tasks: (__VLS_ctx.activeTasks),
    }));
    const __VLS_23 = __VLS_22({
        ...{ 'onUpdate:idleSessions': {} },
        tasks: (__VLS_ctx.activeTasks),
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    let __VLS_26;
    const __VLS_27 = ({ 'update:idleSessions': {} },
        { 'onUpdate:idleSessions': (...[$event]) => {
                if (!(__VLS_ctx.task))
                    return;
                __VLS_ctx.idleSessions = $event;
                // @ts-ignore
                [task, task, refresh, activeTasks, idleSessions,];
            } });
    var __VLS_24;
    var __VLS_25;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
