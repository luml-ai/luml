/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useToast, } from 'primevue';
import { DataTable, Column } from 'primevue';
import { ArtifactStatusEnum, } from '@/lib/api/artifacts/interfaces';
import { computed, onBeforeMount, reactive, ref, watch } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useRouter, useRoute } from 'vue-router';
import { useCollectionsStore } from '@/stores/collections';
import { columnBodyStyle, TABLE_PT, TYPE_COLUMN_PT } from './models-table.data';
import { useArtifactsList } from '@/hooks/useArtifactsList';
import { getErrorMessage, getSizeText } from '@/helpers/helpers';
import { useDebounceFn } from '@vueuse/core';
import { FilterMatchMode } from '@primevue/core/api';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
import TableToolbar from './TableToolbar.vue';
import TagsList from './TagsList.vue';
import NameColumnBody from './NameColumnBody.vue';
import StatusColumnBody from './StatusColumnBody.vue';
import TypeColumnBody from './TypeColumnBody.vue';
import TypeColumnFilter from './TypeColumnFilter.vue';
const INITIAL_VISIBLE_METRICS_COUNT = 20;
const artifactsStore = useArtifactsStore();
const toast = useToast();
const router = useRouter();
const route = useRoute();
const collectionsStore = useCollectionsStore();
const { setRequestInfo, getInitialPage, list, reset, onLazyLoad, setSortData, isLoading, setLoading, setTypesQuery, } = useArtifactsList();
const selectedArtifacts = ref([]);
const allMetricsKeys = ref([]);
const visibleMetrics = ref([]);
const filters = reactive({
    type: { value: [], matchMode: FilterMatchMode.CONTAINS },
});
const showLoader = computed(() => {
    return isLoading.value && list.value.length === 0;
});
const showTypeFilter = computed(() => {
    return collectionsStore.currentCollection?.type === OrbitCollectionTypeEnum.mixed;
});
const virtualScrollerOptions = ref({
    lazy: true,
    onLazyLoad: onLazyLoad,
    itemSize: 62,
    scrollHeight: 'calc(100vh - 330px)',
});
function onRowClick(event) {
    const target = event.originalEvent.target;
    const artifactId = event.data.id;
    const isArtifactUploaded = event.data.status === ArtifactStatusEnum.uploaded;
    if (!target || !artifactId || !isArtifactUploaded)
        return;
    const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]');
    if (rowIncludeCheckbox)
        return;
    router.push({ name: 'artifact', params: { artifactId } });
}
function resetSelectedArtifacts() {
    selectedArtifacts.value = [];
}
async function getMetricsKeys() {
    try {
        const metrics = await artifactsStore.getArtifactsExtraValues();
        allMetricsKeys.value = metrics;
        visibleMetrics.value = allMetricsKeys.value.slice(0, INITIAL_VISIBLE_METRICS_COUNT);
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load metrics')));
    }
}
async function initList() {
    try {
        setLoading(true);
        reset();
        resetSelectedArtifacts();
        await getMetricsKeys();
        setRequestInfo({
            organizationId: String(route.params.organizationId),
            orbitId: String(route.params.id),
            collectionId: String(collectionsStore.currentCollection?.id),
        });
        await getInitialPage();
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load artifacts')));
    }
    finally {
        setLoading(false);
    }
}
const updateSelectedMetrics = useDebounceFn((metrics) => {
    if (!metrics) {
        visibleMetrics.value = [];
        return;
    }
    visibleMetrics.value = metrics;
}, 500);
function onSort(event) {
    const sortData = {
        sort_by: event.sortField,
        order: event.sortOrder === 1 ? 'asc' : 'desc',
    };
    setSortData(sortData);
}
watch(list, (data) => {
    if (!selectedArtifacts.value.length)
        return;
    selectedArtifacts.value = selectedArtifacts.value.map((artifact) => data.find((updatedArtifact) => artifact.id === updatedArtifact.id) || artifact);
});
watch(filters, (newFilters) => {
    setTypesQuery(newFilters.type.value);
});
onBeforeMount(initList);
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
const __VLS_0 = TableToolbar || TableToolbar;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:selectedMetrics': {} },
    ...{ 'onClearSelectedArtifacts': {} },
    selectedMetrics: (__VLS_ctx.visibleMetrics),
    selectedArtifacts: (__VLS_ctx.selectedArtifacts),
    metrics: (__VLS_ctx.allMetricsKeys),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:selectedMetrics': {} },
    ...{ 'onClearSelectedArtifacts': {} },
    selectedMetrics: (__VLS_ctx.visibleMetrics),
    selectedArtifacts: (__VLS_ctx.selectedArtifacts),
    metrics: (__VLS_ctx.allMetricsKeys),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:selectedMetrics': {} },
    { 'onUpdate:selectedMetrics': ((val) => __VLS_ctx.updateSelectedMetrics(val)) });
const __VLS_7 = ({ clearSelectedArtifacts: {} },
    { onClearSelectedArtifacts: (__VLS_ctx.resetSelectedArtifacts) });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
DataTable;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    ...{ 'onRowClick': {} },
    ...{ 'onSort': {} },
    selection: (__VLS_ctx.selectedArtifacts),
    filters: (__VLS_ctx.filters),
    filterDisplay: "menu",
    value: (__VLS_ctx.list),
    pt: (__VLS_ctx.TABLE_PT),
    selectionMode: "multiple",
    dataKey: "id",
    ...{ class: "table-white" },
    scrollable: true,
    scrollHeight: "calc(100vh - 340px)",
    loading: (__VLS_ctx.showLoader),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}));
const __VLS_10 = __VLS_9({
    ...{ 'onRowClick': {} },
    ...{ 'onSort': {} },
    selection: (__VLS_ctx.selectedArtifacts),
    filters: (__VLS_ctx.filters),
    filterDisplay: "menu",
    value: (__VLS_ctx.list),
    pt: (__VLS_ctx.TABLE_PT),
    selectionMode: "multiple",
    dataKey: "id",
    ...{ class: "table-white" },
    scrollable: true,
    scrollHeight: "calc(100vh - 340px)",
    loading: (__VLS_ctx.showLoader),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_13;
const __VLS_14 = ({ rowClick: {} },
    { onRowClick: (__VLS_ctx.onRowClick) });
const __VLS_15 = ({ sort: {} },
    { onSort: (__VLS_ctx.onSort) });
/** @type {__VLS_StyleScopedClasses['table-white']} */ ;
const { default: __VLS_16 } = __VLS_11.slots;
{
    const { empty: __VLS_17 } = __VLS_11.slots;
    if (!__VLS_ctx.isLoading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "placeholder" },
        });
        /** @type {__VLS_StyleScopedClasses['placeholder']} */ ;
    }
    // @ts-ignore
    [visibleMetrics, selectedArtifacts, selectedArtifacts, allMetricsKeys, updateSelectedMetrics, resetSelectedArtifacts, filters, list, TABLE_PT, showLoader, virtualScrollerOptions, onRowClick, onSort, isLoading,];
}
let __VLS_18;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
    selectionMode: "multiple",
}));
const __VLS_20 = __VLS_19({
    selectionMode: "multiple",
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
let __VLS_23;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    field: "name",
    header: "Name",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 180px' } }),
}));
const __VLS_25 = __VLS_24({
    field: "name",
    header: "Name",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 180px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
const { default: __VLS_28 } = __VLS_26.slots;
{
    const { body: __VLS_29 } = __VLS_26.slots;
    const [{ data }] = __VLS_vSlot(__VLS_29, (_) => []);
    const __VLS_30 = NameColumnBody;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
        name: (data.name),
        id: (data.id),
        columnBodyStyle: (__VLS_ctx.columnBodyStyle),
    }));
    const __VLS_32 = __VLS_31({
        name: (data.name),
        id: (data.id),
        columnBodyStyle: (__VLS_ctx.columnBodyStyle),
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    // @ts-ignore
    [columnBodyStyle,];
}
// @ts-ignore
[];
var __VLS_26;
let __VLS_35;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
    field: "type",
    header: "Type",
    pt: (__VLS_ctx.TYPE_COLUMN_PT),
    showFilterOperator: (true),
    showFilterMenu: (__VLS_ctx.showTypeFilter),
}));
const __VLS_37 = __VLS_36({
    field: "type",
    header: "Type",
    pt: (__VLS_ctx.TYPE_COLUMN_PT),
    showFilterOperator: (true),
    showFilterMenu: (__VLS_ctx.showTypeFilter),
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
const { default: __VLS_40 } = __VLS_38.slots;
{
    const { body: __VLS_41 } = __VLS_38.slots;
    const [{ data }] = __VLS_vSlot(__VLS_41, (_) => []);
    const __VLS_42 = TypeColumnBody;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
        data: (data),
    }));
    const __VLS_44 = __VLS_43({
        data: (data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    // @ts-ignore
    [TYPE_COLUMN_PT, showTypeFilter,];
}
{
    const { filterheader: __VLS_47 } = __VLS_38.slots;
    const __VLS_48 = TypeColumnFilter;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent1(__VLS_48, new __VLS_48({
        modelValue: (__VLS_ctx.filters.type.value),
    }));
    const __VLS_50 = __VLS_49({
        modelValue: (__VLS_ctx.filters.type.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    // @ts-ignore
    [filters,];
}
{
    const { filter: __VLS_53 } = __VLS_38.slots;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_38;
let __VLS_54;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent1(__VLS_54, new __VLS_54({
    field: "created_at",
    header: "Creation time",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 180px' } }),
}));
const __VLS_56 = __VLS_55({
    field: "created_at",
    header: "Creation time",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 180px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
const { default: __VLS_59 } = __VLS_57.slots;
{
    const { body: __VLS_60 } = __VLS_57.slots;
    const [{ data }] = __VLS_vSlot(__VLS_60, (_) => []);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: (__VLS_ctx.columnBodyStyle + 'width: 180px') },
    });
    (new Date(data.created_at).toLocaleString());
    // @ts-ignore
    [columnBodyStyle,];
}
// @ts-ignore
[];
var __VLS_57;
let __VLS_61;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent1(__VLS_61, new __VLS_61({
    field: "description",
    header: "Description",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 203px' } }),
}));
const __VLS_63 = __VLS_62({
    field: "description",
    header: "Description",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 203px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
const { default: __VLS_66 } = __VLS_64.slots;
{
    const { body: __VLS_67 } = __VLS_64.slots;
    const [{ data }] = __VLS_vSlot(__VLS_67, (_) => []);
    if (data.description) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "description" },
            ...{ style: {} },
        });
        __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: (data.description) }, null, null);
        /** @type {__VLS_StyleScopedClasses['description']} */ ;
        (data.description);
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    }
    // @ts-ignore
    [vTooltip,];
}
// @ts-ignore
[];
var __VLS_64;
let __VLS_68;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent1(__VLS_68, new __VLS_68({
    field: "status",
    header: "Status",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 150px' } }),
}));
const __VLS_70 = __VLS_69({
    field: "status",
    header: "Status",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 150px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
const { default: __VLS_73 } = __VLS_71.slots;
{
    const { body: __VLS_74 } = __VLS_71.slots;
    const [{ data }] = __VLS_vSlot(__VLS_74, (_) => []);
    const __VLS_75 = StatusColumnBody;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
        status: (data.status),
    }));
    const __VLS_77 = __VLS_76({
        status: (data.status),
    }, ...__VLS_functionalComponentArgsRest(__VLS_76));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_71;
let __VLS_80;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent1(__VLS_80, new __VLS_80({
    field: "tags",
    header: "Tags",
    pt: ({ columnHeaderContent: { style: 'width: 203px' } }),
}));
const __VLS_82 = __VLS_81({
    field: "tags",
    header: "Tags",
    pt: ({ columnHeaderContent: { style: 'width: 203px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
const { default: __VLS_85 } = __VLS_83.slots;
{
    const { body: __VLS_86 } = __VLS_83.slots;
    const [{ data }] = __VLS_vSlot(__VLS_86, (_) => []);
    if (data.tags) {
        const __VLS_87 = TagsList;
        // @ts-ignore
        const __VLS_88 = __VLS_asFunctionalComponent1(__VLS_87, new __VLS_87({
            tags: (data.tags),
        }));
        const __VLS_89 = __VLS_88({
            tags: (data.tags),
        }, ...__VLS_functionalComponentArgsRest(__VLS_88));
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_83;
let __VLS_92;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent1(__VLS_92, new __VLS_92({
    field: "size",
    header: "Size",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 100px' } }),
}));
const __VLS_94 = __VLS_93({
    field: "size",
    header: "Size",
    sortable: true,
    pt: ({ columnHeaderContent: { style: 'width: 100px' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
const { default: __VLS_97 } = __VLS_95.slots;
{
    const { body: __VLS_98 } = __VLS_95.slots;
    const [{ data }] = __VLS_vSlot(__VLS_98, (_) => []);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ style: (__VLS_ctx.columnBodyStyle + 'width: 100px') },
    });
    (__VLS_ctx.getSizeText(data.size));
    // @ts-ignore
    [columnBodyStyle, getSizeText,];
}
// @ts-ignore
[];
var __VLS_95;
for (const [key] of __VLS_vFor((__VLS_ctx.visibleMetrics))) {
    let __VLS_99;
    /** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
    Column;
    // @ts-ignore
    const __VLS_100 = __VLS_asFunctionalComponent1(__VLS_99, new __VLS_99({
        key: (key),
        header: (key),
        field: (key),
        sortable: true,
        pt: ({ columnHeaderContent: { style: 'width: 100px' } }),
    }));
    const __VLS_101 = __VLS_100({
        key: (key),
        header: (key),
        field: (key),
        sortable: true,
        pt: ({ columnHeaderContent: { style: 'width: 100px' } }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_100));
    const { default: __VLS_104 } = __VLS_102.slots;
    {
        const { body: __VLS_105 } = __VLS_102.slots;
        const [{ data }] = __VLS_vSlot(__VLS_105, (_) => []);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "metric-column" },
            ...{ style: {} },
        });
        __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: (key in data.extra_values ? '' + data.extra_values[key] : null) }, null, null);
        /** @type {__VLS_StyleScopedClasses['metric-column']} */ ;
        (key in data.extra_values ? data.extra_values[key] : '-');
        // @ts-ignore
        [visibleMetrics, vTooltip,];
    }
    // @ts-ignore
    [];
    var __VLS_102;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_11;
var __VLS_12;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
