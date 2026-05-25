/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
const props = defineProps();
const emit = defineEmits();
function click() {
    const newTheme = props.modelValue === 'dark' ? 'light' : 'dark';
    emit('update:modelValue', newTheme);
}
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
/** @type {__VLS_StyleScopedClasses['custom-toggle-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-toggle-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "custom-toggle" },
    ...{ class: ({ dark: __VLS_ctx.modelValue === 'dark' }) },
});
/** @type {__VLS_StyleScopedClasses['custom-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['dark']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (__VLS_ctx.click) },
    ...{ class: "custom-toggle-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['custom-toggle-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "custom-toggle-item" },
});
/** @type {__VLS_StyleScopedClasses['custom-toggle-item']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.sun | typeof __VLS_components.Sun} */
sun;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (14),
}));
const __VLS_2 = __VLS_1({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "custom-toggle-item" },
});
/** @type {__VLS_StyleScopedClasses['custom-toggle-item']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.moon | typeof __VLS_components.Moon} */
moon;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    size: (14),
}));
const __VLS_7 = __VLS_6({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
// @ts-ignore
[modelValue, click,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
