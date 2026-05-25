/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { useCollectionsStore } from '@/stores/collections';
import { useOrbitsStore } from '@/stores/orbits';
import CollectionHeader from '@/components/orbits/tabs/registry/collection/CollectionHeader.vue';
import ArtifactsTable from '@/components/orbits/tabs/registry/collection/artifacts-table/ArtifactsTable.vue';
import ArtifactCreator from '@/components/orbits/tabs/registry/collection/artifact/ArtifactCreator.vue';
const collectionsStore = useCollectionsStore();
const orbitsStore = useOrbitsStore();
const creatorVisible = ref(false);
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
if (__VLS_ctx.collectionsStore.currentCollection) {
    const __VLS_0 = CollectionHeader || CollectionHeader;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onAdd': {} },
        id: (__VLS_ctx.collectionsStore.currentCollection.id),
        title: (__VLS_ctx.collectionsStore.currentCollection.name),
        addAvailable: (!!__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.create)),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onAdd': {} },
        id: (__VLS_ctx.collectionsStore.currentCollection.id),
        title: (__VLS_ctx.collectionsStore.currentCollection.name),
        addAvailable: (!!__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.create)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ add: {} },
        { onAdd: (...[$event]) => {
                if (!(__VLS_ctx.collectionsStore.currentCollection))
                    return;
                __VLS_ctx.creatorVisible = true;
                // @ts-ignore
                [collectionsStore, collectionsStore, collectionsStore, orbitsStore, PermissionEnum, creatorVisible,];
            } });
    var __VLS_3;
    var __VLS_4;
}
const __VLS_7 = ArtifactsTable || ArtifactsTable;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ class: "table" },
}));
const __VLS_9 = __VLS_8({
    ...{ class: "table" },
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
/** @type {__VLS_StyleScopedClasses['table']} */ ;
const __VLS_12 = ArtifactCreator || ArtifactCreator;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    visible: (__VLS_ctx.creatorVisible),
}));
const __VLS_14 = __VLS_13({
    visible: (__VLS_ctx.creatorVisible),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
// @ts-ignore
[creatorVisible,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
