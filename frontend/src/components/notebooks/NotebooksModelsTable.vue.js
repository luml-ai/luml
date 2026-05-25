/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { DataTable, Column } from 'primevue';
import NotebooksModelAction from './NotebooksModelAction.vue';
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
/** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
DataTable;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    value: (__VLS_ctx.files),
}));
const __VLS_2 = __VLS_1({
    value: (__VLS_ctx.files),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { empty: __VLS_7 } = __VLS_3.slots;
    // @ts-ignore
    [files,];
}
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    field: "name",
    header: "Model name",
}));
const __VLS_10 = __VLS_9({
    field: "name",
    header: "Model name",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    field: "size",
    header: "Size",
}));
const __VLS_15 = __VLS_14({
    field: "size",
    header: "Size",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
{
    const { body: __VLS_19 } = __VLS_16.slots;
    const [slotProps] = __VLS_vSlot(__VLS_19);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (slotProps.data.size < 1000
        ? slotProps.data.size + ' B'
        : slotProps.data.size < 10000000
            ? slotProps.data.size / 1000 + ' KB'
            : slotProps.data.size / 10000000 + ' MB');
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_16;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    field: "created",
    header: "Created",
}));
const __VLS_22 = __VLS_21({
    field: "created",
    header: "Created",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
const { default: __VLS_25 } = __VLS_23.slots;
{
    const { body: __VLS_26 } = __VLS_23.slots;
    const [slotProps] = __VLS_vSlot(__VLS_26);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (new Date(slotProps.data.created).toLocaleString());
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_23;
let __VLS_27;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
    ...{ style: {} },
}));
const __VLS_29 = __VLS_28({
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_28));
const { default: __VLS_32 } = __VLS_30.slots;
{
    const { body: __VLS_33 } = __VLS_30.slots;
    const [$slot] = __VLS_vSlot(__VLS_33);
    const __VLS_34 = NotebooksModelAction || NotebooksModelAction;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
        file: ($slot.data),
    }));
    const __VLS_36 = __VLS_35({
        file: ($slot.data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_30;
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
