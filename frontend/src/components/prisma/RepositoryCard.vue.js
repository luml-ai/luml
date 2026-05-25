/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Button } from 'primevue';
import { FolderGit, Trash2, Plus } from 'lucide-vue-next';
const __VLS_props = defineProps();
const emit = defineEmits();
function truncateMiddle(str, maxLen = 40) {
    if (str.length <= maxLen)
        return str;
    const keep = Math.floor((maxLen - 3) / 2);
    return str.slice(0, keep) + '...' + str.slice(-keep);
}
function onDelete(repo) {
    emit('delete', repo.id, repo.name);
}
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
__VLS_asFunctionalElement1(__VLS_intrinsics.article, __VLS_intrinsics.article)({
    ...{ class: "card" },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
if (__VLS_ctx.type === 'default' && __VLS_ctx.data) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "content" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.FolderGit} */
    FolderGit;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        size: (20),
        color: "var(--p-primary-color)",
        ...{ class: "icon" },
    }));
    const __VLS_2 = __VLS_1({
        size: (20),
        color: "var(--p-primary-color)",
        ...{ class: "icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    /** @type {__VLS_StyleScopedClasses['icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.data.name);
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        ...{ class: "delete-btn" },
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        ...{ class: "delete-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.type === 'default' && __VLS_ctx.data))
                    return;
                __VLS_ctx.onDelete(__VLS_ctx.data);
                // @ts-ignore
                [type, data, data, data, onDelete,];
            } });
    /** @type {__VLS_StyleScopedClasses['delete-btn']} */ ;
    const { default: __VLS_12 } = __VLS_8.slots;
    {
        const { icon: __VLS_13 } = __VLS_8.slots;
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
        Trash2;
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
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "path" },
        title: (__VLS_ctx.data.path),
    });
    /** @type {__VLS_StyleScopedClasses['path']} */ ;
    (__VLS_ctx.truncateMiddle(__VLS_ctx.data.path, 60));
}
if (__VLS_ctx.type === 'create') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "content content--center" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    /** @type {__VLS_StyleScopedClasses['content--center']} */ ;
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
    }));
    const __VLS_21 = __VLS_20({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    let __VLS_24;
    const __VLS_25 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.type === 'create'))
                    return;
                __VLS_ctx.$emit('createNew');
                // @ts-ignore
                [type, data, data, truncateMiddle, $emit,];
            } });
    const { default: __VLS_26 } = __VLS_22.slots;
    {
        const { icon: __VLS_27 } = __VLS_22.slots;
        let __VLS_28;
        /** @ts-ignore @type { | typeof __VLS_components.Plus} */
        Plus;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
            size: (14),
        }));
        const __VLS_30 = __VLS_29({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_22;
    var __VLS_23;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
