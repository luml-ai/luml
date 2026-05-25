/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useId } from 'vue';
const id = useId();
const __VLS_props = withDefaults(defineProps(), {
    disabled: () => [],
});
const __VLS_emit = defineEmits();
const __VLS_defaults = {
    disabled: () => [],
};
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
/** @type {__VLS_StyleScopedClasses['app-custom-radio-label']} */ ;
/** @type {__VLS_StyleScopedClasses['app-custom-radio-value']} */ ;
/** @type {__VLS_StyleScopedClasses['app-custom-radio-input']} */ ;
/** @type {__VLS_StyleScopedClasses['app-custom-radio-value']} */ ;
/** @type {__VLS_StyleScopedClasses['app-custom-radio-input']} */ ;
/** @type {__VLS_StyleScopedClasses['app-custom-radio-value']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "app-custom-radio" },
});
/** @type {__VLS_StyleScopedClasses['app-custom-radio']} */ ;
for (const [option] of __VLS_vFor((__VLS_ctx.options))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: (__VLS_ctx.id + option),
        ...{ class: "app-custom-radio-label" },
    });
    /** @type {__VLS_StyleScopedClasses['app-custom-radio-label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        ...{ onChange: (...[$event]) => {
                __VLS_ctx.$emit('update:modelValue', option);
                // @ts-ignore
                [options, id, $emit,];
            } },
        type: "radio",
        name: (__VLS_ctx.id),
        id: (__VLS_ctx.id + option),
        value: (option),
        disabled: (__VLS_ctx.disabled.includes(option)),
        checked: (option === __VLS_ctx.modelValue),
        ...{ class: "app-custom-radio-input" },
    });
    /** @type {__VLS_StyleScopedClasses['app-custom-radio-input']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "app-custom-radio-value" },
    });
    /** @type {__VLS_StyleScopedClasses['app-custom-radio-value']} */ ;
    (option);
    // @ts-ignore
    [id, id, disabled, modelValue,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
