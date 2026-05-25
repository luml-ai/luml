/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { DataTable, Column, Button } from 'primevue';
import { ExternalLink } from 'lucide-vue-next';
import { useNotebooksStore } from '@/stores/notebooks';
import NotebookListActions from './NotebookListActions.vue';
import NotebooksModelsTable from './NotebooksModelsTable.vue';
const notebooksStore = useNotebooksStore();
const expandedRows = ref({});
const getLink = computed(() => (databaseName) => import.meta.env.BASE_URL + 'jupyter/lab/index.html?instanceId=' + databaseName);
const __VLS_ctx = {
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
    expandedRows: (__VLS_ctx.expandedRows),
    dataKey: "name",
    value: (__VLS_ctx.notebooksStore.notebooks),
    tableStyle: "min-width: 50rem;",
    ...{ class: "notebooks-table" },
}));
const __VLS_2 = __VLS_1({
    expandedRows: (__VLS_ctx.expandedRows),
    dataKey: "name",
    value: (__VLS_ctx.notebooksStore.notebooks),
    tableStyle: "min-width: 50rem;",
    ...{ class: "notebooks-table" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
/** @type {__VLS_StyleScopedClasses['notebooks-table']} */ ;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { empty: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
    // @ts-ignore
    [expandedRows, notebooksStore,];
}
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    expander: true,
    ...{ style: {} },
}));
const __VLS_10 = __VLS_9({
    expander: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    field: "fullname",
    header: "Instance name",
    ...{ style: {} },
}));
const __VLS_15 = __VLS_14({
    field: "fullname",
    header: "Instance name",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    field: "createdAt",
    header: "Created",
}));
const __VLS_20 = __VLS_19({
    field: "createdAt",
    header: "Created",
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
const { default: __VLS_23 } = __VLS_21.slots;
{
    const { body: __VLS_24 } = __VLS_21.slots;
    const [slot] = __VLS_vSlot(__VLS_24);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (new Date(slot.data.createdAt).toLocaleString());
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_21;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    field: "name",
    header: "Link",
    ...{ style: {} },
    pt: ({ headerCell: { style: 'padding-left: 36px' } }),
}));
const __VLS_27 = __VLS_26({
    field: "name",
    header: "Link",
    ...{ style: {} },
    pt: ({ headerCell: { style: 'padding-left: 36px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
const { default: __VLS_30 } = __VLS_28.slots;
{
    const { body: __VLS_31 } = __VLS_28.slots;
    const [slot] = __VLS_vSlot(__VLS_31);
    let __VLS_32;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
        as: "a",
        variant: "text",
        target: "_blank",
        href: (__VLS_ctx.getLink(slot.data.name)),
    }));
    const __VLS_34 = __VLS_33({
        as: "a",
        variant: "text",
        target: "_blank",
        href: (__VLS_ctx.getLink(slot.data.name)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    const { default: __VLS_37 } = __VLS_35.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    let __VLS_38;
    /** @ts-ignore @type { | typeof __VLS_components.ExternalLink} */
    ExternalLink;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
        size: (14),
    }));
    const __VLS_40 = __VLS_39({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
    // @ts-ignore
    [getLink,];
    var __VLS_35;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_28;
let __VLS_43;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
    ...{ style: {} },
}));
const __VLS_45 = __VLS_44({
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_44));
const { default: __VLS_48 } = __VLS_46.slots;
{
    const { body: __VLS_49 } = __VLS_46.slots;
    const [slot] = __VLS_vSlot(__VLS_49);
    const __VLS_50 = NotebookListActions || NotebookListActions;
    // @ts-ignore
    const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
        notebook: (slot.data),
    }));
    const __VLS_52 = __VLS_51({
        notebook: (slot.data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_51));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_46;
{
    const { expansion: __VLS_55 } = __VLS_3.slots;
    const [slotProps] = __VLS_vSlot(__VLS_55);
    const __VLS_56 = NotebooksModelsTable || NotebooksModelsTable;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent1(__VLS_56, new __VLS_56({
        files: (slotProps.data.files),
    }));
    const __VLS_58 = __VLS_57({
        files: (slotProps.data.files),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
