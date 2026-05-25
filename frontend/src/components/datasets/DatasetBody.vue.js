/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { getErrorMessage } from '@/helpers/helpers';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useDatasetsStore } from '@/stores/datasets';
import { Skeleton, useToast } from 'primevue';
import { onBeforeMount, watch } from 'vue';
import DatasetContent from './DatasetContent.vue';
const datasetsStore = useDatasetsStore();
const toast = useToast();
function setFirstSubset() {
    if (datasetsStore.subsets.length > 0) {
        datasetsStore.setSelectedSubset(datasetsStore.subsets[0].name);
    }
    else {
        datasetsStore.setSelectedSubset(null);
    }
}
function setFirstSplit() {
    if (datasetsStore.splitsList.length > 0) {
        datasetsStore.setSelectedSplit(datasetsStore.splitsList[0].name);
        datasetsStore.setCurrentPage(0);
    }
    else {
        datasetsStore.setSelectedSplit(null);
    }
}
async function init() {
    await datasetsStore.init();
    setFirstSubset();
}
onBeforeMount(async () => {
    if (datasetsStore.isInitialized)
        return;
    try {
        await init();
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to initialize datasets');
        toast.add(simpleErrorToast(message));
    }
});
watch(() => datasetsStore.subsets, () => {
    setFirstSubset();
});
watch(() => datasetsStore.selectedSubset, () => {
    setFirstSplit();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
if (!__VLS_ctx.datasetsStore.isInitialized) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ style: {} },
    }));
    const __VLS_2 = __VLS_1({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Skeleton | typeof __VLS_components.Skeleton} */
    Skeleton;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ style: {} },
    }));
    const __VLS_7 = __VLS_6({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
}
else {
    const __VLS_10 = DatasetContent || DatasetContent;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({}));
    const __VLS_12 = __VLS_11({}, ...__VLS_functionalComponentArgsRest(__VLS_11));
}
// @ts-ignore
[datasetsStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
