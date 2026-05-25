/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useCollectionsStore } from '@/stores/collections';
import { useOrbitsStore } from '@/stores/orbits';
import { useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useOrganizationStore } from '@/stores/organization';
import Ui404 from '@/components/ui/Ui404.vue';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
import CollectionBreadcrumb from '@/components/orbits/tabs/registry/collection/CollectionBreadcrumb.vue';
const route = useRoute();
const router = useRouter();
const organizationStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const collectionsStore = useCollectionsStore();
const toast = useToast();
const loading = ref(true);
function ensureString(param) {
    if (Array.isArray(param))
        return param[0];
    if (!param)
        throw new Error('Missing route param');
    return param;
}
async function init(organizationId) {
    try {
        loading.value = true;
        const orbitId = ensureString(route.params.id);
        const collectionId = ensureString(route.params.collectionId);
        if (orbitsStore.currentOrbitDetails?.id !== orbitId) {
            const details = await orbitsStore.getOrbitDetails(organizationId, orbitId);
            orbitsStore.setCurrentOrbitDetails(details);
        }
        await collectionsStore.setCurrentCollection(collectionId);
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load collection data'));
    }
    finally {
        loading.value = false;
    }
}
watch(() => organizationStore.currentOrganization?.id, async (id) => {
    if (!id || route.params.organizationId === id)
        return;
    await router.push({
        name: 'setup',
        query: { tab: 'registry' },
    });
});
onBeforeMount(() => {
    const organizationId = ensureString(route.params.organizationId);
    init(organizationId);
});
onUnmounted(() => {
    collectionsStore.resetCurrentCollection();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
if (__VLS_ctx.loading) {
    const __VLS_0 = UiPageLoader || UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else if (__VLS_ctx.collectionsStore.currentCollection) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "page-content" },
    });
    /** @type {__VLS_StyleScopedClasses['page-content']} */ ;
    const __VLS_5 = CollectionBreadcrumb || CollectionBreadcrumb;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({}));
    const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.RouterView | typeof __VLS_components.RouterView} */
    RouterView;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({}));
    const __VLS_12 = __VLS_11({}, ...__VLS_functionalComponentArgsRest(__VLS_11));
}
else {
    const __VLS_15 = Ui404 || Ui404;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({}));
    const __VLS_17 = __VLS_16({}, ...__VLS_functionalComponentArgsRest(__VLS_16));
}
// @ts-ignore
[loading, collectionsStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
