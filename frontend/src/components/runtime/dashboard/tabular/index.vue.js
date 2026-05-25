/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onBeforeMount, ref } from 'vue';
import { Info } from 'lucide-vue-next';
import PredictManual from './PredictManual.vue';
import PredictFile from './PredictFile.vue';
import ModelPerformance from './ModelPerformance.vue';
import ModelTopFeatures from './ModelTopFeatures.vue';
import { getMetricsCards } from '@/helpers/helpers';
import { NDArray } from '@fnnx-ai/common';
import { FnnxService } from '@/lib/fnnx/FnnxService';
import '@/lib/onnx/onnx';
const props = defineProps();
const __VLS_emit = defineEmits();
const predictType = ref('Manual');
const metrics = ref(null);
const inputNames = computed(() => {
    if (!props.model)
        return [];
    const manifest = props.model.manifest;
    return manifest.inputs.map((input) => input.name);
});
const features = computed(() => {
    if (!metrics.value)
        return [];
    return FnnxService.getTop5TabularFeatures(metrics.value);
});
const totalScore = computed(() => {
    if (!metrics.value)
        return 0;
    return FnnxService.getTabularTotalScore(metrics.value);
});
const testMetrics = computed(() => {
    if (!metrics.value || !props.currentTag)
        return [];
    return FnnxService.prepareTabularMetrics(metrics.value.performance.eval_cv || metrics.value.performance.eval_holdout, props.currentTag);
});
const trainMetrics = computed(() => {
    if (!metrics.value || !props.currentTag)
        return [];
    return FnnxService.prepareTabularMetrics(metrics.value.performance.train, props.currentTag);
});
const metricCardsData = computed(() => props.currentTag ? getMetricsCards(testMetrics.value, trainMetrics.value, props.currentTag) : []);
async function predict(values) {
    const inputs = prepareData(values);
    if (!Object.keys(inputs).length)
        throw new Error('Failed to convert predict data. The data is incorrect.');
    const result = await props.model.compute(inputs, {});
    if (!result?.y_pred.data)
        throw new Error('Predict Failed');
    return result.y_pred.data;
}
function prepareData(values) {
    const manifest = props.model.getManifest();
    const data = {};
    for (const key in values) {
        const valueInfo = manifest.inputs.find((input) => input.name === key);
        if (!valueInfo)
            throw new Error('Incorrect data');
        const inputType = extractType(valueInfo.dtype);
        if (inputType) {
            data[key] = new NDArray([values[key].length, 1], values[key], inputType);
        }
    }
    return data;
}
function extractType(string) {
    const match = string.match(/Array\[(.*)\]/);
    return match ? match[1] : null;
}
onBeforeMount(() => {
    metrics.value = FnnxService.getTabularMetrics(props.model.getMetadata());
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
/** @type {__VLS_StyleScopedClasses['board']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    label: "exit",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    label: "exit",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$emit('finish');
            // @ts-ignore
            [$emit,];
        } });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "board" },
});
/** @type {__VLS_StyleScopedClasses['board']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Info} */
Info;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    color: "var(--p-icon-muted-color)",
    width: "20",
    height: "20",
}));
const __VLS_9 = __VLS_8({
    color: "var(--p-icon-muted-color)",
    width: "20",
    height: "20",
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: (`Track your model's effectiveness through performance metrics. Higher scores indicate better predictions and generalization to new data`) }, null, null);
const __VLS_12 = ModelPerformance;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    metrics: (__VLS_ctx.metricCardsData),
    totalScore: (__VLS_ctx.totalScore),
}));
const __VLS_14 = __VLS_13({
    metrics: (__VLS_ctx.metricCardsData),
    totalScore: (__VLS_ctx.totalScore),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
    ...{ class: ({ 'card-predict-manual': __VLS_ctx.predictType === 'Manual' }) },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-predict-manual']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card-sub-title" },
});
/** @type {__VLS_StyleScopedClasses['card-sub-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "predict-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['predict-wrapper']} */ ;
let __VLS_17;
/** @ts-ignore @type { | typeof __VLS_components.selectButton | typeof __VLS_components.SelectButton | typeof __VLS_components['select-button']} */
selectButton;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
    modelValue: (__VLS_ctx.predictType),
    options: (['Manual', 'Upload file']),
}));
const __VLS_19 = __VLS_18({
    modelValue: (__VLS_ctx.predictType),
    options: (['Manual', 'Upload file']),
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
if (__VLS_ctx.predictType === 'Manual') {
    const __VLS_22 = PredictManual;
    // @ts-ignore
    const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
        inputNames: (__VLS_ctx.inputNames),
        predictCallback: (__VLS_ctx.predict),
    }));
    const __VLS_24 = __VLS_23({
        inputNames: (__VLS_ctx.inputNames),
        predictCallback: (__VLS_ctx.predict),
    }, ...__VLS_functionalComponentArgsRest(__VLS_23));
}
else {
    const __VLS_27 = PredictFile;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        predictCallback: (__VLS_ctx.predict),
    }));
    const __VLS_29 = __VLS_28({
        predictCallback: (__VLS_ctx.predict),
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
(__VLS_ctx.features.length);
const __VLS_32 = ModelTopFeatures;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    features: (__VLS_ctx.features),
}));
const __VLS_34 = __VLS_33({
    features: (__VLS_ctx.features),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
// @ts-ignore
[vTooltip, metricCardsData, totalScore, predictType, predictType, predictType, inputNames, predict, predict, features, features,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
