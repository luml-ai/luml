/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ModelTypeEnum, } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { computed, onBeforeMount, onBeforeUnmount, ref, watch } from 'vue';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
const props = defineProps();
const options = ref(promptFusionService.availableModels);
const selectedModel = ref(null);
const isTeacherModel = computed(() => props.modelType === ModelTypeEnum.teacher);
function changeOptions(models) {
    options.value = models;
}
watch(selectedModel, (value) => {
    const modelInService = isTeacherModel.value
        ? promptFusionService.teacherModel
        : promptFusionService.studentModel;
    if (value !== modelInService) {
        isTeacherModel.value
            ? promptFusionService.updateTeacherModel(value)
            : promptFusionService.updateStudentModel(value);
    }
});
onBeforeMount(() => {
    selectedModel.value = isTeacherModel.value
        ? promptFusionService.teacherModel
        : promptFusionService.studentModel;
    promptFusionService.on('CHANGE_AVAILABLE_MODELS', changeOptions);
});
onBeforeUnmount(() => {
    promptFusionService.off('CHANGE_AVAILABLE_MODELS', changeOptions);
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
/** @type {__VLS_StyleScopedClasses['option']} */ ;
/** @type {__VLS_StyleScopedClasses['model-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "model" },
});
/** @type {__VLS_StyleScopedClasses['model']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "model-title" },
});
/** @type {__VLS_StyleScopedClasses['model-title']} */ ;
(__VLS_ctx.title);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "model-description" },
});
/** @type {__VLS_StyleScopedClasses['model-description']} */ ;
(__VLS_ctx.description);
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select'] | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select']} */
dSelect;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.selectedModel),
    options: (__VLS_ctx.options),
    optionValue: "id",
    optionLabel: "label",
    optionGroupLabel: "label",
    optionGroupChildren: "items",
    placeholder: "Select a model",
    filter: true,
    fluid: true,
    size: "small",
    filterPlaceholder: "Search model",
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.selectedModel),
    options: (__VLS_ctx.options),
    optionValue: "id",
    optionLabel: "label",
    optionGroupLabel: "label",
    optionGroupChildren: "items",
    placeholder: "Select a model",
    filter: true,
    fluid: true,
    size: "small",
    filterPlaceholder: "Search model",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { option: __VLS_6 } = __VLS_3.slots;
    const [slotProps] = __VLS_vSlot(__VLS_6);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "option" },
    });
    /** @type {__VLS_StyleScopedClasses['option']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
        alt: (slotProps.option.label),
        src: (slotProps.option.icon),
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (slotProps.option.label);
    // @ts-ignore
    [title, description, selectedModel, options,];
}
{
    const { footer: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        ...{ class: "settings-button" },
        variant: "text",
        size: "small",
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        ...{ class: "settings-button" },
        variant: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_13;
    const __VLS_14 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.promptFusionService.openSettings();
                // @ts-ignore
                [promptFusionService,];
            } });
    /** @type {__VLS_StyleScopedClasses['settings-button']} */ ;
    const { default: __VLS_15 } = __VLS_11.slots;
    let __VLS_16;
    /** @ts-ignore @type { | typeof __VLS_components.bolt | typeof __VLS_components.Bolt} */
    bolt;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
        size: (14),
    }));
    const __VLS_18 = __VLS_17({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    // @ts-ignore
    [];
    var __VLS_11;
    var __VLS_12;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
