/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref, watch } from 'vue';
import { CalendarFold, Hash, CaseUpper } from 'lucide-vue-next';
import { cutStringOnMiddle } from '@/helpers/helpers';
import UiCustomRadio from '@/components/ui/UiCustomRadio.vue';
const typesIcons = {
    number: Hash,
    date: CalendarFold,
    string: CaseUpper,
};
const props = defineProps();
const popover = ref();
const searchValue = ref('');
const columnsState = ref(fillColumnsState());
const searchedColumns = computed(() => columnsState.value.filter((column) => column.name.toLowerCase().includes(searchValue.value.toLowerCase())));
function togglePopover(event) {
    popover.value.toggle(event);
}
function apply() {
    columnsState.value.map((column) => {
        const currentColumn = props.columns.find((c) => c.name === column.name);
        if (currentColumn)
            currentColumn.variant = column.variant;
    });
    popover.value.toggle();
}
function fillColumnsState() {
    const availableColumns = props.selectedColumns.length
        ? props.columns.filter((column) => props.selectedColumns.includes(column.name))
        : props.columns;
    return availableColumns.map((column) => ({
        name: column.name,
        type: props.columnTypes[column.name],
        variant: column.variant,
    }));
}
function onPopoverHide() {
    searchValue.value = '';
    columnsState.value = fillColumnsState();
}
watch(() => props.selectedColumns, (val) => {
    columnsState.value = fillColumnsState();
}, { deep: true });
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['variant-icon']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "outlined",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "outlined",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.togglePopover) });
const { default: __VLS_7 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "button-label" },
});
/** @type {__VLS_StyleScopedClasses['button-label']} */ ;
let __VLS_8;
/** @ts-ignore @type { | typeof __VLS_components.bolt | typeof __VLS_components.Bolt} */
bolt;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    width: "14",
    height: "14",
}));
const __VLS_10 = __VLS_9({
    width: "14",
    height: "14",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
// @ts-ignore
[togglePopover,];
var __VLS_3;
var __VLS_4;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover'] | typeof __VLS_components.dPopover | typeof __VLS_components.DPopover | typeof __VLS_components['d-popover']} */
dPopover;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    ...{ 'onHide': {} },
    ref: "popover",
    ...{ style: {} },
}));
const __VLS_15 = __VLS_14({
    ...{ 'onHide': {} },
    ref: "popover",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
const __VLS_19 = ({ hide: {} },
    { onHide: (__VLS_ctx.onPopoverHide) });
var __VLS_20;
const { default: __VLS_22 } = __VLS_16.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "main" },
});
/** @type {__VLS_StyleScopedClasses['main']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
let __VLS_23;
/** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
dInputText;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
    placeholder: "Find column",
    modelValue: (__VLS_ctx.searchValue),
    fluid: true,
    ...{ class: "input" },
}));
const __VLS_25 = __VLS_24({
    placeholder: "Find column",
    modelValue: (__VLS_ctx.searchValue),
    fluid: true,
    ...{ class: "input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
/** @type {__VLS_StyleScopedClasses['input']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "list" },
});
/** @type {__VLS_StyleScopedClasses['list']} */ ;
for (const [column] of __VLS_vFor((__VLS_ctx.searchedColumns))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (column.name),
        ...{ class: "column" },
    });
    /** @type {__VLS_StyleScopedClasses['column']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-title" },
    });
    /** @type {__VLS_StyleScopedClasses['item-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    (__VLS_ctx.cutStringOnMiddle(column.name, 24));
    const __VLS_28 = (__VLS_ctx.typesIcons[column.type]);
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
        width: "16",
        height: "16",
        color: "var(--p-icon-muted-color)",
        ...{ class: "variant-icon" },
    }));
    const __VLS_30 = __VLS_29({
        width: "16",
        height: "16",
        color: "var(--p-icon-muted-color)",
        ...{ class: "variant-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    /** @type {__VLS_StyleScopedClasses['variant-icon']} */ ;
    const __VLS_33 = UiCustomRadio;
    // @ts-ignore
    const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
        modelValue: (column.variant),
        options: (['input', 'output']),
    }));
    const __VLS_35 = __VLS_34({
        modelValue: (column.variant),
        options: (['input', 'output']),
    }, ...__VLS_functionalComponentArgsRest(__VLS_34));
    // @ts-ignore
    [onPopoverHide, searchValue, searchedColumns, cutStringOnMiddle, typesIcons,];
}
let __VLS_38;
/** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
dDivider;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
    ...{ class: "divider" },
}));
const __VLS_40 = __VLS_39({
    ...{ class: "divider" },
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
/** @type {__VLS_StyleScopedClasses['divider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer']} */ ;
let __VLS_43;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}));
const __VLS_45 = __VLS_44({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_44));
let __VLS_48;
const __VLS_49 = ({ click: {} },
    { onClick: (__VLS_ctx.apply) });
var __VLS_46;
var __VLS_47;
// @ts-ignore
[apply,];
var __VLS_16;
var __VLS_17;
// @ts-ignore
var __VLS_21 = __VLS_20;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
