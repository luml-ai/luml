/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, ref } from 'vue';
import { useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { getErrorMessage } from '@/helpers/helpers';
import { useRoute } from 'vue-router';
import { useDeploymentsStore } from '@/stores/deployments';
import { useSatellitesStore } from '@/stores/satellites';
import OpenApi from '../components/openapi/OpenApi.vue';
import UiPageLoader from '@/components/ui/UiPageLoader.vue';
import Ui404 from '@/components/ui/Ui404.vue';
const toast = useToast();
const route = useRoute();
const deploymentsStore = useDeploymentsStore();
const satellitesStore = useSatellitesStore();
const schema = ref(null);
const serverUrl = ref(null);
const loading = ref(true);
onMounted(async () => {
    try {
        const deployment = await deploymentsStore.getDeployment(requestInfo.value.organizationId, requestInfo.value.orbitId, requestInfo.value.deploymentId);
        if (!deployment) {
            throw new Error('Deployment was not found');
        }
        schema.value = getSchema(deployment);
        serverUrl.value = await getServerUrl(deployment);
    }
    catch (error) {
        toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to load deployment schema')));
    }
    finally {
        loading.value = false;
    }
});
const requestInfo = computed(() => {
    const organizationId = route.params.organizationId;
    const orbitId = route.params.id;
    const deploymentId = route.params.deploymentId;
    if (typeof organizationId !== 'string') {
        throw new Error('Organization ID is required');
    }
    if (typeof orbitId !== 'string') {
        throw new Error('Orbit ID is required');
    }
    if (typeof deploymentId !== 'string') {
        throw new Error('Deployment ID is required');
    }
    return {
        organizationId,
        orbitId,
        deploymentId,
    };
});
function getSchema(deployment) {
    const schemas = deployment.schemas;
    if (!schemas || !Object.keys(schemas).length) {
        throw new Error('Deployment schemas were not found');
    }
    return schemas;
}
async function getSatellite(deployment) {
    const satelliteId = deployment.satellite_id;
    const satellite = await satellitesStore.getSatellite(requestInfo.value.organizationId, requestInfo.value.orbitId, satelliteId);
    if (!satellite) {
        throw new Error('Satellite was not found');
    }
    return satellite;
}
async function getServerUrl(deployment) {
    const satellite = await getSatellite(deployment);
    const inferenceUrl = deployment.inference_url;
    if (!inferenceUrl) {
        return null;
    }
    if (inferenceUrl.startsWith('http://') ||
        inferenceUrl.startsWith('https://') ||
        !satellite?.base_url) {
        return inferenceUrl;
    }
    const baseUrl = satellite.base_url.replace(/\/$/, '');
    const normalizedPath = inferenceUrl.replace(/^(\.\/|\/)+/, '');
    return `${baseUrl}/${normalizedPath}`;
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "deployment-schema-page" },
});
/** @type {__VLS_StyleScopedClasses['deployment-schema-page']} */ ;
if (__VLS_ctx.loading) {
    const __VLS_0 = UiPageLoader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
    const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else if (__VLS_ctx.schema && __VLS_ctx.serverUrl) {
    const __VLS_5 = OpenApi;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        content: (__VLS_ctx.schema),
        serverUrl: (__VLS_ctx.serverUrl),
    }));
    const __VLS_7 = __VLS_6({
        content: (__VLS_ctx.schema),
        serverUrl: (__VLS_ctx.serverUrl),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
}
else {
    const __VLS_10 = Ui404;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({}));
    const __VLS_12 = __VLS_11({}, ...__VLS_functionalComponentArgsRest(__VLS_11));
}
// @ts-ignore
[loading, schema, schema, serverUrl, serverUrl,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
