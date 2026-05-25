/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onUnmounted, ref } from 'vue';
import UploadData from '@/components/runtime/UploadData.vue';
import RuntimeDashboard from '@/components/runtime/dashboard/RuntimeDashboard.vue';
import { useFnnxModel } from '@/hooks/useFnnxModel';
import { leavePageConfirmOptions } from '@/lib/primevue/data/confirm';
import { useConfirm } from 'primevue/useconfirm';
const confirm = useConfirm();
const { currentTag, getModel, modelId, createModelFromFile, removeModel, deinit } = useFnnxModel();
const currentStep = ref(1);
function exit() {
    confirm.require(leavePageConfirmOptions(() => {
        currentStep.value = 1;
    }));
}
onUnmounted(() => {
    deinit();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "runtime" },
});
/** @type {__VLS_StyleScopedClasses['runtime']} */ ;
if (__VLS_ctx.currentStep === 1) {
    const __VLS_0 = UploadData;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onContinue': {} },
        removeCallback: (__VLS_ctx.removeModel),
        uploadCallback: (__VLS_ctx.createModelFromFile),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onContinue': {} },
        removeCallback: (__VLS_ctx.removeModel),
        uploadCallback: (__VLS_ctx.createModelFromFile),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ continue: {} },
        { onContinue: (...[$event]) => {
                if (!(__VLS_ctx.currentStep === 1))
                    return;
                __VLS_ctx.currentStep = 2;
                // @ts-ignore
                [currentStep, currentStep, removeModel, createModelFromFile,];
            } });
    var __VLS_3;
    var __VLS_4;
}
else if (__VLS_ctx.getModel && __VLS_ctx.currentTag) {
    const __VLS_7 = RuntimeDashboard;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        ...{ 'onExit': {} },
        currentTag: (__VLS_ctx.currentTag),
        model: __VLS_ctx.getModel,
        modelId: (__VLS_ctx.modelId),
    }));
    const __VLS_9 = __VLS_8({
        ...{ 'onExit': {} },
        currentTag: (__VLS_ctx.currentTag),
        model: __VLS_ctx.getModel,
        modelId: (__VLS_ctx.modelId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    let __VLS_12;
    const __VLS_13 = ({ exit: {} },
        { onExit: (__VLS_ctx.exit) });
    var __VLS_10;
    var __VLS_11;
}
// @ts-ignore
[getModel, getModel, currentTag, currentTag, modelId, exit,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
