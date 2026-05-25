/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useLayout } from '@/hooks/useLayout';
import { Lock } from 'lucide-vue-next';
import { Button } from 'primevue';
import { computed } from 'vue';
const { headerSizes, footerSizes } = useLayout();
const minBlockHeight = computed(() => {
    return window.innerHeight - (headerSizes.value.height + footerSizes.value.height + 50) + 'px';
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "view" },
    ...{ style: ({ minHeight: __VLS_ctx.minBlockHeight }) },
});
/** @type {__VLS_StyleScopedClasses['view']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Lock | typeof __VLS_components.Lock} */
Lock;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (42),
}));
const __VLS_2 = __VLS_1({
    size: (42),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "view__title" },
});
/** @type {__VLS_StyleScopedClasses['view__title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "view__text" },
});
/** @type {__VLS_StyleScopedClasses['view__text']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$router.push({ name: 'home' });
            // @ts-ignore
            [minBlockHeight, $router,];
        } });
const { default: __VLS_12 } = __VLS_8.slots;
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
