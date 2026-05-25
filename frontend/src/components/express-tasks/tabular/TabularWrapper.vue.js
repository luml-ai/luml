/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { Tasks } from '@/lib/data-processing/interfaces';
import { useDataTable } from '@/hooks/useDataTable';
import { useModelTraining } from '@/hooks/useModelTraining';
import { classificationResources, regressionResources } from '@/constants/constants';
import Stepper from 'primevue/stepper';
import StepList from 'primevue/steplist';
import StepPanels from 'primevue/steppanels';
import Step from 'primevue/step';
import StepPanel from 'primevue/steppanel';
import UploadData from '../../ui/UploadData.vue';
import ServiceEvaluate from './third-step/ServiceEvaluate.vue';
import TableView from '@/components/table-view/index.vue';
import UiTraining from '@/components/ui/UiTraining.vue';
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm';
import { dashboardFinishConfirmOptions } from '@/lib/primevue/data/confirm';
const { setGuard } = useRouteLeaveConfirm(dashboardFinishConfirmOptions(() => { }));
const props = defineProps();
const tableValidator = (size, columns, rows) => {
    return {
        size: !!(size && size > 50 * 1024 * 1024),
        columns: !!(columns && columns <= 3),
        rows: !!(rows && rows <= 100),
    };
};
const { isTableExist, fileData, uploadDataErrors, isUploadWithErrors, columnsCount, rowsCount, getAllColumnNames, viewValues, getTarget, getGroup, selectedColumns, getFilters, columnTypes, onSelectFile, onRemoveFile, setTarget, changeGroup, setSelectedColumns, downloadCSV, setFilters, getDataForTraining, } = useDataTable(tableValidator);
const { isLoading, startTraining: startModelTraining, isTrainingSuccess, getTotalScore, getTestMetrics, getTrainingMetrics, getTop5Feature, getPredictedData, isTrainMode, trainingModelId, currentTask, modelBlob, downloadModel, } = useModelTraining('tabular');
const currentStep = ref(1);
const sampleFileName = computed(() => props.task === Tasks.TABULAR_CLASSIFICATION ? 'iris.csv' : 'insurance.csv');
const resources = computed(() => props.task === Tasks.TABULAR_CLASSIFICATION ? classificationResources : regressionResources);
const isStepAvailable = computed(() => (id) => {
    if (currentStep.value === 3)
        return;
    if (id === 1)
        return true;
    else if (id === 2)
        return isTableExist.value && !isUploadWithErrors.value;
    else if (id === 3)
        return false;
});
const getPredictionFields = computed(() => {
    const columns = selectedColumns.value.length ? selectedColumns.value : getAllColumnNames.value;
    return columns.filter((column) => column !== getTarget.value);
});
async function startTraining() {
    const data = getDataForTraining();
    const target = getTarget.value;
    const task = props.task;
    await startModelTraining({ data, target, task });
    if (isTrainingSuccess.value) {
        currentStep.value = 3;
    }
}
watch(currentStep, (value) => {
    setGuard(value === 3);
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
/** @type {__VLS_StyleScopedClasses['navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['navigation']} */ ;
/** @type {__VLS_StyleScopedClasses['stepper']} */ ;
/** @type {__VLS_StyleScopedClasses['navigation']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Stepper | typeof __VLS_components.Stepper} */
Stepper;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:value': {} },
    value: (__VLS_ctx.currentStep),
    ...{ class: "stepper" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:value': {} },
    value: (__VLS_ctx.currentStep),
    ...{ class: "stepper" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:value': {} },
    { 'onUpdate:value': ((step) => (__VLS_ctx.currentStep = step)) });
/** @type {__VLS_StyleScopedClasses['stepper']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.StepList | typeof __VLS_components.StepList} */
StepList;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const { default: __VLS_13 } = __VLS_11.slots;
for (const [step] of __VLS_vFor((__VLS_ctx.steps))) {
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Step | typeof __VLS_components.Step} */
    Step;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        key: (step.id),
        value: (step.id),
        disabled: (!__VLS_ctx.isStepAvailable(step.id)),
    }));
    const __VLS_16 = __VLS_15({
        key: (step.id),
        value: (step.id),
        disabled: (!__VLS_ctx.isStepAvailable(step.id)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    const { default: __VLS_19 } = __VLS_17.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "step-label" },
    });
    /** @type {__VLS_StyleScopedClasses['step-label']} */ ;
    (step.text);
    // @ts-ignore
    [currentStep, currentStep, steps, isStepAvailable,];
    var __VLS_17;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_11;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.StepPanels | typeof __VLS_components.StepPanels} */
StepPanels;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    ...{ class: "steppanels" },
}));
const __VLS_22 = __VLS_21({
    ...{ class: "steppanels" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
/** @type {__VLS_StyleScopedClasses['steppanels']} */ ;
const { default: __VLS_25 } = __VLS_23.slots;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.StepPanel | typeof __VLS_components.StepPanel} */
StepPanel;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    value: (1),
}));
const __VLS_28 = __VLS_27({
    value: (1),
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
{
    const { default: __VLS_31 } = __VLS_29.slots;
    const [{ activateCallback }] = __VLS_vSlot(__VLS_31);
    if (__VLS_ctx.currentStep === 1) {
        const __VLS_32 = UploadData;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
            ...{ 'onSelectFile': {} },
            ...{ 'onRemoveFile': {} },
            errors: (__VLS_ctx.uploadDataErrors),
            isTableExist: (__VLS_ctx.isTableExist),
            file: (__VLS_ctx.fileData),
            minColumnsCount: (3),
            minRowsCount: (100),
            resources: (__VLS_ctx.resources),
            sampleFileName: (__VLS_ctx.sampleFileName),
        }));
        const __VLS_34 = __VLS_33({
            ...{ 'onSelectFile': {} },
            ...{ 'onRemoveFile': {} },
            errors: (__VLS_ctx.uploadDataErrors),
            isTableExist: (__VLS_ctx.isTableExist),
            file: (__VLS_ctx.fileData),
            minColumnsCount: (3),
            minRowsCount: (100),
            resources: (__VLS_ctx.resources),
            sampleFileName: (__VLS_ctx.sampleFileName),
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        let __VLS_37;
        const __VLS_38 = ({ selectFile: {} },
            { onSelectFile: (__VLS_ctx.onSelectFile) });
        const __VLS_39 = ({ removeFile: {} },
            { onRemoveFile: (__VLS_ctx.onRemoveFile) });
        var __VLS_35;
        var __VLS_36;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "navigation" },
    });
    /** @type {__VLS_StyleScopedClasses['navigation']} */ ;
    let __VLS_40;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        ...{ 'onClick': {} },
        label: "Back",
        severity: "secondary",
    }));
    const __VLS_42 = __VLS_41({
        ...{ 'onClick': {} },
        label: "Back",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    let __VLS_45;
    const __VLS_46 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.$router.push({ name: 'home' });
                // @ts-ignore
                [currentStep, uploadDataErrors, isTableExist, fileData, resources, sampleFileName, onSelectFile, onRemoveFile, $router,];
            } });
    var __VLS_43;
    var __VLS_44;
    let __VLS_47;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
        ...{ 'onClick': {} },
        disabled: (!__VLS_ctx.isStepAvailable(2)),
    }));
    const __VLS_49 = __VLS_48({
        ...{ 'onClick': {} },
        disabled: (!__VLS_ctx.isStepAvailable(2)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_48));
    let __VLS_52;
    const __VLS_53 = ({ click: {} },
        { onClick: (...[$event]) => {
                activateCallback(2);
                // @ts-ignore
                [isStepAvailable,];
            } });
    const { default: __VLS_54 } = __VLS_50.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ style: {} },
    });
    let __VLS_55;
    /** @ts-ignore @type { | typeof __VLS_components.arrowRight | typeof __VLS_components.ArrowRight | typeof __VLS_components['arrow-right']} */
    arrowRight;
    // @ts-ignore
    const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
        width: "14",
        height: "14",
    }));
    const __VLS_57 = __VLS_56({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_56));
    // @ts-ignore
    [];
    var __VLS_50;
    var __VLS_51;
    // @ts-ignore
    [];
    __VLS_29.slots['' /* empty slot name completion */];
}
var __VLS_29;
let __VLS_60;
/** @ts-ignore @type { | typeof __VLS_components.StepPanel | typeof __VLS_components.StepPanel} */
StepPanel;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
    value: (2),
}));
const __VLS_62 = __VLS_61({
    value: (2),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
{
    const { default: __VLS_65 } = __VLS_63.slots;
    const [{ activateCallback }] = __VLS_vSlot(__VLS_65);
    if (__VLS_ctx.currentStep === 2 && __VLS_ctx.columnsCount && __VLS_ctx.rowsCount && __VLS_ctx.viewValues) {
        const __VLS_66 = TableView;
        // @ts-ignore
        const __VLS_67 = __VLS_asFunctionalComponent1(__VLS_66, new __VLS_66({
            ...{ 'onSetTarget': {} },
            ...{ 'onChangeGroup': {} },
            ...{ 'onEdit': {} },
            ...{ 'onChangeFilters': {} },
            columnsCount: (__VLS_ctx.columnsCount),
            rowsCount: (__VLS_ctx.rowsCount),
            allColumns: (__VLS_ctx.getAllColumnNames),
            value: (__VLS_ctx.viewValues),
            target: (__VLS_ctx.getTarget),
            group: (__VLS_ctx.getGroup),
            selectedColumns: (__VLS_ctx.selectedColumns),
            exportCallback: (__VLS_ctx.downloadCSV),
            filters: (__VLS_ctx.getFilters),
            columnTypes: (__VLS_ctx.columnTypes),
            showColumnHeaderMenu: true,
        }));
        const __VLS_68 = __VLS_67({
            ...{ 'onSetTarget': {} },
            ...{ 'onChangeGroup': {} },
            ...{ 'onEdit': {} },
            ...{ 'onChangeFilters': {} },
            columnsCount: (__VLS_ctx.columnsCount),
            rowsCount: (__VLS_ctx.rowsCount),
            allColumns: (__VLS_ctx.getAllColumnNames),
            value: (__VLS_ctx.viewValues),
            target: (__VLS_ctx.getTarget),
            group: (__VLS_ctx.getGroup),
            selectedColumns: (__VLS_ctx.selectedColumns),
            exportCallback: (__VLS_ctx.downloadCSV),
            filters: (__VLS_ctx.getFilters),
            columnTypes: (__VLS_ctx.columnTypes),
            showColumnHeaderMenu: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_67));
        let __VLS_71;
        const __VLS_72 = ({ setTarget: {} },
            { onSetTarget: (__VLS_ctx.setTarget) });
        const __VLS_73 = ({ changeGroup: {} },
            { onChangeGroup: (__VLS_ctx.changeGroup) });
        const __VLS_74 = ({ edit: {} },
            { onEdit: (__VLS_ctx.setSelectedColumns) });
        const __VLS_75 = ({ changeFilters: {} },
            { onChangeFilters: (__VLS_ctx.setFilters) });
        var __VLS_69;
        var __VLS_70;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "navigation" },
    });
    /** @type {__VLS_StyleScopedClasses['navigation']} */ ;
    let __VLS_76;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent1(__VLS_76, new __VLS_76({
        ...{ 'onClick': {} },
        label: "Back",
        severity: "secondary",
    }));
    const __VLS_78 = __VLS_77({
        ...{ 'onClick': {} },
        label: "Back",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    let __VLS_81;
    const __VLS_82 = ({ click: {} },
        { onClick: (...[$event]) => {
                activateCallback(1);
                // @ts-ignore
                [currentStep, columnsCount, columnsCount, rowsCount, rowsCount, viewValues, viewValues, getAllColumnNames, getTarget, getGroup, selectedColumns, downloadCSV, getFilters, columnTypes, setTarget, changeGroup, setSelectedColumns, setFilters,];
            } });
    var __VLS_79;
    var __VLS_80;
    let __VLS_83;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_84 = __VLS_asFunctionalComponent1(__VLS_83, new __VLS_83({
        ...{ 'onClick': {} },
    }));
    const __VLS_85 = __VLS_84({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_84));
    let __VLS_88;
    const __VLS_89 = ({ click: {} },
        { onClick: (__VLS_ctx.startTraining) });
    const { default: __VLS_90 } = __VLS_86.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ style: {} },
    });
    let __VLS_91;
    /** @ts-ignore @type { | typeof __VLS_components.arrowRight | typeof __VLS_components.ArrowRight | typeof __VLS_components['arrow-right']} */
    arrowRight;
    // @ts-ignore
    const __VLS_92 = __VLS_asFunctionalComponent1(__VLS_91, new __VLS_91({
        width: "14",
        height: "14",
    }));
    const __VLS_93 = __VLS_92({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_92));
    // @ts-ignore
    [startTraining,];
    var __VLS_86;
    var __VLS_87;
    // @ts-ignore
    [];
    __VLS_63.slots['' /* empty slot name completion */];
}
var __VLS_63;
let __VLS_96;
/** @ts-ignore @type { | typeof __VLS_components.StepPanel | typeof __VLS_components.StepPanel} */
StepPanel;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent1(__VLS_96, new __VLS_96({
    value: (3),
}));
const __VLS_98 = __VLS_97({
    value: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
const { default: __VLS_101 } = __VLS_99.slots;
if (__VLS_ctx.currentStep === 3 && __VLS_ctx.trainingModelId) {
    const __VLS_102 = ServiceEvaluate;
    // @ts-ignore
    const __VLS_103 = __VLS_asFunctionalComponent1(__VLS_102, new __VLS_102({
        predictionFields: (__VLS_ctx.getPredictionFields),
        totalScore: (__VLS_ctx.getTotalScore),
        testMetrics: (__VLS_ctx.getTestMetrics),
        trainingMetrics: (__VLS_ctx.getTrainingMetrics),
        features: (__VLS_ctx.getTop5Feature),
        predictedData: __VLS_ctx.getPredictedData,
        isTrainMode: (__VLS_ctx.isTrainMode),
        downloadModelCallback: (__VLS_ctx.downloadModel),
        trainingModelId: (__VLS_ctx.trainingModelId),
        currentTask: (__VLS_ctx.currentTask),
        modelBlob: (__VLS_ctx.modelBlob),
    }));
    const __VLS_104 = __VLS_103({
        predictionFields: (__VLS_ctx.getPredictionFields),
        totalScore: (__VLS_ctx.getTotalScore),
        testMetrics: (__VLS_ctx.getTestMetrics),
        trainingMetrics: (__VLS_ctx.getTrainingMetrics),
        features: (__VLS_ctx.getTop5Feature),
        predictedData: __VLS_ctx.getPredictedData,
        isTrainMode: (__VLS_ctx.isTrainMode),
        downloadModelCallback: (__VLS_ctx.downloadModel),
        trainingModelId: (__VLS_ctx.trainingModelId),
        currentTask: (__VLS_ctx.currentTask),
        modelBlob: (__VLS_ctx.modelBlob),
    }, ...__VLS_functionalComponentArgsRest(__VLS_103));
}
// @ts-ignore
[currentStep, trainingModelId, trainingModelId, getPredictionFields, getTotalScore, getTestMetrics, getTrainingMetrics, getTop5Feature, getPredictedData, isTrainMode, downloadModel, currentTask, modelBlob,];
var __VLS_99;
// @ts-ignore
[];
var __VLS_23;
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
const __VLS_107 = UiTraining;
// @ts-ignore
const __VLS_108 = __VLS_asFunctionalComponent1(__VLS_107, new __VLS_107({
    modelValue: (__VLS_ctx.isLoading),
    time: (8),
}));
const __VLS_109 = __VLS_108({
    modelValue: (__VLS_ctx.isLoading),
    time: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_108));
// @ts-ignore
[isLoading,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
