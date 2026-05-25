/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
const __VLS_props = withDefaults(defineProps(), {
    mainColor: 'var(--p-progressbar-value-background)',
    secondaryColor: 'var(--p-progressbar-background)',
    size: 44,
});
const radius = 45;
const circumference = 2 * Math.PI * radius;
const __VLS_defaults = {
    mainColor: 'var(--p-progressbar-value-background)',
    secondaryColor: 'var(--p-progressbar-background)',
    size: 44,
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)({
    width: (__VLS_ctx.size),
    height: (__VLS_ctx.size),
    viewBox: "0 0 100 100",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.circle)({
    cx: "50",
    cy: "50",
    r: "45",
    stroke: (__VLS_ctx.secondaryColor),
    'stroke-width': "10",
    fill: "none",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.circle)({
    cx: "50",
    cy: "50",
    r: "45",
    stroke: (__VLS_ctx.mainColor),
    'stroke-width': "10",
    fill: "none",
    'stroke-linecap': "butt",
    'stroke-dasharray': (__VLS_ctx.circumference),
    'stroke-dashoffset': (__VLS_ctx.circumference - (__VLS_ctx.progress / 100) * __VLS_ctx.circumference),
    transform: "rotate(-90 50 50)",
});
// @ts-ignore
[size, size, secondaryColor, mainColor, circumference, circumference, circumference, progress,];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
