/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { Button, Dialog, useToast } from 'primevue';
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue';
import { useNotebooksStore } from '@/stores/notebooks';
const dialogPt = {
    root: {
        style: 'max-width: 500px; width: 100%;',
    },
    header: {
        style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
    },
    content: {
        style: 'padding: 0 28px 28px;',
    },
};
const notebooksStore = useNotebooksStore();
const toast = useToast();
const visible = ref(false);
const loading = ref(false);
async function onSubmit(payload) {
    loading.value = true;
    await notebooksStore.create(payload);
    loading.value = false;
    visible.value = false;
    toast.add({ severity: 'success', summary: 'Success', detail: 'Instance Created', life: 2000 });
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    label: "Create instance",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    label: "Create instance",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (...[$event]) => {
            __VLS_ctx.visible = true;
            // @ts-ignore
            [visible,];
        } });
var __VLS_3;
var __VLS_4;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "CREATE A NEW INSTANCE",
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_9 = __VLS_8({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "CREATE A NEW INSTANCE",
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
const { default: __VLS_12 } = __VLS_10.slots;
const __VLS_13 = NotebookCreateUpdateForm || NotebookCreateUpdateForm;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_15 = __VLS_14({
    ...{ 'onSubmit': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
const __VLS_19 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
var __VLS_16;
var __VLS_17;
// @ts-ignore
[visible, dialogPt, loading, onSubmit,];
var __VLS_10;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
