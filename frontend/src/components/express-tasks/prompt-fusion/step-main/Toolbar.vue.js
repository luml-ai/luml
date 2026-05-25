/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useVueFlow } from '@vue-flow/core';
import { computed, ref, watch } from 'vue';
import { NodeTypeEnum, PROMPT_NODES_ICONS } from '../interfaces';
import { getEmptyGateNode, getEmptyProcessorNode } from '@/constants/prompt-fusion';
const { zoomIn: zoomInFunction, zoomOut: zoomOutFunction, zoomTo, viewport, addNodes, panOnDrag, } = useVueFlow();
const zoomValue = ref((viewport.value.zoom * 100).toFixed());
const cursorMode = ref('pointer');
const toggleMenuButton = ref();
const isMenuOpen = ref(false);
const isViewportLocked = computed(() => cursorMode.value === 'pointer');
const toggleMenu = () => {
    isMenuOpen.value = !isMenuOpen.value;
};
function changeZoom(e) {
    const target = e.target;
    const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0;
    zoomTo(value);
}
function onMenuOutsideClick() {
    if (isMenuOpen.value)
        toggleMenu();
}
function addNode(node) {
    isMenuOpen.value = false;
    if (node === NodeTypeEnum.gate) {
        addNodes(getEmptyGateNode());
    }
    else if (node === NodeTypeEnum.processor) {
        addNodes(getEmptyProcessorNode());
    }
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
/** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
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
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
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
    { onClick: (__VLS_ctx.zoomOutFunction) });
/** @type {__VLS_StyleScopedClasses['smallest-button']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.zoomOut | typeof __VLS_components.ZoomOut | typeof __VLS_components['zoom-out']} */
    zoomOut;
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
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
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
    { onClick: (__VLS_ctx.zoomInFunction) });
/** @type {__VLS_StyleScopedClasses['smallest-button']} */ ;
const { default: __VLS_21 } = __VLS_17.slots;
{
    const { icon: __VLS_22 } = __VLS_17.slots;
    let __VLS_23;
    /** @ts-ignore @type { | typeof __VLS_components.zoomIn | typeof __VLS_components.ZoomIn | typeof __VLS_components['zoom-in']} */
    zoomIn;
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
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
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
    /** @ts-ignore @type { | typeof __VLS_components.pointer | typeof __VLS_components.Pointer} */
    pointer;
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
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
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
    /** @ts-ignore @type { | typeof __VLS_components.mousePointer2 | typeof __VLS_components.MousePointer2 | typeof __VLS_components['mouse-pointer-2']} */
    mousePointer2;
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
let __VLS_56;
/** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
dDivider;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent1(__VLS_56, new __VLS_56({
    layout: "vertical",
    ...{ class: "divider" },
}));
const __VLS_58 = __VLS_57({
    layout: "vertical",
    ...{ class: "divider" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
/** @type {__VLS_StyleScopedClasses['divider']} */ ;
let __VLS_61;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent1(__VLS_61, new __VLS_61({
    ...{ 'onClick': {} },
    ref: "toggleMenuButton",
    ...{ class: "small-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}));
const __VLS_63 = __VLS_62({
    ...{ 'onClick': {} },
    ref: "toggleMenuButton",
    ...{ class: "small-button" },
    variant: "text",
    severity: "secondary",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
let __VLS_66;
const __VLS_67 = ({ click: {} },
    { onClick: (__VLS_ctx.toggleMenu) });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Add card') }, null, null);
var __VLS_68;
/** @type {__VLS_StyleScopedClasses['small-button']} */ ;
const { default: __VLS_70 } = __VLS_64.slots;
{
    const { icon: __VLS_71 } = __VLS_64.slots;
    let __VLS_72;
    /** @ts-ignore @type { | typeof __VLS_components.circlePlus | typeof __VLS_components.CirclePlus | typeof __VLS_components['circle-plus']} */
    circlePlus;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent1(__VLS_72, new __VLS_72({
        size: (14),
    }));
    const __VLS_74 = __VLS_73({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    // @ts-ignore
    [toggleMenu, vTooltip,];
}
// @ts-ignore
[];
var __VLS_64;
var __VLS_65;
if (__VLS_ctx.isMenuOpen) {
    let __VLS_77;
    /** @ts-ignore @type { | typeof __VLS_components.onClickOutside | typeof __VLS_components.OnClickOutside | typeof __VLS_components['on-click-outside'] | typeof __VLS_components.onClickOutside | typeof __VLS_components.OnClickOutside | typeof __VLS_components['on-click-outside']} */
    onClickOutside;
    // @ts-ignore
    const __VLS_78 = __VLS_asFunctionalComponent1(__VLS_77, new __VLS_77({
        ...{ 'onTrigger': {} },
        options: ({ ignore: [__VLS_ctx.toggleMenuButton] }),
        ...{ class: "menu" },
    }));
    const __VLS_79 = __VLS_78({
        ...{ 'onTrigger': {} },
        options: ({ ignore: [__VLS_ctx.toggleMenuButton] }),
        ...{ class: "menu" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_78));
    let __VLS_82;
    const __VLS_83 = ({ trigger: {} },
        { onTrigger: (__VLS_ctx.onMenuOutsideClick) });
    /** @type {__VLS_StyleScopedClasses['menu']} */ ;
    const { default: __VLS_84 } = __VLS_80.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.isMenuOpen))
                    return;
                __VLS_ctx.addNode(__VLS_ctx.NodeTypeEnum.gate);
                // @ts-ignore
                [isMenuOpen, toggleMenuButton, onMenuOutsideClick, addNode, NodeTypeEnum,];
            } },
        ...{ class: "menu-item" },
    });
    /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
    const __VLS_85 = (__VLS_ctx.PROMPT_NODES_ICONS.gate);
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
        size: (14),
        color: "var(--p-badge-success-background)",
    }));
    const __VLS_87 = __VLS_86({
        size: (14),
        color: "var(--p-badge-success-background)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    let __VLS_90;
    /** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
    dDivider;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent1(__VLS_90, new __VLS_90({
        ...{ style: ({ margin: '2px 0' }) },
    }));
    const __VLS_92 = __VLS_91({
        ...{ style: ({ margin: '2px 0' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.isMenuOpen))
                    return;
                __VLS_ctx.addNode(__VLS_ctx.NodeTypeEnum.processor);
                // @ts-ignore
                [addNode, NodeTypeEnum, PROMPT_NODES_ICONS,];
            } },
        ...{ class: "menu-item" },
    });
    /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
    const __VLS_95 = (__VLS_ctx.PROMPT_NODES_ICONS.cpu);
    // @ts-ignore
    const __VLS_96 = __VLS_asFunctionalComponent1(__VLS_95, new __VLS_95({
        size: (14),
        color: "var(--p-badge-warn-background)",
    }));
    const __VLS_97 = __VLS_96({
        size: (14),
        color: "var(--p-badge-warn-background)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_96));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [PROMPT_NODES_ICONS,];
    var __VLS_80;
    var __VLS_81;
}
// @ts-ignore
var __VLS_69 = __VLS_68;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
