/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useDatasetsStore } from '@/stores/datasets';
import { DataTable, Column } from 'primevue';
import { computed, nextTick, ref, watch } from 'vue';
import DatasetDataTableCell from './DatasetDataTableCell.vue';
const datasetsStore = useDatasetsStore();
const dataTableRef = ref();
const totalRecords = computed(() => {
    return datasetsStore.selectedSplit?.num_rows || 0;
});
function onPageChange(event) {
    datasetsStore.setCurrentPage(event.page);
}
function resetScroll() {
    const el = dataTableRef.value?.$el;
    const scrollBody = el?.querySelector('.p-datatable-table-container');
    if (scrollBody) {
        scrollBody.scrollTop = 0;
    }
}
watch(() => datasetsStore.tableRows, async () => {
    await nextTick();
    resetScroll();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "table-container" },
});
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
if (__VLS_ctx.datasetsStore.tableColumns.length) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
    DataTable;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onPage': {} },
        ref: "dataTableRef",
        value: (__VLS_ctx.datasetsStore.tableRows),
        rows: (__VLS_ctx.datasetsStore.rowsPerPage),
        totalRecords: (__VLS_ctx.totalRecords),
        loading: (__VLS_ctx.datasetsStore.loading),
        paginator: true,
        lazy: true,
        showGridlines: true,
        paginatorTemplate: "FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink",
        currentPageReportTemplate: "Show {first}-{last} of {totalRecords}",
        scrollable: true,
        scrollHeight: "calc(100vh - 535px)",
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onPage': {} },
        ref: "dataTableRef",
        value: (__VLS_ctx.datasetsStore.tableRows),
        rows: (__VLS_ctx.datasetsStore.rowsPerPage),
        totalRecords: (__VLS_ctx.totalRecords),
        loading: (__VLS_ctx.datasetsStore.loading),
        paginator: true,
        lazy: true,
        showGridlines: true,
        paginatorTemplate: "FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink",
        currentPageReportTemplate: "Show {first}-{last} of {totalRecords}",
        scrollable: true,
        scrollHeight: "calc(100vh - 535px)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ page: {} },
        { onPage: (__VLS_ctx.onPageChange) });
    var __VLS_7;
    const { default: __VLS_9 } = __VLS_3.slots;
    for (const [col] of __VLS_vFor((__VLS_ctx.datasetsStore.tableColumns))) {
        let __VLS_10;
        /** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
        Column;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            key: (col),
            field: (col),
            header: (col),
        }));
        const __VLS_12 = __VLS_11({
            key: (col),
            field: (col),
            header: (col),
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        const { default: __VLS_15 } = __VLS_13.slots;
        {
            const { body: __VLS_16 } = __VLS_13.slots;
            const [slotProps] = __VLS_vSlot(__VLS_16);
            const __VLS_17 = DatasetDataTableCell;
            // @ts-ignore
            const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
                value: (slotProps.data[col]),
            }));
            const __VLS_19 = __VLS_18({
                value: (slotProps.data[col]),
            }, ...__VLS_functionalComponentArgsRest(__VLS_18));
            // @ts-ignore
            [datasetsStore, datasetsStore, datasetsStore, datasetsStore, datasetsStore, totalRecords, onPageChange,];
        }
        // @ts-ignore
        [];
        var __VLS_13;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
}
// @ts-ignore
var __VLS_8 = __VLS_7;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
