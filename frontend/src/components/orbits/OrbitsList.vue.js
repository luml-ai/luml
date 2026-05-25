/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import OrbitCard from './card/OrbitCard.vue';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "list" },
});
/** @type {__VLS_StyleScopedClasses['list']} */ ;
if (__VLS_ctx.orbits.length === 0) {
    const __VLS_0 = OrbitCard || OrbitCard;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onCreateNew': {} },
        manageAvailable: (__VLS_ctx.createAvailable),
        type: "create",
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onCreateNew': {} },
        manageAvailable: (__VLS_ctx.createAvailable),
        type: "create",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ createNew: {} },
        { onCreateNew: (...[$event]) => {
                if (!(__VLS_ctx.orbits.length === 0))
                    return;
                __VLS_ctx.$emit('createNew');
                // @ts-ignore
                [orbits, createAvailable, $emit,];
            } });
    var __VLS_3;
    var __VLS_4;
}
for (const [orbit] of __VLS_vFor((__VLS_ctx.orbits))) {
    const __VLS_7 = OrbitCard || OrbitCard;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        manageAvailable: (__VLS_ctx.createAvailable),
        key: (orbit.id),
        data: (orbit),
        type: "default",
    }));
    const __VLS_9 = __VLS_8({
        manageAvailable: (__VLS_ctx.createAvailable),
        key: (orbit.id),
        data: (orbit),
        type: "default",
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    // @ts-ignore
    [orbits, createAvailable,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
