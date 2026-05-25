/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Target } from 'lucide-vue-next';
import { computed, ref } from 'vue';
import { cutStringOnMiddle } from '@/helpers/helpers';
import { OverlayBadge, Button, Popover, InputText, ToggleSwitch, Divider, Checkbox } from 'primevue';
const props = defineProps();
const emit = defineEmits();
const popover = ref();
const searchValue = ref('');
const selectedColumnsCurrent = ref(fillSelectedColumns(props.columns, props.selectedColumns));
const isShowAll = computed(() => {
    return selectedColumnsCurrent.value.every((column) => column.selected);
});
const visibleColumns = computed(() => {
    if (searchValue.value)
        return selectedColumnsCurrent.value.filter((column) => column.name.includes(searchValue.value.trim()));
    return selectedColumnsCurrent.value;
});
const hideColumnsCount = computed(() => {
    if (!props.selectedColumns.length)
        return 0;
    return props.columns.length - props.selectedColumns.length;
});
function fillSelectedColumns(allColumns, selectedColumns) {
    return allColumns.map((column) => ({
        name: column,
        selected: !selectedColumns.length ? true : selectedColumns.includes(column),
    }));
}
function togglePopover(event) {
    popover.value.toggle(event);
}
function apply() {
    const newSelectedColumns = selectedColumnsCurrent.value
        .filter((column) => column.selected)
        .map((column) => column.name);
    emit('edit', JSON.parse(JSON.stringify(newSelectedColumns)));
    popover.value.toggle();
}
function onShowAllUpdate(value) {
    if (value)
        selectedColumnsCurrent.value = fillSelectedColumns(props.columns, []);
    else
        selectedColumnsCurrent.value = fillSelectedColumns(props.columns, props.columns.filter((column) => column === props.target));
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
if (__VLS_ctx.hideColumnsCount) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.OverlayBadge | typeof __VLS_components.OverlayBadge} */
    OverlayBadge;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        value: (__VLS_ctx.hideColumnsCount),
    }));
    const __VLS_2 = __VLS_1({
        value: (__VLS_ctx.hideColumnsCount),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    const { default: __VLS_5 } = __VLS_3.slots;
    let __VLS_6;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: (__VLS_ctx.roundedButton),
        variant: "outlined",
    }));
    const __VLS_8 = __VLS_7({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: (__VLS_ctx.roundedButton),
        variant: "outlined",
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    let __VLS_11;
    const __VLS_12 = ({ click: {} },
        { onClick: (__VLS_ctx.togglePopover) });
    const { default: __VLS_13 } = __VLS_9.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    const __VLS_14 = (__VLS_ctx.buttonIcon);
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        size: (14),
    }));
    const __VLS_16 = __VLS_15({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [hideColumnsCount, hideColumnsCount, roundedButton, togglePopover, buttonIcon,];
    var __VLS_9;
    var __VLS_10;
    // @ts-ignore
    [];
    var __VLS_3;
}
else {
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: (__VLS_ctx.roundedButton),
        variant: "outlined",
    }));
    const __VLS_21 = __VLS_20({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: (__VLS_ctx.roundedButton),
        variant: "outlined",
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    let __VLS_24;
    const __VLS_25 = ({ click: {} },
        { onClick: (__VLS_ctx.togglePopover) });
    const { default: __VLS_26 } = __VLS_22.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "button-label" },
    });
    /** @type {__VLS_StyleScopedClasses['button-label']} */ ;
    const __VLS_27 = (__VLS_ctx.buttonIcon);
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent1(__VLS_27, new __VLS_27({
        size: (14),
    }));
    const __VLS_29 = __VLS_28({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    // @ts-ignore
    [roundedButton, togglePopover, buttonIcon,];
    var __VLS_22;
    var __VLS_23;
}
let __VLS_32;
/** @ts-ignore @type { | typeof __VLS_components.Popover | typeof __VLS_components.Popover} */
Popover;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent1(__VLS_32, new __VLS_32({
    ref: "popover",
}));
const __VLS_34 = __VLS_33({
    ref: "popover",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_37;
const { default: __VLS_39 } = __VLS_35.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['popover-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "main" },
});
/** @type {__VLS_StyleScopedClasses['main']} */ ;
let __VLS_40;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent1(__VLS_40, new __VLS_40({
    placeholder: "Column",
    modelValue: (__VLS_ctx.searchValue),
}));
const __VLS_42 = __VLS_41({
    placeholder: "Column",
    modelValue: (__VLS_ctx.searchValue),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "list" },
});
/** @type {__VLS_StyleScopedClasses['list']} */ ;
for (const [column] of __VLS_vFor((__VLS_ctx.visibleColumns))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        key: (column.name),
        ...{ class: "column" },
    });
    /** @type {__VLS_StyleScopedClasses['column']} */ ;
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.ToggleSwitch} */
    ToggleSwitch;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        modelValue: (column.selected),
        disabled: (column.name === __VLS_ctx.target),
    }));
    const __VLS_47 = __VLS_46({
        modelValue: (column.selected),
        disabled: (column.name === __VLS_ctx.target),
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item-title" },
    });
    /** @type {__VLS_StyleScopedClasses['item-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "label" },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    (__VLS_ctx.cutStringOnMiddle(column.name, 24));
    if (column.name === __VLS_ctx.target) {
        let __VLS_50;
        /** @ts-ignore @type { | typeof __VLS_components.Target} */
        Target;
        // @ts-ignore
        const __VLS_51 = __VLS_asFunctionalComponent1(__VLS_50, new __VLS_50({
            width: "16",
            height: "16",
            color: "var(--p-message-error-color)",
        }));
        const __VLS_52 = __VLS_51({
            width: "16",
            height: "16",
            color: "var(--p-message-error-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_51));
    }
    // @ts-ignore
    [searchValue, visibleColumns, target, target, cutStringOnMiddle,];
}
let __VLS_55;
/** @ts-ignore @type { | typeof __VLS_components.Divider} */
Divider;
// @ts-ignore
const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
    ...{ class: "divider" },
}));
const __VLS_57 = __VLS_56({
    ...{ class: "divider" },
}, ...__VLS_functionalComponentArgsRest(__VLS_56));
/** @type {__VLS_StyleScopedClasses['divider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "popover-footer" },
});
/** @type {__VLS_StyleScopedClasses['popover-footer']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-2" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
let __VLS_60;
/** @ts-ignore @type { | typeof __VLS_components.Checkbox} */
Checkbox;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent1(__VLS_60, new __VLS_60({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.isShowAll),
    inputId: "showAll",
    binary: true,
}));
const __VLS_62 = __VLS_61({
    ...{ 'onUpdate:modelValue': {} },
    modelValue: (__VLS_ctx.isShowAll),
    inputId: "showAll",
    binary: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
let __VLS_65;
const __VLS_66 = ({ 'update:modelValue': {} },
    { 'onUpdate:modelValue': (...[$event]) => {
            __VLS_ctx.onShowAllUpdate($event);
            // @ts-ignore
            [isShowAll, onShowAllUpdate,];
        } });
var __VLS_63;
var __VLS_64;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "showAll",
});
let __VLS_67;
/** @ts-ignore @type { | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_68 = __VLS_asFunctionalComponent1(__VLS_67, new __VLS_67({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}));
const __VLS_69 = __VLS_68({
    ...{ 'onClick': {} },
    label: "apply",
    severity: "secondary",
}, ...__VLS_functionalComponentArgsRest(__VLS_68));
let __VLS_72;
const __VLS_73 = ({ click: {} },
    { onClick: (__VLS_ctx.apply) });
var __VLS_70;
var __VLS_71;
// @ts-ignore
[apply,];
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
