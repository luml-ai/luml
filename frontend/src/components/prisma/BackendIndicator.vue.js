/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Button, InputText, Popover } from 'primevue';
import { api } from '@/lib/api';
const emit = defineEmits();
const popover = ref();
const url = ref(api.dataAgent.getBackendUrl());
function displayHost() {
    try {
        return new URL(url.value).host;
    }
    catch {
        return url.value;
    }
}
function toggle(event) {
    url.value = api.dataAgent.getBackendUrl();
    popover.value.toggle(event);
}
function save() {
    api.dataAgent.setBackendUrl(url.value);
    popover.value.hide();
    emit('changed');
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
/** @type {__VLS_StyleScopedClasses['indicator']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.toggle) },
    ...{ class: "indicator" },
});
/** @type {__VLS_StyleScopedClasses['indicator']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span)({
    ...{ class: "dot" },
});
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "host" },
});
/** @type {__VLS_StyleScopedClasses['host']} */ ;
(__VLS_ctx.displayHost());
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Popover | typeof __VLS_components.Popover} */
Popover;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ref: "popover",
}));
const __VLS_2 = __VLS_1({
    ref: "popover",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_7 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-content" },
});
/** @type {__VLS_StyleScopedClasses['popover-content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "popover-label" },
});
/** @type {__VLS_StyleScopedClasses['popover-label']} */ ;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.url),
    placeholder: "http://localhost:8420",
    ...{ class: "popover-input" },
}));
const __VLS_10 = __VLS_9({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.url),
    placeholder: "http://localhost:8420",
    ...{ class: "popover-input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_13;
const __VLS_14 = ({ keydown: {} },
    { onKeydown: (__VLS_ctx.save) });
/** @type {__VLS_StyleScopedClasses['popover-input']} */ ;
var __VLS_11;
var __VLS_12;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_17 = __VLS_16({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
let __VLS_20;
const __VLS_21 = ({ click: {} },
    { onClick: (__VLS_ctx.save) });
const { default: __VLS_22 } = __VLS_18.slots;
// @ts-ignore
[toggle, displayHost, url, save, save,];
var __VLS_18;
var __VLS_19;
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
var __VLS_6 = __VLS_5;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};
