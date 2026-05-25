/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { getBezierPath } from '@vue-flow/core';
import CustomMarker from './CustomMarker.vue';
import { useVueFlow } from '@vue-flow/core';
const { findNode, getSelectedEdges } = useVueFlow();
const props = defineProps();
const path = computed(() => getBezierPath(props));
const markerId = computed(() => `${props.id}-marker`);
const isEdgeSelected = computed(() => getSelectedEdges.value.find((edge) => edge.id === props.id));
const isNodesSelected = computed(() => {
    const sourceNode = findNode(props.source);
    const targetNode = findNode(props.target);
    return (sourceNode && sourceNode.selected) || (targetNode && targetNode.selected);
});
const markerColor = computed(() => isEdgeSelected.value || isNodesSelected.value ? 'var(--p-primary-color)' : 'var(--p-surface-500)');
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.baseEdge | typeof __VLS_components.BaseEdge | typeof __VLS_components['base-edge']} */
baseEdge;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    path: (__VLS_ctx.path[0]),
    markerEnd: (`url(#${__VLS_ctx.markerId})`),
    markerStart: (`url(#${__VLS_ctx.markerId})`),
}));
const __VLS_2 = __VLS_1({
    path: (__VLS_ctx.path[0]),
    markerEnd: (`url(#${__VLS_ctx.markerId})`),
    markerStart: (`url(#${__VLS_ctx.markerId})`),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_5 = CustomMarker;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    id: (__VLS_ctx.markerId),
    stroke: (__VLS_ctx.markerColor),
    fill: (__VLS_ctx.markerColor),
}));
const __VLS_7 = __VLS_6({
    id: (__VLS_ctx.markerId),
    stroke: (__VLS_ctx.markerColor),
    fill: (__VLS_ctx.markerColor),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
// @ts-ignore
[path, markerId, markerId, markerId, markerColor, markerColor,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
