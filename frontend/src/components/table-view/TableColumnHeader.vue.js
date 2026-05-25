/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { PROMPT_NODES_ICONS } from '@/components/express-tasks/prompt-fusion/interfaces';
import { Blocks, CalendarFold, CaseUpper, Hash, Target, EllipsisVertical } from 'lucide-vue-next';
import { Menu } from 'primevue';
import { computed, ref } from 'vue';
const props = defineProps();
const emit = defineEmits();
const menu = ref();
const menuItems = computed(() => {
    const items = [
        {
            label: 'Set as group',
            iconComponent: Blocks,
            disabled: true,
            command() {
                emit('changeGroup', props.column);
            },
        },
    ];
    if (props.column !== props.target) {
        items.push({
            label: 'Set as target',
            iconComponent: Target,
            command() {
                emit('setTarget', props.column);
            },
        });
    }
    return items;
});
const getCurrentMenuIconColor = computed(() => (icon) => {
    if (icon === Target)
        return 'var(--p-message-error-color)';
    if (icon === Blocks)
        return 'var(--p-primary-color)';
});
const currentColumnTypeIcon = computed(() => {
    if (props.columnType === 'number')
        return Hash;
    else if (props.columnType === 'date')
        return CalendarFold;
    else
        return CaseUpper;
});
function toggleMenu(event) {
    menu.value.toggle(event);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column-header" },
});
/** @type {__VLS_StyleScopedClasses['column-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column-header-title" },
});
/** @type {__VLS_StyleScopedClasses['column-header-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.column);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column-header-icons" },
});
/** @type {__VLS_StyleScopedClasses['column-header-icons']} */ ;
const __VLS_0 = (__VLS_ctx.currentColumnTypeIcon);
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
if (__VLS_ctx.target && __VLS_ctx.column === __VLS_ctx.target) {
    let __VLS_5;
    /** @ts-ignore @type { | typeof __VLS_components.Target} */
    Target;
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        width: "16",
        height: "16",
        color: "var(--p-message-error-color)",
    }));
    const __VLS_7 = __VLS_6({
        width: "16",
        height: "16",
        color: "var(--p-message-error-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
}
if (__VLS_ctx.group && __VLS_ctx.group.includes(__VLS_ctx.column)) {
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.Blocks} */
    Blocks;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        width: "16",
        height: "16",
        color: "var(--p-primary-color)",
    }));
    const __VLS_12 = __VLS_11({
        width: "16",
        height: "16",
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
}
if (__VLS_ctx.inputsOutputsColumns) {
    if (__VLS_ctx.inputsOutputsColumns.find((c) => c.name === __VLS_ctx.column)?.variant === 'input') {
        const __VLS_15 = (__VLS_ctx.PROMPT_NODES_ICONS.input);
        // @ts-ignore
        const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
            size: (16),
            color: "var(--p-primary-color)",
        }));
        const __VLS_17 = __VLS_16({
            size: (16),
            color: "var(--p-primary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    }
    if (__VLS_ctx.inputsOutputsColumns.find((c) => c.name === __VLS_ctx.column)?.variant === 'output') {
        const __VLS_20 = (__VLS_ctx.PROMPT_NODES_ICONS.output);
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
            size: (16),
            color: "var(--p-primary-color)",
        }));
        const __VLS_22 = __VLS_21({
            size: (16),
            color: "var(--p-primary-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    }
}
if (__VLS_ctx.showMenu) {
    let __VLS_25;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "text",
        'aria-haspopup': "true",
        'aria-controls': "overlay_menu",
        ...{ style: ({ width: '30px', height: '31px' }) },
    }));
    const __VLS_27 = __VLS_26({
        ...{ 'onClick': {} },
        severity: "secondary",
        rounded: true,
        variant: "text",
        'aria-haspopup': "true",
        'aria-controls': "overlay_menu",
        ...{ style: ({ width: '30px', height: '31px' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    let __VLS_30;
    const __VLS_31 = ({ click: {} },
        { onClick: (__VLS_ctx.toggleMenu) });
    const { default: __VLS_32 } = __VLS_28.slots;
    {
        const { icon: __VLS_33 } = __VLS_28.slots;
        let __VLS_34;
        /** @ts-ignore @type { | typeof __VLS_components.EllipsisVertical} */
        EllipsisVertical;
        // @ts-ignore
        const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
            size: (14),
        }));
        const __VLS_36 = __VLS_35({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_35));
        // @ts-ignore
        [column, column, column, column, column, currentColumnTypeIcon, target, target, group, group, inputsOutputsColumns, inputsOutputsColumns, inputsOutputsColumns, PROMPT_NODES_ICONS, PROMPT_NODES_ICONS, showMenu, toggleMenu,];
    }
    // @ts-ignore
    [];
    var __VLS_28;
    var __VLS_29;
}
let __VLS_39;
/** @ts-ignore @type { | typeof __VLS_components.Menu | typeof __VLS_components.Menu} */
Menu;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ref: "menu",
}));
const __VLS_41 = __VLS_40({
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ref: "menu",
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
var __VLS_44;
const { default: __VLS_46 } = __VLS_42.slots;
{
    const { itemicon: __VLS_47 } = __VLS_42.slots;
    const [{ item }] = __VLS_vSlot(__VLS_47);
    const __VLS_48 = (item.iconComponent);
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent1(__VLS_48, new __VLS_48({
        width: "14",
        height: "14",
        color: (__VLS_ctx.getCurrentMenuIconColor(item.iconComponent)),
    }));
    const __VLS_50 = __VLS_49({
        width: "14",
        height: "14",
        color: (__VLS_ctx.getCurrentMenuIconColor(item.iconComponent)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    // @ts-ignore
    [menuItems, getCurrentMenuIconColor,];
}
// @ts-ignore
[];
var __VLS_42;
// @ts-ignore
var __VLS_45 = __VLS_44;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
