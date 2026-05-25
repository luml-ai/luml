/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { ArrowDownUp, Trash2, Plus } from 'lucide-vue-next';
const props = defineProps();
const emit = defineEmits();
const isPopoverOpen = ref(false);
const sortPopover = ref();
function getInitialSortData() {
    if (props.multiSortMeta.length) {
        return props.multiSortMeta.map((meta, i) => ({
            id: i + 1,
            selectedColumn: meta.field,
            sortOrder: String(meta.order),
        }));
    }
    if (!props.columns.length)
        return [];
    return [{ id: 1, selectedColumn: props.columns[0] ?? '', sortOrder: null }];
}
const sortData = ref(getInitialSortData());
const canAddSort = computed(() => {
    const usedColumns = new Set(sortData.value.map((item) => item.selectedColumn));
    return props.columns.some((col) => !usedColumns.has(col));
});
const isSortAvailable = computed(() => {
    return sortData.value.reduce((acc, item) => {
        if (!item.selectedColumn || !item.sortOrder)
            acc = false;
        return acc;
    }, true);
});
const columnsForSelect = computed(() => {
    const columnsForSelect = [...props.columns];
    const selected = sortData.value
        .filter((item) => !columnsForSelect.includes(item.selectedColumn))
        .map((item) => item.selectedColumn);
    columnsForSelect.push(...selected);
    return columnsForSelect;
});
function toggleSort(event) {
    sortPopover.value.toggle(event);
    isPopoverOpen.value = !isPopoverOpen.value;
}
function deleteSort(id) {
    sortData.value = sortData.value.filter((item) => item.id !== id);
}
function addSort() {
    const selectedColumnsNames = sortData.value.map((item) => item.selectedColumn);
    const currentColumn = props.columns.find((column) => !selectedColumnsNames.includes(column));
    sortData.value.push({
        id: sortData.value.length + 1,
        selectedColumn: currentColumn || '',
        sortOrder: null,
    });
}
function clear() {
    sortData.value = [
        {
            id: 1,
            selectedColumn: props.columns[0] ?? '',
            sortOrder: null,
        },
    ];
    emit('update:multiSortMeta', []);
    sortPopover.value.hide();
}
function apply() {
    if (!isSortAvailable.value)
        return;
    const newMultiSortMeta = sortData.value.map((item) => ({
        field: item.selectedColumn,
        order: Number(item.sortOrder),
    }));
    emit('update:multiSortMeta', JSON.parse(JSON.stringify(newMultiSortMeta)));
    sortPopover.value.hide();
}
function isOptionDisabled(option, id) {
    return !!sortData.value.find((item) => item.selectedColumn === option && item.id !== id);
}
function onPopoverHide() {
    sortData.value = getInitialSortData();
    isPopoverOpen.value = false;
}
watch([() => props.multiSortMeta, () => props.columns], () => {
    if (!isPopoverOpen.value) {
        sortData.value = getInitialSortData();
    }
}, { deep: true });
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
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['radio']} */ ;
if (__VLS_ctx.multiSortMeta.length) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.dOverlayBadge | typeof __VLS_components.DOverlayBadge | typeof __VLS_components['d-overlay-badge'] | typeof __VLS_components.dOverlayBadge | typeof __VLS_components.DOverlayBadge | typeof __VLS_components['d-overlay-badge']} */
    dOverlayBadge;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        value: (__VLS_ctx.multiSortMeta.length),
    }));
    const __VLS_2 = __VLS_1({
        value: (__VLS_ctx.multiSortMeta.length),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    const { default: __VLS_5 } = __VLS_3.slots;
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "outlined",
    }));
    const __VLS_8 = __VLS_7({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "outlined",
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    let __VLS_11;
    const __VLS_12 = ({ click: {} },
        { onClick: (__VLS_ctx.toggleSort) });
    const { default: __VLS_13 } = __VLS_9.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.ArrowDownUp} */
    ArrowDownUp;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        width: "14",
        height: "14",
    }));
    const __VLS_16 = __VLS_15({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [multiSortMeta, multiSortMeta, toggleSort,];
    var __VLS_9;
    var __VLS_10;
    // @ts-ignore
    [];
    var __VLS_3;
}
else {
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "outlined",
    }));
    const __VLS_21 = __VLS_20({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "outlined",
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    let __VLS_24;
    const __VLS_25 = ({ click: {} },
        { onClick: (__VLS_ctx.toggleSort) });
    const { default: __VLS_26 } = __VLS_22.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    let __VLS_27;
    /** @ts-ignore @type { | typeof __VLS_components.ArrowDownUp} */
    ArrowDownUp;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        width: "14",
        height: "14",
    }));
    const __VLS_29 = __VLS_28({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    // @ts-ignore
    [toggleSort,];
    var __VLS_22;
    var __VLS_23;
}
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover'] | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover']} */
dPopover;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    ...{ 'onHide': {} },
    ref: "sortPopover",
}));
const __VLS_34 = __VLS_33({
    ...{ 'onHide': {} },
    ref: "sortPopover",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_37;
const __VLS_38 = ({ hide: {} },
    { onHide: (__VLS_ctx.onPopoverHide) });
var __VLS_39;
const { default: __VLS_41 } = __VLS_35.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sort-list" },
});
/** @type {__VLS_StyleScopedClasses['sort-list']} */ ;
for (const [sortItem] of __VLS_vFor((__VLS_ctx.sortData))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (sortItem.id),
        ...{ class: "sort-item" },
    });
    /** @type {__VLS_StyleScopedClasses['sort-item']} */ ;
    let __VLS_42;
    /** @ts-ignore @type { | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select']} */
    dSelect;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
        options: (__VLS_ctx.columnsForSelect),
        modelValue: (sortItem.selectedColumn),
        optionDisabled: ((option) => __VLS_ctx.isOptionDisabled(option, sortItem.id)),
    }));
    const __VLS_44 = __VLS_43({
        options: (__VLS_ctx.columnsForSelect),
        modelValue: (sortItem.selectedColumn),
        optionDisabled: ((option) => __VLS_ctx.isOptionDisabled(option, sortItem.id)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "sort-radio" },
    });
    /** @type {__VLS_StyleScopedClasses['sort-radio']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "radio" },
    });
    /** @type {__VLS_StyleScopedClasses['radio']} */ ;
    let __VLS_47;
    /** @ts-ignore @type { | typeof __VLS_components.dRadioButton | typeof __VLS_components.DRadioButton | typeof __VLS_components['d-radio-button']} */
    dRadioButton;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
        modelValue: (sortItem.sortOrder),
        inputId: (`sort_${sortItem.id}_1`),
        value: "1",
    }));
    const __VLS_49 = __VLS_48({
        modelValue: (sortItem.sortOrder),
        inputId: (`sort_${sortItem.id}_1`),
        value: "1",
    }, ...__VLS_functionalComponentArgsRest(__VLS_48));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: (`sort_${sortItem.id}_1`),
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "radio" },
    });
    /** @type {__VLS_StyleScopedClasses['radio']} */ ;
    let __VLS_52;
    /** @ts-ignore @type { | typeof __VLS_components.dRadioButton | typeof __VLS_components.DRadioButton | typeof __VLS_components['d-radio-button']} */
    dRadioButton;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent1(__VLS_52, new __VLS_52({
        modelValue: (sortItem.sortOrder),
        inputId: (`sort_${sortItem.id}_2`),
        value: "-1",
    }));
    const __VLS_54 = __VLS_53({
        modelValue: (sortItem.sortOrder),
        inputId: (`sort_${sortItem.id}_2`),
        value: "-1",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: (`sort_${sortItem.id}_2`),
    });
    if (__VLS_ctx.sortData.length > 1) {
        let __VLS_57;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_58 = __VLS_asFunctionalComponent1(__VLS_57, new __VLS_57({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
        }));
        const __VLS_59 = __VLS_58({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
        }, ...__VLS_functionalComponentArgsRest(__VLS_58));
        let __VLS_62;
        const __VLS_63 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.sortData.length > 1))
                        return;
                    __VLS_ctx.deleteSort(sortItem.id);
                    // @ts-ignore
                    [onPopoverHide, sortData, sortData, columnsForSelect, isOptionDisabled, deleteSort,];
                } });
        const { default: __VLS_64 } = __VLS_60.slots;
        {
            const { icon: __VLS_65 } = __VLS_60.slots;
            let __VLS_66;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_67 = __VLS_asFunctionalComponent1(__VLS_66, new __VLS_66({
                width: "14",
                height: "14",
            }));
            const __VLS_68 = __VLS_67({
                width: "14",
                height: "14",
            }, ...__VLS_functionalComponentArgsRest(__VLS_67));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_60;
        var __VLS_61;
    }
    // @ts-ignore
    [];
}
let __VLS_71;
/** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
dDivider;
// @ts-ignore
const __VLS_72 = __VLS_asFunctionalComponent1(__VLS_71, new __VLS_71({}));
const __VLS_73 = __VLS_72({}, ...__VLS_functionalComponentArgsRest(__VLS_72));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer']} */ ;
let __VLS_76;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent1(__VLS_76, new __VLS_76({
    ...{ 'onClick': {} },
    ...{ style: ({ visibility: __VLS_ctx.canAddSort ? 'visible' : 'hidden' }) },
    label: "Add sort",
    variant: "text",
}));
const __VLS_78 = __VLS_77({
    ...{ 'onClick': {} },
    ...{ style: ({ visibility: __VLS_ctx.canAddSort ? 'visible' : 'hidden' }) },
    label: "Add sort",
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
let __VLS_81;
const __VLS_82 = ({ click: {} },
    { onClick: (__VLS_ctx.addSort) });
const { default: __VLS_83 } = __VLS_79.slots;
{
    const { icon: __VLS_84 } = __VLS_79.slots;
    let __VLS_85;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent1(__VLS_85, new __VLS_85({
        width: "14",
        height: "14",
    }));
    const __VLS_87 = __VLS_86({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    // @ts-ignore
    [canAddSort, addSort,];
}
// @ts-ignore
[];
var __VLS_79;
var __VLS_80;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer-buttons" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer-buttons']} */ ;
let __VLS_90;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent1(__VLS_90, new __VLS_90({
    ...{ 'onClick': {} },
    label: "clear",
    severity: "secondary",
    variant: "outlined",
}));
const __VLS_92 = __VLS_91({
    ...{ 'onClick': {} },
    label: "clear",
    severity: "secondary",
    variant: "outlined",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
let __VLS_95;
const __VLS_96 = ({ click: {} },
    { onClick: (__VLS_ctx.clear) });
var __VLS_93;
var __VLS_94;
let __VLS_97;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent1(__VLS_97, new __VLS_97({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
    disabled: (!__VLS_ctx.isSortAvailable),
}));
const __VLS_99 = __VLS_98({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
    disabled: (!__VLS_ctx.isSortAvailable),
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
let __VLS_102;
const __VLS_103 = ({ click: {} },
    { onClick: (__VLS_ctx.apply) });
var __VLS_100;
var __VLS_101;
// @ts-ignore
[clear, isSortAvailable, apply,];
var __VLS_35;
var __VLS_36;
// @ts-ignore
var __VLS_40 = __VLS_39;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
