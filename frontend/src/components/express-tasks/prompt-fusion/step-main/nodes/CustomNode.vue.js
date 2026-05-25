/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PROMPT_NODES_ICONS } from '../../interfaces';
import { computed, ref } from 'vue';
import NodeField from './NodeField.vue';
const props = defineProps();
const emit = defineEmits();
const nodeRef = ref();
const toggleMenuButton = ref();
const isMenuOpen = ref(false);
const icon = computed(() => PROMPT_NODES_ICONS[props.data.icon]);
const inputFields = computed(() => props.data.fields.filter((field) => field.variant === 'input'));
const outputFields = computed(() => props.data.fields.filter((field) => field.variant === 'output'));
const conditionFields = computed(() => props.data.fields.filter((field) => field.variant === 'condition'));
const menuPosition = computed(() => {
    if (!nodeRef.value)
        return { left: 0, top: 0 };
    const nodePosition = { left: nodeRef.value.offsetLeft, top: nodeRef.value.offsetTop };
    return { left: nodePosition.left + 48, top: nodePosition.top + 36 };
});
const toggleMenu = () => {
    isMenuOpen.value = !isMenuOpen.value;
};
function onDuplicateClick() {
    toggleMenu();
    emit('duplicate');
}
function onDeleteClick() {
    emit('delete');
}
function onMenuOutsideClick() {
    if (isMenuOpen.value)
        toggleMenu();
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
/** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ref: "nodeRef",
    ...{ class: "node-body" },
});
/** @type {__VLS_StyleScopedClasses['node-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-left" },
});
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
const __VLS_0 = (__VLS_ctx.icon);
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    width: "15",
    height: "15",
    color: (__VLS_ctx.data.iconColor),
}));
const __VLS_2 = __VLS_1({
    width: "15",
    height: "15",
    color: (__VLS_ctx.data.iconColor),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "header-title" },
});
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
(__VLS_ctx.data.label);
if (__VLS_ctx.data.showMenu) {
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        ...{ 'onClick': {} },
        ref: "toggleMenuButton",
        severity: "secondary",
        variant: "text",
        rounded: true,
        ...{ class: "button" },
    }));
    const __VLS_7 = __VLS_6({
        ...{ 'onClick': {} },
        ref: "toggleMenuButton",
        severity: "secondary",
        variant: "text",
        rounded: true,
        ...{ class: "button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    let __VLS_10;
    const __VLS_11 = ({ click: {} },
        { onClick: (__VLS_ctx.toggleMenu) });
    var __VLS_12;
    /** @type {__VLS_StyleScopedClasses['button']} */ ;
    const { default: __VLS_14 } = __VLS_8.slots;
    {
        const { icon: __VLS_15 } = __VLS_8.slots;
        let __VLS_16;
        /** @ts-ignore @type { | typeof __VLS_components.ellipsis | typeof __VLS_components.Ellipsis} */
        ellipsis;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
            width: "20",
            height: "20",
        }));
        const __VLS_18 = __VLS_17({
            width: "20",
            height: "20",
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        // @ts-ignore
        [icon, data, data, data, toggleMenu,];
    }
    // @ts-ignore
    [];
    var __VLS_8;
    var __VLS_9;
    if (__VLS_ctx.isMenuOpen) {
        let __VLS_21;
        /** @ts-ignore @type { | typeof __VLS_components.onClickOutside | typeof __VLS_components.OnClickOutside | typeof __VLS_components['on-click-outside'] | typeof __VLS_components.onClickOutside | typeof __VLS_components.OnClickOutside | typeof __VLS_components['on-click-outside']} */
        onClickOutside;
        // @ts-ignore
        const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
            ...{ 'onTrigger': {} },
            options: ({ ignore: [__VLS_ctx.toggleMenuButton] }),
            ...{ class: "menu" },
            ...{ style: ({ left: `${__VLS_ctx.menuPosition.left}px`, top: `${__VLS_ctx.menuPosition.top}px` }) },
        }));
        const __VLS_23 = __VLS_22({
            ...{ 'onTrigger': {} },
            options: ({ ignore: [__VLS_ctx.toggleMenuButton] }),
            ...{ class: "menu" },
            ...{ style: ({ left: `${__VLS_ctx.menuPosition.left}px`, top: `${__VLS_ctx.menuPosition.top}px` }) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_22));
        let __VLS_26;
        const __VLS_27 = ({ trigger: {} },
            { onTrigger: (__VLS_ctx.onMenuOutsideClick) });
        /** @type {__VLS_StyleScopedClasses['menu']} */ ;
        const { default: __VLS_28 } = __VLS_24.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (__VLS_ctx.onDuplicateClick) },
            ...{ class: "menu-item" },
        });
        /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
        let __VLS_29;
        /** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
        dDivider;
        // @ts-ignore
        const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
            ...{ style: ({ margin: '2px 0' }) },
        }));
        const __VLS_31 = __VLS_30({
            ...{ style: ({ margin: '2px 0' }) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_30));
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (__VLS_ctx.onDeleteClick) },
            ...{ class: "menu-item" },
        });
        /** @type {__VLS_StyleScopedClasses['menu-item']} */ ;
        // @ts-ignore
        [isMenuOpen, toggleMenuButton, menuPosition, menuPosition, onMenuOutsideClick, onDuplicateClick, onDeleteClick,];
        var __VLS_24;
        var __VLS_25;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "all-fields" },
    key: (__VLS_ctx.data.fields.length),
});
/** @type {__VLS_StyleScopedClasses['all-fields']} */ ;
if (__VLS_ctx.inputFields.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "fields input-fields" },
    });
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    /** @type {__VLS_StyleScopedClasses['input-fields']} */ ;
    for (const [field] of __VLS_vFor((__VLS_ctx.inputFields))) {
        const __VLS_34 = NodeField;
        // @ts-ignore
        const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
            key: (field.id),
            field: (field),
        }));
        const __VLS_36 = __VLS_35({
            key: (field.id),
            field: (field),
        }, ...__VLS_functionalComponentArgsRest(__VLS_35));
        // @ts-ignore
        [data, inputFields, inputFields,];
    }
}
if (__VLS_ctx.inputFields.length && __VLS_ctx.outputFields.length) {
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.dDivider | typeof __VLS_components.DDivider | typeof __VLS_components['d-divider']} */
    dDivider;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        ...{ style: {} },
    }));
    const __VLS_41 = __VLS_40({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
}
if (__VLS_ctx.outputFields.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "fields output-fields" },
    });
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    /** @type {__VLS_StyleScopedClasses['output-fields']} */ ;
    for (const [field] of __VLS_vFor((__VLS_ctx.outputFields))) {
        const __VLS_44 = NodeField;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
            key: (field.id),
            field: (field),
        }));
        const __VLS_46 = __VLS_45({
            key: (field.id),
            field: (field),
        }, ...__VLS_functionalComponentArgsRest(__VLS_45));
        // @ts-ignore
        [inputFields, outputFields, outputFields, outputFields,];
    }
}
if (__VLS_ctx.conditionFields.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "fields condition-fields" },
    });
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    /** @type {__VLS_StyleScopedClasses['condition-fields']} */ ;
    for (const [field, index] of __VLS_vFor((__VLS_ctx.conditionFields))) {
        const __VLS_49 = NodeField;
        // @ts-ignore
        const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
            index: (index + 1),
            key: (field.id),
            field: (field),
        }));
        const __VLS_51 = __VLS_50({
            index: (index + 1),
            key: (field.id),
            field: (field),
        }, ...__VLS_functionalComponentArgsRest(__VLS_50));
        // @ts-ignore
        [conditionFields, conditionFields,];
    }
}
// @ts-ignore
var __VLS_13 = __VLS_12;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
