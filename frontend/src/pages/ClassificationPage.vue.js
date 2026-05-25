/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import TabularWrapper from '@/components/express-tasks/tabular/TabularWrapper.vue';
import { Tasks } from '@/lib/data-processing/interfaces';
import { tabularSteps } from '@/constants/constants';
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = TabularWrapper || TabularWrapper;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    steps: (__VLS_ctx.tabularSteps),
    task: (__VLS_ctx.Tasks.TABULAR_CLASSIFICATION),
}));
const __VLS_2 = __VLS_1({
    steps: (__VLS_ctx.tabularSteps),
    task: (__VLS_ctx.Tasks.TABULAR_CLASSIFICATION),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
var __VLS_3;
// @ts-ignore
[tabularSteps, Tasks,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
