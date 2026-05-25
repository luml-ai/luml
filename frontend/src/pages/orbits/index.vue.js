/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useOrbitsStore } from '@/stores/orbits';
import { computed, onBeforeMount, ref, watch } from 'vue';
import { useOrganizationStore } from '@/stores/organization';
import { useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import Ui404 from '@/components/ui/Ui404.vue';
import OrbitsListHeader from '@/components/orbits/OrbitsListHeader.vue';
import OrbitsList from '@/components/orbits/OrbitsList.vue';
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
import { useRoute, useRouter } from 'vue-router';
import { PermissionEnum } from '@/lib/api/api.interfaces';
const organizationStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const toast = useToast();
const route = useRoute();
const router = useRouter();
const loading = ref(false);
const showCreator = ref(false);
const createAvailable = computed(() => !!organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create));
async function loadOrbits(organizationId, skipHideLoading = false) {
    try {
        loading.value = true;
        await orbitsStore.loadOrbitsList(organizationId);
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.message || 'Failed to load orbits'));
    }
    finally {
        if (skipHideLoading)
            return;
        loading.value = false;
    }
}
function getSingleParam(param) {
    return Array.isArray(param) ? param[0] : param || '';
}
watch(() => organizationStore.currentOrganization?.id, async (id) => {
    if (!id || getSingleParam(route.params.organizationId) === id)
        return;
    await router.push({ name: route.name, params: { organizationId: id } });
    loadOrbits(id);
});
onBeforeMount(async () => {
    const organizationId = getSingleParam(route.params.organizationId);
    if (!organizationId) {
        toast.add(simpleErrorToast('Organization ID is missing in the URL.'));
        loading.value = false;
        return;
    }
    try {
        await loadOrbits(organizationId, true);
        await organizationStore.getOrganizationDetails(organizationId);
    }
    catch (e) {
        console.error(e?.response?.data?.detail, e?.message);
    }
    finally {
        loading.value = false;
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
if (__VLS_ctx.loading) {
    const __VLS_0 = UiPageLoader || UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else if (__VLS_ctx.organizationStore.currentOrganization) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    const __VLS_5 = OrbitsListHeader || OrbitsListHeader;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onCreateNew': {} },
        ...{ class: "header" },
        createAvailable: (__VLS_ctx.createAvailable),
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onCreateNew': {} },
        ...{ class: "header" },
        createAvailable: (__VLS_ctx.createAvailable),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ createNew: {} },
        { onCreateNew: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.organizationStore.currentOrganization))
                    return;
                __VLS_ctx.showCreator = true;
                // @ts-ignore
                [loading, organizationStore, createAvailable, showCreator,];
            } });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    var __VLS_8;
    var __VLS_9;
    const __VLS_12 = OrbitsList || OrbitsList;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
        ...{ 'onCreateNew': {} },
        createAvailable: (__VLS_ctx.createAvailable),
        orbits: (__VLS_ctx.orbitsStore.orbitsList),
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onCreateNew': {} },
        createAvailable: (__VLS_ctx.createAvailable),
        orbits: (__VLS_ctx.orbitsStore.orbitsList),
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_17;
    const __VLS_18 = ({ createNew: {} },
        { onCreateNew: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.organizationStore.currentOrganization))
                    return;
                __VLS_ctx.showCreator = true;
                // @ts-ignore
                [createAvailable, showCreator, orbitsStore,];
            } });
    var __VLS_15;
    var __VLS_16;
    if (__VLS_ctx.organizationStore.currentOrganization) {
        const __VLS_19 = OrbitCreator || OrbitCreator;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            visible: (__VLS_ctx.showCreator),
            organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
        }));
        const __VLS_21 = __VLS_20({
            visible: (__VLS_ctx.showCreator),
            organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    }
}
else {
    const __VLS_24 = Ui404 || Ui404;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
// @ts-ignore
[organizationStore, organizationStore, showCreator,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
