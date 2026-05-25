/// <reference types="../../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, watch } from 'vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { useVueFlow, VueFlow } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import CustomNode from '@/components/express-tasks/prompt-fusion/step-main/nodes/CustomNode.vue';
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue';
const props = defineProps();
const { addEdges, addNodes } = useVueFlow();
const vueFlowData = computed(() => promptFusionService.createFlowFromMetadata(props.data));
watch(vueFlowData, (data) => {
    addNodes(data.nodes);
    addEdges(data.edges);
}, { immediate: true });
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flow-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['flow-wrapper']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.VueFlow | typeof __VLS_components.VueFlow} */
VueFlow;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    defaultViewport: ({ zoom: 0.8 }),
}));
const __VLS_2 = __VLS_1({
    defaultViewport: ({ zoom: 0.8 }),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { 'node-custom': __VLS_6 } = __VLS_3.slots;
    const [props] = __VLS_vSlot(__VLS_6);
    const __VLS_7 = CustomNode;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        id: (props.id),
        data: (props.data),
    }));
    const __VLS_9 = __VLS_8({
        id: (props.id),
        data: (props.data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
}
{
    const { 'edge-custom': __VLS_12 } = __VLS_3.slots;
    const [edgeProps] = __VLS_vSlot(__VLS_12);
    const __VLS_13 = CustomEdge;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        ...(edgeProps),
    }));
    const __VLS_15 = __VLS_14({
        ...(edgeProps),
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
}
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Background} */
Background;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    patternColor: "var(--dots-color)",
}));
const __VLS_20 = __VLS_19({
    patternColor: "var(--dots-color)",
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
var __VLS_3;
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
