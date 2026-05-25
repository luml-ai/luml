/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useLayout } from '@/hooks/useLayout';
import { ProgressSpinner } from 'primevue';
const { headerSizes } = useLayout();
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-loader" },
    ...{ style: ({
            height: `calc(100vh - ${__VLS_ctx.headerSizes.height}px)`,
        }) },
});
/** @type {__VLS_StyleScopedClasses['page-loader']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.ProgressSpinner | typeof __VLS_components.ProgressSpinner} */
ProgressSpinner;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
// @ts-ignore
[headerSizes,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
