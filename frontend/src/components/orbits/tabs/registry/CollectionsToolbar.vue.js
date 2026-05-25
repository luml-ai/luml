/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { IconField, InputText, InputIcon, MultiSelect } from 'primevue';
import { Search } from 'lucide-vue-next';
import { COLLECTION_TYPE_OPTIONS, COLLECTION_TYPE_SELECT_PT } from './collection.const';
const search = defineModel('search');
const types = defineModel('types', { default: [] });
function updateSearch(val) {
    search.value = val;
}
const __VLS_defaultModels = {
    'types': [],
};
let __VLS_modelEmit;
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
/** @type {__VLS_StyleScopedClasses['p-iconfield']} */ ;
/** @type {__VLS_StyleScopedClasses['p-iconfield']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "toolbar" },
});
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.IconField | typeof __VLS_components.IconField} */
IconField;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
let __VLS_6;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.search),
    size: "small",
    placeholder: "Search",
}));
const __VLS_8 = __VLS_7({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.search),
    size: "small",
    placeholder: "Search",
}, ...__VLS_functionalComponentArgsRest(__VLS_7));
let __VLS_11;
const __VLS_12 = ({ 'update:modelValue': {} },
    { 'onUpdate:modelValue': (__VLS_ctx.updateSearch) });
var __VLS_9;
var __VLS_10;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.InputIcon | typeof __VLS_components.InputIcon} */
InputIcon;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({}));
const __VLS_15 = __VLS_14({}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
let __VLS_19;
/** @ts-ignore @type { | typeof __VLS_components.Search} */
Search;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
    size: (12),
}));
const __VLS_21 = __VLS_20({
    size: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
// @ts-ignore
[search, updateSearch,];
var __VLS_16;
// @ts-ignore
[];
var __VLS_3;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.MultiSelect} */
MultiSelect;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    modelValue: (__VLS_ctx.types),
    options: (__VLS_ctx.COLLECTION_TYPE_OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    size: "small",
    placeholder: "Filter by type",
    pt: (__VLS_ctx.COLLECTION_TYPE_SELECT_PT),
}));
const __VLS_26 = __VLS_25({
    modelValue: (__VLS_ctx.types),
    options: (__VLS_ctx.COLLECTION_TYPE_OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    size: "small",
    placeholder: "Filter by type",
    pt: (__VLS_ctx.COLLECTION_TYPE_SELECT_PT),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
// @ts-ignore
[types, COLLECTION_TYPE_OPTIONS, COLLECTION_TYPE_SELECT_PT,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
