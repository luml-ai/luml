/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useVueFlow, VueFlow } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { onMounted } from 'vue';
import CustomNode from '@/components/express-tasks/prompt-fusion/step-main/nodes/CustomNode.vue';
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue';
import PresentationAreaToolbar from './PresentationAreaToolbar.vue';
const props = defineProps();
const { addEdges } = useVueFlow();
onMounted(() => {
    addEdges(props.initialEdges);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "presentation" },
});
/** @type {__VLS_StyleScopedClasses['presentation']} */ ;
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
}));
const __VLS_2 = __VLS_1({
    nodes: (__VLS_ctx.initialNodes),
    ...{ class: "basic-flow" },
    defaultViewport: ({ zoom: 1 }),
    minZoom: (0.2),
    maxZoom: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['basic-flow']} */ ;
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
    // @ts-ignore
    [initialNodes,];
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
    // @ts-ignore
    [];
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
// @ts-ignore
[];
var __VLS_3;
const __VLS_23 = PresentationAreaToolbar || PresentationAreaToolbar;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    ...{ class: "toolbar" },
}));
const __VLS_25 = __VLS_24({
    ...{ class: "toolbar" },
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
