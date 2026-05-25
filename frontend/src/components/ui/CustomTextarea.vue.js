/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onMounted, onUnmounted, ref, useAttrs } from 'vue';
import { Textarea } from 'primevue';
const props = defineProps();
const attrs = useAttrs();
const wrapperRef = ref();
const isScrollable = ref(false);
let observer = null;
onMounted(() => {
    observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
            isScrollable.value = entry.contentRect.height > props.maxHeight;
        }
    });
    if (wrapperRef.value) {
        observer.observe(wrapperRef.value);
    }
});
onUnmounted(() => {
    if (observer) {
        observer.disconnect();
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['textarea']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ref: "wrapperRef",
});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...(__VLS_ctx.attrs),
    ...{ class: "textarea" },
    ...{ class: ({ scrollable: __VLS_ctx.isScrollable }) },
    ...{ style: ({ maxHeight: props.maxHeight + 'px' }) },
}));
const __VLS_2 = __VLS_1({
    ...(__VLS_ctx.attrs),
    ...{ class: "textarea" },
    ...{ class: ({ scrollable: __VLS_ctx.isScrollable }) },
    ...{ style: ({ maxHeight: props.maxHeight + 'px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['scrollable']} */ ;
// @ts-ignore
[attrs, isScrollable,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
