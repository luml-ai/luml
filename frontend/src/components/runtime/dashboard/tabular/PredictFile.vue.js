/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import FileInput from '@/components/ui/FileInput.vue';
import { useDataTable } from '@/hooks/useDataTable';
import { convertObjectToCsvBlob } from '@/helpers/helpers';
import { predictErrorToast } from '@/lib/primevue/data/toasts';
import { useToast } from 'primevue';
const toast = useToast();
const props = defineProps();
const tableValidator = () => ({
    size: false,
    columns: false,
    rows: false,
});
const { isUploadWithErrors, fileData, onSelectFile, getDataForTraining, onRemoveFile } = useDataTable(tableValidator);
const filePredictWithError = ref(false);
const isLoading = ref(false);
const downloadPredictBlob = ref(null);
const isPredictReadyForDownload = computed(() => !!downloadPredictBlob.value);
const isPredictButtonDisabled = computed(() => !fileData.value.name || !isUploadWithErrors || isLoading.value);
async function submit() {
    isLoading.value = true;
    const data = getDataForTraining();
    try {
        const result = await props.predictCallback(data);
        downloadPredictBlob.value = convertObjectToCsvBlob(result);
    }
    catch (e) {
        toast.add(predictErrorToast(e));
        filePredictWithError.value = true;
    }
    finally {
        isLoading.value = false;
    }
}
function downloadPredict() {
    if (!downloadPredictBlob.value)
        return;
    const url = URL.createObjectURL(downloadPredictBlob.value);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dfs-predictions';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
const __VLS_0 = FileInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "predict",
    file: (__VLS_ctx.fileData),
    error: (__VLS_ctx.isUploadWithErrors || __VLS_ctx.filePredictWithError),
    loading: (__VLS_ctx.isLoading),
    loadingMessage: "Loading prediction...",
    successMessageOnly: (__VLS_ctx.isPredictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''),
    successRemoveText: "Upload new dataset",
    accept: (['text/csv']),
    acceptText: "Supports CSV file format",
    uploadText: "upload CSV",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "predict",
    file: (__VLS_ctx.fileData),
    error: (__VLS_ctx.isUploadWithErrors || __VLS_ctx.filePredictWithError),
    loading: (__VLS_ctx.isLoading),
    loadingMessage: "Loading prediction...",
    successMessageOnly: (__VLS_ctx.isPredictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''),
    successRemoveText: "Upload new dataset",
    accept: (['text/csv']),
    acceptText: "Supports CSV file format",
    uploadText: "upload CSV",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ selectFile: {} },
    { onSelectFile: (__VLS_ctx.onSelectFile) });
const __VLS_7 = ({ removeFile: {} },
    { onRemoveFile: (__VLS_ctx.onRemoveFile) });
var __VLS_3;
var __VLS_4;
if (__VLS_ctx.isPredictReadyForDownload) {
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        label: "Download",
        type: "submit",
        fluid: true,
        rounded: true,
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        label: "Download",
        type: "submit",
        fluid: true,
        rounded: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ click: {} },
        { onClick: (__VLS_ctx.downloadPredict) });
    var __VLS_11;
    var __VLS_12;
}
else {
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        ...{ 'onClick': {} },
        label: "Predict",
        type: "submit",
        fluid: true,
        disabled: (__VLS_ctx.isPredictButtonDisabled),
        rounded: true,
    }));
    const __VLS_17 = __VLS_16({
        ...{ 'onClick': {} },
        label: "Predict",
        type: "submit",
        fluid: true,
        disabled: (__VLS_ctx.isPredictButtonDisabled),
        rounded: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    let __VLS_20;
    const __VLS_21 = ({ click: {} },
        { onClick: (__VLS_ctx.submit) });
    var __VLS_18;
    var __VLS_19;
}
// @ts-ignore
[fileData, isUploadWithErrors, filePredictWithError, isLoading, isPredictReadyForDownload, isPredictReadyForDownload, onSelectFile, onRemoveFile, downloadPredict, isPredictButtonDisabled, submit,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
