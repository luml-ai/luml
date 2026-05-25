/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, watch } from 'vue';
import { Dialog, SelectButton, Button } from 'primevue';
import { Plus, ListTodo, Waypoints } from 'lucide-vue-next';
import { api } from '@/lib/api';
import TaskForm from './TaskForm.vue';
import WorkflowForm from './WorkflowForm.vue';
const props = defineProps();
const emit = defineEmits();
const selectedType = ref(props.initialType);
const loading = ref(false);
const error = ref('');
const formRef = ref(null);
watch(() => props.visible, (v) => {
    if (v) {
        selectedType.value = props.initialType;
        error.value = '';
    }
});
const typeOptions = [
    { label: 'Workflow', value: 'workflow', icon: Waypoints },
    { label: 'Task', value: 'task', icon: ListTodo },
];
const formComponent = computed(() => (selectedType.value === 'task' ? TaskForm : WorkflowForm));
async function onFormSubmit(data) {
    error.value = '';
    loading.value = true;
    try {
        if (selectedType.value === 'task') {
            await api.dataAgent.createTask(data);
        }
        else {
            await api.dataAgent.createRun(data);
        }
        emit('created');
    }
    catch (e) {
        const label = selectedType.value === 'task' ? 'task' : 'workflow';
        error.value = e?.response?.data?.detail ?? `Failed to create ${label}`;
    }
    finally {
        loading.value = false;
    }
}
function onCreateClick() {
    formRef.value?.submit();
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
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    header: "Create new item",
    modal: true,
    ...{ style: ({ width: '540px' }) },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    header: "Create new item",
    modal: true,
    ...{ style: ({ width: '540px' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            !$event && __VLS_ctx.emit('close');
            // @ts-ignore
            [visible, emit,];
        } });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
let __VLS_9;
/** @ts-ignore @type { | typeof __VLS_components.SelectButton | typeof __VLS_components.SelectButton} */
SelectButton;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
    modelValue: (__VLS_ctx.selectedType),
    options: (__VLS_ctx.typeOptions),
    optionLabel: "label",
    optionValue: "value",
    ...{ class: "type-select" },
}));
const __VLS_11 = __VLS_10({
    modelValue: (__VLS_ctx.selectedType),
    options: (__VLS_ctx.typeOptions),
    optionLabel: "label",
    optionValue: "value",
    ...{ class: "type-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
/** @type {__VLS_StyleScopedClasses['type-select']} */ ;
const { default: __VLS_14 } = __VLS_12.slots;
{
    const { option: __VLS_15 } = __VLS_12.slots;
    const [{ option }] = __VLS_vSlot(__VLS_15);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "type-option" },
    });
    /** @type {__VLS_StyleScopedClasses['type-option']} */ ;
    const __VLS_16 = (option.icon);
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
        size: (14),
    }));
    const __VLS_18 = __VLS_17({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    (option.label);
    // @ts-ignore
    [selectedType, typeOptions,];
}
// @ts-ignore
[];
var __VLS_12;
const __VLS_21 = (__VLS_ctx.formComponent);
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    ...{ 'onSubmit': {} },
    ref: "formRef",
    repositories: (__VLS_ctx.repositories),
    loading: (__VLS_ctx.loading),
}));
const __VLS_23 = __VLS_22({
    ...{ 'onSubmit': {} },
    ref: "formRef",
    repositories: (__VLS_ctx.repositories),
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
let __VLS_26;
const __VLS_27 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onFormSubmit) });
var __VLS_28;
var __VLS_24;
var __VLS_25;
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "error" },
    });
    /** @type {__VLS_StyleScopedClasses['error']} */ ;
    (__VLS_ctx.error);
}
{
    const { footer: __VLS_30 } = __VLS_3.slots;
    let __VLS_31;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
        ...{ 'onClick': {} },
        severity: "secondary",
    }));
    const __VLS_33 = __VLS_32({
        ...{ 'onClick': {} },
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    let __VLS_36;
    const __VLS_37 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.emit('close');
                // @ts-ignore
                [emit, formComponent, repositories, loading, onFormSubmit, error, error,];
            } });
    const { default: __VLS_38 } = __VLS_34.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_34;
    var __VLS_35;
    let __VLS_39;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_41 = __VLS_40({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    let __VLS_44;
    const __VLS_45 = ({ click: {} },
        { onClick: (__VLS_ctx.onCreateClick) });
    const { default: __VLS_46 } = __VLS_42.slots;
    let __VLS_47;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
        size: (14),
    }));
    const __VLS_49 = __VLS_48({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_48));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [loading, onCreateClick,];
    var __VLS_42;
    var __VLS_43;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
var __VLS_29 = __VLS_28;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
