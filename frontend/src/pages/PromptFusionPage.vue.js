/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { nextTick, onBeforeMount, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDataTable } from '@/hooks/useDataTable';
import { promptFusionResources } from '@/constants/constants';
import { getInitialNodes, getSample } from '@/constants/prompt-fusion';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { useVueFlow } from '@vue-flow/core';
import FirstStepNavigation from '@/components/express-tasks/prompt-fusion/step-upload/Navigation.vue';
import TableView from '@/components/table-view/index.vue';
import StepEdit from '@/components/express-tasks/prompt-fusion/step-edit/StepEdit.vue';
import StepMain from '@/components/express-tasks/prompt-fusion/step-main/index.vue';
import UploadData from '@/components/ui/UploadData.vue';
const { $reset, addEdges, addNodes, toObject } = useVueFlow();
const tableValidator = (size, columns, rows) => {
    return {
        size: !!(size && size > 50 * 1024 * 1024),
        columns: !!(columns && columns <= 1),
        rows: !!(rows && rows <= 10),
    };
};
const route = useRoute();
const router = useRouter();
const { isTableExist, fileData, uploadDataErrors, isUploadWithErrors, columnsCount, rowsCount, getAllColumnNames, viewValues, selectedColumns, columnTypes, inputsOutputsColumns, getInputsColumns, getOutputsColumns, onSelectFile, onRemoveFile, setSelectedColumns, downloadCSV, getDataForTraining, } = useDataTable(tableValidator);
const step = ref();
const initialNodes = ref([]);
const isSampleDataset = ref(false);
function backFromMain() {
    if (route.params.mode === 'data-driven')
        step.value = 2;
    else
        router.back();
}
function goToMainStep() {
    promptFusionService.saveTrainingData(getDataForTraining(), getInputsColumns.value, getOutputsColumns.value);
    step.value = 3;
    nextTick(() => {
        if (isSampleDataset.value) {
            const sample = getSample(getInputsColumns.value, getOutputsColumns.value);
            addNodes(sample.nodes);
            addEdges(sample.edges);
        }
        else {
            addNodes(getInitialNodes());
        }
    });
}
function selectFile(file) {
    onSelectFile(file);
    isSampleDataset.value = file.name === 'formal-phrases.csv';
}
onBeforeMount(() => {
    step.value = route.params.mode === 'data-driven' ? 1 : 3;
});
onMounted(() => {
    if (step.value === 3) {
        addNodes(getInitialNodes());
    }
});
onBeforeUnmount(() => {
    $reset();
    promptFusionService.resetState();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "prompt-fusion-page" },
});
/** @type {__VLS_StyleScopedClasses['prompt-fusion-page']} */ ;
if (__VLS_ctx.step === 1) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    const __VLS_0 = UploadData;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onSelectFile': {} },
        ...{ 'onRemoveFile': {} },
        errors: (__VLS_ctx.uploadDataErrors),
        isTableExist: (__VLS_ctx.isTableExist),
        file: (__VLS_ctx.fileData),
        minColumnsCount: (2),
        minRowsCount: (10),
        resources: (__VLS_ctx.promptFusionResources),
        sampleFileName: "formal-phrases.csv",
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onSelectFile': {} },
        ...{ 'onRemoveFile': {} },
        errors: (__VLS_ctx.uploadDataErrors),
        isTableExist: (__VLS_ctx.isTableExist),
        file: (__VLS_ctx.fileData),
        minColumnsCount: (2),
        minRowsCount: (10),
        resources: (__VLS_ctx.promptFusionResources),
        sampleFileName: "formal-phrases.csv",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ selectFile: {} },
        { onSelectFile: (__VLS_ctx.selectFile) });
    const __VLS_7 = ({ removeFile: {} },
        { onRemoveFile: (__VLS_ctx.onRemoveFile) });
    var __VLS_3;
    var __VLS_4;
    const __VLS_8 = FirstStepNavigation;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onContinue': {} },
        isNextStepAvailable: (!!__VLS_ctx.fileData.name && !__VLS_ctx.isUploadWithErrors),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onContinue': {} },
        isNextStepAvailable: (!!__VLS_ctx.fileData.name && !__VLS_ctx.isUploadWithErrors),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ continue: {} },
        { onContinue: (...[$event]) => {
                if (!(__VLS_ctx.step === 1))
                    return;
                __VLS_ctx.step = 2;
                // @ts-ignore
                [step, step, uploadDataErrors, isTableExist, fileData, fileData, promptFusionResources, selectFile, onRemoveFile, isUploadWithErrors,];
            } });
    var __VLS_11;
    var __VLS_12;
}
else if (__VLS_ctx.step === 2 && __VLS_ctx.columnsCount && __VLS_ctx.rowsCount && __VLS_ctx.viewValues) {
    const __VLS_15 = StepEdit || StepEdit;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        ...{ 'onBack': {} },
        ...{ 'onContinue': {} },
    }));
    const __VLS_17 = __VLS_16({
        ...{ 'onBack': {} },
        ...{ 'onContinue': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    let __VLS_20;
    const __VLS_21 = ({ back: {} },
        { onBack: (...[$event]) => {
                if (!!(__VLS_ctx.step === 1))
                    return;
                if (!(__VLS_ctx.step === 2 && __VLS_ctx.columnsCount && __VLS_ctx.rowsCount && __VLS_ctx.viewValues))
                    return;
                __VLS_ctx.step = 1;
                // @ts-ignore
                [step, step, columnsCount, rowsCount, viewValues,];
            } });
    const __VLS_22 = ({ continue: {} },
        { onContinue: (__VLS_ctx.goToMainStep) });
    const { default: __VLS_23 } = __VLS_18.slots;
    const __VLS_24 = TableView;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
        ...{ 'onEdit': {} },
        columnsCount: (__VLS_ctx.columnsCount),
        rowsCount: (__VLS_ctx.rowsCount),
        allColumns: (__VLS_ctx.getAllColumnNames),
        value: (__VLS_ctx.viewValues),
        selectedColumns: (__VLS_ctx.selectedColumns),
        exportCallback: (__VLS_ctx.downloadCSV),
        columnTypes: (__VLS_ctx.columnTypes),
        inputsOutputsColumns: (__VLS_ctx.inputsOutputsColumns),
        showColumnHeaderMenu: true,
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onEdit': {} },
        columnsCount: (__VLS_ctx.columnsCount),
        rowsCount: (__VLS_ctx.rowsCount),
        allColumns: (__VLS_ctx.getAllColumnNames),
        value: (__VLS_ctx.viewValues),
        selectedColumns: (__VLS_ctx.selectedColumns),
        exportCallback: (__VLS_ctx.downloadCSV),
        columnTypes: (__VLS_ctx.columnTypes),
        inputsOutputsColumns: (__VLS_ctx.inputsOutputsColumns),
        showColumnHeaderMenu: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_29;
    const __VLS_30 = ({ edit: {} },
        { onEdit: (__VLS_ctx.setSelectedColumns) });
    var __VLS_27;
    var __VLS_28;
    // @ts-ignore
    [columnsCount, rowsCount, viewValues, goToMainStep, getAllColumnNames, selectedColumns, downloadCSV, columnTypes, inputsOutputsColumns, setSelectedColumns,];
    var __VLS_18;
    var __VLS_19;
}
else if (__VLS_ctx.step === 3) {
    const __VLS_31 = StepMain;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        ...{ 'onGoBack': {} },
        initialNodes: (__VLS_ctx.initialNodes),
    }));
    const __VLS_33 = __VLS_32({
        ...{ 'onGoBack': {} },
        initialNodes: (__VLS_ctx.initialNodes),
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    let __VLS_36;
    const __VLS_37 = ({ goBack: {} },
        { onGoBack: (__VLS_ctx.backFromMain) });
    var __VLS_34;
    var __VLS_35;
}
// @ts-ignore
[step, initialNodes, backFromMain,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
