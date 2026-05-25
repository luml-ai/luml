/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { Textarea } from 'primevue';
import { cutStringOnMiddle } from '@/helpers/helpers';
import { predictErrorToast } from '@/lib/primevue/data/toasts';
import { useToast } from 'primevue';
const toast = useToast();
const props = defineProps();
const manualValues = ref(createManualValuesObject(props.inputNames));
const isLoading = ref(false);
const prediction = ref('');
const isPredictButtonDisabled = computed(() => {
    for (const key in manualValues.value) {
        if (!manualValues.value[key])
            return true;
    }
    return isLoading.value;
});
function createManualValuesObject(inputs) {
    return inputs.reduce((acc, input) => {
        acc[input] = '';
        return acc;
    }, {});
}
async function submit() {
    isLoading.value = true;
    try {
        const data = {};
        for (const key in manualValues.value) {
            data[key] = [manualValues.value[key]];
        }
        const predictionResult = await props.predictCallback(data);
        if (predictionResult)
            prediction.value = predictionResult.join(', ');
    }
    catch (e) {
        toast.add(predictErrorToast(e));
    }
    finally {
        isLoading.value = false;
    }
}
watch(manualValues, () => {
    prediction.value = '';
}, { deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['prediction']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "manual-wrapper disabled" },
});
/** @type {__VLS_StyleScopedClasses['manual-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "inputs" },
});
/** @type {__VLS_StyleScopedClasses['inputs']} */ ;
for (const [field] of __VLS_vFor((Object.keys(__VLS_ctx.manualValues)))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "input-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
    dFloatLabel;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        variant: "on",
    }));
    const __VLS_2 = __VLS_1({
        variant: "on",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    const { default: __VLS_5 } = __VLS_3.slots;
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        modelValue: (__VLS_ctx.manualValues[field]),
        id: (field),
        fluid: true,
    }));
    const __VLS_8 = __VLS_7({
        modelValue: (__VLS_ctx.manualValues[field]),
        id: (field),
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "label" },
        for: (field),
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    (__VLS_ctx.cutStringOnMiddle(field, 24));
    // @ts-ignore
    [manualValues, manualValues, manualValues, cutStringOnMiddle,];
    var __VLS_3;
    // @ts-ignore
    [];
}
let __VLS_11;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
    ...{ 'onClick': {} },
    label: "Predict",
    type: "submit",
    fluid: true,
    rounded: true,
    disabled: (__VLS_ctx.isPredictButtonDisabled),
}));
const __VLS_13 = __VLS_12({
    ...{ 'onClick': {} },
    label: "Predict",
    type: "submit",
    fluid: true,
    rounded: true,
    disabled: (__VLS_ctx.isPredictButtonDisabled),
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
let __VLS_16;
const __VLS_17 = ({ click: {} },
    { onClick: (__VLS_ctx.submit) });
var __VLS_14;
var __VLS_15;
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    ...{ class: "prediction" },
    id: "prediction",
    modelValue: (__VLS_ctx.prediction),
    fluid: true,
    rows: "4",
    ...{ style: ({ resize: 'none' }) },
    disabled: true,
    placeholder: "Prediction",
}));
const __VLS_20 = __VLS_19({
    ...{ class: "prediction" },
    id: "prediction",
    modelValue: (__VLS_ctx.prediction),
    fluid: true,
    rows: "4",
    ...{ style: ({ resize: 'none' }) },
    disabled: true,
    placeholder: "Prediction",
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
/** @type {__VLS_StyleScopedClasses['prediction']} */ ;
// @ts-ignore
[isPredictButtonDisabled, submit, prediction,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
