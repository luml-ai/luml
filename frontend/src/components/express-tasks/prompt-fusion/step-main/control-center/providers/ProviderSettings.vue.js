/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { onBeforeMount, ref, watch } from 'vue';
import { LocalStorageService } from '@/utils/services/LocalStorageService';
const props = defineProps();
const emit = defineEmits();
const saveApiKey = ref(false);
const settingsState = ref(JSON.parse(JSON.stringify(props.settings)));
function onSave() {
    emit('save', JSON.parse(JSON.stringify(settingsState.value)));
}
onBeforeMount(() => {
    const settings = LocalStorageService.get('providersSettings');
    saveApiKey.value = !!settings?.saveApiKeys;
});
watch(saveApiKey, (val) => {
    const settings = LocalStorageService.get('providersSettings') || {};
    settings.saveApiKeys = val;
    LocalStorageService.set('providersSettings', settings);
});
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
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog'] | typeof __VLS_components.dDialog | typeof __VLS_components.DDialog | typeof __VLS_components['d-dialog']} */
dDialog;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modelValue),
    modal: true,
    ...{ style: {} },
    dismissableMask: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ 'update:visible': {} },
    { 'onUpdate:visible': ((value) => __VLS_ctx.$emit('update:modelValue', value)) });
var __VLS_7;
const { default: __VLS_8 } = __VLS_3.slots;
{
    const { header: __VLS_9 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    (__VLS_ctx.providerName);
    // @ts-ignore
    [modelValue, $emit, providerName,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "items" },
});
/** @type {__VLS_StyleScopedClasses['items']} */ ;
for (const [setting] of __VLS_vFor((__VLS_ctx.settingsState))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "item" },
    });
    /** @type {__VLS_StyleScopedClasses['item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: (setting.id),
        ...{ class: "label" },
        ...{ class: ({ required: setting.required }) },
    });
    /** @type {__VLS_StyleScopedClasses['label']} */ ;
    /** @type {__VLS_StyleScopedClasses['required']} */ ;
    (setting.label);
    let __VLS_10;
    /** @ts-ignore @type { | typeof __VLS_components.dInputText | typeof __VLS_components.DInputText | typeof __VLS_components['d-input-text']} */
    dInputText;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
        id: (setting.id),
        modelValue: (setting.value),
        placeholder: (setting.placeholder),
        fluid: true,
    }));
    const __VLS_12 = __VLS_11({
        id: (setting.id),
        modelValue: (setting.value),
        placeholder: (setting.placeholder),
        fluid: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    // @ts-ignore
    [settingsState,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "save-key" },
});
/** @type {__VLS_StyleScopedClasses['save-key']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.dCheckbox | typeof __VLS_components.DCheckbox | typeof __VLS_components['d-checkbox']} */
dCheckbox;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.saveApiKey),
    inputId: "saveKey",
    ...{ class: "checkbox" },
    binary: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.saveApiKey),
    inputId: "saveKey",
    ...{ class: "checkbox" },
    binary: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
/** @type {__VLS_StyleScopedClasses['checkbox']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "saveKey",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
{
    const { footer: __VLS_20 } = __VLS_3.slots;
    let __VLS_21;
    /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
    dButton;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
        ...{ 'onClick': {} },
        label: "Save",
    }));
    const __VLS_23 = __VLS_22({
        ...{ 'onClick': {} },
        label: "Save",
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
    let __VLS_26;
    const __VLS_27 = ({ click: {} },
        { onClick: (__VLS_ctx.onSave) });
    var __VLS_24;
    var __VLS_25;
    // @ts-ignore
    [saveApiKey, onSave,];
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
