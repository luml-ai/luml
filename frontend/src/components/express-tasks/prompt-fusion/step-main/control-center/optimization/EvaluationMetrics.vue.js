/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { EvaluationModesEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces';
import { v4 as uuid4 } from 'uuid';
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService';
import UiCustomRadio from '@/components/ui/UiCustomRadio.vue';
import { useRoute } from 'vue-router';
const route = useRoute();
const mode = ref(promptFusionService.evaluationMode);
const criteriaList = ref(getInitialCriteriaList());
const disabledMetrics = computed(() => route.params.mode === 'data-driven'
    ? []
    : [EvaluationModesEnum.exactMatch, EvaluationModesEnum.llmBased]);
function getInitialCriteriaList() {
    return promptFusionService.evaluationCriteriaList.length
        ? promptFusionService.evaluationCriteriaList.map((value) => createCriteria(value))
        : [createCriteria()];
}
function createCriteria(value = '') {
    return { id: uuid4(), value };
}
function addCriteria() {
    criteriaList.value.push(createCriteria());
}
function removeCriteria(id) {
    criteriaList.value = criteriaList.value.filter((criteria) => criteria.id !== id);
}
watch(mode, (val) => {
    promptFusionService.evaluationMode = val;
    val === EvaluationModesEnum.llmBased
        ? (criteriaList.value = [createCriteria()])
        : (criteriaList.value = []);
}, {});
watch(criteriaList, (val) => {
    promptFusionService.evaluationCriteriaList = val.map((criteria) => criteria.value);
}, { deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "evaluation" },
});
/** @type {__VLS_StyleScopedClasses['evaluation']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "description" },
});
/** @type {__VLS_StyleScopedClasses['description']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "modes" },
});
/** @type {__VLS_StyleScopedClasses['modes']} */ ;
const __VLS_0 = UiCustomRadio;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.mode),
    options: (Object.values(__VLS_ctx.EvaluationModesEnum)),
    disabled: (__VLS_ctx.disabledMetrics),
    ...{ style: {} },
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.mode),
    options: (Object.values(__VLS_ctx.EvaluationModesEnum)),
    disabled: (__VLS_ctx.disabledMetrics),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
if (__VLS_ctx.mode === __VLS_ctx.EvaluationModesEnum.llmBased) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "based-info" },
    });
    /** @type {__VLS_StyleScopedClasses['based-info']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "criteria-list" },
    });
    /** @type {__VLS_StyleScopedClasses['criteria-list']} */ ;
    for (const [criteria] of __VLS_vFor((__VLS_ctx.criteriaList))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
            key: (criteria.id),
            ...{ class: "criteria-item" },
        });
        /** @type {__VLS_StyleScopedClasses['criteria-item']} */ ;
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
        dInputText;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            modelValue: (criteria.value),
            placeholder: "Criteria",
            size: "small",
            ...{ class: "criteria-input" },
        }));
        const __VLS_7 = __VLS_6({
            modelValue: (criteria.value),
            placeholder: "Criteria",
            size: "small",
            ...{ class: "criteria-input" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
        /** @type {__VLS_StyleScopedClasses['criteria-input']} */ ;
        let __VLS_10;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "text",
            rounded: true,
            ...{ class: "criteria-trash" },
        }));
        const __VLS_12 = __VLS_11({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "text",
            rounded: true,
            ...{ class: "criteria-trash" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        let __VLS_15;
        const __VLS_16 = ({ click: {} },
            { onClick: (() => __VLS_ctx.removeCriteria(criteria.id)) });
        /** @type {__VLS_StyleScopedClasses['criteria-trash']} */ ;
        const { default: __VLS_17 } = __VLS_13.slots;
        {
            const { icon: __VLS_18 } = __VLS_13.slots;
            let __VLS_19;
            /** @ts-ignore @type { | typeof __VLS_components.trash2 | typeof __VLS_components.Trash2} */
            trash2;
            // @ts-ignore
            const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
                size: (14),
            }));
            const __VLS_21 = __VLS_20({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_20));
            // @ts-ignore
            [mode, mode, EvaluationModesEnum, EvaluationModesEnum, disabledMetrics, criteriaList, removeCriteria,];
        }
        // @ts-ignore
        [];
        var __VLS_13;
        var __VLS_14;
        // @ts-ignore
        [];
    }
    let __VLS_24;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        label: "Add evaluation criteria",
        variant: "text",
        size: "small",
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        label: "Add evaluation criteria",
        variant: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_29;
    const __VLS_30 = ({ click: {} },
        { onClick: (__VLS_ctx.addCriteria) });
    const { default: __VLS_31 } = __VLS_27.slots;
    {
        const { icon: __VLS_32 } = __VLS_27.slots;
        let __VLS_33;
        /** @ts-ignore @type { | typeof __VLS_components.plus | typeof __VLS_components.Plus} */
        plus;
        // @ts-ignore
        const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
            size: (14),
        }));
        const __VLS_35 = __VLS_34({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_34));
        // @ts-ignore
        [addCriteria,];
    }
    // @ts-ignore
    [];
    var __VLS_27;
    var __VLS_28;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
