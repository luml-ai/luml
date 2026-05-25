/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Plus, Lock, Orbit, EllipsisVertical } from 'lucide-vue-next';
import { Button } from 'primevue';
import OrbitEditor from '../editor/OrbitEditor.vue';
import UiId from '@/components/ui/UiId.vue';
const __VLS_props = defineProps();
const __VLS_emit = defineEmits();
const editVisible = ref(false);
function openEdit() {
    editVisible.value = true;
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
/** @type {__VLS_StyleScopedClasses['card--clickable']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.article, __VLS_intrinsics.article)({
    ...{ class: "card" },
    ...{ class: ({ 'card--clickable': __VLS_ctx.type === 'default' }) },
});
/** @type {__VLS_StyleScopedClasses['card']} */ ;
/** @type {__VLS_StyleScopedClasses['card--clickable']} */ ;
if (__VLS_ctx.type === 'default' && __VLS_ctx.data) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.type === 'default' && __VLS_ctx.data))
                    return;
                __VLS_ctx.$router.push({ name: 'orbit-registry', params: { id: __VLS_ctx.data.id } });
                // @ts-ignore
                [type, type, data, data, $router,];
            } },
        ...{ class: "content content--clickable" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    /** @type {__VLS_StyleScopedClasses['content--clickable']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "header" },
    });
    /** @type {__VLS_StyleScopedClasses['header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Orbit} */
    Orbit;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        size: (24),
        color: "var(--p-primary-color)",
        ...{ class: "icon" },
    }));
    const __VLS_2 = __VLS_1({
        size: (24),
        color: "var(--p-primary-color)",
        ...{ class: "icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    /** @type {__VLS_StyleScopedClasses['icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.data.name);
    if (__VLS_ctx.manageAvailable) {
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }));
        const __VLS_7 = __VLS_6({
            ...{ 'onClick': {} },
            variant: "text",
            severity: "secondary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
        let __VLS_10;
        const __VLS_11 = ({ click: {} },
            { onClick: (__VLS_ctx.openEdit) });
        const { default: __VLS_12 } = __VLS_8.slots;
        {
            const { icon: __VLS_13 } = __VLS_8.slots;
            let __VLS_14;
            /** @ts-ignore @type { | typeof __VLS_components.EllipsisVertical} */
            EllipsisVertical;
            // @ts-ignore
            const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
                size: (14),
            }));
            const __VLS_16 = __VLS_15({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_15));
            // @ts-ignore
            [data, manageAvailable, openEdit,];
        }
        // @ts-ignore
        [];
        var __VLS_8;
        var __VLS_9;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "list" },
    });
    /** @type {__VLS_StyleScopedClasses['list']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    const __VLS_19 = UiId || UiId;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        id: (__VLS_ctx.data.id),
    }));
    const __VLS_21 = __VLS_20({
        id: (__VLS_ctx.data.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "value" },
    });
    /** @type {__VLS_StyleScopedClasses['value']} */ ;
    (__VLS_ctx.data.total_collections);
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "value" },
    });
    /** @type {__VLS_StyleScopedClasses['value']} */ ;
    (new Date(__VLS_ctx.data.created_at).toLocaleDateString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text" },
    });
    /** @type {__VLS_StyleScopedClasses['text']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "value" },
    });
    /** @type {__VLS_StyleScopedClasses['value']} */ ;
    (__VLS_ctx.data.total_members);
}
if (__VLS_ctx.type === 'create') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "content content--center" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    /** @type {__VLS_StyleScopedClasses['content--center']} */ ;
    if (__VLS_ctx.manageAvailable) {
        let __VLS_24;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
            ...{ 'onClick': {} },
            severity: "secondary",
            rounded: true,
        }));
        const __VLS_26 = __VLS_25({
            ...{ 'onClick': {} },
            severity: "secondary",
            rounded: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        let __VLS_29;
        const __VLS_30 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.type === 'create'))
                        return;
                    if (!(__VLS_ctx.manageAvailable))
                        return;
                    __VLS_ctx.$emit('createNew');
                    // @ts-ignore
                    [type, data, data, data, data, manageAvailable, $emit,];
                } });
        const { default: __VLS_31 } = __VLS_27.slots;
        {
            const { icon: __VLS_32 } = __VLS_27.slots;
            let __VLS_33;
            /** @ts-ignore @type { | typeof __VLS_components.Plus} */
            Plus;
            // @ts-ignore
            const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
                size: (14),
            }));
            const __VLS_35 = __VLS_34({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_34));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_27;
        var __VLS_28;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text" },
        });
        /** @type {__VLS_StyleScopedClasses['text']} */ ;
    }
    else {
        let __VLS_38;
        /** @ts-ignore @type { | typeof __VLS_components.Lock} */
        Lock;
        // @ts-ignore
        const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
            size: (35),
            color: "var(--p-primary-color)",
        }));
        const __VLS_40 = __VLS_39({
            size: (35),
            color: "var(--p-primary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_39));
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text" },
        });
        /** @type {__VLS_StyleScopedClasses['text']} */ ;
    }
}
if (__VLS_ctx.data) {
    const __VLS_43 = OrbitEditor || OrbitEditor;
    // @ts-ignore
    const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
        visible: (__VLS_ctx.editVisible),
        orbit: (__VLS_ctx.data),
    }));
    const __VLS_45 = __VLS_44({
        visible: (__VLS_ctx.editVisible),
        orbit: (__VLS_ctx.data),
    }, ...__VLS_functionalComponentArgsRest(__VLS_44));
}
// @ts-ignore
[data, data, editVisible,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
