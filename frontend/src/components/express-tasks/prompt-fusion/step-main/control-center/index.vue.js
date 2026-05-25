/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, onBeforeUnmount, ref } from 'vue';
import ProvidersComponent from '@/components/express-tasks/prompt-fusion/step-main/control-center/providers/index.vue';
import OptimizationComponent from '@/components/express-tasks/prompt-fusion/step-main/control-center/optimization/index.vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
import ModelUpload from '@/components/model-upload/ModelUpload.vue';
import { SplitButton } from 'primevue';
import { useOrganizationStore } from '@/stores/organization';
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
const organizationStore = useOrganizationStore();
const optimizationDisabled = ref(true);
const isPredictAvailable = ref(false);
const modelUploadVisible = ref(false);
function setOptimizationState() {
    promptFusionService.changeAvailableModels();
    optimizationDisabled.value = !promptFusionService.getConnectedProviders().length;
}
function onChangeModelId(modelId) {
    isPredictAvailable.value = !!modelId;
}
function onDownloadClick() {
    promptFusionService.downloadModel();
    AnalyticsService.track(AnalyticsTrackKeysEnum.download, { task: 'prompt_optimization' });
}
onBeforeMount(() => {
    setOptimizationState();
    promptFusionService.on('CLOSE_PROVIDER_SETTINGS', setOptimizationState);
    promptFusionService.on('CHANGE_MODEL_ID', onChangeModelId);
});
onBeforeUnmount(() => {
    promptFusionService.off('CLOSE_PROVIDER_SETTINGS', setOptimizationState);
    promptFusionService.off('CHANGE_MODEL_ID', onChangeModelId);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
const __VLS_0 = ProvidersComponent;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_5 = OptimizationComponent;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    disabled: (__VLS_ctx.optimizationDisabled),
}));
const __VLS_7 = __VLS_6({
    disabled: (__VLS_ctx.optimizationDisabled),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.SplitButton | typeof __VLS_components.SplitButton} */
SplitButton;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    ...{ 'onClick': {} },
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
    disabled: (!__VLS_ctx.isPredictAvailable),
}));
const __VLS_12 = __VLS_11({
    ...{ 'onClick': {} },
    severity: "secondary",
    model: (__VLS_ctx.EXPORT_ITEMS),
    disabled: (!__VLS_ctx.isPredictAvailable),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
let __VLS_15;
const __VLS_16 = ({ click: {} },
    { onClick: (__VLS_ctx.onDownloadClick) });
const { default: __VLS_17 } = __VLS_13.slots;
{
    const { icon: __VLS_18 } = __VLS_13.slots;
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.cloudDownload | typeof __VLS_components.CloudDownload | typeof __VLS_components['cloud-download']} */
    cloudDownload;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        size: (14),
    }));
    const __VLS_21 = __VLS_20({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    // @ts-ignore
    [optimizationDisabled, EXPORT_ITEMS, isPredictAvailable, onDownloadClick,];
}
// @ts-ignore
[];
var __VLS_13;
var __VLS_14;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    severity: "secondary",
    disabled: (!__VLS_ctx.isPredictAvailable),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    severity: "secondary",
    disabled: (!__VLS_ctx.isPredictAvailable),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
const __VLS_30 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.promptFusionService.togglePredict();
            // @ts-ignore
            [isPredictAvailable, promptFusionService,];
        } });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { bottom: true, }, value: ('Run the model') }, null, null);
const { default: __VLS_31 } = __VLS_27.slots;
{
    const { icon: __VLS_32 } = __VLS_27.slots;
    let __VLS_33;
    /** @ts-ignore @type { | typeof __VLS_components.play | typeof __VLS_components.Play} */
    play;
    // @ts-ignore
    const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
        size: (14),
    }));
    const __VLS_35 = __VLS_34({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_34));
    // @ts-ignore
    [vTooltip,];
}
// @ts-ignore
[];
var __VLS_27;
var __VLS_28;
if (__VLS_ctx.promptFusionService.modelBlob && !!__VLS_ctx.organizationStore.currentOrganization) {
    const __VLS_38 = ModelUpload || ModelUpload;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
        visible: (__VLS_ctx.modelUploadVisible),
        currentTask: "prompt_optimization",
        modelBlob: (__VLS_ctx.promptFusionService.modelBlob),
    }));
    const __VLS_40 = __VLS_39({
        visible: (__VLS_ctx.modelUploadVisible),
        currentTask: "prompt_optimization",
        modelBlob: (__VLS_ctx.promptFusionService.modelBlob),
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
}
// @ts-ignore
[promptFusionService, promptFusionService, organizationStore, modelUploadVisible,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
