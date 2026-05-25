/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Select, Button, useToast } from 'primevue';
import { useCollectionsList } from '@/hooks/useCollectionsList';
import { getErrorMessage } from '@/helpers/helpers';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { watch, ref, computed } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { Plus } from 'lucide-vue-next';
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces';
import CollectionCreator from '../orbits/tabs/registry/CollectionCreator.vue';
const COLLECTION_TYPES = [OrbitCollectionTypeEnum.model, OrbitCollectionTypeEnum.mixed];
const props = defineProps();
const modelValue = defineModel('modelValue');
const toast = useToast();
const { setRequestInfo, getInitialPage, collectionsList, reset, onLazyLoad, setSearchQuery } = useCollectionsList(20, false, COLLECTION_TYPES);
const collectionCreatorVisible = ref(false);
const virtualScrollerOptions = computed(() => {
    if (collectionsList.value.length < 10)
        return undefined;
    return { lazy: true, onLazyLoad: onLazyLoad, itemSize: 38 };
});
async function onRequestInfoChange() {
    try {
        reset();
        modelValue.value = null;
        if (!props.orbitId)
            return;
        setRequestInfo({
            organizationId: String(props.organizationId),
            orbitId: props.orbitId,
        });
        await getInitialPage();
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')));
    }
}
const debouncedOnRequestInfoChange = useDebounceFn(onRequestInfoChange, 500);
function onFilter(event) {
    setSearchQuery(event.value);
    debouncedOnRequestInfoChange();
}
watch(() => props.orbitId, onRequestInfoChange, { immediate: true });
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
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onFilter': {} },
    modelValue: (__VLS_ctx.modelValue),
    id: "collection",
    name: "collection",
    placeholder: (__VLS_ctx.orbitId ? 'Select collection' : 'Select orbit first'),
    disabled: (!__VLS_ctx.orbitId),
    fluid: true,
    filter: true,
    options: (__VLS_ctx.collectionsList),
    optionLabel: "name",
    optionValue: "id",
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onFilter': {} },
    modelValue: (__VLS_ctx.modelValue),
    id: "collection",
    name: "collection",
    placeholder: (__VLS_ctx.orbitId ? 'Select collection' : 'Select orbit first'),
    disabled: (!__VLS_ctx.orbitId),
    fluid: true,
    filter: true,
    options: (__VLS_ctx.collectionsList),
    optionLabel: "name",
    optionValue: "id",
    virtualScrollerOptions: (__VLS_ctx.virtualScrollerOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ filter: {} },
    { onFilter: (__VLS_ctx.onFilter) });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { footer: __VLS_8 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "select-footer" },
    });
    /** @type {__VLS_StyleScopedClasses['select-footer']} */ ;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        ...{ 'onClick': {} },
        label: "Create new collection",
        variant: "text",
    }));
    const __VLS_11 = __VLS_10({
        ...{ 'onClick': {} },
        label: "Create new collection",
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    let __VLS_14;
    const __VLS_15 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.collectionCreatorVisible = true;
                // @ts-ignore
                [modelValue, orbitId, orbitId, collectionsList, virtualScrollerOptions, onFilter, collectionCreatorVisible,];
            } });
    const { default: __VLS_16 } = __VLS_12.slots;
    {
        const { icon: __VLS_17 } = __VLS_12.slots;
        let __VLS_18;
        /** @ts-ignore @type { | typeof __VLS_components.Plus} */
        Plus;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
            size: (14),
        }));
        const __VLS_20 = __VLS_19({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_12;
    var __VLS_13;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
if (__VLS_ctx.organizationId && __VLS_ctx.orbitId) {
    const __VLS_23 = CollectionCreator || CollectionCreator;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        organizationId: (__VLS_ctx.organizationId),
        orbitId: (__VLS_ctx.orbitId),
        visible: (__VLS_ctx.collectionCreatorVisible),
    }));
    const __VLS_25 = __VLS_24({
        organizationId: (__VLS_ctx.organizationId),
        orbitId: (__VLS_ctx.orbitId),
        visible: (__VLS_ctx.collectionCreatorVisible),
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
}
// @ts-ignore
[orbitId, orbitId, collectionCreatorVisible, organizationId, organizationId,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
