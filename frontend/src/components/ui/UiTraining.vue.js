/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import UiLoader from '@/components/ui/UiLoader.vue';
const emit = defineEmits();
const __VLS_props = defineProps();
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
/** @type {__VLS_StyleScopedClasses['info']} */ ;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['loader']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    closable: (false),
    closeOnEscape: (false),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    closable: (false),
    closeOnEscape: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((event) => __VLS_ctx.$emit('update:modelValue', event)) });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { container: __VLS_9 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "loader" },
    });
    /** @type {__VLS_StyleScopedClasses['loader']} */ ;
    const __VLS_10 = UiLoader;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({}));
    const __VLS_12 = __VLS_11({}, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "content" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.progressBar | typeof __VLS_components.ProgressBar | typeof __VLS_components['progress-bar']} */
    progressBar;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        mode: "indeterminate",
        ...{ style: {} },
    }));
    const __VLS_17 = __VLS_16({
        mode: "indeterminate",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "info" },
    });
    /** @type {__VLS_StyleScopedClasses['info']} */ ;
    (__VLS_ctx.time);
    if (__VLS_ctx.isCancelAvailable) {
        let __VLS_20;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
            ...{ 'onClick': {} },
            label: "cancel",
        }));
        const __VLS_22 = __VLS_21({
            ...{ 'onClick': {} },
            label: "cancel",
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        let __VLS_25;
        const __VLS_26 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.isCancelAvailable))
                        return;
                    __VLS_ctx.$emit('cancel');
                    // @ts-ignore
                    [modelValue, $emit, $emit, time, isCancelAvailable,];
                } });
        var __VLS_23;
        var __VLS_24;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
