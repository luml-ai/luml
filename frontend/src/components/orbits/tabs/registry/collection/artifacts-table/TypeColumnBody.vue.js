/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Tag } from 'primevue';
import { ARTIFACT_TYPE_TAGS_CONFIG } from './models-table.data';
const __VLS_props = defineProps();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
Tag;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    severity: (__VLS_ctx.ARTIFACT_TYPE_TAGS_CONFIG[__VLS_ctx.data.type]?.severity ?? 'info'),
}));
const __VLS_2 = __VLS_1({
    severity: (__VLS_ctx.ARTIFACT_TYPE_TAGS_CONFIG[__VLS_ctx.data.type]?.severity ?? 'info'),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
if (__VLS_ctx.ARTIFACT_TYPE_TAGS_CONFIG[__VLS_ctx.data.type]) {
    const __VLS_7 = (__VLS_ctx.ARTIFACT_TYPE_TAGS_CONFIG[__VLS_ctx.data.type]?.icon);
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        size: (12),
    }));
    const __VLS_9 = __VLS_8({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
}
(__VLS_ctx.ARTIFACT_TYPE_TAGS_CONFIG[__VLS_ctx.data.type]?.text ?? 'Unknown type');
// @ts-ignore
[ARTIFACT_TYPE_TAGS_CONFIG, ARTIFACT_TYPE_TAGS_CONFIG, ARTIFACT_TYPE_TAGS_CONFIG, ARTIFACT_TYPE_TAGS_CONFIG, data, data, data, data,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
