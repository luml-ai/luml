/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { VueFlow } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import { usePrismaStore } from '@/stores/prisma';
import { computeLayout } from './utils/graphLayout';
import GraphNodeCard from './GraphNodeCard.vue';
const store = usePrismaStore();
const emit = defineEmits();
function handleOpenTerminal(sessionId, nodeType, nodeId) {
    emit('open-terminal', sessionId, `${nodeType} #${nodeId}`);
}
const layout = computed(() => computeLayout(store.nodes, store.edges));
const bestNodeId = computed(() => store.selectedRun?.best_node_id ?? null);
const flowNodes = computed(() => {
    return layout.value.nodes.map((n) => ({
        ...n,
        data: {
            ...n.data,
            selected: n.data.id === store.selectedNodeId,
            isBest: n.data.id === bestNodeId.value,
            onOpenTerminal: (sid) => handleOpenTerminal(sid, n.data.node_type, n.data.id),
        },
    }));
});
const flowEdges = computed(() => layout.value.edges);
function onNodeClick(event) {
    store.selectNode(event.node.id);
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['graph-container']} */ ;
/** @type {__VLS_StyleScopedClasses['agent-flow']} */ ;
/** @type {__VLS_StyleScopedClasses['agent-flow']} */ ;
/** @type {__VLS_StyleScopedClasses['agent-flow']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "graph-container" },
});
/** @type {__VLS_StyleScopedClasses['graph-container']} */ ;
if (__VLS_ctx.store.selectedRunId && __VLS_ctx.store.nodes.length > 0) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.VueFlow | typeof __VLS_components.VueFlow} */
    VueFlow;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onNodeClick': {} },
        nodes: (__VLS_ctx.flowNodes),
        edges: (__VLS_ctx.flowEdges),
        nodesDraggable: (false),
        nodesConnectable: (false),
        fitViewOnInit: true,
        ...{ class: "agent-flow" },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onNodeClick': {} },
        nodes: (__VLS_ctx.flowNodes),
        edges: (__VLS_ctx.flowEdges),
        nodesDraggable: (false),
        nodesConnectable: (false),
        fitViewOnInit: true,
        ...{ class: "agent-flow" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ nodeClick: {} },
        { onNodeClick: (__VLS_ctx.onNodeClick) });
    /** @type {__VLS_StyleScopedClasses['agent-flow']} */ ;
    const { default: __VLS_7 } = __VLS_3.slots;
    {
        const { 'node-graphNode': __VLS_8 } = __VLS_3.slots;
        const [{ data }] = __VLS_vSlot(__VLS_8);
        const __VLS_9 = GraphNodeCard;
        // @ts-ignore
        const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
            data: (data),
            selected: (data.selected),
        }));
        const __VLS_11 = __VLS_10({
            data: (data),
            selected: (data.selected),
        }, ...__VLS_functionalComponentArgsRest(__VLS_10));
        // @ts-ignore
        [store, store, flowNodes, flowEdges, onNodeClick,];
    }
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Background} */
    Background;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        patternColor: "var(--dots-color)",
    }));
    const __VLS_16 = __VLS_15({
        patternColor: "var(--dots-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
}
else if (__VLS_ctx.store.selectedRunId) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
}
// @ts-ignore
[store,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};
