/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Tag } from 'primevue';
import { computed } from 'vue';
const CELL_WIDTH = 203;
const MORE_TAGS_WIDTH = 30;
const AVAILABLE_WIDTH = CELL_WIDTH - MORE_TAGS_WIDTH;
const TAG_PADDING = 8;
const GAP = 4;
const LETTER_WIDTH = 10;
const props = defineProps();
const visibleTags = computed(() => {
    const { tags } = props.tags.reduce((acc, tag) => {
        const tagWidth = tag.length * LETTER_WIDTH + TAG_PADDING * 2;
        if (acc.width + tagWidth > AVAILABLE_WIDTH) {
            return acc;
        }
        acc.width += tagWidth + GAP;
        acc.tags.push(tag);
        return acc;
    }, { tags: [], width: 0 });
    return tags;
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
if (__VLS_ctx.tags.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "tags" },
    });
    /** @type {__VLS_StyleScopedClasses['tags']} */ ;
    for (const [tag, index] of __VLS_vFor((__VLS_ctx.visibleTags))) {
        let __VLS_0;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
            key: (index),
            ...{ class: "tag" },
        }));
        const __VLS_2 = __VLS_1({
            key: (index),
            ...{ class: "tag" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        /** @type {__VLS_StyleScopedClasses['tag']} */ ;
        const { default: __VLS_5 } = __VLS_3.slots;
        (tag);
        // @ts-ignore
        [tags, visibleTags,];
        var __VLS_3;
        // @ts-ignore
        [];
    }
    if (__VLS_ctx.visibleTags.length < __VLS_ctx.tags.length) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "more-tags" },
        });
        /** @type {__VLS_StyleScopedClasses['more-tags']} */ ;
        (__VLS_ctx.tags.length - __VLS_ctx.visibleTags.length);
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
}
// @ts-ignore
[tags, tags, visibleTags, visibleTags,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
