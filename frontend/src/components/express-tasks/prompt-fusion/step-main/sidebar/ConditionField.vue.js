/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import CustomTextarea from '@/components/ui/CustomTextarea.vue';
const __VLS_props = defineProps();
const emit = defineEmits();
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
(__VLS_ctx.index);
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
    severity: "secondary",
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "text",
    ...{ class: "filed-actives-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.onTrashClick) });
/** @type {__VLS_StyleScopedClasses['filed-actives-button']} */ ;
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.trash | typeof __VLS_components.Trash} */
    trash;
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
    [index, onTrashClick,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
const __VLS_14 = CustomTextarea;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    modelValue: (__VLS_ctx.data.value),
    fluid: true,
    rows: "1",
    placeholder: "Hint",
    size: "small",
    autoResize: true,
    maxHeight: (75),
}));
const __VLS_16 = __VLS_15({
    modelValue: (__VLS_ctx.data.value),
    fluid: true,
    rows: "1",
    placeholder: "Hint",
    size: "small",
    autoResize: true,
    maxHeight: (75),
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
// @ts-ignore
[data,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
