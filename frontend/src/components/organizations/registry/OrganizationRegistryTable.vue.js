/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useBucketsStore } from '@/stores/buckets';
import { useOrganizationStore } from '@/stores/organization';
import { onMounted, ref } from 'vue';
import BucketSettings from './BucketSettings.vue';
const bucketsStore = useBucketsStore();
const organizationStore = useOrganizationStore();
const loading = ref();
onMounted(async () => {
    try {
        const organizationId = organizationStore.currentOrganization?.id;
        if (!organizationId)
            return;
        await bucketsStore.getBuckets(organizationId);
    }
    catch {
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
    ...{ class: "table-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['table-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "table" },
});
/** @type {__VLS_StyleScopedClasses['table']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__header" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__row" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__rows" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__rows']} */ ;
if (!__VLS_ctx.bucketsStore.buckets.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "simple-table__placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['simple-table__placeholder']} */ ;
}
for (const [bucket] of __VLS_vFor((__VLS_ctx.bucketsStore.buckets))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "simple-table__row" },
    });
    /** @type {__VLS_StyleScopedClasses['simple-table__row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (bucket.bucket_name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (bucket.endpoint);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (new Date(bucket.created_at).toLocaleDateString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    const __VLS_0 = BucketSettings;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        bucket: (bucket),
    }));
    const __VLS_2 = __VLS_1({
        bucket: (bucket),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    // @ts-ignore
    [bucketsStore, bucketsStore,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
