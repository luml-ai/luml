/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onBeforeMount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useOrganizationStore } from '@/stores/organization';
import { useToast } from 'primevue';
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import OrganizationInfo from '@/components/organizations/OrganizationInfo.vue';
import OrganizationLimits from '@/components/organizations/OrganizationLimits.vue';
import OrganizationTabs from '@/components/organizations/OrganizationTabs.vue';
import OrganizationLocked from '@/components/organizations/OrganizationLocked.vue';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
const route = useRoute();
const router = useRouter();
const organizationStore = useOrganizationStore();
const toast = useToast();
const hasPermission = computed(() => {
    const userRole = organizationStore.availableOrganizations.find((organization) => organization.id === organizationStore.currentOrganization?.id)?.role;
    if (!userRole || userRole === OrganizationRoleEnum.member)
        return false;
    return true;
});
async function init() {
    const idParam = route.params.id;
    const organizationId = Array.isArray(idParam) ? idParam[0] : idParam;
    if (!organizationId) {
        toast.add(simpleErrorToast('Organization not found'));
        return;
    }
    try {
        organizationStore.resetCurrentOrganization();
        await organizationStore.setCurrentOrganizationId(organizationId);
        organizationStore.getOrganizationDetails(organizationId);
    }
    catch (e) {
        toast.add(simpleErrorToast(e.details || 'Unable to retrieve organization data'));
    }
}
onBeforeMount(() => {
    init();
});
watch(() => organizationStore.currentOrganization?.id, async (id) => {
    if (!id || route.params.id === id)
        return;
    await router.push({
        name: route.name,
        params: {
            ...route.params,
            id,
        },
    });
    init();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.organizationStore.loading) {
    const __VLS_0 = UiPageLoader || UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
    var __VLS_5;
    var __VLS_3;
}
else if (__VLS_ctx.organizationStore.currentOrganization) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (!__VLS_ctx.hasPermission) {
        const __VLS_6 = OrganizationLocked || OrganizationLocked;
        // @ts-ignore
        const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({}));
        const __VLS_8 = __VLS_7({}, ...__VLS_functionalComponentArgsRest(__VLS_7));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "organization-page" },
        });
        /** @type {__VLS_StyleScopedClasses['organization-page']} */ ;
        const __VLS_11 = OrganizationInfo || OrganizationInfo;
        // @ts-ignore
        const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
            ...{ class: "info" },
        }));
        const __VLS_13 = __VLS_12({
            ...{ class: "info" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_12));
        /** @type {__VLS_StyleScopedClasses['info']} */ ;
        const __VLS_16 = OrganizationLimits || OrganizationLimits;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
            ...{ class: "limits" },
        }));
        const __VLS_18 = __VLS_17({
            ...{ class: "limits" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        /** @type {__VLS_StyleScopedClasses['limits']} */ ;
        const __VLS_21 = OrganizationTabs || OrganizationTabs;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({}));
        const __VLS_23 = __VLS_22({}, ...__VLS_functionalComponentArgsRest(__VLS_22));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "views" },
        });
        /** @type {__VLS_StyleScopedClasses['views']} */ ;
        let __VLS_26;
        /** @ts-ignore @type { | typeof __VLS_components.RouterView | typeof __VLS_components.RouterView} */
        RouterView;
        // @ts-ignore
        const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({}));
        const __VLS_28 = __VLS_27({}, ...__VLS_functionalComponentArgsRest(__VLS_27));
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    (__VLS_ctx.route.params.id);
}
// @ts-ignore
[organizationStore, organizationStore, hasPermission, route,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
