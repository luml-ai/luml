/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, onBeforeUnmount, ref } from 'vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import PredictContent from '@/components/predict/index.vue';
const visible = ref(false);
const modelId = ref(promptFusionService.modelId);
const fields = ref(null);
function onChangePredictVisible(value) {
    visible.value = value;
}
function onChangeModelId(id) {
    modelId.value = id;
}
function onChangePredictionFields(data) {
    fields.value = data;
}
onBeforeMount(() => {
    promptFusionService.on('CHANGE_PREDICT_VISIBLE', onChangePredictVisible);
    promptFusionService.on('CHANGE_MODEL_ID', onChangeModelId);
    promptFusionService.on('CHANGE_PREDICTION_FIELDS', onChangePredictionFields);
});
onBeforeUnmount(() => {
    promptFusionService.off('CHANGE_PREDICT_VISIBLE', onChangePredictVisible);
    promptFusionService.off('CHANGE_MODEL_ID', onChangeModelId);
    promptFusionService.off('CHANGE_PREDICTION_FIELDS', onChangePredictionFields);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Predict",
    ...{ style: ({ width: '31.25rem' }) },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Predict",
    ...{ style: ({ width: '31.25rem' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            __VLS_ctx.promptFusionService.togglePredict();
            // @ts-ignore
            [visible, promptFusionService,];
        } });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
if (__VLS_ctx.modelId && __VLS_ctx.fields) {
    const __VLS_9 = PredictContent;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        manualFields: (__VLS_ctx.fields),
        modelId: (__VLS_ctx.modelId),
        task: "prompt_optimization",
    }));
    const __VLS_11 = __VLS_10({
        manualFields: (__VLS_ctx.fields),
        modelId: (__VLS_ctx.modelId),
        task: "prompt_optimization",
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({});
}
// @ts-ignore
[modelId, modelId, fields, fields,];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
