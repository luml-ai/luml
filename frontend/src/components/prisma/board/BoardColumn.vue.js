/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { Tag } from 'primevue';
import { Plus } from 'lucide-vue-next';
import draggable from 'vuedraggable';
import BoardCard from './BoardCard.vue';
const props = withDefaults(defineProps(), { failCount: 0 });
const emit = defineEmits();
const localItems = ref([]);
watch(() => props.items, (val) => {
    localItems.value = [...val];
}, { immediate: true });
function onDragEnd() {
    emit('reorder', localItems.value);
}
const repoMap = computed(() => {
    const map = new Map();
    for (const r of props.repositories) {
        map.set(r.id, r.name);
    }
    return map;
});
function repoName(item) {
    return repoMap.value.get(item.data.repository_id) ?? 'Unknown';
}
function itemKey(item) {
    return `${item.kind}-${item.data.id}`;
}
const __VLS_defaults = { failCount: 0 };
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
/** @type {__VLS_StyleScopedClasses['create-card']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "board-column" },
});
/** @type {__VLS_StyleScopedClasses['board-column']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column-header" },
});
/** @type {__VLS_StyleScopedClasses['column-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "column-title" },
});
/** @type {__VLS_StyleScopedClasses['column-title']} */ ;
(__VLS_ctx.title);
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Tag} */
Tag;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    value: (String(__VLS_ctx.items.length - __VLS_ctx.failCount)),
    severity: (__VLS_ctx.severity),
    rounded: true,
    ...{ class: "count-badge" },
}));
const __VLS_2 = __VLS_1({
    value: (String(__VLS_ctx.items.length - __VLS_ctx.failCount)),
    severity: (__VLS_ctx.severity),
    rounded: true,
    ...{ class: "count-badge" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['count-badge']} */ ;
if (__VLS_ctx.failCount > 0) {
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Tag} */
    Tag;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        value: (String(__VLS_ctx.failCount)),
        severity: "danger",
        rounded: true,
        ...{ class: "count-badge" },
    }));
    const __VLS_7 = __VLS_6({
        value: (String(__VLS_ctx.failCount)),
        severity: "danger",
        rounded: true,
        ...{ class: "count-badge" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    /** @type {__VLS_StyleScopedClasses['count-badge']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column-scroll" },
});
/** @type {__VLS_StyleScopedClasses['column-scroll']} */ ;
if (__VLS_ctx.showCreate) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showCreate))
                    return;
                __VLS_ctx.emit('create');
                // @ts-ignore
                [title, items, failCount, failCount, failCount, severity, showCreate, emit,];
            } },
        ...{ class: "create-card" },
    });
    /** @type {__VLS_StyleScopedClasses['create-card']} */ ;
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        size: (14),
    }));
    const __VLS_12 = __VLS_11({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
}
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.draggable | typeof __VLS_components.Draggable | typeof __VLS_components.draggable | typeof __VLS_components.Draggable} */
draggable;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    ...{ 'onEnd': {} },
    modelValue: (__VLS_ctx.localItems),
    itemKey: (__VLS_ctx.itemKey),
    animation: (150),
    ghostClass: "drag-ghost",
    ...{ class: "drag-list" },
}));
const __VLS_17 = __VLS_16({
    ...{ 'onEnd': {} },
    modelValue: (__VLS_ctx.localItems),
    itemKey: (__VLS_ctx.itemKey),
    animation: (150),
    ghostClass: "drag-ghost",
    ...{ class: "drag-list" },
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
let __VLS_20;
const __VLS_21 = ({ end: {} },
    { onEnd: (__VLS_ctx.onDragEnd) });
/** @type {__VLS_StyleScopedClasses['drag-list']} */ ;
const { default: __VLS_22 } = __VLS_18.slots;
{
    const { item: __VLS_23 } = __VLS_18.slots;
    const [{ element }] = __VLS_vSlot(__VLS_23);
    const __VLS_24 = BoardCard;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
        ...{ 'onSelect': {} },
        ...{ 'onStart': {} },
        ...{ 'onDelete': {} },
        item: (element),
        repositoryName: (__VLS_ctx.repoName(element)),
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onSelect': {} },
        ...{ 'onStart': {} },
        ...{ 'onDelete': {} },
        item: (element),
        repositoryName: (__VLS_ctx.repoName(element)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_29;
    const __VLS_30 = ({ select: {} },
        { onSelect: (...[$event]) => {
                __VLS_ctx.emit('select', element);
                // @ts-ignore
                [emit, localItems, itemKey, onDragEnd, repoName,];
            } });
    const __VLS_31 = ({ start: {} },
        { onStart: (...[$event]) => {
                __VLS_ctx.emit('start', element);
                // @ts-ignore
                [emit,];
            } });
    const __VLS_32 = ({ delete: {} },
        { onDelete: (...[$event]) => {
                __VLS_ctx.emit('delete', element);
                // @ts-ignore
                [emit,];
            } });
    var __VLS_27;
    var __VLS_28;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_18;
var __VLS_19;
if (__VLS_ctx.items.length === 0 && !__VLS_ctx.showCreate) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "empty" },
    });
    /** @type {__VLS_StyleScopedClasses['empty']} */ ;
}
// @ts-ignore
[items, showCreate,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
