/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import TableSort from './TableSort.vue';
import TableFilters from './TableFilters.vue';
import TableEdit from './TableEdit.vue';
import TableColumnHeader from './TableColumnHeader.vue';
import TableInputOutputs from './TableInputOutputs.vue';
import { CloudDownload } from 'lucide-vue-next';
import { DataTable, Column } from 'primevue';
import { computed, onBeforeMount, onBeforeUnmount, ref } from 'vue';
import { cutStringOnMiddle } from '@/helpers/helpers';
const props = defineProps();
const __VLS_emit = defineEmits();
const multiSortMeta = ref([]);
const tableHeight = ref(0);
const currentColumns = computed(() => (props.value.length ? Object.keys(props.value[0]) : []));
const dataForFilters = computed(() => {
    return props.allColumns.map((key) => ({
        name: key,
        type: (props.columnTypes[key] === 'number' ? 'number' : 'string'),
    }));
});
function calcTableHeight() {
    let minusValue = 0;
    if (window.innerWidth > 992)
        minusValue = 305;
    else if (window.innerWidth > 768)
        minusValue = 345;
    else {
        minusValue = 300;
    }
    tableHeight.value = document.documentElement.clientHeight - minusValue;
}
onBeforeMount(() => {
    calcTableHeight();
    window.addEventListener('resize', calcTableHeight);
});
onBeforeUnmount(() => {
    window.removeEventListener('resize', calcTableHeight);
});
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
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-left" },
});
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-info" },
});
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.columnsCount);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-info" },
});
/** @type {__VLS_StyleScopedClasses['header-info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.value.length);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-right" },
});
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
if (__VLS_ctx.inputsOutputsColumns) {
    const __VLS_0 = TableInputOutputs;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        columns: (__VLS_ctx.inputsOutputsColumns),
        columnTypes: (__VLS_ctx.columnTypes),
        selectedColumns: (__VLS_ctx.selectedColumns),
    }));
    const __VLS_2 = __VLS_1({
        columns: (__VLS_ctx.inputsOutputsColumns),
        columnTypes: (__VLS_ctx.columnTypes),
        selectedColumns: (__VLS_ctx.selectedColumns),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
const __VLS_5 = TableSort;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    columns: (__VLS_ctx.currentColumns),
    multiSortMeta: (__VLS_ctx.multiSortMeta),
}));
const __VLS_7 = __VLS_6({
    columns: (__VLS_ctx.currentColumns),
    multiSortMeta: (__VLS_ctx.multiSortMeta),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
if (__VLS_ctx.filters) {
    const __VLS_10 = TableFilters;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ 'onApply': {} },
        data: (__VLS_ctx.dataForFilters),
        filters: (__VLS_ctx.filters),
        columnTypes: (__VLS_ctx.columnTypes),
    }));
    const __VLS_12 = __VLS_11({
        ...{ 'onApply': {} },
        data: (__VLS_ctx.dataForFilters),
        filters: (__VLS_ctx.filters),
        columnTypes: (__VLS_ctx.columnTypes),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    let __VLS_15;
    const __VLS_16 = ({ apply: {} },
        { onApply: ((event) => __VLS_ctx.$emit('changeFilters', event)) });
    var __VLS_13;
    var __VLS_14;
}
const __VLS_17 = TableEdit;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
    ...{ 'onEdit': {} },
    columns: (__VLS_ctx.allColumns),
    selectedColumns: (__VLS_ctx.selectedColumns),
    target: (__VLS_ctx.target),
}));
const __VLS_19 = __VLS_18({
    ...{ 'onEdit': {} },
    columns: (__VLS_ctx.allColumns),
    selectedColumns: (__VLS_ctx.selectedColumns),
    target: (__VLS_ctx.target),
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
let __VLS_22;
const __VLS_23 = ({ edit: {} },
    { onEdit: ((event) => __VLS_ctx.$emit('edit', event)) });
var __VLS_20;
var __VLS_21;
let __VLS_24;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "outlined",
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "outlined",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_29;
const __VLS_30 = ({ click: {} },
    { onClick: (__VLS_ctx.exportCallback) });
const { default: __VLS_31 } = __VLS_27.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "button-label" },
});
/** @type {__VLS_StyleScopedClasses['button-label']} */ ;
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.CloudDownload} */
CloudDownload;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    width: "14",
    height: "14",
}));
const __VLS_34 = __VLS_33({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
// @ts-ignore
[columnsCount, value, inputsOutputsColumns, inputsOutputsColumns, columnTypes, columnTypes, selectedColumns, selectedColumns, currentColumns, multiSortMeta, filters, filters, dataForFilters, $emit, $emit, allColumns, target, exportCallback,];
var __VLS_27;
var __VLS_28;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ style: ({ height: __VLS_ctx.tableHeight + 'px' }) },
});
if (__VLS_ctx.value.length) {
    let __VLS_37;
    /** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
    DataTable;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        value: (__VLS_ctx.value),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: (__VLS_ctx.tableHeight + 'px'),
        multiSortMeta: (__VLS_ctx.multiSortMeta),
        sortMode: "multiple",
        virtualScrollerOptions: ({ itemSize: 31 }),
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }));
    const __VLS_39 = __VLS_38({
        value: (__VLS_ctx.value),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: (__VLS_ctx.tableHeight + 'px'),
        multiSortMeta: (__VLS_ctx.multiSortMeta),
        sortMode: "multiple",
        virtualScrollerOptions: ({ itemSize: 31 }),
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    const { default: __VLS_42 } = __VLS_40.slots;
    for (const [column] of __VLS_vFor((__VLS_ctx.currentColumns))) {
        let __VLS_43;
        /** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
        Column;
        // @ts-ignore
        const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
            id: (column),
            field: (column),
            ...{ style: {} },
        }));
        const __VLS_45 = __VLS_44({
            id: (column),
            field: (column),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_44));
        const { default: __VLS_48 } = __VLS_46.slots;
        {
            const { header: __VLS_49 } = __VLS_46.slots;
            const __VLS_50 = TableColumnHeader;
            // @ts-ignore
            const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
                ...{ 'onChangeGroup': {} },
                ...{ 'onSetTarget': {} },
                values: (__VLS_ctx.value),
                column: (__VLS_ctx.cutStringOnMiddle(column)),
                group: (__VLS_ctx.group),
                target: (__VLS_ctx.target),
                columnType: (__VLS_ctx.columnTypes[column]),
                showMenu: (__VLS_ctx.showColumnHeaderMenu),
                inputsOutputsColumns: (__VLS_ctx.inputsOutputsColumns),
            }));
            const __VLS_52 = __VLS_51({
                ...{ 'onChangeGroup': {} },
                ...{ 'onSetTarget': {} },
                values: (__VLS_ctx.value),
                column: (__VLS_ctx.cutStringOnMiddle(column)),
                group: (__VLS_ctx.group),
                target: (__VLS_ctx.target),
                columnType: (__VLS_ctx.columnTypes[column]),
                showMenu: (__VLS_ctx.showColumnHeaderMenu),
                inputsOutputsColumns: (__VLS_ctx.inputsOutputsColumns),
            }, ...__VLS_functionalComponentArgsRest(__VLS_51));
            let __VLS_55;
            const __VLS_56 = ({ changeGroup: {} },
                { onChangeGroup: ((event) => __VLS_ctx.$emit('changeGroup', event)) });
            const __VLS_57 = ({ setTarget: {} },
                { onSetTarget: ((event) => __VLS_ctx.$emit('setTarget', event)) });
            var __VLS_53;
            var __VLS_54;
            // @ts-ignore
            [value, value, value, inputsOutputsColumns, columnTypes, currentColumns, multiSortMeta, $emit, $emit, target, tableHeight, tableHeight, cutStringOnMiddle, group, showColumnHeaderMenu,];
        }
        // @ts-ignore
        [];
        var __VLS_46;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_40;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
