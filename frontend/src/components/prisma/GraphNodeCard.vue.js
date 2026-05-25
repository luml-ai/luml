/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { Terminal } from 'lucide-vue-next';
import { usePrismaStore } from '@/stores/prisma';
import { displayStatus } from './board/board.types';
const props = defineProps();
const store = usePrismaStore();
const statusColors = {
    queued: 'var(--p-surface-400)',
    running: 'var(--p-blue-500)',
    waiting_input: 'var(--p-yellow-500)',
    succeeded: 'var(--p-green-500)',
    failed: 'var(--p-red-500)',
    canceled: 'var(--p-surface-400)',
};
const storeNode = computed(() => store.nodes.find((n) => n.id === props.data.id));
const statusColor = computed(() => statusColors[props.data.status] ?? 'var(--p-surface-400)');
const isRunning = computed(() => props.data.status === 'running');
const isWaitingInput = computed(() => props.data.status === 'waiting_input');
const hasTerminal = computed(() => isRunning.value || isWaitingInput.value);
const isRunNode = computed(() => props.data.node_type === 'run');
const metric = computed(() => {
    if (!isRunNode.value)
        return null;
    const node = storeNode.value ?? props.data;
    const val = node?.result?.artifacts?.metric;
    return val !== undefined && val !== null ? val : null;
});
function formatMetric(val) {
    if (typeof val === 'number') {
        return Number.isInteger(val) ? String(val) : val.toFixed(4);
    }
    return JSON.stringify(val);
}
function openTerminal(e) {
    e.stopPropagation();
    const sid = storeNode.value?.session_id ?? props.data.session_id;
    if (sid && props.data.onOpenTerminal) {
        props.data.onOpenTerminal(sid);
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['score-best']} */ ;
/** @type {__VLS_StyleScopedClasses['score-value']} */ ;
/** @type {__VLS_StyleScopedClasses['terminal-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "node-body" },
});
/** @type {__VLS_StyleScopedClasses['node-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-left" },
});
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span)({
    ...{ class: "status-dot" },
    ...{ style: ({ background: __VLS_ctx.statusColor }) },
});
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "header-title" },
});
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
(__VLS_ctx.data.node_type);
if (__VLS_ctx.data.isBest) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "best-tag" },
    });
    /** @type {__VLS_StyleScopedClasses['best-tag']} */ ;
}
if (__VLS_ctx.hasTerminal) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Terminal} */
    Terminal;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onPointerdown': {} },
        ...{ 'onClick': {} },
        size: (14),
        ...{ class: "terminal-icon" },
        title: "Open terminal",
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onPointerdown': {} },
        ...{ 'onClick': {} },
        size: (14),
        ...{ class: "terminal-icon" },
        title: "Open terminal",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ pointerdown: {} },
        { onPointerdown: () => { } });
    const __VLS_7 = ({ click: {} },
        { onClick: (__VLS_ctx.openTerminal) });
    /** @type {__VLS_StyleScopedClasses['terminal-icon']} */ ;
    var __VLS_3;
    var __VLS_4;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "status-label" },
});
/** @type {__VLS_StyleScopedClasses['status-label']} */ ;
(__VLS_ctx.displayStatus(__VLS_ctx.data.status));
if (__VLS_ctx.metric !== null) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "score" },
        ...{ class: ({ 'score-best': __VLS_ctx.data.isBest }) },
    });
    /** @type {__VLS_StyleScopedClasses['score']} */ ;
    /** @type {__VLS_StyleScopedClasses['score-best']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "score-label" },
    });
    /** @type {__VLS_StyleScopedClasses['score-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "score-value" },
    });
    /** @type {__VLS_StyleScopedClasses['score-value']} */ ;
    (__VLS_ctx.formatMetric(__VLS_ctx.metric));
}
// @ts-ignore
[statusColor, data, data, data, data, hasTerminal, openTerminal, displayStatus, metric, metric, formatMetric,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
