/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { useDatasetsStore } from '@/stores/datasets';
import { getShortcutCountText } from '@/helpers/text';
import DatasetDataSelect from './DatasetDataSelect.vue';
import DatasetDataTable from './DatasetDataTable.vue';
const datasetsStore = useDatasetsStore();
const subsetsHeading = computed(() => {
    return `Subset (${datasetsStore.subsets.length})`;
});
const splitsHeading = computed(() => {
    return `Split (${datasetsStore.splitsList.length})`;
});
const subsetOptions = computed(() => {
    return datasetsStore.subsets.map((subset) => ({
        label: `${subset.name} (${getShortcutCountText(subset.num_rows)} rows)`,
        value: subset.name,
    }));
});
const splitOptions = computed(() => {
    return datasetsStore.splitsList.map((split) => ({
        label: `${split.name} (${getShortcutCountText(split.num_rows)} rows)`,
        value: split.name,
    }));
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "selectors" },
});
/** @type {__VLS_StyleScopedClasses['selectors']} */ ;
if (__VLS_ctx.datasetsStore.selectedSubset) {
    const __VLS_0 = DatasetDataSelect;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (__VLS_ctx.datasetsStore.selectedSubset.name),
        heading: (__VLS_ctx.subsetsHeading),
        name: (__VLS_ctx.datasetsStore.selectedSubset.name),
        text: (`${__VLS_ctx.getShortcutCountText(__VLS_ctx.datasetsStore.selectedSubset.num_rows)} rows`),
        options: (__VLS_ctx.subsetOptions),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (__VLS_ctx.datasetsStore.selectedSubset.name),
        heading: (__VLS_ctx.subsetsHeading),
        name: (__VLS_ctx.datasetsStore.selectedSubset.name),
        text: (`${__VLS_ctx.getShortcutCountText(__VLS_ctx.datasetsStore.selectedSubset.num_rows)} rows`),
        options: (__VLS_ctx.subsetOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ 'update:modelValue': {} },
        { 'onUpdate:modelValue': (...[$event]) => {
                if (!(__VLS_ctx.datasetsStore.selectedSubset))
                    return;
                __VLS_ctx.datasetsStore.setSelectedSubset($event);
                // @ts-ignore
                [datasetsStore, datasetsStore, datasetsStore, datasetsStore, datasetsStore, subsetsHeading, getShortcutCountText, subsetOptions,];
            } });
    var __VLS_3;
    var __VLS_4;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "separator" },
});
/** @type {__VLS_StyleScopedClasses['separator']} */ ;
if (__VLS_ctx.datasetsStore.selectedSplit) {
    const __VLS_7 = DatasetDataSelect;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (__VLS_ctx.datasetsStore.selectedSplit.name),
        heading: (__VLS_ctx.splitsHeading),
        name: (__VLS_ctx.datasetsStore.selectedSplit.name),
        text: (`${__VLS_ctx.getShortcutCountText(__VLS_ctx.datasetsStore.selectedSplit.num_rows)} rows`),
        options: (__VLS_ctx.splitOptions),
    }));
    const __VLS_9 = __VLS_8({
        ...{ 'onUpdate:modelValue': {} },
        modelValue: (__VLS_ctx.datasetsStore.selectedSplit.name),
        heading: (__VLS_ctx.splitsHeading),
        name: (__VLS_ctx.datasetsStore.selectedSplit.name),
        text: (`${__VLS_ctx.getShortcutCountText(__VLS_ctx.datasetsStore.selectedSplit.num_rows)} rows`),
        options: (__VLS_ctx.splitOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    let __VLS_12;
    const __VLS_13 = ({ 'update:modelValue': {} },
        { 'onUpdate:modelValue': (...[$event]) => {
                if (!(__VLS_ctx.datasetsStore.selectedSplit))
                    return;
                __VLS_ctx.datasetsStore.setSelectedSplit($event);
                // @ts-ignore
                [datasetsStore, datasetsStore, datasetsStore, datasetsStore, datasetsStore, getShortcutCountText, splitsHeading, splitOptions,];
            } });
    var __VLS_10;
    var __VLS_11;
}
const __VLS_14 = DatasetDataTable;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({}));
const __VLS_16 = __VLS_15({}, ...__VLS_functionalComponentArgsRest(__VLS_15));
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
