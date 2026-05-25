/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { cutStringOnMiddle } from '@/helpers/helpers';
import { Orbit as OrbitIcon } from 'lucide-vue-next';
import UiCopyButton from '@/components/ui/UiCopyButton.vue';
const props = defineProps();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "orbit" },
});
/** @type {__VLS_StyleScopedClasses['orbit']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.OrbitIcon} */
OrbitIcon;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (24),
    color: "var(--p-primary-color)",
    ...{ class: "orbit-icon" },
}));
const __VLS_2 = __VLS_1({
    size: (24),
    color: "var(--p-primary-color)",
    ...{ class: "orbit-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['orbit-icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "orbit-name" },
});
/** @type {__VLS_StyleScopedClasses['orbit-name']} */ ;
(__VLS_ctx.orbit.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "orbit-id" },
});
/** @type {__VLS_StyleScopedClasses['orbit-id']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "orbit-id-label" },
});
/** @type {__VLS_StyleScopedClasses['orbit-id-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "orbit-id-value" },
});
/** @type {__VLS_StyleScopedClasses['orbit-id-value']} */ ;
(__VLS_ctx.cutStringOnMiddle(__VLS_ctx.orbit.id, 8));
const __VLS_5 = UiCopyButton || UiCopyButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    text: (__VLS_ctx.orbit.id),
}));
const __VLS_7 = __VLS_6({
    text: (__VLS_ctx.orbit.id),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
// @ts-ignore
[orbit, orbit, orbit, cutStringOnMiddle,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
