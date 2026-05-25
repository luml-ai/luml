/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Menu, Button, Dialog, useConfirm, useToast } from 'primevue';
import { DatabaseBackup, PenLine, Trash2, EllipsisVertical } from 'lucide-vue-next';
import { ref } from 'vue';
import { useNotebooksStore } from '@/stores/notebooks';
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue';
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
const props = defineProps();
const confirm = useConfirm();
const toast = useToast();
const notebooksStore = useNotebooksStore();
const menuItems = [
    {
        label: 'Backup',
        iconComponent: DatabaseBackup,
        disabled: false,
        color: 'var(--p-primary-color)',
        command() {
            onBackupClick();
        },
    },
    {
        label: 'Rename',
        iconComponent: PenLine,
        color: 'var(--p-primary-color)',
        command() {
            onEditClick();
        },
    },
    {
        label: 'Delete',
        iconComponent: Trash2,
        color: 'var(--p-message-error-color)',
        command() {
            onDeleteClick();
        },
    },
];
const menu = ref();
const visible = ref(false);
const editData = ref();
function toggleMenu(event) {
    menu.value.toggle(event);
}
function onDeleteClick() {
    confirm.require({
        header: 'Delete this instance?',
        message: 'Deleting this instance will remove all associated models. This action cannot be undone.',
        acceptProps: {
            label: 'delete',
            severity: 'warn',
            variant: 'outlined',
        },
        rejectProps: {
            label: 'cancel',
        },
        accept: async () => {
            try {
                await notebooksStore.remove(props.notebook.name);
                toast.add({
                    severity: 'success',
                    summary: 'Success',
                    detail: 'Notebook deleted',
                    life: 2000,
                });
            }
            catch (e) {
                toast.add({
                    severity: 'error',
                    summary: 'Error',
                    detail: e?.message || 'Failed to delete the instance',
                });
            }
        },
    });
}
function onEditClick() {
    editData.value = { ...props.notebook };
    visible.value = true;
}
async function onUpdateSubmit(payload) {
    visible.value = false;
    await notebooksStore.edit({ ...editData.value, fullname: payload.fullname });
    toast.add({ severity: 'success', summary: 'Success', detail: 'Notebook info saved', life: 2000 });
}
function onBackupClick() {
    confirm.require({
        header: 'Create backup?',
        message: 'Your data is only stored in your browser. Make a backup to avoid losing it.',
        acceptProps: {
            label: 'confirm',
        },
        rejectProps: {
            label: 'cancel',
            severity: 'secondary',
        },
        accept: async () => {
            try {
                await notebooksStore.createBackup(props.notebook.name);
            }
            catch (e) {
                toast.add({
                    severity: 'error',
                    summary: 'Error',
                    detail: e?.message || 'Failed to create a backup',
                    life: 2000,
                });
            }
        },
    });
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    rounded: true,
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    variant: "text",
    severity: "secondary",
    rounded: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ click: {} },
    { onClick: (__VLS_ctx.toggleMenu) });
const { default: __VLS_7 } = __VLS_3.slots;
{
    const { icon: __VLS_8 } = __VLS_3.slots;
    let __VLS_9;
    /** @ts-ignore @type { | typeof __VLS_components.EllipsisVertical} */
    EllipsisVertical;
    // @ts-ignore
    const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
        size: (14),
    }));
    const __VLS_11 = __VLS_10({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_10));
    // @ts-ignore
    [toggleMenu,];
}
// @ts-ignore
[];
var __VLS_3;
var __VLS_4;
let __VLS_14;
/** @ts-ignore @type { | typeof __VLS_components.Menu | typeof __VLS_components.Menu} */
Menu;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ref: "menu",
}));
const __VLS_16 = __VLS_15({
    model: (__VLS_ctx.menuItems),
    popup: (true),
    ref: "menu",
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
var __VLS_19;
const { default: __VLS_21 } = __VLS_17.slots;
{
    const { itemicon: __VLS_22 } = __VLS_17.slots;
    const [{ item }] = __VLS_vSlot(__VLS_22);
    const __VLS_23 = (item.iconComponent);
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
        width: "14",
        height: "14",
        color: (item.color),
    }));
    const __VLS_25 = __VLS_24({
        width: "14",
        height: "14",
        color: (item.color),
    }, ...__VLS_functionalComponentArgsRest(__VLS_24));
    // @ts-ignore
    [menuItems,];
}
// @ts-ignore
[];
var __VLS_17;
let __VLS_28;
/** @ts-ignore @type { | typeof __VLS_components.Dialog | typeof __VLS_components.Dialog} */
Dialog;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Rename instance",
    pt: (__VLS_ctx.dialogPt),
}));
const __VLS_30 = __VLS_29({
    visible: (__VLS_ctx.visible),
    modal: true,
    header: "Rename instance",
    pt: (__VLS_ctx.dialogPt),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
const { default: __VLS_33 } = __VLS_31.slots;
if (__VLS_ctx.editData) {
    const __VLS_34 = NotebookCreateUpdateForm || NotebookCreateUpdateForm;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
        ...{ 'onSubmit': {} },
        updateMode: true,
        initialData: (__VLS_ctx.editData),
    }));
    const __VLS_36 = __VLS_35({
        ...{ 'onSubmit': {} },
        updateMode: true,
        initialData: (__VLS_ctx.editData),
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    let __VLS_39;
    const __VLS_40 = ({ submit: {} },
        { onSubmit: (__VLS_ctx.onUpdateSubmit) });
    var __VLS_37;
    var __VLS_38;
}
// @ts-ignore
[visible, dialogPt, editData, editData, onUpdateSubmit,];
var __VLS_31;
// @ts-ignore
var __VLS_20 = __VLS_19;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
