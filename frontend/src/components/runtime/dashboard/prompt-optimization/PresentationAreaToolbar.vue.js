/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useVueFlow } from '@vue-flow/core';
import { computed, ref, watch } from 'vue';
import { Button } from 'primevue';
import { MousePointer2, Pointer, ZoomIn, ZoomOut } from 'lucide-vue-next';
const { zoomIn: zoomInFunction, zoomOut: zoomOutFunction, zoomTo, viewport, panOnDrag, } = useVueFlow();
const zoomValue = ref((viewport.value.zoom * 100).toFixed());
const cursorMode = ref('hand');
const isViewportLocked = computed(() => cursorMode.value === 'pointer');
function changeZoom(e) {
    const target = e.target;
    const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0;
    zoomTo(value);
}
watch(() => viewport.value.zoom, (value) => {
    zoomValue.value = (value * 100).toFixed();
});
watch(isViewportLocked, (val) => {
    panOnDrag.value = !val;
}, { immediate: true });
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar-body" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar-zoom" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-zoom']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    ...{ class: "smallest-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    ...{ class: "smallest-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (() => __VLS_ctx.zoomOutFunction()) });
/** @type {__VLS_StyleScopedClasses['smallest-button']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.ZoomOut} */
    ZoomOut;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [zoomOutFunction,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar-zoom-value" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-zoom-value']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onInput: (__VLS_ctx.changeZoom) },
    type: "number",
    ...{ class: "toolbar-zoom-input" },
});
(__VLS_ctx.zoomValue);
/** @type {__VLS_StyleScopedClasses['toolbar-zoom-input']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "toolbar-zoom-value" },
});
/** @type {__VLS_StyleScopedClasses['toolbar-zoom-value']} */ ;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    ...{ 'onClick': {} },
    ...{ class: "smallest-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}));
const __VLS_16 = __VLS_15({
    ...{ 'onClick': {} },
    ...{ class: "smallest-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
let __VLS_19;
const __VLS_20 = ({ click: {} },
    { onClick: (() => __VLS_ctx.zoomInFunction()) });
/** @type {__VLS_StyleScopedClasses['smallest-button']} */ ;
const { default: __VLS_21 } = __VLS_17.slots;
{
    const { icon: __VLS_22 } = __VLS_17.slots;
    let __VLS_23;
    /** @ts-ignore @type { | typeof __VLS_components.ZoomIn} */
    ZoomIn;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        size: (14),
    }));
    const __VLS_25 = __VLS_24({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
    // @ts-ignore
    [changeZoom, zoomValue, zoomInFunction,];
}
// @ts-ignore
[];
var __VLS_17;
var __VLS_18;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "pointers" },
});
/** @type {__VLS_StyleScopedClasses['pointers']} */ ;
let __VLS_28;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
    ...{ class: "small-button" },
    variant: "text",
    severity: (__VLS_ctx.cursorMode === 'hand' ? 'primary' : 'secondary'),
    size: "small",
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
    ...{ class: "small-button" },
    variant: "text",
    severity: (__VLS_ctx.cursorMode === 'hand' ? 'primary' : 'secondary'),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_33;
const __VLS_34 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.cursorMode = 'hand';
            // @ts-ignore
            [cursorMode, cursorMode,];
        } });
/** @type {__VLS_StyleScopedClasses['small-button']} */ ;
const { default: __VLS_35 } = __VLS_31.slots;
{
    const { icon: __VLS_36 } = __VLS_31.slots;
    let __VLS_37;
    /** @ts-ignore @type { | typeof __VLS_components.Pointer} */
    Pointer;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        size: (14),
    }));
    const __VLS_39 = __VLS_38({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_31;
var __VLS_32;
let __VLS_42;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
    ...{ 'onClick': {} },
    ...{ class: "small-button" },
    variant: "text",
    severity: (__VLS_ctx.cursorMode === 'pointer' ? 'primary' : 'secondary'),
    size: "small",
}));
const __VLS_44 = __VLS_43({
    ...{ 'onClick': {} },
    ...{ class: "small-button" },
    variant: "text",
    severity: (__VLS_ctx.cursorMode === 'pointer' ? 'primary' : 'secondary'),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
let __VLS_47;
const __VLS_48 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.cursorMode = 'pointer';
            // @ts-ignore
            [cursorMode, cursorMode,];
        } });
/** @type {__VLS_StyleScopedClasses['small-button']} */ ;
const { default: __VLS_49 } = __VLS_45.slots;
{
    const { icon: __VLS_50 } = __VLS_45.slots;
    let __VLS_51;
    /** @ts-ignore @type { | typeof __VLS_components.MousePointer2} */
    MousePointer2;
    // @ts-ignore
    const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
        size: (14),
    }));
    const __VLS_53 = __VLS_52({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_52));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_45;
var __VLS_46;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
