/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { DataTable, Column, Dialog } from 'primevue';
import { Maximize2, Minimize2 } from 'lucide-vue-next';
import { cutStringOnMiddle } from '@/helpers/helpers';
const props = defineProps();
// const highlightIncorrect = ref(false)
const maximizeTable = ref(false);
const currentColumns = computed(() => Object.keys(props.values[0]));
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "card-header" },
});
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "card-title" },
});
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
if (__VLS_ctx.isTrainMode) {
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.triangleAlert | typeof __VLS_components.TriangleAlert | typeof __VLS_components['triangle-alert']} */
    triangleAlert;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        size: (20),
        ...{ class: "warning-icon" },
    }));
    const __VLS_2 = __VLS_1({
        size: (20),
        ...{ class: "warning-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, value: ('Cross-validation was used due to insufficient test data. The sample is from the training set.') }, null, null);
    /** @type {__VLS_StyleScopedClasses['warning-icon']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "detailed-actions" },
});
/** @type {__VLS_StyleScopedClasses['detailed-actions']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ style: ({ width: '20px', height: '20px' }) },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    ...{ style: ({ width: '20px', height: '20px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.maximizeTable = true;
            // @ts-ignore
            [isTrainMode, vTooltip, maximizeTable,];
        } });
const { default: __VLS_12 } = __VLS_8.slots;
{
    const { icon: __VLS_13 } = __VLS_8.slots;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.Maximize2} */
    Maximize2;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        size: (20),
    }));
    const __VLS_16 = __VLS_15({
        size: (20),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.values.length) {
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
    DataTable;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        value: (__VLS_ctx.values),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: "19rem",
        virtualScrollerOptions: ({ itemSize: 31 }),
        ...{ class: "table" },
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }));
    const __VLS_21 = __VLS_20({
        value: (__VLS_ctx.values),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: "19rem",
        virtualScrollerOptions: ({ itemSize: 31 }),
        ...{ class: "table" },
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    /** @type {__VLS_StyleScopedClasses['table']} */ ;
    const { default: __VLS_24 } = __VLS_22.slots;
    for (const [column] of __VLS_vFor((__VLS_ctx.currentColumns))) {
        let __VLS_25;
        /** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
        Column;
        // @ts-ignore
        const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
            id: (column),
            field: (column),
            header: (column === '<=PREDICTED=>' ? 'Prediction' : __VLS_ctx.cutStringOnMiddle(column)),
        }));
        const __VLS_27 = __VLS_26({
            id: (column),
            field: (column),
            header: (column === '<=PREDICTED=>' ? 'Prediction' : __VLS_ctx.cutStringOnMiddle(column)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_26));
        // @ts-ignore
        [values, values, currentColumns, cutStringOnMiddle,];
    }
    // @ts-ignore
    [];
    var __VLS_22;
}
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    visible: (__VLS_ctx.maximizeTable),
    blockScroll: true,
    header: "Detailed view",
    ...{ class: "p-dialog-maximized" },
}));
const __VLS_32 = __VLS_31({
    visible: (__VLS_ctx.maximizeTable),
    blockScroll: true,
    header: "Detailed view",
    ...{ class: "p-dialog-maximized" },
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
/** @type {__VLS_StyleScopedClasses['p-dialog-maximized']} */ ;
const { default: __VLS_35 } = __VLS_33.slots;
{
    const { header: __VLS_36 } = __VLS_33.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
        ...{ class: "card-header" },
        ...{ style: ({ width: '100%', marginBottom: '0', marginRight: '20px' }) },
    });
    /** @type {__VLS_StyleScopedClasses['card-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "card-title" },
    });
    /** @type {__VLS_StyleScopedClasses['card-title']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "detailed-actions" },
    });
    /** @type {__VLS_StyleScopedClasses['detailed-actions']} */ ;
    // @ts-ignore
    [maximizeTable,];
}
{
    const { closeicon: __VLS_37 } = __VLS_33.slots;
    let __VLS_38;
    /** @ts-ignore @type { | typeof __VLS_components.Minimize2} */
    Minimize2;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({}));
    const __VLS_40 = __VLS_39({}, ...__VLS_functionalComponentArgsRest(__VLS_39));
    // @ts-ignore
    [];
}
if (__VLS_ctx.values.length) {
    let __VLS_43;
    /** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
    DataTable;
    // @ts-ignore
    const __VLS_44 = __VLS_asFunctionalComponent1(__VLS_43, new __VLS_43({
        value: (__VLS_ctx.values),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: "calc(100vh - 120px)",
        virtualScrollerOptions: ({ itemSize: 31 }),
        ...{ class: "table" },
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }));
    const __VLS_45 = __VLS_44({
        value: (__VLS_ctx.values),
        showGridlines: true,
        stripedRows: true,
        scrollable: true,
        scrollHeight: "calc(100vh - 120px)",
        virtualScrollerOptions: ({ itemSize: 31 }),
        ...{ class: "table" },
        size: "small",
        ...{ style: ({ fontSize: '14px' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_44));
    /** @type {__VLS_StyleScopedClasses['table']} */ ;
    const { default: __VLS_48 } = __VLS_46.slots;
    for (const [column] of __VLS_vFor((__VLS_ctx.currentColumns))) {
        let __VLS_49;
        /** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
        Column;
        // @ts-ignore
        const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
            id: (column),
            field: (column),
            header: (column === '<=PREDICTED=>' ? 'Prediction' : __VLS_ctx.cutStringOnMiddle(column)),
        }));
        const __VLS_51 = __VLS_50({
            id: (column),
            field: (column),
            header: (column === '<=PREDICTED=>' ? 'Prediction' : __VLS_ctx.cutStringOnMiddle(column)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_50));
        // @ts-ignore
        [values, values, currentColumns, cutStringOnMiddle,];
    }
    // @ts-ignore
    [];
    var __VLS_46;
}
// @ts-ignore
[];
var __VLS_33;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
