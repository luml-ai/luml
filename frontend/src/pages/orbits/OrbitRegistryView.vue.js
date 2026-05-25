/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { Skeleton, useToast } from 'primevue';
import { useAuthStore } from '@/stores/auth';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useCollectionsStore } from '@/stores/collections';
import { useCollectionsList } from '@/hooks/useCollectionsList';
import { useDebounceFn } from '@vueuse/core';
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue';
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue';
import CollectionsToolbar from '@/components/orbits/tabs/registry/CollectionsToolbar.vue';
import CollectionsWelcome from '@/components/orbits/tabs/registry/CollectionsWelcome.vue';
import { Folders, Plus } from 'lucide-vue-next';
const route = useRoute();
const authStore = useAuthStore();
const collectionsStore = useCollectionsStore();
const toast = useToast();
const { setRequestInfo, getInitialPage, collectionsList, reset, searchQuery, setSearchQuery, onLazyLoad, typesQuery, setTypesQuery, } = useCollectionsList();
const loading = ref(false);
function updateCreatorVisible(visible) {
    visible ? collectionsStore.showCreator() : collectionsStore.hideCreator();
}
function onSearch(value) {
    setSearchQuery(value?.trim() ?? '');
}
async function getFirstCollectionsPage() {
    const organizationId = route.params.organizationId;
    const orbitId = route.params.id;
    if (!organizationId || !orbitId)
        return;
    try {
        loading.value = true;
        reset();
        setRequestInfo({ organizationId, orbitId });
        await getInitialPage();
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load collections'));
    }
    finally {
        loading.value = false;
    }
}
watch(() => route.params.id, async (newId) => {
    if (!newId)
        return;
    await getFirstCollectionsPage();
}, { immediate: true });
const debouncedFirstPage = useDebounceFn(getFirstCollectionsPage, 500);
watch([searchQuery, typesQuery], debouncedFirstPage);
onUnmounted(() => {
    collectionsStore.reset();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-header" },
});
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-header__left" },
});
/** @type {__VLS_StyleScopedClasses['page-header__left']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Folders} */
Folders;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (20),
    ...{ class: "page-header__icon" },
}));
const __VLS_2 = __VLS_1({
    size: (20),
    ...{ class: "page-header__icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['page-header__icon']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "page-header__title" },
});
/** @type {__VLS_StyleScopedClasses['page-header__title']} */ ;
if (__VLS_ctx.authStore.isAuth) {
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onClick': {} },
        label: "Create collection",
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        label: "Create collection",
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.authStore.isAuth))
                    return;
                __VLS_ctx.collectionsStore.showCreator();
                // @ts-ignore
                [authStore, collectionsStore,];
            } });
    const { default: __VLS_12 } = __VLS_8.slots;
    {
        const { icon: __VLS_13 } = __VLS_8.slots;
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Plus} */
        Plus;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            size: (14),
        }));
        const __VLS_16 = __VLS_15({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_8;
    var __VLS_9;
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "loading-container" },
    });
    /** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
    for (const [i] of __VLS_vFor((10))) {
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.Skeleton} */
        Skeleton;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            key: (i),
            ...{ style: {} },
        }));
        const __VLS_21 = __VLS_20({
            key: (i),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        // @ts-ignore
        [loading,];
    }
}
else if (__VLS_ctx.collectionsList.length === 0) {
    const __VLS_24 = CollectionsWelcome;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    const __VLS_29 = CollectionsToolbar;
    // @ts-ignore
    const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
        ...{ 'onUpdate:search': {} },
        ...{ 'onUpdate:types': {} },
        types: (__VLS_ctx.typesQuery),
        search: (__VLS_ctx.searchQuery),
    }));
    const __VLS_31 = __VLS_30({
        ...{ 'onUpdate:search': {} },
        ...{ 'onUpdate:types': {} },
        types: (__VLS_ctx.typesQuery),
        search: (__VLS_ctx.searchQuery),
    }, ...__VLS_functionalComponentArgsRest(__VLS_30));
    let __VLS_34;
    const __VLS_35 = ({ 'update:search': {} },
        { 'onUpdate:search': (__VLS_ctx.onSearch) });
    const __VLS_36 = ({ 'update:types': {} },
        { 'onUpdate:types': (__VLS_ctx.setTypesQuery) });
    var __VLS_32;
    var __VLS_33;
    const __VLS_37 = CollectionsList;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        ...{ 'onLazyLoad': {} },
        list: (__VLS_ctx.collectionsList),
    }));
    const __VLS_39 = __VLS_38({
        ...{ 'onLazyLoad': {} },
        list: (__VLS_ctx.collectionsList),
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    let __VLS_42;
    const __VLS_43 = ({ lazyLoad: {} },
        { onLazyLoad: (__VLS_ctx.onLazyLoad) });
    var __VLS_40;
    var __VLS_41;
}
const __VLS_44 = CollectionCreator;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
    ...{ 'onUpdate:visible': {} },
    organizationId: __VLS_ctx.route.params.organizationId,
    orbitId: __VLS_ctx.route.params.id,
    visible: (__VLS_ctx.collectionsStore.creatorVisible),
}));
const __VLS_46 = __VLS_45({
    ...{ 'onUpdate:visible': {} },
    organizationId: __VLS_ctx.route.params.organizationId,
    orbitId: __VLS_ctx.route.params.id,
    visible: (__VLS_ctx.collectionsStore.creatorVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_49;
const __VLS_50 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (__VLS_ctx.updateCreatorVisible) });
var __VLS_47;
var __VLS_48;
// @ts-ignore
[collectionsStore, collectionsList, collectionsList, typesQuery, searchQuery, onSearch, setTypesQuery, onLazyLoad, route, route, updateCreatorVisible,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
