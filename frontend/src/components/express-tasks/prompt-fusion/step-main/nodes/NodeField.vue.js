/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, ref } from 'vue';
import { PROMPT_FIELDS_ICONS } from '../../interfaces';
import { Position } from '@vue-flow/core';
import { useVueFlow } from '@vue-flow/core';
const { edges } = useVueFlow();
const props = defineProps();
const fieldRef = ref();
const handleTopPosition = ref(null);
const variantClass = computed(() => props.field.variant || '');
const connectingHandles = computed(() => {
    return edges.value.reduce((acc, edge) => {
        edge.sourceHandle && acc.add(edge.sourceHandle);
        edge.targetHandle && acc.add(edge.targetHandle);
        return acc;
    }, new Set());
});
const label = computed(() => (props.index ? `CONDITION ${props.index}` : null));
function calcHandlePosition() {
    if (!fieldRef.value)
        return;
    handleTopPosition.value = fieldRef.value.offsetTop + fieldRef.value.clientHeight / 2;
}
onMounted(() => {
    calcHandlePosition();
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
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['condition']} */ ;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ref: "fieldRef",
    ...{ class: "field" },
    ...{ class: ({ [__VLS_ctx.variantClass]: __VLS_ctx.field.variant }) },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
if (__VLS_ctx.label) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    (__VLS_ctx.label);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text" },
});
/** @type {__VLS_StyleScopedClasses['text']} */ ;
(__VLS_ctx.field.value);
if (__VLS_ctx.field.type || __VLS_ctx.field.variadic) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "icons" },
    });
    /** @type {__VLS_StyleScopedClasses['icons']} */ ;
    if (__VLS_ctx.field.type) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "icon" },
        });
        /** @type {__VLS_StyleScopedClasses['icon']} */ ;
        const __VLS_0 = (__VLS_ctx.PROMPT_FIELDS_ICONS[__VLS_ctx.field.type]);
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
            width: "16",
            height: "16",
            color: "var(--p-icon-muted-color)",
        }));
        const __VLS_2 = __VLS_1({
            width: "16",
            height: "16",
            color: "var(--p-icon-muted-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    }
    if (__VLS_ctx.field.variadic) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "icon" },
        });
        /** @type {__VLS_StyleScopedClasses['icon']} */ ;
        let __VLS_5;
        /** @ts-ignore @type { | typeof __VLS_components.brackets | typeof __VLS_components.Brackets} */
        brackets;
        // @ts-ignore
        const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
            width: "16",
            height: "16",
            color: "var(--p-icon-muted-color)",
        }));
        const __VLS_7 = __VLS_6({
            width: "16",
            height: "16",
            color: "var(--p-icon-muted-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    }
}
if (__VLS_ctx.handleTopPosition) {
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.handle | typeof __VLS_components.Handle} */
    handle;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        ...{ class: ({ connected: __VLS_ctx.connectingHandles.has(__VLS_ctx.field.id) }) },
        id: (__VLS_ctx.field.id),
        position: (__VLS_ctx.field.handlePosition),
        ...{ style: ({ top: __VLS_ctx.handleTopPosition + 'px' }) },
        type: (__VLS_ctx.field.handlePosition === __VLS_ctx.Position.Left ? 'target' : 'source'),
    }));
    const __VLS_12 = __VLS_11({
        ...{ class: ({ connected: __VLS_ctx.connectingHandles.has(__VLS_ctx.field.id) }) },
        id: (__VLS_ctx.field.id),
        position: (__VLS_ctx.field.handlePosition),
        ...{ style: ({ top: __VLS_ctx.handleTopPosition + 'px' }) },
        type: (__VLS_ctx.field.handlePosition === __VLS_ctx.Position.Left ? 'target' : 'source'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    /** @type {__VLS_StyleScopedClasses['connected']} */ ;
}
// @ts-ignore
[variantClass, field, field, field, field, field, field, field, field, field, field, field, label, label, PROMPT_FIELDS_ICONS, handleTopPosition, handleTopPosition, connectingHandles, Position,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
