/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Button, InputText } from 'primevue';
import { Pyramid } from 'lucide-vue-next';
import { api } from '@/lib/api';
import { getStoredBackendUrl } from '@/lib/api/prisma';
const props = withDefaults(defineProps(), {
    versionMismatch: false,
});
const emit = defineEmits();
const retrying = ref(false);
const backendUrl = ref(getStoredBackendUrl());
async function onRetry() {
    retrying.value = true;
    api.dataAgent.setBackendUrl(backendUrl.value);
    emit('retry');
    setTimeout(() => {
        retrying.value = false;
    }, 1000);
}
const __VLS_defaults = {
    versionMismatch: false,
};
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
/** @type {__VLS_StyleScopedClasses['offline-hint']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "offline-container" },
});
/** @type {__VLS_StyleScopedClasses['offline-container']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "offline-card" },
});
/** @type {__VLS_StyleScopedClasses['offline-card']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Pyramid} */
Pyramid;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (48),
    ...{ class: "offline-icon" },
}));
const __VLS_2 = __VLS_1({
    size: (48),
    ...{ class: "offline-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['offline-icon']} */ ;
if (props.versionMismatch) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "offline-title" },
    });
    /** @type {__VLS_StyleScopedClasses['offline-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "offline-hint" },
    });
    /** @type {__VLS_StyleScopedClasses['offline-hint']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "offline-title" },
    });
    /** @type {__VLS_StyleScopedClasses['offline-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "offline-hint" },
    });
    /** @type {__VLS_StyleScopedClasses['offline-hint']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({});
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "offline-commands" },
});
/** @type {__VLS_StyleScopedClasses['offline-commands']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "offline-command" },
});
/** @type {__VLS_StyleScopedClasses['offline-command']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "offline-command-label" },
});
/** @type {__VLS_StyleScopedClasses['offline-command-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
    ...{ class: "offline-command-code" },
});
/** @type {__VLS_StyleScopedClasses['offline-command-code']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "offline-command" },
});
/** @type {__VLS_StyleScopedClasses['offline-command']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "offline-command-label" },
});
/** @type {__VLS_StyleScopedClasses['offline-command-label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
    ...{ class: "offline-command-code" },
});
/** @type {__VLS_StyleScopedClasses['offline-command-code']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "url-input-group" },
});
/** @type {__VLS_StyleScopedClasses['url-input-group']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "url-label" },
});
/** @type {__VLS_StyleScopedClasses['url-label']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.backendUrl),
    placeholder: "http://localhost:8420",
    ...{ class: "url-input" },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.backendUrl),
    placeholder: "http://localhost:8420",
    ...{ class: "url-input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ keydown: {} },
    { onKeydown: (__VLS_ctx.onRetry) });
/** @type {__VLS_StyleScopedClasses['url-input']} */ ;
var __VLS_8;
var __VLS_9;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "url-hint" },
});
/** @type {__VLS_StyleScopedClasses['url-hint']} */ ;
let __VLS_12;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.retrying),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.retrying),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_17;
const __VLS_18 = ({ click: {} },
    { onClick: (__VLS_ctx.onRetry) });
const { default: __VLS_19 } = __VLS_15.slots;
// @ts-ignore
[backendUrl, onRetry, onRetry, retrying,];
var __VLS_15;
var __VLS_16;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
