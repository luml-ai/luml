/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useSatellitesStore } from '@/stores/satellites';
import { useAuthStore } from '@/stores/auth';
import { Skeleton, useToast } from 'primevue';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import SatellitesCreateModal from '@/components/satellites/SatellitesCreateModal.vue';
import UiCardAdd from '@/components/ui/UiCardAdd.vue';
import SatellitesApiKeyModal from '@/components/satellites/SatellitesApiKeyModal.vue';
import SatellitesCard from '@/components/satellites/SatellitesCard.vue';
import { Satellite, Plus } from 'lucide-vue-next';
const route = useRoute();
const authStore = useAuthStore();
const toast = useToast();
const satellitesStore = useSatellitesStore();
const createdSatellite = ref(null);
const loading = ref(false);
async function loadSatellitesList() {
    const organizationId = route.params.organizationId;
    const orbitId = route.params.id;
    if (!organizationId || !orbitId)
        return;
    try {
        loading.value = true;
        const list = await satellitesStore.loadSatellites(organizationId, orbitId);
        satellitesStore.setList(list);
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.detail?.message || e?.message || 'Failed to load satellites list'));
    }
    finally {
        loading.value = false;
    }
}
function onCreate(event) {
    createdSatellite.value = event;
    satellitesStore.hideCreator();
}
function onApiKeyClose() {
    createdSatellite.value = null;
}
watch(() => route.params.id, async (newId) => {
    if (!newId)
        return;
    await loadSatellitesList();
}, { immediate: true });
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
/** @ts-ignore @type { | typeof __VLS_components.Satellite} */
Satellite;
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
        label: "Add satellite",
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        label: "Add satellite",
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.authStore.isAuth))
                    return;
                __VLS_ctx.satellitesStore.showCreator();
                // @ts-ignore
                [authStore, satellitesStore,];
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
    for (const [i] of __VLS_vFor((3))) {
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
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "list" },
    });
    /** @type {__VLS_StyleScopedClasses['list']} */ ;
    if (!__VLS_ctx.satellitesStore.satellitesList.length) {
        const __VLS_24 = UiCardAdd;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            ...{ 'onAdd': {} },
            title: "Add new Satellite",
            text: "Connect external compute resources as satellites.",
        }));
        const __VLS_26 = __VLS_25({
            ...{ 'onAdd': {} },
            title: "Add new Satellite",
            text: "Connect external compute resources as satellites.",
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        let __VLS_29;
        const __VLS_30 = ({ add: {} },
            { onAdd: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!(!__VLS_ctx.satellitesStore.satellitesList.length))
                        return;
                    __VLS_ctx.satellitesStore.showCreator();
                    // @ts-ignore
                    [satellitesStore, satellitesStore,];
                } });
        var __VLS_27;
        var __VLS_28;
    }
    else {
        for (const [card] of __VLS_vFor((__VLS_ctx.satellitesStore.satellitesList))) {
            const __VLS_31 = SatellitesCard;
            // @ts-ignore
            const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
                key: (card.id),
                data: (card),
            }));
            const __VLS_33 = __VLS_32({
                key: (card.id),
                data: (card),
            }, ...__VLS_functionalComponentArgsRest(__VLS_32));
            // @ts-ignore
            [satellitesStore,];
        }
    }
}
const __VLS_36 = SatellitesCreateModal;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
    ...{ 'onUpdate:visible': {} },
    ...{ 'onCreate': {} },
    visible: (__VLS_ctx.satellitesStore.creatorVisible),
}));
const __VLS_38 = __VLS_37({
    ...{ 'onUpdate:visible': {} },
    ...{ 'onCreate': {} },
    visible: (__VLS_ctx.satellitesStore.creatorVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_41;
const __VLS_42 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((val) => (val ? __VLS_ctx.satellitesStore.showCreator() : __VLS_ctx.satellitesStore.hideCreator())) });
const __VLS_43 = ({ create: {} },
    { onCreate: (__VLS_ctx.onCreate) });
var __VLS_39;
var __VLS_40;
if (__VLS_ctx.createdSatellite) {
    const __VLS_44 = SatellitesApiKeyModal;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
        ...{ 'onUpdate:visible': {} },
        apiKey: (__VLS_ctx.createdSatellite.api_key),
        satelliteId: (__VLS_ctx.createdSatellite.satellite.id),
        visible: (!!__VLS_ctx.createdSatellite),
    }));
    const __VLS_46 = __VLS_45({
        ...{ 'onUpdate:visible': {} },
        apiKey: (__VLS_ctx.createdSatellite.api_key),
        satelliteId: (__VLS_ctx.createdSatellite.satellite.id),
        visible: (!!__VLS_ctx.createdSatellite),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    let __VLS_49;
    const __VLS_50 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (__VLS_ctx.onApiKeyClose) });
    var __VLS_47;
    var __VLS_48;
}
// @ts-ignore
[satellitesStore, satellitesStore, satellitesStore, onCreate, createdSatellite, createdSatellite, createdSatellite, createdSatellite, onApiKeyClose,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
