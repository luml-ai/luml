/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { VirtualScroller } from 'primevue';
import { computed } from 'vue';
import { useOrbitsStore } from '@/stores/orbits';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import CollectionCard from './CollectionCard.vue';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
const orbitsStore = useOrbitsStore();
const editAvailable = computed(() => {
    return !!orbitsStore.getCurrentOrbitPermissions?.collection.includes(PermissionEnum.update);
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.VirtualScroller | typeof __VLS_components.VirtualScroller} */
VirtualScroller;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onLazyLoad': {} },
    items: (__VLS_ctx.list),
    itemSize: (171),
    lazy: true,
    ...{ class: "border border-surface-200 dark:border-surface-700 rounded" },
    ...{ style: {} },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onLazyLoad': {} },
    items: (__VLS_ctx.list),
    itemSize: (171),
    lazy: true,
    ...{ class: "border border-surface-200 dark:border-surface-700 rounded" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ lazyLoad: {} },
    { onLazyLoad: (...[$event]) => {
            __VLS_ctx.$emit('lazy-load', $event);
            // @ts-ignore
            [list, $emit,];
        } });
var __VLS_7;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-surface-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-surface-700']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { item: __VLS_9 } = __VLS_3.slots;
    const [{ item }] = __VLS_vSlot(__VLS_9);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "card-wrapper" },
    });
    /** @type {__VLS_StyleScopedClasses['card-wrapper']} */ ;
    const __VLS_10 = CollectionCard || CollectionCard;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        editAvailable: (__VLS_ctx.editAvailable),
        data: (item),
    }));
    const __VLS_12 = __VLS_11({
        editAvailable: (__VLS_ctx.editAvailable),
        data: (item),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    // @ts-ignore
    [editAvailable,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
