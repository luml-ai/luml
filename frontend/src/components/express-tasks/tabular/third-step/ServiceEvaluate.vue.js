/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Tasks } from '@/lib/data-processing/interfaces';
import { computed, onBeforeMount, ref } from 'vue';
import { getBarOptions } from '@/lib/apex-charts/apex-charts';
import { table } from 'arquero';
import { useRouter } from 'vue-router';
import DetailedTable from './DetailedTable.vue';
import PredictContent from '@/components/predict/index.vue';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
import { SplitButton } from 'primevue';
import ModelUpload from '@/components/model-upload/ModelUpload.vue';
import { useOrganizationStore } from '@/stores/organization';
import ModelTabularPerformance from '@/components/model/ModelTabularPerformance.vue';
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService';
const props = defineProps();
const router = useRouter();
const organizationStore = useOrganizationStore();
const modelUploadVisible = ref(false);
const EXPORT_ITEMS = [
    {
        label: 'Upload to Registry',
        command: () => {
            modelUploadVisible.value = true;
        },
        disabled: () => !organizationStore.currentOrganization,
    },
    {
        label: 'Download model',
        command: () => {
            onDownloadClick();
        },
    },
];
const isPredictVisible = ref(false);
const detailedView = ref([]);
const featuresData = computed(() => {
    const data = props.features.map((feature) => (feature.scaled_importance * 100).toFixed());
    return [{ data }];
});
const featuresOptions = computed(() => getBarOptions(props.features.map((feature) => {
    const name = feature.feature_name.length > 12
        ? feature.feature_name.slice(0, 10) + '...'
        : feature.feature_name;
    return `${name} (${(feature.scaled_importance * 100).toFixed()}%)`;
})));
const barChartHeight = computed(() => {
    const featuresCount = props.features.length;
    return 45 * featuresCount + 60 + 'px';
});
const taskName = computed(() => props.currentTask === Tasks.TABULAR_CLASSIFICATION ? 'classification' : 'regression');
const producedTag = computed(() => props.currentTask === Tasks.TABULAR_CLASSIFICATION
    ? FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1
    : FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1);
function onDownloadClick() {
    props.downloadModelCallback();
    if (props.currentTask) {
        AnalyticsService.track(AnalyticsTrackKeysEnum.download, { task: taskName.value });
    }
}
const finishConfirm = () => {
    if (props.currentTask) {
        AnalyticsService.track(AnalyticsTrackKeysEnum.finish, { task: taskName.value });
    }
    router.push({ name: 'home' });
};
onBeforeMount(() => {
    detailedView.value = table(props.predictedData).objects();
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
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['body']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-cards']} */ ;
/** @type {__VLS_StyleScopedClasses['info-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    visible: (__VLS_ctx.isPredictVisible),
    modal: true,
    header: "Predict",
    ...{ style: ({ width: '31.25rem' }) },
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.isPredictVisible),
    modal: true,
    header: "Predict",
    ...{ style: ({ width: '31.25rem' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
const __VLS_6 = PredictContent;
// @ts-ignore
const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
    manualFields: (__VLS_ctx.predictionFields),
    modelId: (__VLS_ctx.trainingModelId),
    task: (__VLS_ctx.taskName),
}));
const __VLS_8 = __VLS_7({
    manualFields: (__VLS_ctx.predictionFields),
    modelId: (__VLS_ctx.trainingModelId),
    task: (__VLS_ctx.taskName),
}, ...__VLS_functionalComponentArgsRest(__VLS_7));
// @ts-ignore
[isPredictVisible, predictionFields, trainingModelId, taskName,];
var __VLS_3;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "buttons" },
});
/** @type {__VLS_StyleScopedClasses['buttons']} */ ;
let __VLS_11;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_13 = __VLS_12({
    ...{ 'onClick': {} },
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
let __VLS_16;
const __VLS_17 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.isPredictVisible = true;
            // @ts-ignore
            [isPredictVisible,];
        } });
const { default: __VLS_18 } = __VLS_14.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_19;
/** @ts-ignore @type { | typeof __VLS_components.wandSparkles | typeof __VLS_components.WandSparkles | typeof __VLS_components['wand-sparkles']} */
wandSparkles;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
    width: "14",
    height: "14",
}));
const __VLS_21 = __VLS_20({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
// @ts-ignore
[];
var __VLS_14;
var __VLS_15;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.SplitButton} */
SplitButton;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    label: "export",
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    label: "export",
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
const __VLS_30 = ({ click: {} },
    { onClick: (__VLS_ctx.onDownloadClick) });
var __VLS_27;
var __VLS_28;
let __VLS_31;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    ...{ 'onClick': {} },
}));
const __VLS_33 = __VLS_32({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
let __VLS_36;
const __VLS_37 = ({ click: {} },
    { onClick: (__VLS_ctx.finishConfirm) });
const { default: __VLS_38 } = __VLS_34.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_39;
/** @ts-ignore @type { | typeof __VLS_components.logOut | typeof __VLS_components.LogOut | typeof __VLS_components['log-out']} */
logOut;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
    width: "14",
    height: "14",
}));
const __VLS_41 = __VLS_40({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
// @ts-ignore
[EXPORT_ITEMS, onDownloadClick, finishConfirm,];
var __VLS_34;
var __VLS_35;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
if (__VLS_ctx.currentTask) {
    const __VLS_44 = ModelTabularPerformance || ModelTabularPerformance;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
        totalScore: (__VLS_ctx.totalScore),
        testMetrics: (__VLS_ctx.testMetrics),
        trainingMetrics: (__VLS_ctx.trainingMetrics),
        tag: (__VLS_ctx.producedTag),
        ...{ class: "performance" },
    }));
    const __VLS_46 = __VLS_45({
        totalScore: (__VLS_ctx.totalScore),
        testMetrics: (__VLS_ctx.testMetrics),
        trainingMetrics: (__VLS_ctx.trainingMetrics),
        tag: (__VLS_ctx.producedTag),
        ...{ class: "performance" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    /** @type {__VLS_StyleScopedClasses['performance']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "features card" },
});
/** @type {__VLS_StyleScopedClasses['features']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "card-header" },
});
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
(__VLS_ctx.features.length);
let __VLS_49;
/** @ts-ignore @type { | typeof __VLS_components.info | typeof __VLS_components.Info} */
info;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
    width: "20",
    height: "20",
    ...{ class: "info-icon" },
}));
const __VLS_51 = __VLS_50({
    width: "20",
    height: "20",
    ...{ class: "info-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: (`Understand which features play the biggest role in your model's outcomes to guide further data analysis`) }, null, null);
/** @type {__VLS_StyleScopedClasses['info-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ style: ({ maxWidth: '725px' }) },
});
let __VLS_54;
/** @ts-ignore @type { | typeof __VLS_components.apexchart | typeof __VLS_components.Apexchart} */
apexchart;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
    type: "bar",
    options: (__VLS_ctx.featuresOptions),
    series: (__VLS_ctx.featuresData),
    height: (__VLS_ctx.barChartHeight),
    width: "100%",
    ...{ style: ({ pointerEvents: 'none', margin: '-30px 0' }) },
}));
const __VLS_56 = __VLS_55({
    type: "bar",
    options: (__VLS_ctx.featuresOptions),
    series: (__VLS_ctx.featuresData),
    height: (__VLS_ctx.barChartHeight),
    width: "100%",
    ...{ style: ({ pointerEvents: 'none', margin: '-30px 0' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "detailed card" },
});
/** @type {__VLS_StyleScopedClasses['detailed']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
const __VLS_59 = DetailedTable;
// @ts-ignore
const __VLS_60 = __VLS_asFunctionalComponent1(__VLS_59, new __VLS_59({
    values: (__VLS_ctx.detailedView),
    isTrainMode: (__VLS_ctx.isTrainMode),
}));
const __VLS_61 = __VLS_60({
    values: (__VLS_ctx.detailedView),
    isTrainMode: (__VLS_ctx.isTrainMode),
}, ...__VLS_functionalComponentArgsRest(__VLS_60));
if (__VLS_ctx.modelBlob && __VLS_ctx.currentTask && !!__VLS_ctx.organizationStore.currentOrganization) {
    const __VLS_64 = ModelUpload || ModelUpload;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent1(__VLS_64, new __VLS_64({
        modelBlob: (__VLS_ctx.modelBlob),
        currentTask: (__VLS_ctx.currentTask),
        visible: (__VLS_ctx.modelUploadVisible),
    }));
    const __VLS_66 = __VLS_65({
        modelBlob: (__VLS_ctx.modelBlob),
        currentTask: (__VLS_ctx.currentTask),
        visible: (__VLS_ctx.modelUploadVisible),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
// @ts-ignore
[currentTask, currentTask, currentTask, totalScore, testMetrics, trainingMetrics, producedTag, features, vTooltip, featuresOptions, featuresData, barChartHeight, detailedView, isTrainMode, modelBlob, modelBlob, organizationStore, modelUploadVisible,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
