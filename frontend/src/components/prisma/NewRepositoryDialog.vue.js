/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Dialog, InputText, Button } from 'primevue';
import { Plus } from 'lucide-vue-next';
import FolderPicker from './FolderPicker.vue';
import { api } from '@/lib/api';
const __VLS_props = defineProps();
const emit = defineEmits();
const name = ref('');
const path = ref('');
const error = ref('');
async function submit() {
    error.value = '';
    if (!name.value.trim()) {
        error.value = 'Name is required';
        return;
    }
    if (!path.value.trim()) {
        error.value = 'Repository path is required';
        return;
    }
    try {
        await api.dataAgent.createRepository({ name: name.value.trim(), path: path.value });
        name.value = '';
        path.value = '';
        emit('created');
    }
    catch (e) {
        const detail = e?.response?.data?.detail;
        if (typeof detail === 'string') {
            error.value = detail;
        }
        else if (e?.message) {
            error.value = e.message;
        }
        else {
            error.value = 'Failed to create repository';
        }
    }
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
    header: "New Repository",
    modal: true,
    ...{ style: ({ width: '450px' }) },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.visible),
    header: "New Repository",
    modal: true,
    ...{ style: ({ width: '450px' }) },
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form" },
});
/** @type {__VLS_StyleScopedClasses['form']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_9;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
    modelValue: (__VLS_ctx.name),
    placeholder: "my-repo",
    ...{ class: "w-full" },
}));
const __VLS_11 = __VLS_10({
    modelValue: (__VLS_ctx.name),
    placeholder: "my-repo",
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
const __VLS_14 = FolderPicker;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    modelValue: (__VLS_ctx.path),
}));
const __VLS_16 = __VLS_15({
    modelValue: (__VLS_ctx.path),
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "error" },
    });
    /** @type {__VLS_StyleScopedClasses['error']} */ ;
    (__VLS_ctx.error);
}
{
    const { footer: __VLS_19 } = __VLS_3.slots;
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
        severity: "secondary",
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_25;
    const __VLS_26 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.emit('close');
                // @ts-ignore
                [emit, name, path, error, error,];
            } });
    const { default: __VLS_27 } = __VLS_23.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [];
    var __VLS_23;
    var __VLS_24;
    let __VLS_28;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_33;
    const __VLS_34 = ({ click: {} },
        { onClick: (__VLS_ctx.submit) });
    const { default: __VLS_35 } = __VLS_31.slots;
    let __VLS_36;
    /** @ts-ignore @type { | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
        size: (14),
    }));
    const __VLS_38 = __VLS_37({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [submit,];
    var __VLS_31;
    var __VLS_32;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
