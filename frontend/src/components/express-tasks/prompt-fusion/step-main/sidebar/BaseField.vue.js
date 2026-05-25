/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PromptFieldTypeEnum } from '../../interfaces';
const props = defineProps();
const emit = defineEmits();
const options = [
    { name: PromptFieldTypeEnum.string, value: 'string' },
    { name: PromptFieldTypeEnum.integer, value: 'integer' },
    { name: PromptFieldTypeEnum.float, value: 'float' },
];
function onVariadicClick() {
    props.data.variadic = !props.data.variadic;
}
function onTrashClick() {
    emit('delete');
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
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "field-header" },
});
/** @type {__VLS_StyleScopedClasses['field-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "field-type" },
});
/** @type {__VLS_StyleScopedClasses['field-type']} */ ;
(__VLS_ctx.typeLabel ? __VLS_ctx.typeLabel : __VLS_ctx.data.variant);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field-actives" },
});
/** @type {__VLS_StyleScopedClasses['field-actives']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: (__VLS_ctx.data.variadic ? 'primary' : 'secondary'),
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: (__VLS_ctx.data.variadic ? 'primary' : 'secondary'),
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.onVariadicClick) });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Set as List') }, null, null);
/** @type {__VLS_StyleScopedClasses['filed-actives-button']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.brackets | typeof __VLS_components.Brackets} */
    brackets;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        width: "14",
        height: "14",
    }));
    const __VLS_11 = __VLS_10({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [typeLabel, typeLabel, data, data, onVariadicClick, vTooltip,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "divider" },
});
/** @type {__VLS_StyleScopedClasses['divider']} */ ;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}));
const __VLS_16 = __VLS_15({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
let __VLS_19;
const __VLS_20 = ({ click: {} },
    { onClick: (__VLS_ctx.onTrashClick) });
/** @type {__VLS_StyleScopedClasses['filed-actives-button']} */ ;
const { default: __VLS_21 } = __VLS_17.slots;
{
    const { icon: __VLS_22 } = __VLS_17.slots;
    let __VLS_23;
    /** @ts-ignore @type { | typeof __VLS_components.trash | typeof __VLS_components.Trash} */
    trash;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        width: "14",
        height: "14",
    }));
    const __VLS_25 = __VLS_24({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
    // @ts-ignore
    [onTrashClick,];
}
// @ts-ignore
[];
var __VLS_17;
var __VLS_18;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field-body" },
});
/** @type {__VLS_StyleScopedClasses['field-body']} */ ;
let __VLS_28;
/** @ts-ignore @type { | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select']} */
dSelect;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
    modelValue: (__VLS_ctx.data.type),
    options: (__VLS_ctx.options),
    optionLabel: "name",
    optionValue: "value",
    size: "small",
    placeholder: "Data type",
    ...{ class: "select" },
}));
const __VLS_30 = __VLS_29({
    modelValue: (__VLS_ctx.data.type),
    options: (__VLS_ctx.options),
    optionLabel: "name",
    optionValue: "value",
    size: "small",
    placeholder: "Data type",
    ...{ class: "select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
/** @type {__VLS_StyleScopedClasses['select']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "input-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['input-wrapper']} */ ;
let __VLS_33;
/** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
dInputText;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
    modelValue: (__VLS_ctx.data.value),
    placeholder: "Field name",
    size: "small",
    ...{ class: "input" },
    invalid: (__VLS_ctx.isDuplicate),
}));
const __VLS_35 = __VLS_34({
    modelValue: (__VLS_ctx.data.value),
    placeholder: "Field name",
    size: "small",
    ...{ class: "input" },
    invalid: (__VLS_ctx.isDuplicate),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
/** @type {__VLS_StyleScopedClasses['input']} */ ;
if (__VLS_ctx.isDuplicate) {
    let __VLS_38;
    /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
    dMessage;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
        severity: "error",
        size: "small",
        variant: "simple",
        ...{ class: "error" },
    }));
    const __VLS_40 = __VLS_39({
        severity: "error",
        size: "small",
        variant: "simple",
        ...{ class: "error" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
    /** @type {__VLS_StyleScopedClasses['error']} */ ;
    const { default: __VLS_43 } = __VLS_41.slots;
    // @ts-ignore
    [data, data, options, isDuplicate, isDuplicate,];
    var __VLS_41;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
