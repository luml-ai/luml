/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService';
import { useRoute, useRouter } from 'vue-router';
const emit = defineEmits();
const route = useRoute();
const router = useRouter();
function onBackClick() {
    if (route.params.mode === 'data-driven') {
        emit('goBack');
    }
    else {
        router.back();
    }
}
function onFinishClick() {
    AnalyticsService.track(AnalyticsTrackKeysEnum.finish, { task: 'prompt_optimization' });
    router.push({ name: 'home' });
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "navigation" },
});
/** @type {__VLS_StyleScopedClasses['navigation']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.onBackClick) });
const { default: __VLS_7 } = __VLS_3.slots;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.arrowLeft | typeof __VLS_components.ArrowLeft | typeof __VLS_components['arrow-left']} */
arrowLeft;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    size: (14),
}));
const __VLS_10 = __VLS_9({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
// @ts-ignore
[onBackClick,];
var __VLS_3;
var __VLS_4;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    ...{ 'onClick': {} },
    severity: "secondary",
}));
const __VLS_15 = __VLS_14({
    ...{ 'onClick': {} },
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
const __VLS_19 = ({ click: {} },
    { onClick: (__VLS_ctx.onFinishClick) });
const { default: __VLS_20 } = __VLS_16.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
let __VLS_21;
/** @ts-ignore @type { | typeof __VLS_components.logOut | typeof __VLS_components.LogOut | typeof __VLS_components['log-out']} */
logOut;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    width: "14",
    height: "14",
}));
const __VLS_23 = __VLS_22({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
// @ts-ignore
[onFinishClick,];
var __VLS_16;
var __VLS_17;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};
