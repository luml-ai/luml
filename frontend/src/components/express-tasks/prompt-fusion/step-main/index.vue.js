/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, onBeforeUnmount, ref } from 'vue';
import { useVueFlow } from '@vue-flow/core';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker';
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm';
import { leavePageConfirmOptions } from '@/lib/primevue/data/confirm';
import PresentationArea from '@/components/express-tasks/prompt-fusion/step-main/PresentationArea.vue';
import Sidebar from '@/components/express-tasks/prompt-fusion/step-main/sidebar/index.vue';
import Navigation from '@/components/express-tasks/prompt-fusion/step-main/Navigation.vue';
import Toolbar from '@/components/express-tasks/prompt-fusion/step-main/Toolbar.vue';
import ControlCenter from '@/components/express-tasks/prompt-fusion/step-main/control-center/index.vue';
import UiTraining from '@/components/ui/UiTraining.vue';
import PromptFusionPredict from './predict/PromptFusionPredict.vue';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
const { onNodeClick, onPaneClick } = useVueFlow();
const { setGuard } = useRouteLeaveConfirm(leavePageConfirmOptions(() => { }));
const activeNode = ref(null);
const isTrainingActive = ref(false);
function closeSidebar() {
    activeNode.value = null;
}
async function cancelTraining() {
    DataProcessingWorker.interrupt();
    promptFusionService.endTraining();
}
function onChangeTrainingState(value) {
    isTrainingActive.value = value;
}
onNodeClick(({ node }) => {
    activeNode.value = node;
});
onPaneClick(() => {
    activeNode.value = null;
});
onBeforeMount(() => {
    promptFusionService.on('CHANGE_TRAINING_STATE', onChangeTrainingState);
    setGuard(true);
});
onBeforeUnmount(() => {
    promptFusionService.off('CHANGE_TRAINING_STATE', onChangeTrainingState);
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
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
const __VLS_0 = PresentationArea;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    initialNodes: (__VLS_ctx.initialNodes),
}));
const __VLS_2 = __VLS_1({
    initialNodes: (__VLS_ctx.initialNodes),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
const { default: __VLS_10 } = __VLS_8.slots;
if (__VLS_ctx.activeNode) {
    const __VLS_11 = Sidebar;
    // @ts-ignore
    const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
        ...{ 'onClose': {} },
        data: (__VLS_ctx.activeNode.data),
        ...{ class: "sidebar" },
    }));
    const __VLS_13 = __VLS_12({
        ...{ 'onClose': {} },
        data: (__VLS_ctx.activeNode.data),
        ...{ class: "sidebar" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_12));
    let __VLS_16;
    const __VLS_17 = ({ close: {} },
        { onClose: (__VLS_ctx.closeSidebar) });
    /** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
    var __VLS_14;
    var __VLS_15;
}
// @ts-ignore
[initialNodes, activeNode, activeNode, closeSidebar,];
var __VLS_8;
const __VLS_18 = ControlCenter;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({}));
const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
const __VLS_23 = Navigation;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    ...{ 'onGoBack': {} },
}));
const __VLS_25 = __VLS_24({
    ...{ 'onGoBack': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
let __VLS_28;
const __VLS_29 = ({ goBack: {} },
    { onGoBack: (...[$event]) => {
            __VLS_ctx.$emit('goBack');
            // @ts-ignore
            [$emit,];
        } });
var __VLS_26;
var __VLS_27;
const __VLS_30 = Toolbar;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({}));
const __VLS_32 = __VLS_31({}, ...__VLS_functionalComponentArgsRest(__VLS_31));
const __VLS_35 = UiTraining;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
    ...{ 'onCancel': {} },
    modelValue: (__VLS_ctx.isTrainingActive),
    time: (8),
    isCancelAvailable: (true),
}));
const __VLS_37 = __VLS_36({
    ...{ 'onCancel': {} },
    modelValue: (__VLS_ctx.isTrainingActive),
    time: (8),
    isCancelAvailable: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
let __VLS_40;
const __VLS_41 = ({ cancel: {} },
    { onCancel: (__VLS_ctx.cancelTraining) });
var __VLS_38;
var __VLS_39;
const __VLS_42 = PromptFusionPredict;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({}));
const __VLS_44 = __VLS_43({}, ...__VLS_functionalComponentArgsRest(__VLS_43));
// @ts-ignore
[isTrainingActive, cancelTraining,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
