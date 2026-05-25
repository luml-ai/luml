/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { PROMPT_NODES_ICONS, NodeTypeEnum } from '../../interfaces';
import { v4 as uuidv4 } from 'uuid';
import { Position } from '@vue-flow/core';
import BaseField from './BaseField.vue';
import ConditionField from './ConditionField.vue';
import CustomTextarea from '@/components/ui/CustomTextarea.vue';
import { useVueFlow } from '@vue-flow/core';
const { getEdges, removeEdges } = useVueFlow();
const props = defineProps();
const __VLS_emit = defineEmits();
const inputFields = computed(() => props.data.fields.filter((field) => field.variant === 'input'));
const outputFields = computed(() => props.data.fields.filter((field) => field.variant === 'output'));
const conditionFields = computed(() => props.data.fields.filter((field) => field.variant === 'condition'));
const hintVisible = computed(() => props.data.type === NodeTypeEnum.gate || props.data.type === NodeTypeEnum.processor);
const inputsVisible = computed(() => props.data.type === NodeTypeEnum.input || props.data.type === NodeTypeEnum.processor);
const outputsVisible = computed(() => props.data.type === NodeTypeEnum.output ||
    props.data.type === NodeTypeEnum.processor ||
    props.data.type === NodeTypeEnum.gate);
const conditionsVisible = computed(() => props.data.type === NodeTypeEnum.gate);
const availableAddOutput = computed(() => !(props.data.type === NodeTypeEnum.gate) || outputFields.value.length === 0);
const addOutputLabel = computed(() => props.data.type === NodeTypeEnum.gate ? 'Add input field' : 'Add output field');
const duplicatedFieldsIds = computed(() => {
    const inputDuplicates = inputFields.value.filter((item, index, self) => item.value &&
        self.find((searchedItem) => searchedItem.value === item.value && searchedItem.id !== item.id));
    const outputDuplicates = inputFields.value.filter((item, index, self) => item.value &&
        self.find((searchedItem) => searchedItem.value === item.value && searchedItem.id !== item.id));
    return [...inputDuplicates.map((item) => item.id), ...outputDuplicates.map((item) => item.id)];
});
const isDuplicate = computed(() => (id) => !!duplicatedFieldsIds.value.find((searchedId) => searchedId === id));
function onDeleteField(id) {
    const fieldEdges = getEdges.value.filter((edge) => edge.targetHandle === id || edge.sourceHandle === id);
    removeEdges(fieldEdges);
    props.data.fields = props.data.fields.filter((field) => field.id !== id);
}
function addField(variant) {
    let handlePosition;
    if (props.data.type === NodeTypeEnum.processor) {
        handlePosition = variant === 'output' ? Position.Right : Position.Left;
    }
    else {
        handlePosition = variant === 'output' ? Position.Left : Position.Right;
    }
    const field = {
        id: uuidv4(),
        value: '',
        handlePosition,
        variant,
    };
    props.data.fields.push(field);
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
/** @type {__VLS_StyleScopedClasses['outputs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sidebar" },
});
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-main" },
});
/** @type {__VLS_StyleScopedClasses['header-main']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "header-left" },
});
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
const __VLS_0 = (__VLS_ctx.PROMPT_NODES_ICONS[__VLS_ctx.data.icon]);
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    width: "20",
    height: "20",
    color: (__VLS_ctx.data.iconColor),
}));
const __VLS_2 = __VLS_1({
    width: "20",
    height: "20",
    color: (__VLS_ctx.data.iconColor),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.data.label),
    type: "text",
    ...{ class: "title-input" },
});
/** @type {__VLS_StyleScopedClasses['title-input']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "text",
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    severity: "secondary",
    rounded: true,
    variant: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.$emit('close');
            // @ts-ignore
            [PROMPT_NODES_ICONS, data, data, data, $emit,];
        } });
const { default: __VLS_12 } = __VLS_8.slots;
{
    const { icon: __VLS_13 } = __VLS_8.slots;
    let __VLS_14;
    /** @ts-ignore @type { | typeof __VLS_components.x | typeof __VLS_components.X} */
    x;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        width: "16",
        height: "16",
        color: "var(--p-button-text-secondary-color)",
    }));
    const __VLS_16 = __VLS_15({
        width: "16",
        height: "16",
        color: "var(--p-button-text-secondary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.duplicatedFieldsIds.length) {
    let __VLS_19;
    /** @ts-ignore @type { | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message'] | typeof __VLS_components.dMessage | typeof __VLS_components.DMessage | typeof __VLS_components['d-message']} */
    dMessage;
    // @ts-ignore
    const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
        severity: "error",
    }));
    const __VLS_21 = __VLS_20({
        severity: "error",
    }, ...__VLS_functionalComponentArgsRest(__VLS_20));
    const { default: __VLS_24 } = __VLS_22.slots;
    // @ts-ignore
    [duplicatedFieldsIds,];
    var __VLS_22;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "body" },
});
/** @type {__VLS_StyleScopedClasses['body']} */ ;
if (__VLS_ctx.hintVisible) {
    const __VLS_25 = CustomTextarea;
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
        modelValue: (__VLS_ctx.data.hint),
        fluid: true,
        rows: "1",
        placeholder: "Hint",
        size: "small",
        autoResize: true,
        maxHeight: (75),
        ...{ class: "hint" },
    }));
    const __VLS_27 = __VLS_26({
        modelValue: (__VLS_ctx.data.hint),
        fluid: true,
        rows: "1",
        placeholder: "Hint",
        size: "small",
        autoResize: true,
        maxHeight: (75),
        ...{ class: "hint" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_26));
    /** @type {__VLS_StyleScopedClasses['hint']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "all-fields" },
});
/** @type {__VLS_StyleScopedClasses['all-fields']} */ ;
if (__VLS_ctx.inputsVisible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "inputs fields" },
    });
    /** @type {__VLS_StyleScopedClasses['inputs']} */ ;
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    for (const [field] of __VLS_vFor((__VLS_ctx.inputFields))) {
        const __VLS_30 = BaseField;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
            ...{ 'onDelete': {} },
            data: (field),
            isDuplicate: (__VLS_ctx.isDuplicate(field.id)),
        }));
        const __VLS_32 = __VLS_31({
            ...{ 'onDelete': {} },
            data: (field),
            isDuplicate: (__VLS_ctx.isDuplicate(field.id)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
        let __VLS_35;
        const __VLS_36 = ({ delete: {} },
            { onDelete: (...[$event]) => {
                    if (!(__VLS_ctx.inputsVisible))
                        return;
                    __VLS_ctx.onDeleteField(field.id);
                    // @ts-ignore
                    [data, hintVisible, inputsVisible, inputFields, isDuplicate, onDeleteField,];
                } });
        var __VLS_33;
        var __VLS_34;
        // @ts-ignore
        [];
    }
    let __VLS_37;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        ...{ 'onClick': {} },
        label: "Add input field",
        variant: "text",
        size: "small",
        ...{ class: "add-button" },
    }));
    const __VLS_39 = __VLS_38({
        ...{ 'onClick': {} },
        label: "Add input field",
        variant: "text",
        size: "small",
        ...{ class: "add-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    let __VLS_42;
    const __VLS_43 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.inputsVisible))
                    return;
                __VLS_ctx.addField('input');
                // @ts-ignore
                [addField,];
            } });
    /** @type {__VLS_StyleScopedClasses['add-button']} */ ;
    const { default: __VLS_44 } = __VLS_40.slots;
    {
        const { icon: __VLS_45 } = __VLS_40.slots;
        let __VLS_46;
        /** @ts-ignore @type { | typeof __VLS_components.plus | typeof __VLS_components.Plus} */
        plus;
        // @ts-ignore
        const __VLS_47 = __VLS_asFunctionalComponent1(__VLS_46, new __VLS_46({
            width: "14",
            height: "14",
        }));
        const __VLS_48 = __VLS_47({
            width: "14",
            height: "14",
        }, ...__VLS_functionalComponentArgsRest(__VLS_47));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_40;
    var __VLS_41;
}
if (__VLS_ctx.outputsVisible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "outputs fields" },
    });
    /** @type {__VLS_StyleScopedClasses['outputs']} */ ;
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    for (const [field] of __VLS_vFor((__VLS_ctx.outputFields))) {
        const __VLS_51 = BaseField;
        // @ts-ignore
        const __VLS_52 = __VLS_asFunctionalComponent1(__VLS_51, new __VLS_51({
            ...{ 'onDelete': {} },
            data: (field),
            isDuplicate: (__VLS_ctx.isDuplicate(field.id)),
            typeLabel: (props.data.type === __VLS_ctx.NodeTypeEnum.gate ? 'input' : undefined),
        }));
        const __VLS_53 = __VLS_52({
            ...{ 'onDelete': {} },
            data: (field),
            isDuplicate: (__VLS_ctx.isDuplicate(field.id)),
            typeLabel: (props.data.type === __VLS_ctx.NodeTypeEnum.gate ? 'input' : undefined),
        }, ...__VLS_functionalComponentArgsRest(__VLS_52));
        let __VLS_56;
        const __VLS_57 = ({ delete: {} },
            { onDelete: (...[$event]) => {
                    if (!(__VLS_ctx.outputsVisible))
                        return;
                    __VLS_ctx.onDeleteField(field.id);
                    // @ts-ignore
                    [isDuplicate, onDeleteField, outputsVisible, outputFields, NodeTypeEnum,];
                } });
        var __VLS_54;
        var __VLS_55;
        // @ts-ignore
        [];
    }
    if (__VLS_ctx.availableAddOutput) {
        let __VLS_58;
        /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
        dButton;
        // @ts-ignore
        const __VLS_59 = __VLS_asFunctionalComponent1(__VLS_58, new __VLS_58({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.addOutputLabel),
            variant: "text",
            size: "small",
            ...{ class: "add-button" },
        }));
        const __VLS_60 = __VLS_59({
            ...{ 'onClick': {} },
            label: (__VLS_ctx.addOutputLabel),
            variant: "text",
            size: "small",
            ...{ class: "add-button" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_59));
        let __VLS_63;
        const __VLS_64 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.outputsVisible))
                        return;
                    if (!(__VLS_ctx.availableAddOutput))
                        return;
                    __VLS_ctx.addField('output');
                    // @ts-ignore
                    [addField, availableAddOutput, addOutputLabel,];
                } });
        /** @type {__VLS_StyleScopedClasses['add-button']} */ ;
        const { default: __VLS_65 } = __VLS_61.slots;
        {
            const { icon: __VLS_66 } = __VLS_61.slots;
            let __VLS_67;
            /** @ts-ignore @type { | typeof __VLS_components.plus | typeof __VLS_components.Plus} */
            plus;
            // @ts-ignore
            const __VLS_68 = __VLS_asFunctionalComponent1(__VLS_67, new __VLS_67({
                width: "14",
                height: "14",
            }));
            const __VLS_69 = __VLS_68({
                width: "14",
                height: "14",
            }, ...__VLS_functionalComponentArgsRest(__VLS_68));
            // @ts-ignore
            [];
        }
        // @ts-ignore
        [];
        var __VLS_61;
        var __VLS_62;
    }
}
if (__VLS_ctx.conditionsVisible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "conditions fields" },
    });
    /** @type {__VLS_StyleScopedClasses['conditions']} */ ;
    /** @type {__VLS_StyleScopedClasses['fields']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "field-title" },
    });
    /** @type {__VLS_StyleScopedClasses['field-title']} */ ;
    for (const [field, index] of __VLS_vFor((__VLS_ctx.conditionFields))) {
        const __VLS_72 = ConditionField;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent1(__VLS_72, new __VLS_72({
            ...{ 'onDelete': {} },
            data: (field),
            index: (index + 1),
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onDelete': {} },
            data: (field),
            index: (index + 1),
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_77;
        const __VLS_78 = ({ delete: {} },
            { onDelete: (...[$event]) => {
                    if (!(__VLS_ctx.conditionsVisible))
                        return;
                    __VLS_ctx.onDeleteField(field.id);
                    // @ts-ignore
                    [onDeleteField, conditionsVisible, conditionFields,];
                } });
        var __VLS_75;
        var __VLS_76;
        // @ts-ignore
        [];
    }
    let __VLS_79;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_80 = __VLS_asFunctionalComponent1(__VLS_79, new __VLS_79({
        ...{ 'onClick': {} },
        label: "Add condition",
        variant: "text",
        size: "small",
        ...{ class: "add-button" },
    }));
    const __VLS_81 = __VLS_80({
        ...{ 'onClick': {} },
        label: "Add condition",
        variant: "text",
        size: "small",
        ...{ class: "add-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_80));
    let __VLS_84;
    const __VLS_85 = ({ click: {} },
        { onClick: (...[$event]) => {
                if (!(__VLS_ctx.conditionsVisible))
                    return;
                __VLS_ctx.addField('condition');
                // @ts-ignore
                [addField,];
            } });
    /** @type {__VLS_StyleScopedClasses['add-button']} */ ;
    const { default: __VLS_86 } = __VLS_82.slots;
    {
        const { icon: __VLS_87 } = __VLS_82.slots;
        let __VLS_88;
        /** @ts-ignore @type { | typeof __VLS_components.plus | typeof __VLS_components.Plus} */
        plus;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent1(__VLS_88, new __VLS_88({
            width: "14",
            height: "14",
        }));
        const __VLS_90 = __VLS_89({
            width: "14",
            height: "14",
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_82;
    var __VLS_83;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
