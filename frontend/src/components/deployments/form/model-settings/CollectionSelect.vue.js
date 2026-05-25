/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useCollectionsList } from '@/hooks/useCollectionsList';
import { Select, useToast } from 'primevue';
import { useCollectionsStore } from '@/stores/collections';
import { getErrorMessage } from '@/helpers/helpers';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { computed, watch } from 'vue';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
const COLLECTION_TYPES = [OrbitCollectionTypeEnum.mixed, OrbitCollectionTypeEnum.model];
const props = defineProps();
const collectionsStore = useCollectionsStore();
const toast = useToast();
const { setRequestInfo, getInitialPage, collectionsList, reset, onLazyLoad, addCollectionsToList } = useCollectionsList(20, false, COLLECTION_TYPES);
const virtualScrollerOptions = computed(() => {
    if (collectionsList.value.length < 10)
        return undefined;
    return { lazy: true, onLazyLoad: onLazyLoad, itemSize: 38 };
});
const modelValue = defineModel('modelValue');
async function addInitialCollectionToList(collectionId) {
    const collection = await collectionsStore.getCollection(collectionId);
    addCollectionsToList([collection]);
}
async function onRequestInfoChange() {
    try {
        reset();
        if (props.initialCollectionId) {
            addInitialCollectionToList(props.initialCollectionId);
        }
        setRequestInfo({
            organizationId: props.organizationId,
            orbitId: props.orbitId,
        });
        await getInitialPage();
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to load collections');
        toast.add(simpleErrorToast(message));
    }
}
watch(() => [props.organizationId, props.orbitId], onRequestInfoChange, {
    immediate: true,
    deep: true,
});
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "collectionId",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.modelValue),
    id: "collectionId",
    name: "collectionId",
    placeholder: "Select collection",
    fluid: true,
    optionLabel: "name",
    optionValue: "id",
    options: (__VLS_ctx.collectionsList),
    disabled: (__VLS_ctx.disabled),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.modelValue),
    id: "collectionId",
    name: "collectionId",
    placeholder: "Select collection",
    fluid: true,
    optionLabel: "name",
    optionValue: "id",
    options: (__VLS_ctx.collectionsList),
    disabled: (__VLS_ctx.disabled),
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { header: __VLS_6 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "dropdown-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dropdown-title']} */ ;
    // @ts-ignore
    [modelValue, collectionsList, disabled, virtualScrollerOptions,];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
