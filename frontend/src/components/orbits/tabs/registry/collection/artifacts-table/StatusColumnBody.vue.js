/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { STATUS_TAGS_CONFIG } from './models-table.data';
import { Tag } from 'primevue';
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
    ...{ style: {} },
});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
Tag;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    severity: (__VLS_ctx.STATUS_TAGS_CONFIG[__VLS_ctx.status]?.severity ?? 'info'),
    ...{ class: "tag" },
}));
const __VLS_2 = __VLS_1({
    severity: (__VLS_ctx.STATUS_TAGS_CONFIG[__VLS_ctx.status]?.severity ?? 'info'),
    ...{ class: "tag" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['tag']} */ ;
const { default: __VLS_5 } = __VLS_3.slots;
(__VLS_ctx.STATUS_TAGS_CONFIG[__VLS_ctx.status]?.text ?? 'Unknown status');
// @ts-ignore
[STATUS_TAGS_CONFIG, STATUS_TAGS_CONFIG, status, status,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
