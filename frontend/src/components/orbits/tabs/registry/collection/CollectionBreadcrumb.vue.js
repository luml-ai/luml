/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Breadcrumb } from 'primevue';
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useCollectionsStore } from '@/stores/collections';
import { useArtifactsStore } from '@/stores/artifacts';
const route = useRoute();
const collectionStore = useCollectionsStore();
const artifactsStore = useArtifactsStore();
const breadcrumbs = computed(() => {
    const list = [
        {
            label: 'Registry',
            route: `/organization/${route.params.organizationId}/orbit/${route.params.id}`,
        },
    ];
    if (collectionStore.currentCollection) {
        list.push({
            label: collectionStore.currentCollection.name,
            route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}`,
        });
    }
    if (artifactsStore.currentArtifact) {
        list.push({
            label: artifactsStore.currentArtifact.name,
            route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}/artifacts/${route.params.artifactId}`,
        });
    }
    const modelsToCompare = typeof route.query.artifacts === 'object' ? route.query.artifacts : null;
    if (modelsToCompare?.length) {
        const queryString = modelsToCompare.map((id) => `artifacts=${id}`).join('&');
        list.push({
            label: `Experiments comparison (${modelsToCompare.length})`,
            route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}/compare?${queryString}`,
        });
    }
    return list;
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Breadcrumb | typeof __VLS_components.Breadcrumb} */
Breadcrumb;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    model: (__VLS_ctx.breadcrumbs),
    pt: ({ root: { style: 'padding-left: 0' } }),
}));
const __VLS_2 = __VLS_1({
    model: (__VLS_ctx.breadcrumbs),
    pt: ({ root: { style: 'padding-left: 0' } }),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { item: __VLS_7 } = __VLS_3.slots;
    const [{ item, props }] = __VLS_vSlot(__VLS_7);
    if (item.route) {
        let __VLS_8;
        /** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
        RouterLink;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
            to: (item.route),
            custom: true,
        }));
        const __VLS_10 = __VLS_9({
            to: (item.route),
            custom: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_9));
        {
            const { default: __VLS_13 } = __VLS_11.slots;
            const [{ href, navigate }] = __VLS_vSlot(__VLS_13);
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
                ...{ onClick: (navigate) },
                href: (href),
                ...(props.action),
            });
            (item.label);
            // @ts-ignore
            [breadcrumbs,];
            __VLS_11.slots['' /* empty slot name completion */];
        }
        var __VLS_11;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
