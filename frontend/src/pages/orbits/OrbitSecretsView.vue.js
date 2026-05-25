/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, ref } from 'vue';
import { useToast } from 'primevue';
import { useOrbitsStore } from '@/stores/orbits';
import { useSecretsStore } from '@/stores/orbit-secrets';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import SecretsList from '@/components/orbit-secrets/SecretsList.vue';
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue';
const orbitsStore = useOrbitsStore();
const secretsStore = useSecretsStore();
const toast = useToast();
const loading = ref(false);
onBeforeMount(async () => {
    try {
        loading.value = true;
        const currentOrbit = orbitsStore.currentOrbitDetails;
        if (currentOrbit?.organization_id && currentOrbit?.id) {
            await secretsStore.loadSecrets(currentOrbit.organization_id, currentOrbit.id);
        }
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to load secrets'));
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
if (!__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "list" },
    });
    /** @type {__VLS_StyleScopedClasses['list']} */ ;
    const __VLS_0 = SecretsList;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        organizationId: (__VLS_ctx.orbitsStore.currentOrbitDetails.organization_id),
        editAvailable: (true),
        copyAvailable: (true),
    }));
    const __VLS_2 = __VLS_1({
        organizationId: (__VLS_ctx.orbitsStore.currentOrbitDetails.organization_id),
        editAvailable: (true),
        copyAvailable: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
const __VLS_5 = SecretCreator;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onUpdate:visible': {} },
    organizationId: (__VLS_ctx.orbitsStore.currentOrbitDetails.organization_id),
    orbitId: (__VLS_ctx.orbitsStore.currentOrbitDetails.id),
    visible: (__VLS_ctx.secretsStore.creatorVisible),
}));
const __VLS_7 = __VLS_6({
    ...{ 'onUpdate:visible': {} },
    organizationId: (__VLS_ctx.orbitsStore.currentOrbitDetails.organization_id),
    orbitId: (__VLS_ctx.orbitsStore.currentOrbitDetails.id),
    visible: (__VLS_ctx.secretsStore.creatorVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((val) => (val ? __VLS_ctx.secretsStore.showCreator() : __VLS_ctx.secretsStore.hideCreator())) });
var __VLS_8;
var __VLS_9;
// @ts-ignore
[loading, orbitsStore, orbitsStore, orbitsStore, secretsStore, secretsStore, secretsStore,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
