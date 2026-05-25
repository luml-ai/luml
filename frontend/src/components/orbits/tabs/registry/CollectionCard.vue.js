/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Button, Tag } from 'primevue';
import { EllipsisVertical, History, Database, Tag as TagIcon } from 'lucide-vue-next';
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { getLastUpdateText } from '@/helpers/helpers';
import { COLLECTION_TYPE_CONFIG } from './collection.const';
import CollectionEditor from './CollectionEditor.vue';
import UiId from '@/components/ui/UiId.vue';
const props = defineProps();
const router = useRouter();
const isEditorVisible = ref(false);
const updatedText = computed(() => {
    return getLastUpdateText(props.data.updated_at || props.data.created_at);
});
function goToCollection() {
    router.push({
        name: 'collection',
        params: {
            id: props.data.orbit_id,
            collectionId: props.data.id,
        },
    });
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (__VLS_ctx.goToCollection) },
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "left" },
});
/** @type {__VLS_StyleScopedClasses['left']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
(__VLS_ctx.data.name);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.History} */
History;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    size: (12),
}));
const __VLS_2 = __VLS_1({
    size: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.updatedText);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
if (__VLS_ctx.COLLECTION_TYPE_CONFIG[__VLS_ctx.data.type]) {
    const __VLS_5 = (__VLS_ctx.COLLECTION_TYPE_CONFIG[__VLS_ctx.data.type].icon);
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        size: (12),
    }));
    const __VLS_7 = __VLS_6({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.COLLECTION_TYPE_CONFIG[__VLS_ctx.data.type]?.label ?? 'Unknown type');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
let __VLS_10;
/** @ts-ignore @type { | typeof __VLS_components.Database} */
Database;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    size: (12),
}));
const __VLS_12 = __VLS_11({
    size: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.data.total_artifacts);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "id-row" },
});
/** @type {__VLS_StyleScopedClasses['id-row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "id-text" },
});
/** @type {__VLS_StyleScopedClasses['id-text']} */ ;
const __VLS_15 = UiId || UiId;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    id: (__VLS_ctx.data.id),
    ...{ class: "id-value" },
}));
const __VLS_17 = __VLS_16({
    id: (__VLS_ctx.data.id),
    ...{ class: "id-value" },
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
/** @type {__VLS_StyleScopedClasses['id-value']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "tags" },
});
/** @type {__VLS_StyleScopedClasses['tags']} */ ;
for (const [tag] of __VLS_vFor((__VLS_ctx.data.tags))) {
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
    Tag;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        ...{ class: "tag" },
    }));
    const __VLS_22 = __VLS_21({
        ...{ class: "tag" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    /** @type {__VLS_StyleScopedClasses['tag']} */ ;
    const { default: __VLS_25 } = __VLS_23.slots;
    let __VLS_26;
    /** @ts-ignore @type { | typeof __VLS_components.TagIcon} */
    TagIcon;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
        size: (12),
        ...{ class: "tag-icon" },
    }));
    const __VLS_28 = __VLS_27({
        size: (12),
        ...{ class: "tag-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    /** @type {__VLS_StyleScopedClasses['tag-icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (tag);
    // @ts-ignore
    [goToCollection, data, data, data, data, data, data, data, updatedText, COLLECTION_TYPE_CONFIG, COLLECTION_TYPE_CONFIG, COLLECTION_TYPE_CONFIG,];
    var __VLS_23;
    // @ts-ignore
    [];
}
if (__VLS_ctx.editAvailable) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "right" },
    });
    /** @type {__VLS_StyleScopedClasses['right']} */ ;
    let __VLS_31;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
    }));
    const __VLS_33 = __VLS_32({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    let __VLS_36;
    const __VLS_37 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.editAvailable))
                    return;
                __VLS_ctx.isEditorVisible = true;
                // @ts-ignore
                [editAvailable, isEditorVisible,];
            } });
    const { default: __VLS_38 } = __VLS_34.slots;
    {
        const { icon: __VLS_39 } = __VLS_34.slots;
        let __VLS_40;
        /** @ts-ignore @type { | typeof __VLS_components.EllipsisVertical} */
        EllipsisVertical;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
            size: (14),
        }));
        const __VLS_42 = __VLS_41({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_34;
    var __VLS_35;
}
const __VLS_45 = CollectionEditor || CollectionEditor;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
    visible: (__VLS_ctx.isEditorVisible),
    data: (__VLS_ctx.data),
}));
const __VLS_47 = __VLS_46({
    visible: (__VLS_ctx.isEditorVisible),
    data: (__VLS_ctx.data),
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
// @ts-ignore
[data, isEditorVisible,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
