/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ProviderAttributesMap, ProviderDynamicAttributesTagsEnum, ProvidersEnum, } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { computed, onBeforeMount, onMounted, onUnmounted, ref } from 'vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { Skeleton } from 'primevue';
import { LocalStorageService } from '@/utils/services/LocalStorageService';
import RuntimeDashboardPromptOptimizationHeader from './RuntimeDashboardPromptOptimizationHeader.vue';
import PresentationArea from './PresentationArea.vue';
import RuntimeDashboardPromptOptimizationPredict from './RuntimeDashboardPromptOptimizationPredict.vue';
import { mock } from 'mock-json-schema';
const props = defineProps();
const __VLS_emit = defineEmits();
const providerConnected = ref(false);
const initialNodes = ref(null);
const initialEdges = ref(null);
const dynamicAttributes = ref({});
const providerId = computed(() => {
    const metadata = props.model.getMetadata();
    const info = metadata[0];
    return Object.values(ProvidersEnum).find((item) => item.toLowerCase() === info.provider);
});
const fields = computed(() => {
    const dtypes = props.model.getDtypes();
    const schema = dtypes['ext::in'];
    if (!schema)
        return [];
    const sample = mock(schema);
    return Object.keys(sample);
});
function onSettingsChange() {
    providerConnected.value = !!promptFusionService.availableModels.find((model) => model.providerId === providerId.value);
    setDynamicAttributes();
}
function setDynamicAttributes() {
    const manifest = props.model.getManifest();
    const dynamicAttributesList = manifest.dynamic_attributes
        .map((attribute) => {
        const tag = attribute.tags?.find((tag) => tag in ProviderDynamicAttributesTagsEnum);
        return tag ? ProviderDynamicAttributesTagsEnum[tag] : null;
    })
        .filter((attribute) => !!attribute);
    const providerSettings = LocalStorageService.get('providersSettings')?.[providerId.value];
    const entries = dynamicAttributesList.map((attribute) => {
        const value = providerSettings?.[attribute] || '';
        return [ProviderAttributesMap[attribute], value];
    });
    dynamicAttributes.value = Object.fromEntries(entries);
}
onBeforeMount(() => {
    const metadata = props.model.getMetadata();
    const payload = metadata[0].payload;
    if (!payload.nodes || !payload.edges)
        return;
    const flow = promptFusionService.createFlowFromMetadata(payload);
    initialNodes.value = flow.nodes;
    initialEdges.value = flow.edges;
});
onMounted(() => {
    promptFusionService.on('CHANGE_AVAILABLE_MODELS', onSettingsChange);
    onSettingsChange();
});
onUnmounted(() => {
    promptFusionService.off('CHANGE_AVAILABLE_MODELS', onSettingsChange);
});
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
/** @type {__VLS_StyleScopedClasses['body']} */ ;
/** @type {__VLS_StyleScopedClasses['content-area']} */ ;
/** @type {__VLS_StyleScopedClasses['predict-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
const __VLS_0 = RuntimeDashboardPromptOptimizationHeader;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onFinish': {} },
    providerId: (__VLS_ctx.providerId),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onFinish': {} },
    providerId: (__VLS_ctx.providerId),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ finish: {} },
    { onFinish: (...[$event]) => {
            __VLS_ctx.$emit('finish');
            // @ts-ignore
            [providerId, $emit,];
        } });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content-area" },
});
/** @type {__VLS_StyleScopedClasses['content-area']} */ ;
if (__VLS_ctx.initialNodes && __VLS_ctx.initialEdges) {
    const __VLS_7 = PresentationArea || PresentationArea;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        initialNodes: (__VLS_ctx.initialNodes),
        initialEdges: (__VLS_ctx.initialEdges),
    }));
    const __VLS_9 = __VLS_8({
        initialNodes: (__VLS_ctx.initialNodes),
        initialEdges: (__VLS_ctx.initialEdges),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
}
else {
    let __VLS_12;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
        ...{ style: {} },
    }));
    const __VLS_14 = __VLS_13({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "predict-card" },
});
/** @type {__VLS_StyleScopedClasses['predict-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "predict-card-title" },
});
/** @type {__VLS_StyleScopedClasses['predict-card-title']} */ ;
const __VLS_17 = RuntimeDashboardPromptOptimizationPredict || RuntimeDashboardPromptOptimizationPredict;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
    manualFields: (__VLS_ctx.fields),
    modelId: (props.modelId),
    dynamicAttributes: (__VLS_ctx.dynamicAttributes),
    providerConnected: (__VLS_ctx.providerConnected),
}));
const __VLS_19 = __VLS_18({
    manualFields: (__VLS_ctx.fields),
    modelId: (props.modelId),
    dynamicAttributes: (__VLS_ctx.dynamicAttributes),
    providerConnected: (__VLS_ctx.providerConnected),
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
// @ts-ignore
[initialNodes, initialNodes, initialEdges, initialEdges, fields, dynamicAttributes, providerConnected,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
