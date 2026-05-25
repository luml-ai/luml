/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
const __VLS_props = withDefaults(defineProps(), {
    stroke: 'var(--p-surface-500)',
    fill: 'var(--p-surface-500)',
    strokeWidth: 2,
    width: 2,
    height: 6.5,
});
const __VLS_defaults = {
    stroke: 'var(--p-surface-500)',
    fill: 'var(--p-surface-500)',
    strokeWidth: 2,
    width: 2,
    height: 6.5,
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)({
    ...{ class: "vue-flow__marker vue-flow__container" },
});
/** @type {__VLS_StyleScopedClasses['vue-flow__marker']} */ ;
/** @type {__VLS_StyleScopedClasses['vue-flow__container']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.defs, __VLS_intrinsics.defs)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.marker, __VLS_intrinsics.marker)({
    id: (__VLS_ctx.id),
    ...{ class: "vue-flow__arrowhead" },
    viewBox: "-2 -6.5 4 13",
    refX: "0",
    refY: "0",
    markerWidth: (__VLS_ctx.width),
    markerHeight: (__VLS_ctx.height),
    markerUnits: "strokeWidth",
    orient: "auto-start-reverse",
});
/** @type {__VLS_StyleScopedClasses['vue-flow__arrowhead']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.rect)({
    x: "-2",
    y: "-6.5",
    width: "4",
    height: "13",
    rx: "2",
    ry: "2",
    fill: (__VLS_ctx.fill),
    d: "M -2 -6.5 H 2 V 6.5 H -2 Z",
});
// @ts-ignore
[id, width, height, fill,];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
