/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import SplitButton from 'primevue/splitbutton';
import TaskModal from '@/components/express-tasks/prompt-fusion/TaskModal.vue';
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
const props = defineProps();
const router = useRouter();
const isPopupVisible = ref(false);
const isPromptFusionTask = computed(() => props.task.id === 5);
function onButtonClick() {
    AnalyticsService.track(AnalyticsTrackKeysEnum.select_task, { task: props.task.analyticsTaskName });
    if (props.task.linkName)
        router.push({ name: props.task.linkName });
    else if (isPromptFusionTask.value) {
        isPopupVisible.value = true;
    }
}
const dropdownItems = computed(() => (props.task.dropdownOptions || []).map((opt) => ({
    label: opt.label,
    command: () => {
        AnalyticsService.track(AnalyticsTrackKeysEnum.select_task, {
            task: props.task.analyticsTaskName,
        });
        const target = opt.route || props.task.linkName;
        if (target)
            router.push({ name: target });
        else if (isPromptFusionTask.value)
            isPopupVisible.value = true;
    },
})));
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['p-splitbutton']} */ ;
/** @type {__VLS_StyleScopedClasses['p-splitbutton']} */ ;
/** @type {__VLS_StyleScopedClasses['p-splitbutton']} */ ;
/** @type {__VLS_StyleScopedClasses['p-splitbutton-dropdown']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    ...{ class: "image" },
    alt: "",
    src: (__VLS_ctx.task.icon),
    width: "48",
    height: "48",
});
/** @type {__VLS_StyleScopedClasses['image']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    autoHide: "false",
});
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { left: true, }, value: (__VLS_ctx.task.tooltipData) }, null, null);
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.circleHelp | typeof __VLS_components.CircleHelp | typeof __VLS_components['circle-help']} */
circleHelp;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (20),
    ...{ class: "tooltip-icon" },
}));
const __VLS_2 = __VLS_1({
    size: (20),
    ...{ class: "tooltip-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['tooltip-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
(__VLS_ctx.task.title);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
(__VLS_ctx.task.description);
if (__VLS_ctx.task.btnText) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "footer" },
    });
    /** @type {__VLS_StyleScopedClasses['footer']} */ ;
    if (__VLS_ctx.task.dropdownOptions?.length) {
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.SplitButton} */
        SplitButton;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.task.btnText),
            model: (__VLS_ctx.dropdownItems),
            severity: "secondary",
            ...{ class: "w-full" },
        }));
        const __VLS_7 = __VLS_6({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.task.btnText),
            model: (__VLS_ctx.dropdownItems),
            severity: "secondary",
            ...{ class: "w-full" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
        let __VLS_10;
        const __VLS_11 = ({ click: {} },
            { onClick: (__VLS_ctx.onButtonClick) });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        var __VLS_8;
        var __VLS_9;
    }
    else {
        let __VLS_12;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.task.btnText),
            severity: "secondary",
            ...{ class: "w-full" },
            disabled: (__VLS_ctx.task.isDisabled),
        }));
        const __VLS_14 = __VLS_13({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.task.btnText),
            severity: "secondary",
            ...{ class: "w-full" },
            disabled: (__VLS_ctx.task.isDisabled),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        let __VLS_17;
        const __VLS_18 = ({ click: {} },
            { onClick: (__VLS_ctx.onButtonClick) });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        var __VLS_15;
        var __VLS_16;
    }
}
if (__VLS_ctx.isPromptFusionTask) {
    const __VLS_19 = TaskModal;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        modelValue: (__VLS_ctx.isPopupVisible),
    }));
    const __VLS_21 = __VLS_20({
        modelValue: (__VLS_ctx.isPopupVisible),
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
}
// @ts-ignore
[task, task, task, task, task, task, task, task, task, vTooltip, dropdownItems, onButtonClick, onButtonClick, isPromptFusionTask, isPopupVisible,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
