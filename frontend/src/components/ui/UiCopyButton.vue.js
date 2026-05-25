/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Copy, CopyCheck } from 'lucide-vue-next';
import { Button } from 'primevue';
const props = defineProps();
const copied = ref(false);
function copy() {
    copied.value = true;
    navigator.clipboard.writeText(props.text);
    setTimeout(() => {
        copied.value = false;
    }, 2000);
}
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
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    ...{ class: "copy-button" },
    severity: "secondary",
    variant: "text",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    ...{ class: "copy-button" },
    severity: "secondary",
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.copy) });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['copy-button']} */ ;
const { default: __VLS_8 } = __VLS_3.slots;
const __VLS_9 = (__VLS_ctx.copied ? __VLS_ctx.CopyCheck : __VLS_ctx.Copy);
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
    size: (12),
}));
const __VLS_11 = __VLS_10({
    size: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
// @ts-ignore
[copy, copied, CopyCheck, Copy,];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
