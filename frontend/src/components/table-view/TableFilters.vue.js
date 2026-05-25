/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { FilterType } from '@/lib/data-table/interfaces';
import { Filter, Plus, Trash2 } from 'lucide-vue-next';
const props = defineProps();
const emit = defineEmits();
const filterPopover = ref();
const currentFilters = ref(getCurrentFilters());
const columnSelectOptions = computed(() => {
    const filterAcc = props.filters.reduce((acc, filter) => {
        acc.includes(filter.column) || acc.push(filter.column);
        return acc;
    }, []);
    props.data.forEach((item) => {
        filterAcc.includes(item.name) || filterAcc.push(item.name);
    });
    return filterAcc;
});
const getFilterTypeSelectOptions = computed(() => (column) => {
    const columnType = props.columnTypes[column];
    switch (columnType) {
        case undefined:
            return [];
        case 'number':
            return [
                FilterType.Equals,
                FilterType.NotEquals,
                FilterType.LessThan,
                FilterType.LessThanOrEqualTo,
                FilterType.GreaterThan,
                FilterType.GreaterThanOrEqualTo,
            ];
        default:
            return [FilterType.Equals, FilterType.NotEquals];
    }
});
const getInputType = computed(() => (column) => {
    const columnType = props.data.find((item) => item.name === column)?.type;
    switch (columnType) {
        case 'number':
            return 'number';
        default:
            return 'string';
    }
});
function getCurrentFilters() {
    return props.filters.length
        ? JSON.parse(JSON.stringify(props.filters))
        : [
            {
                id: 1,
                column: '',
                filterType: FilterType.Equals,
                parameter: '',
            },
        ];
}
function toggleFilter(event) {
    filterPopover.value.toggle(event);
}
function deleteFilter(id) {
    currentFilters.value = currentFilters.value.filter((filter) => filter.id !== id);
}
function addMoreFilter() {
    currentFilters.value.push({
        id: currentFilters.value.length + 1,
        column: '',
        filterType: FilterType.Equals,
        parameter: '',
    });
}
function clear() {
    currentFilters.value = [
        {
            id: 1,
            column: '',
            filterType: FilterType.Equals,
            parameter: '',
        },
    ];
    emit('apply', []);
    filterPopover.value.toggle();
}
function apply() {
    const availableFilters = currentFilters.value.filter((filter) => filter.column && filter.filterType && filter.parameter);
    emit('apply', JSON.parse(JSON.stringify(availableFilters)));
    filterPopover.value.toggle();
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
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
if (__VLS_ctx.filters.length) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.dOverlayBadge | typeof __VLS_components.DOverlayBadge | typeof __VLS_components['d-overlay-badge'] | typeof __VLS_components.dOverlayBadge | typeof __VLS_components.DOverlayBadge | typeof __VLS_components['d-overlay-badge']} */
    dOverlayBadge;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        value: (__VLS_ctx.filters.length),
    }));
    const __VLS_2 = __VLS_1({
        value: (__VLS_ctx.filters.length),
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
        { onClick: (__VLS_ctx.toggleFilter) });
    const { default: __VLS_13 } = __VLS_9.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Filter} */
    Filter;
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
    [filters, filters, toggleFilter,];
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
        { onClick: (__VLS_ctx.toggleFilter) });
    const { default: __VLS_26 } = __VLS_22.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    let __VLS_27;
    /** @ts-ignore @type { | typeof __VLS_components.Filter} */
    Filter;
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
    [toggleFilter,];
    var __VLS_22;
    var __VLS_23;
}
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover'] | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover']} */
dPopover;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    ref: "filterPopover",
}));
const __VLS_34 = __VLS_33({
    ref: "filterPopover",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_37;
const { default: __VLS_39 } = __VLS_35.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-wrapper" },
    ...{ style: ({ width: '39.9rem' }) },
});
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "filters-list" },
});
/** @type {__VLS_StyleScopedClasses['filters-list']} */ ;
for (const [filter] of __VLS_vFor((__VLS_ctx.currentFilters))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (filter.id),
        ...{ class: "filter-item" },
    });
    /** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
    let __VLS_40;
    /** @ts-ignore @type { | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select']} */
    dSelect;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
        placeholder: "Column",
        options: (__VLS_ctx.columnSelectOptions),
        modelValue: (filter.column),
    }));
    const __VLS_42 = __VLS_41({
        placeholder: "Column",
        options: (__VLS_ctx.columnSelectOptions),
        modelValue: (filter.column),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.dSelect | typeof __VLS_components.DSelect | typeof __VLS_components['d-select']} */
    dSelect;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        placeholder: "Operator",
        options: (__VLS_ctx.getFilterTypeSelectOptions(filter.column)),
        modelValue: (filter.filterType),
    }));
    const __VLS_47 = __VLS_46({
        placeholder: "Operator",
        options: (__VLS_ctx.getFilterTypeSelectOptions(filter.column)),
        modelValue: (filter.filterType),
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    let __VLS_50;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
        ...{ class: "input" },
        placeholder: "Value",
        modelValue: (filter.parameter),
        type: (__VLS_ctx.getInputType(filter.column)),
    }));
    const __VLS_52 = __VLS_51({
        ...{ class: "input" },
        placeholder: "Value",
        modelValue: (filter.parameter),
        type: (__VLS_ctx.getInputType(filter.column)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_51));
    /** @type {__VLS_StyleScopedClasses['input']} */ ;
    if (__VLS_ctx.currentFilters.length > 1) {
        let __VLS_55;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
        }));
        const __VLS_57 = __VLS_56({
            ...{ 'onClick': {} },
            severity: "secondary",
            variant: "outlined",
        }, ...__VLS_functionalComponentArgsRest(__VLS_56));
        let __VLS_60;
        const __VLS_61 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.currentFilters.length > 1))
                        return;
                    __VLS_ctx.deleteFilter(filter.id);
                    // @ts-ignore
                    [currentFilters, currentFilters, columnSelectOptions, getFilterTypeSelectOptions, getInputType, deleteFilter,];
                } });
        const { default: __VLS_62 } = __VLS_58.slots;
        {
            const { icon: __VLS_63 } = __VLS_58.slots;
            let __VLS_64;
            /** @ts-ignore @type { | typeof __VLS_components.Trash2} */
            Trash2;
            // @ts-ignore
            const __VLS_65 = __VLS_asFunctionalComponent1(__VLS_64, new __VLS_64({
                width: "14",
                height: "14",
            }));
            const __VLS_66 = __VLS_65({
                width: "14",
                height: "14",
            }, ...__VLS_functionalComponentArgsRest(__VLS_65));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_58;
        var __VLS_59;
    }
    // @ts-ignore
    [];
}
let __VLS_69;
/** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
dDivider;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent1(__VLS_69, new __VLS_69({}));
const __VLS_71 = __VLS_70({}, ...__VLS_functionalComponentArgsRest(__VLS_70));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer']} */ ;
let __VLS_74;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent1(__VLS_74, new __VLS_74({
    ...{ 'onClick': {} },
    label: "Add filter",
    variant: "text",
}));
const __VLS_76 = __VLS_75({
    ...{ 'onClick': {} },
    label: "Add filter",
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
let __VLS_79;
const __VLS_80 = ({ click: {} },
    { onClick: (__VLS_ctx.addMoreFilter) });
const { default: __VLS_81 } = __VLS_77.slots;
{
    const { icon: __VLS_82 } = __VLS_77.slots;
    let __VLS_83;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_84 = __VLS_asFunctionalComponent1(__VLS_83, new __VLS_83({
        width: "14",
        height: "14",
    }));
    const __VLS_85 = __VLS_84({
        width: "14",
        height: "14",
    }, ...__VLS_functionalComponentArgsRest(__VLS_84));
    // @ts-ignore
    [addMoreFilter,];
}
// @ts-ignore
[];
var __VLS_77;
var __VLS_78;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer-buttons" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer-buttons']} */ ;
let __VLS_88;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent1(__VLS_88, new __VLS_88({
    ...{ 'onClick': {} },
    label: "clear",
    severity: "secondary",
    variant: "outlined",
}));
const __VLS_90 = __VLS_89({
    ...{ 'onClick': {} },
    label: "clear",
    severity: "secondary",
    variant: "outlined",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
let __VLS_93;
const __VLS_94 = ({ click: {} },
    { onClick: (__VLS_ctx.clear) });
var __VLS_91;
var __VLS_92;
let __VLS_95;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_96 = __VLS_asFunctionalComponent1(__VLS_95, new __VLS_95({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}));
const __VLS_97 = __VLS_96({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_96));
let __VLS_100;
const __VLS_101 = ({ click: {} },
    { onClick: (__VLS_ctx.apply) });
var __VLS_98;
var __VLS_99;
// @ts-ignore
[clear, apply,];
var __VLS_35;
// @ts-ignore
var __VLS_38 = __VLS_37;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
