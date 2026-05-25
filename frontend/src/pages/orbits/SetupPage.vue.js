/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Folders, Rocket, Satellite } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { useOrbitsStore } from '@/stores/orbits';
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
import { TAB_TO_ROUTE } from '@/constants/orbit-navigation';
const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const organizationStore = useOrganizationStore();
const orbitsStore = useOrbitsStore();
const isCreateOrbitMode = ref(false);
const isLoading = ref(true);
onMounted(() => {
    isLoading.value = false;
});
watch(() => organizationStore.currentOrganization?.id, async (orgId) => {
    if (!orgId || !authStore.isAuth)
        return;
    isLoading.value = true;
    if (!orbitsStore.orbitsList.length) {
        try {
            await orbitsStore.loadOrbitsList(orgId);
        }
        catch {
            isLoading.value = false;
            return;
        }
    }
    const firstOrbit = orbitsStore.orbitsList[0];
    if (!firstOrbit) {
        isLoading.value = false;
        return;
    }
    const tab = route.query.tab ?? 'registry';
    const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry';
    router.replace({
        name: targetRoute,
        params: { organizationId: orgId, id: firstOrbit.id },
    });
});
const TABS = {
    registry: {
        title: 'Registry',
        icon: Folders,
        cards: [
            {
                title: 'Registry',
                description: 'Registry is a centralized hub for organizing and tracking ML models, experiments, and datasets — managing their versions and metadata throughout the entire lifecycle.',
            },
            {
                title: 'Overview',
                description: 'Overview is a technical passport for any registry item — models, experiments, or datasets — containing metadata: name, date, size, content manifest, and tags for search and organization across collections.',
            },
        ],
    },
    deployments: {
        title: 'Deployments',
        icon: Rocket,
        cards: [
            {
                title: 'Deployments',
                description: 'A Deployment transforms a model from the Registry into a live endpoint by linking it to a Satellite. You can create, update, stop, or delete it without changing the model itself.',
            },
            {
                title: 'Secrets',
                description: 'Secrets is a secure store for sensitive data scoped to an Orbit. When a key is rotated, the update automatically propagates to all linked deployments.',
            },
        ],
    },
    satellites: {
        title: 'Satellites',
        icon: Satellite,
        cards: [
            {
                title: 'Satellites',
                description: 'A Satellite is an external compute node that connects to LUML via a pairing key and becomes the execution environment for an Orbit.',
            },
            {
                title: 'How it works',
                description: 'The platform queues tasks, and the Satellite pulls and executes them within your own infrastructure, remaining fully under your control.',
            },
        ],
    },
};
const currentTab = computed(() => {
    const tab = route.query.tab;
    return TABS[tab] ?? TABS.registry;
});
function onOrbitCreated(orbit) {
    const tab = route.query.tab ?? 'registry';
    const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry';
    router.push({
        name: targetRoute,
        params: {
            organizationId: organizationStore.currentOrganization.id,
            id: orbit.id,
        },
    });
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "setup-page" },
});
/** @type {__VLS_StyleScopedClasses['setup-page']} */ ;
if (__VLS_ctx.isLoading) {
    const __VLS_0 = UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "page-header" },
    });
    /** @type {__VLS_StyleScopedClasses['page-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "page-header__left" },
    });
    /** @type {__VLS_StyleScopedClasses['page-header__left']} */ ;
    const __VLS_5 = (__VLS_ctx.currentTab.icon);
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        size: (20),
        ...{ class: "page-header__icon" },
    }));
    const __VLS_7 = __VLS_6({
        size: (20),
        ...{ class: "page-header__icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    /** @type {__VLS_StyleScopedClasses['page-header__icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "page-header__title" },
    });
    /** @type {__VLS_StyleScopedClasses['page-header__title']} */ ;
    (__VLS_ctx.currentTab.title);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grid" },
    });
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card card--action" },
    });
    /** @type {__VLS_StyleScopedClasses['card']} */ ;
    /** @type {__VLS_StyleScopedClasses['card--action']} */ ;
    if (!__VLS_ctx.authStore.isAuth) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "content" },
        });
        /** @type {__VLS_StyleScopedClasses['content']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text" },
        });
        /** @type {__VLS_StyleScopedClasses['text']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "actions" },
        });
        /** @type {__VLS_StyleScopedClasses['actions']} */ ;
        let __VLS_10;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            ...{ 'onClick': {} },
            label: "Log in",
            severity: "secondary",
        }));
        const __VLS_12 = __VLS_11({
            ...{ 'onClick': {} },
            label: "Log in",
            severity: "secondary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        let __VLS_15;
        const __VLS_16 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!(!__VLS_ctx.authStore.isAuth))
                        return;
                    __VLS_ctx.$router.push({ name: 'sign-in', query: { redirect: __VLS_ctx.$route.fullPath } });
                    // @ts-ignore
                    [isLoading, currentTab, currentTab, authStore, $router, $route,];
                } });
        var __VLS_13;
        var __VLS_14;
        let __VLS_17;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
            ...{ 'onClick': {} },
            label: "Sign up",
        }));
        const __VLS_19 = __VLS_18({
            ...{ 'onClick': {} },
            label: "Sign up",
        }, ...__VLS_functionalComponentArgsRest(__VLS_18));
        let __VLS_22;
        const __VLS_23 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!(!__VLS_ctx.authStore.isAuth))
                        return;
                    __VLS_ctx.$router.push({ name: 'sign-up', query: { redirect: __VLS_ctx.$route.fullPath } });
                    // @ts-ignore
                    [$router, $route,];
                } });
        var __VLS_20;
        var __VLS_21;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "content" },
        });
        /** @type {__VLS_StyleScopedClasses['content']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text" },
        });
        /** @type {__VLS_StyleScopedClasses['text']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "actions" },
        });
        /** @type {__VLS_StyleScopedClasses['actions']} */ ;
        let __VLS_24;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            ...{ 'onClick': {} },
            label: "Create orbit",
        }));
        const __VLS_26 = __VLS_25({
            ...{ 'onClick': {} },
            label: "Create orbit",
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        let __VLS_29;
        const __VLS_30 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!!(!__VLS_ctx.authStore.isAuth))
                        return;
                    __VLS_ctx.isCreateOrbitMode = true;
                    // @ts-ignore
                    [isCreateOrbitMode,];
                } });
        var __VLS_27;
        var __VLS_28;
    }
    for (const [card] of __VLS_vFor((__VLS_ctx.currentTab.cards))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (card.title),
            ...{ class: "card" },
        });
        /** @type {__VLS_StyleScopedClasses['card']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "content" },
        });
        /** @type {__VLS_StyleScopedClasses['content']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        (card.title);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text" },
        });
        /** @type {__VLS_StyleScopedClasses['text']} */ ;
        (card.description);
        // @ts-ignore
        [currentTab,];
    }
    if (__VLS_ctx.organizationStore.currentOrganization) {
        const __VLS_31 = OrbitCreator;
        // @ts-ignore
        const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
            ...{ 'onCreated': {} },
            visible: (__VLS_ctx.isCreateOrbitMode),
            organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
        }));
        const __VLS_33 = __VLS_32({
            ...{ 'onCreated': {} },
            visible: (__VLS_ctx.isCreateOrbitMode),
            organizationId: (__VLS_ctx.organizationStore.currentOrganization.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_32));
        let __VLS_36;
        const __VLS_37 = ({ created: {} },
            { onCreated: (__VLS_ctx.onOrbitCreated) });
        var __VLS_34;
        var __VLS_35;
    }
}
// @ts-ignore
[isCreateOrbitMode, organizationStore, organizationStore, onOrbitCreated,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
