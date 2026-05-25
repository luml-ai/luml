/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDeploymentsStore } from '@/stores/deployments';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { useAuthStore } from '@/stores/auth';
import { Skeleton, useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { getErrorMessage } from '@/helpers/helpers';
import { Rocket, Lock, Plus } from 'lucide-vue-next';
import UiCardAdd from '@/components/ui/UiCardAdd.vue';
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue';
import DeploymentsTable from '@/components/deployments/table/DeploymentsTable.vue';
import SecretsList from '@/components/orbit-secrets/SecretsList.vue';
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue';
const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const deploymentsStore = useDeploymentsStore();
const secretsStore = useSecretsStore();
const toast = useToast();
const deploymentsLoading = ref(false);
const secretsLoading = ref(false);
const activeTab = computed(() => {
    return route.name === 'orbit-secrets' ? 'secrets' : 'deployments';
});
function switchTab(tab) {
    const targetRoute = tab === 'secrets' ? 'orbit-secrets' : 'orbit-deployments';
    router.push({
        name: targetRoute,
        params: route.params,
    });
}
async function loadDeployments() {
    const organizationId = route.params.organizationId;
    const orbitId = route.params.id;
    if (!organizationId || !orbitId)
        return;
    try {
        deploymentsLoading.value = true;
        const deployments = await deploymentsStore.getDeployments(organizationId, orbitId);
        deploymentsStore.setDeployments(deployments);
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load deployments list')));
    }
    finally {
        deploymentsLoading.value = false;
    }
}
async function loadSecrets() {
    const organizationId = route.params.organizationId;
    const orbitId = route.params.id;
    if (!organizationId || !orbitId)
        return;
    try {
        secretsLoading.value = true;
        await secretsStore.loadSecrets(organizationId, orbitId);
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load secrets'));
    }
    finally {
        secretsLoading.value = false;
    }
}
async function loadAll() {
    await Promise.all([loadDeployments(), loadSecrets()]);
}
watch(() => route.params.id, async (newId) => {
    if (!newId)
        return;
    await loadAll();
}, { immediate: true });
onUnmounted(() => {
    deploymentsStore.reset();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-header" },
});
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "page-header__left" },
});
/** @type {__VLS_StyleScopedClasses['page-header__left']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Rocket} */
Rocket;
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
    if (__VLS_ctx.activeTab === 'deployments') {
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            ...{ 'onClick': {} },
            label: "Create deployment",
        }));
        const __VLS_7 = __VLS_6({
            ...{ 'onClick': {} },
            label: "Create deployment",
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
        let __VLS_10;
        const __VLS_11 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.authStore.isAuth))
                        return;
                    if (!(__VLS_ctx.activeTab === 'deployments'))
                        return;
                    __VLS_ctx.deploymentsStore.showCreator();
                    // @ts-ignore
                    [authStore, activeTab, deploymentsStore,];
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
    else {
        let __VLS_19;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
            ...{ 'onClick': {} },
            label: "Create secret",
        }));
        const __VLS_21 = __VLS_20({
            ...{ 'onClick': {} },
            label: "Create secret",
        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
        let __VLS_24;
        const __VLS_25 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.authStore.isAuth))
                        return;
                    if (!!(__VLS_ctx.activeTab === 'deployments'))
                        return;
                    __VLS_ctx.secretsStore.showCreator();
                    // @ts-ignore
                    [secretsStore,];
                } });
        const { default: __VLS_26 } = __VLS_22.slots;
        {
            const { icon: __VLS_27 } = __VLS_22.slots;
            let __VLS_28;
            /** @ts-ignore @type { | typeof __VLS_components.Plus} */
            Plus;
            // @ts-ignore
            const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
                size: (14),
            }));
            const __VLS_30 = __VLS_29({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_29));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_22;
        var __VLS_23;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "tabs" },
});
/** @type {__VLS_StyleScopedClasses['tabs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.switchTab('deployments');
            // @ts-ignore
            [switchTab,];
        } },
    ...{ class: "tab" },
    ...{ class: ({ active: __VLS_ctx.activeTab === 'deployments' }) },
});
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
let __VLS_33;
/** @ts-ignore @type { | typeof __VLS_components.Rocket} */
Rocket;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
    size: (14),
}));
const __VLS_35 = __VLS_34({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.switchTab('secrets');
            // @ts-ignore
            [activeTab, switchTab,];
        } },
    ...{ class: "tab" },
    ...{ class: ({ active: __VLS_ctx.activeTab === 'secrets' }) },
});
/** @type {__VLS_StyleScopedClasses['tab']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
let __VLS_38;
/** @ts-ignore @type { | typeof __VLS_components.Lock} */
Lock;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
    size: (14),
}));
const __VLS_40 = __VLS_39({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
if (__VLS_ctx.activeTab === 'deployments') {
    if (__VLS_ctx.deploymentsLoading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "loading-container" },
        });
        /** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
        for (const [i] of __VLS_vFor((1))) {
            let __VLS_43;
            /** @ts-ignore @type { | typeof __VLS_components.Skeleton} */
            Skeleton;
            // @ts-ignore
            const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
                key: (i),
                ...{ style: {} },
            }));
            const __VLS_45 = __VLS_44({
                key: (i),
                ...{ style: {} },
            }, ...__VLS_functionalComponentArgsRest(__VLS_44));
            // @ts-ignore
            [activeTab, activeTab, deploymentsLoading,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        if (__VLS_ctx.deploymentsStore.deployments.length) {
            const __VLS_48 = DeploymentsTable;
            // @ts-ignore
            const __VLS_49 = __VLS_asFunctionalComponent1(__VLS_48, new __VLS_48({
                data: (__VLS_ctx.deploymentsStore.deployments),
            }));
            const __VLS_50 = __VLS_49({
                data: (__VLS_ctx.deploymentsStore.deployments),
            }, ...__VLS_functionalComponentArgsRest(__VLS_49));
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "list" },
            });
            /** @type {__VLS_StyleScopedClasses['list']} */ ;
            const __VLS_53 = UiCardAdd;
            // @ts-ignore
            const __VLS_54 = __VLS_asFunctionalComponent1(__VLS_53, new __VLS_53({
                ...{ 'onAdd': {} },
                title: "Add new Deployment",
                text: "Instantly deploy models in a single click.",
            }));
            const __VLS_55 = __VLS_54({
                ...{ 'onAdd': {} },
                title: "Add new Deployment",
                text: "Instantly deploy models in a single click.",
            }, ...__VLS_functionalComponentArgsRest(__VLS_54));
            let __VLS_58;
            const __VLS_59 = ({ add: {} },
                { onAdd: (...[$event]) => {
                        if (!(__VLS_ctx.activeTab === 'deployments'))
                            return;
                        if (!!(__VLS_ctx.deploymentsLoading))
                            return;
                        if (!!(__VLS_ctx.deploymentsStore.deployments.length))
                            return;
                        __VLS_ctx.deploymentsStore.showCreator();
                        // @ts-ignore
                        [deploymentsStore, deploymentsStore, deploymentsStore,];
                    } });
            var __VLS_56;
            var __VLS_57;
        }
    }
}
else if (__VLS_ctx.activeTab === 'secrets') {
    if (__VLS_ctx.secretsLoading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "loading-container" },
        });
        /** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
        for (const [i] of __VLS_vFor((3))) {
            let __VLS_60;
            /** @ts-ignore @type { | typeof __VLS_components.Skeleton} */
            Skeleton;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
                key: (i),
                ...{ style: {} },
            }));
            const __VLS_62 = __VLS_61({
                key: (i),
                ...{ style: {} },
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            // @ts-ignore
            [activeTab, secretsLoading,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        const __VLS_65 = SecretsList;
        // @ts-ignore
        const __VLS_66 = __VLS_asFunctionalComponent1(__VLS_65, new __VLS_65({
            organizationId: __VLS_ctx.route.params.organizationId,
            editAvailable: (true),
            copyAvailable: (true),
        }));
        const __VLS_67 = __VLS_66({
            organizationId: __VLS_ctx.route.params.organizationId,
            editAvailable: (true),
            copyAvailable: (true),
        }, ...__VLS_functionalComponentArgsRest(__VLS_66));
    }
}
if (__VLS_ctx.deploymentsStore.creatorVisible) {
    const __VLS_70 = DeploymentsCreateModal;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent1(__VLS_70, new __VLS_70({
        ...{ 'onUpdate:visible': {} },
        visible: (__VLS_ctx.deploymentsStore.creatorVisible),
    }));
    const __VLS_72 = __VLS_71({
        ...{ 'onUpdate:visible': {} },
        visible: (__VLS_ctx.deploymentsStore.creatorVisible),
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    let __VLS_75;
    const __VLS_76 = ({ 'update:visible': {} },
        { 'onUpdate:visible': ((val) => (val ? __VLS_ctx.deploymentsStore.showCreator() : __VLS_ctx.deploymentsStore.hideCreator())) });
    var __VLS_73;
    var __VLS_74;
}
const __VLS_77 = SecretCreator;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent1(__VLS_77, new __VLS_77({
    ...{ 'onUpdate:visible': {} },
    organizationId: __VLS_ctx.route.params.organizationId,
    orbitId: __VLS_ctx.route.params.id,
    visible: (__VLS_ctx.secretsStore.creatorVisible),
}));
const __VLS_79 = __VLS_78({
    ...{ 'onUpdate:visible': {} },
    organizationId: __VLS_ctx.route.params.organizationId,
    orbitId: __VLS_ctx.route.params.id,
    visible: (__VLS_ctx.secretsStore.creatorVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
let __VLS_82;
const __VLS_83 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((val) => (val ? __VLS_ctx.secretsStore.showCreator() : __VLS_ctx.secretsStore.hideCreator())) });
var __VLS_80;
var __VLS_81;
// @ts-ignore
[deploymentsStore, deploymentsStore, deploymentsStore, deploymentsStore, secretsStore, secretsStore, secretsStore, route, route, route,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
