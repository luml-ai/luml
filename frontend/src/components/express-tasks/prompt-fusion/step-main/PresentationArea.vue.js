/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { VueFlow, useVueFlow } from '@vue-flow/core';
import CustomNode from './nodes/CustomNode.vue';
import { v4 as uuidv4 } from 'uuid';
import { Background } from '@vue-flow/background';
import { onBeforeMount, onBeforeUnmount } from 'vue';
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue';
const __VLS_props = defineProps();
const { nodes, onConnect, addEdges, removeNodes, addNodes, removeEdges, getSelectedEdges } = useVueFlow();
function duplicateNode(id) {
    const node = nodes.value.find((node) => node.id === id);
    if (!node)
        throw new Error('Node not found');
    const clone = JSON.parse(JSON.stringify(node));
    clone.id = uuidv4();
    clone.data.fields = clone.data.fields.map((field) => ({ ...field, id: uuidv4() }));
    clone.position.x = 10;
    clone.position.y = 10;
    clone.selected = false;
    addNodes(clone);
}
function isValidConnection(connection) {
    if (connection.source === connection.target)
        return false;
    const sourceNode = nodes.value.find((node) => node.id === connection.source);
    const targetNode = nodes.value.find((node) => node.id === connection.target);
    const sourceField = sourceNode?.data.fields.find((field) => field.id === connection.sourceHandle);
    const targetField = targetNode?.data.fields.find((field) => field.id === connection.targetHandle);
    if (sourceField?.handlePosition === targetField?.handlePosition)
        return false;
    return true;
}
function onBackspaceClick(e) {
    if (e.code === 'Delete') {
        removeEdges(getSelectedEdges.value);
    }
}
onConnect((connection) => {
    addEdges({ ...connection, type: 'custom' });
});
onBeforeMount(() => {
    document.addEventListener('keydown', onBackspaceClick);
});
onBeforeUnmount(() => {
    document.removeEventListener('keydown', onBackspaceClick);
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['basic-flow']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.VueFlow | typeof __VLS_components.VueFlow} */
VueFlow;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    nodes: (__VLS_ctx.initialNodes),
    ...{ class: "basic-flow" },
    defaultViewport: ({ zoom: 1 }),
    minZoom: (0.2),
    maxZoom: (4),
    isValidConnection: (__VLS_ctx.isValidConnection),
}));
const __VLS_2 = __VLS_1({
    nodes: (__VLS_ctx.initialNodes),
    ...{ class: "basic-flow" },
    defaultViewport: ({ zoom: 1 }),
    minZoom: (0.2),
    maxZoom: (4),
    isValidConnection: (__VLS_ctx.isValidConnection),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
/** @type {__VLS_StyleScopedClasses['basic-flow']} */ ;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { 'node-custom': __VLS_7 } = __VLS_3.slots;
    const [props] = __VLS_vSlot(__VLS_7);
    const __VLS_8 = CustomNode;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onDuplicate': {} },
        ...{ 'onDelete': {} },
        id: (props.id),
        data: (props.data),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onDuplicate': {} },
        ...{ 'onDelete': {} },
        id: (props.id),
        data: (props.data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ duplicate: {} },
        { onDuplicate: (...[$event]) => {
                __VLS_ctx.duplicateNode(props.id);
                // @ts-ignore
                [initialNodes, isValidConnection, duplicateNode,];
            } });
    const __VLS_15 = ({ delete: {} },
        { onDelete: (...[$event]) => {
                __VLS_ctx.removeNodes(props.id);
                // @ts-ignore
                [removeNodes,];
            } });
    var __VLS_11;
    var __VLS_12;
    // @ts-ignore
    [];
}
{
    const { 'edge-custom': __VLS_16 } = __VLS_3.slots;
    const [edgeProps] = __VLS_vSlot(__VLS_16);
    const __VLS_17 = CustomEdge;
    // @ts-ignore
    const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
        ...(edgeProps),
    }));
    const __VLS_19 = __VLS_18({
        ...(edgeProps),
    }, ...__VLS_functionalComponentArgsRest(__VLS_18));
    // @ts-ignore
    [];
}
let __VLS_22;
/** @ts-ignore @type { | typeof __VLS_components.Background} */
Background;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
    patternColor: "var(--dots-color)",
}));
const __VLS_24 = __VLS_23({
    patternColor: "var(--dots-color)",
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
