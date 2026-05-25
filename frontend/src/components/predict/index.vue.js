/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { useDataTable } from '@/hooks/useDataTable';
import { useModelTraining } from '@/hooks/useModelTraining';
import { convertObjectToCsvBlob, downloadFileFromBlob } from '@/helpers/helpers';
import { cutStringOnMiddle } from '@/helpers/helpers';
import { Textarea } from 'primevue';
import SelectButton from 'primevue/selectbutton';
import FileInput from '@/components/ui/FileInput.vue';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
const props = defineProps();
const { startPredict, isLoading } = useModelTraining(props.task === 'prompt_optimization' ? 'prompt_optimization' : 'tabular');
const tableValidator = () => {
    return { size: false, columns: false, rows: false };
};
const { isUploadWithErrors, fileData, onSelectFile, getDataForTraining, onRemoveFile } = useDataTable(tableValidator);
const selectValue = ref('Manual');
const selectOptions = ref(['Manual', 'Upload file']);
const manualValues = ref(props.manualFields.reduce((acc, field) => {
    acc[field] = '';
    return acc;
}, {}));
const predictionText = ref('');
const filePredictWithError = ref(false);
const downloadPredictBlob = ref(null);
const predictReadyForDownload = computed(() => !!downloadPredictBlob.value);
const isPredictButtonDisabled = computed(() => !fileData.value.name || isUploadWithErrors.value);
const isManualPredictButtonDisabled = computed(() => {
    for (const input in manualValues.value) {
        if (!manualValues.value[input])
            return true;
    }
    return false;
});
async function onManualSubmit() {
    AnalyticsService.track(AnalyticsTrackKeysEnum.predict, { task: props.task });
    predictionText.value = '';
    const data = prepareManualData();
    const predictRequest = { data, model_id: props.modelId };
    const result = await startPredict(predictRequest);
    if (!result?.predictions)
        return;
    if (typeof result.predictions[0] === 'string' || typeof result.predictions[0] === 'number') {
        predictionText.value = result.predictions.join(', ');
    }
    else if (typeof result.predictions[0] === 'object') {
        predictionText.value = JSON.stringify(result.predictions);
    }
}
async function onFileSubmit() {
    AnalyticsService.track(AnalyticsTrackKeysEnum.predict, { task: props.task });
    const data = getDataForTraining();
    const predictRequest = { data, model_id: props.modelId };
    const result = await startPredict(predictRequest);
    if (result) {
        data.prediction = result.predictions;
        downloadPredictBlob.value = convertObjectToCsvBlob(data);
    }
    else {
        filePredictWithError.value = true;
    }
}
function prepareManualData() {
    const data = {};
    for (const key in manualValues.value) {
        const value = manualValues.value[key].trim();
        if (!value)
            continue;
        const formattedValue = isNaN(Number(value)) ? value : Number(value);
        data[key] = [formattedValue];
    }
    return data;
}
function downloadPredict() {
    if (!downloadPredictBlob.value)
        return;
    downloadFileFromBlob(downloadPredictBlob.value, 'dfs-predictions');
}
watch(fileData, () => {
    filePredictWithError.value = false;
    downloadPredictBlob.value = null;
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
    ...{ class: "content" },
    ...{ class: ({ disabled: __VLS_ctx.isLoading }) },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.SelectButton} */
SelectButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.selectValue),
    options: (__VLS_ctx.selectOptions),
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.selectValue),
    options: (__VLS_ctx.selectOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
if (__VLS_ctx.selectValue === 'Manual') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "manual" },
    });
    /** @type {__VLS_StyleScopedClasses['manual']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "inputs" },
    });
    /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
    for (const [field] of __VLS_vFor((Object.keys(__VLS_ctx.manualValues)))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (field),
            ...{ class: "input-wrapper" },
        });
        /** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label'] | typeof __VLS_components.dFloatLabel | typeof __VLS_components.DFloatLabel | typeof __VLS_components['d-float-label']} */
        dFloatLabel;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            variant: "on",
        }));
        const __VLS_7 = __VLS_6({
            variant: "on",
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
        const { default: __VLS_10 } = __VLS_8.slots;
        let __VLS_11;
        /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
        dInputText;
        // @ts-ignore
        const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
            modelValue: (__VLS_ctx.manualValues[field]),
            id: (field),
            fluid: true,
        }));
        const __VLS_13 = __VLS_12({
            modelValue: (__VLS_ctx.manualValues[field]),
            id: (field),
            fluid: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_12));
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
            for: (field),
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        (__VLS_ctx.cutStringOnMiddle(field, 24));
        // @ts-ignore
        [isLoading, selectValue, selectValue, selectOptions, manualValues, manualValues, manualValues, cutStringOnMiddle,];
        var __VLS_8;
        // @ts-ignore
        [];
    }
    let __VLS_16;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
        ...{ 'onClick': {} },
        label: "Predict",
        type: "submit",
        fluid: true,
        rounded: true,
        disabled: (__VLS_ctx.isManualPredictButtonDisabled),
    }));
    const __VLS_18 = __VLS_17({
        ...{ 'onClick': {} },
        label: "Predict",
        type: "submit",
        fluid: true,
        rounded: true,
        disabled: (__VLS_ctx.isManualPredictButtonDisabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    let __VLS_21;
    const __VLS_22 = ({ click: {} },
        { onClick: (__VLS_ctx.onManualSubmit) });
    var __VLS_19;
    var __VLS_20;
    let __VLS_23;
    /** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
    Textarea;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        ...{ class: "prediction" },
        modelValue: (__VLS_ctx.predictionText),
        id: "prediction",
        fluid: true,
        rows: "4",
        ...{ style: ({ resize: 'none' }) },
        disabled: true,
        placeholder: "Prediction",
    }));
    const __VLS_25 = __VLS_24({
        ...{ class: "prediction" },
        modelValue: (__VLS_ctx.predictionText),
        id: "prediction",
        fluid: true,
        rows: "4",
        ...{ style: ({ resize: 'none' }) },
        disabled: true,
        placeholder: "Prediction",
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
    /** @type {__VLS_StyleScopedClasses['prediction']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "upload" },
    });
    /** @type {__VLS_StyleScopedClasses['upload']} */ ;
    const __VLS_28 = FileInput;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
        ...{ 'onSelectFile': {} },
        ...{ 'onRemoveFile': {} },
        id: "predict",
        file: (__VLS_ctx.fileData),
        error: (__VLS_ctx.isUploadWithErrors || __VLS_ctx.filePredictWithError),
        loading: (__VLS_ctx.isLoading),
        loadingMessage: "Loading prediction...",
        successMessageOnly: (__VLS_ctx.predictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''),
        successRemoveText: "Upload new dataset",
        accept: (['text/csv']),
        acceptText: "Supports CSV file format",
        uploadText: "upload CSV",
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onSelectFile': {} },
        ...{ 'onRemoveFile': {} },
        id: "predict",
        file: (__VLS_ctx.fileData),
        error: (__VLS_ctx.isUploadWithErrors || __VLS_ctx.filePredictWithError),
        loading: (__VLS_ctx.isLoading),
        loadingMessage: "Loading prediction...",
        successMessageOnly: (__VLS_ctx.predictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''),
        successRemoveText: "Upload new dataset",
        accept: (['text/csv']),
        acceptText: "Supports CSV file format",
        uploadText: "upload CSV",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_33;
    const __VLS_34 = ({ selectFile: {} },
        { onSelectFile: (__VLS_ctx.onSelectFile) });
    const __VLS_35 = ({ removeFile: {} },
        { onRemoveFile: (__VLS_ctx.onRemoveFile) });
    var __VLS_31;
    var __VLS_32;
    if (__VLS_ctx.predictReadyForDownload) {
        let __VLS_36;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
            ...{ 'onClick': {} },
            label: "Download",
            type: "submit",
            fluid: true,
        }));
        const __VLS_38 = __VLS_37({
            ...{ 'onClick': {} },
            label: "Download",
            type: "submit",
            fluid: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
        let __VLS_41;
        const __VLS_42 = ({ click: {} },
            { onClick: (__VLS_ctx.downloadPredict) });
        var __VLS_39;
        var __VLS_40;
    }
    else {
        let __VLS_43;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
            ...{ 'onClick': {} },
            label: "Predict",
            type: "submit",
            fluid: true,
            disabled: (__VLS_ctx.isPredictButtonDisabled),
        }));
        const __VLS_45 = __VLS_44({
            ...{ 'onClick': {} },
            label: "Predict",
            type: "submit",
            fluid: true,
            disabled: (__VLS_ctx.isPredictButtonDisabled),
        }, ...__VLS_functionalComponentArgsRest(__VLS_44));
        let __VLS_48;
        const __VLS_49 = ({ click: {} },
            { onClick: (__VLS_ctx.onFileSubmit) });
        var __VLS_46;
        var __VLS_47;
    }
}
// @ts-ignore
[isLoading, isManualPredictButtonDisabled, onManualSubmit, predictionText, fileData, isUploadWithErrors, filePredictWithError, predictReadyForDownload, predictReadyForDownload, onSelectFile, onRemoveFile, downloadPredict, isPredictButtonDisabled, onFileSubmit,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
