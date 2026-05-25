/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import { EvaluationModesEnum, ModelTypeEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { useConfirm, useToast } from 'primevue';
import { runOptimizationConfirmOptions } from '@/lib/primevue/data/confirm';
import { simpleSuccessToast, trainingErrorToast } from '@/lib/primevue/data/toasts';
import { useVueFlow } from '@vue-flow/core';
import CustomTextarea from '@/components/ui/CustomTextarea.vue';
import ModelSelect from './ModelSelect.vue';
import EvaluationMetrics from './EvaluationMetrics.vue';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
const confirm = useConfirm();
const toast = useToast();
const { toObject } = useVueFlow();
const __VLS_props = defineProps();
const mainButton = ref();
const visible = ref(false);
const description = ref(promptFusionService.taskDescription);
const helpLink = computed(() => `${import.meta.env.VITE_DOCS_URL}/task-guides/prompt-optimization`);
function onChangeOptimizationState(isOpen) {
    visible.value = isOpen;
}
function onRunOptimizationClick() {
    const vueFlowObject = toObject();
    try {
        promptFusionService.prepareData(vueFlowObject);
        promptFusionService.checkIsOptimizationAvailable();
        confirm.require(runOptimizationConfirmOptions(runOptimization));
    }
    catch (e) {
        const error = e;
        promptFusionService.endTraining();
        toast.add(trainingErrorToast(error.message));
    }
}
async function runOptimization() {
    const teacher_model = promptFusionService.teacherModel;
    const student_model = promptFusionService.studentModel;
    let evaluation_metrics = '';
    switch (promptFusionService.evaluationMode) {
        case EvaluationModesEnum.exactMatch:
            evaluation_metrics = 'exact_match';
        case EvaluationModesEnum.llmBased:
            evaluation_metrics = 'llm_based';
        default:
            evaluation_metrics = 'none';
    }
    AnalyticsService.track(AnalyticsTrackKeysEnum.run_optimization, {
        task: 'prompt_optimization',
        teacher_model,
        student_model,
        evaluation_metrics,
    });
    try {
        await promptFusionService.runOptimization();
        toast.add(simpleSuccessToast('Your model is successfully trained'));
    }
    catch (e) {
        toast.add(trainingErrorToast(e));
    }
}
watch(description, (val) => {
    promptFusionService.taskDescription = val;
});
onBeforeMount(() => {
    promptFusionService.on('CHANGE_OPTIMIZATION_STATE', onChangeOptimizationState);
});
onBeforeUnmount(() => {
    promptFusionService.off('CHANGE_OPTIMIZATION_STATE', onChangeOptimizationState);
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
/** @type {__VLS_StyleScopedClasses['description-label']} */ ;
/** @type {__VLS_StyleScopedClasses['footer']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    ref: "mainButton",
    severity: "secondary",
    disabled: (__VLS_ctx.disabled),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    ref: "mainButton",
    severity: "secondary",
    disabled: (__VLS_ctx.disabled),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.promptFusionService.changeOptimizationState(true);
            // @ts-ignore
            [disabled, promptFusionService,];
        } });
var __VLS_7;
const { default: __VLS_9 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.slidersHorizontal | typeof __VLS_components.SlidersHorizontal | typeof __VLS_components['sliders-horizontal']} */
slidersHorizontal;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    size: (14),
}));
const __VLS_12 = __VLS_11({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({}));
const __VLS_17 = __VLS_16({}, ...__VLS_functionalComponentArgsRest(__VLS_16));
const { default: __VLS_20 } = __VLS_18.slots;
let __VLS_21;
/** @ts-ignore @type { | typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    to: "body",
}));
const __VLS_23 = __VLS_22({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
const { default: __VLS_26 } = __VLS_24.slots;
if (__VLS_ctx.visible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.visible))
                    return;
                __VLS_ctx.promptFusionService.changeOptimizationState(false);
                // @ts-ignore
                [promptFusionService, visible,];
            } },
        options: ({ ignore: [__VLS_ctx.mainButton] }),
        ...{ class: "sidebar-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['sidebar-wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sidebar" },
    });
    /** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    let __VLS_27;
    /** @ts-ignore @type { | typeof __VLS_components.slidersHorizontal | typeof __VLS_components.SlidersHorizontal | typeof __VLS_components['sliders-horizontal']} */
    slidersHorizontal;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        size: (20),
        color: "var(--p-badge-secondary-color)",
    }));
    const __VLS_29 = __VLS_28({
        size: (20),
        color: "var(--p-badge-secondary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "text",
    }));
    const __VLS_34 = __VLS_33({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    let __VLS_37;
    const __VLS_38 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.visible))
                    return;
                __VLS_ctx.promptFusionService.changeOptimizationState(false);
                // @ts-ignore
                [promptFusionService, mainButton,];
            } });
    const { default: __VLS_39 } = __VLS_35.slots;
    {
        const { icon: __VLS_40 } = __VLS_35.slots;
        let __VLS_41;
        /** @ts-ignore @type { | typeof __VLS_components.x | typeof __VLS_components.X} */
        x;
        // @ts-ignore
        const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
            width: "16",
            height: "16",
            color: "var(--p-button-text-secondary-color)",
        }));
        const __VLS_43 = __VLS_42({
            width: "16",
            height: "16",
            color: "var(--p-button-text-secondary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_42));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_35;
    var __VLS_36;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "body" },
    });
    /** @type {__VLS_StyleScopedClasses['body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "description" },
    });
    /** @type {__VLS_StyleScopedClasses['description']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "description-label" },
    });
    /** @type {__VLS_StyleScopedClasses['description-label']} */ ;
    const __VLS_46 = CustomTextarea;
    // @ts-ignore
    const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
        modelValue: (__VLS_ctx.description),
        fluid: true,
        rows: "1",
        placeholder: "Provide a short task description",
        size: "small",
        autoResize: true,
        maxHeight: (75),
        ...{ class: "hint" },
    }));
    const __VLS_48 = __VLS_47({
        modelValue: (__VLS_ctx.description),
        fluid: true,
        rows: "1",
        placeholder: "Provide a short task description",
        size: "small",
        autoResize: true,
        maxHeight: (75),
        ...{ class: "hint" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_47));
    /** @type {__VLS_StyleScopedClasses['hint']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "teacher-model" },
    });
    /** @type {__VLS_StyleScopedClasses['teacher-model']} */ ;
    const __VLS_51 = ModelSelect;
    // @ts-ignore
    const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
        title: "teacher model",
        description: "Model that provides reference outputs",
        modelType: (__VLS_ctx.ModelTypeEnum.teacher),
    }));
    const __VLS_53 = __VLS_52({
        title: "teacher model",
        description: "Model that provides reference outputs",
        modelType: (__VLS_ctx.ModelTypeEnum.teacher),
    }, ...__VLS_functionalComponentArgsRest(__VLS_52));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "student-model" },
    });
    /** @type {__VLS_StyleScopedClasses['student-model']} */ ;
    const __VLS_56 = ModelSelect;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent1(__VLS_56, new __VLS_56({
        title: "student model",
        description: "Model being optimized",
        modelType: (__VLS_ctx.ModelTypeEnum.student),
    }));
    const __VLS_58 = __VLS_57({
        title: "student model",
        description: "Model being optimized",
        modelType: (__VLS_ctx.ModelTypeEnum.student),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    const __VLS_61 = EvaluationMetrics;
    // @ts-ignore
    const __VLS_62 = __VLS_asFunctionalComponent1(__VLS_61, new __VLS_61({}));
    const __VLS_63 = __VLS_62({}, ...__VLS_functionalComponentArgsRest(__VLS_62));
    __VLS_asFunctionalElement1(__VLS_intrinsics.footer, __VLS_intrinsics.footer)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    let __VLS_66;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_67 = __VLS_asFunctionalComponent1(__VLS_66, new __VLS_66({
        as: "a",
        label: "Need help?",
        href: (__VLS_ctx.helpLink),
        target: "_blank",
        variant: "text",
    }));
    const __VLS_68 = __VLS_67({
        as: "a",
        label: "Need help?",
        href: (__VLS_ctx.helpLink),
        target: "_blank",
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_67));
    let __VLS_71;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_72 = __VLS_asFunctionalComponent1(__VLS_71, new __VLS_71({
        ...{ 'onClick': {} },
        label: "run optimization",
        severity: "secondary",
    }));
    const __VLS_73 = __VLS_72({
        ...{ 'onClick': {} },
        label: "run optimization",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_72));
    let __VLS_76;
    const __VLS_77 = ({ click: {} },
        { onClick: (__VLS_ctx.onRunOptimizationClick) });
    var __VLS_74;
    var __VLS_75;
}
// @ts-ignore
[description, ModelTypeEnum, ModelTypeEnum, helpLink, onRunOptimizationClick,];
var __VLS_24;
// @ts-ignore
[];
var __VLS_18;
// @ts-ignore
var __VLS_8 = __VLS_7;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
