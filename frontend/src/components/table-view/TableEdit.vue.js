/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PenLine } from 'lucide-vue-next';
import TableEditColumns from '../table/TableEditColumns.vue';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
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
const __VLS_0 = TableEditColumns || TableEditColumns;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onEdit': {} },
    target: (__VLS_ctx.target),
    columns: (__VLS_ctx.columns),
    selectedColumns: (__VLS_ctx.selectedColumns),
    roundedButton: (true),
    buttonIcon: (__VLS_ctx.PenLine),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onEdit': {} },
    target: (__VLS_ctx.target),
    columns: (__VLS_ctx.columns),
    selectedColumns: (__VLS_ctx.selectedColumns),
    roundedButton: (true),
    buttonIcon: (__VLS_ctx.PenLine),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ edit: {} },
    { onEdit: ((data) => __VLS_ctx.$emit('edit', data)) });
var __VLS_7;
var __VLS_3;
var __VLS_4;
// @ts-ignore
[target, columns, selectedColumns, PenLine, $emit,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
