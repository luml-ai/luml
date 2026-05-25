/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, watch } from 'vue';
import { Dialog, Button, InputText, Textarea, AutoComplete, useToast, useConfirm, } from 'primevue';
import { Bolt } from 'lucide-vue-next';
import { Form } from '@primevue/forms';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { deleteArtifactConfirmOptions } from '@/lib/primevue/data/confirm';
import { artifactEditResolver } from '@/utils/forms/resolvers';
import { useOrbitsStore } from '@/stores/orbits';
import { PermissionEnum } from '@/lib/api/api.interfaces';
import { useArtifactsStore } from '@/stores/artifacts';
import { useArtifactsTags } from '@/hooks/useArtifactsTags';
import { getErrorMessage } from '@/helpers/helpers';
const dialogPT = {
    footer: {
        style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
    },
};
const props = defineProps();
const emit = defineEmits();
const visible = defineModel('visible');
const toast = useToast();
const confirm = useConfirm();
const orbitsStore = useOrbitsStore();
const artifactsStore = useArtifactsStore();
const { getTagsByQuery, loadTags } = useArtifactsTags();
const initialValues = ref({
    name: props.data.name,
    description: props.data.description,
    tags: [...(props.data.tags || [])],
});
const loading = ref(false);
const autocompleteItems = ref([]);
function searchTags(event) {
    autocompleteItems.value = getTagsByQuery(event.query);
}
async function saveChanges() {
    try {
        loading.value = true;
        const payload = {
            id: props.data.id,
            file_name: props.data.file_name,
            name: initialValues.value.name,
            description: initialValues.value.description,
            tags: initialValues.value.tags,
        };
        const result = await artifactsStore.updateArtifact(payload);
        emit('updateArtifact', result);
        toast.add(simpleSuccessToast('Artifact successfully updated'));
        visible.value = false;
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to update artifact'));
    }
    finally {
        loading.value = false;
    }
}
function onDeleteClick() {
    confirm.require(deleteArtifactConfirmOptions(deleteArtifact, 1));
}
async function deleteArtifact() {
    try {
        loading.value = true;
        const result = await artifactsStore.deleteArtifacts([props.data.id]);
        if (result.deleted?.length) {
            toast.add(simpleSuccessToast(`Artifact "${props.data.name}" was removed from the collection.`));
            visible.value = false;
            emit('artifactDeleted');
        }
        else if (result.failed?.length) {
            toast.add(simpleErrorToast(`Failed to delete artifact "${props.data.name}".`));
        }
    }
    catch (e) {
        toast.add(simpleErrorToast('Failed to delete artifact'));
    }
    finally {
        loading.value = false;
    }
}
watch(() => artifactsStore.requestInfo, async (info) => {
    try {
        autocompleteItems.value = [];
        if (!info)
            return;
        await loadTags(info.organizationId, info.orbitId, info.collectionId);
    }
    catch (e) {
        const message = getErrorMessage(e, 'Failed to load tags');
        toast.add(simpleErrorToast(message));
    }
}, { immediate: true, deep: true });
let __VLS_modelEmit;
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
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    position: "topright",
    draggable: (false),
    ...{ style: {} },
    pt: (__VLS_ctx.dialogPT),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
{
    const { header: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "dialog-title" },
    });
    /** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
    let __VLS_8;
    /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
    Bolt;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
        size: (20),
        color: "var(--p-primary-color)",
    }));
    const __VLS_10 = __VLS_9({
        size: (20),
        color: "var(--p-primary-color)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    // @ts-ignore
    [visible, dialogPT,];
}
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    ...{ 'onSubmit': {} },
    id: "orbit-edit-form",
    initialValues: __VLS_ctx.initialValues,
    resolver: (__VLS_ctx.artifactEditResolver),
    ...{ class: "form" },
}));
const __VLS_15 = __VLS_14({
    ...{ 'onSubmit': {} },
    id: "orbit-edit-form",
    initialValues: __VLS_ctx.initialValues,
    resolver: (__VLS_ctx.artifactEditResolver),
    ...{ class: "form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
let __VLS_18;
const __VLS_19 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.saveChanges) });
/** @type {__VLS_StyleScopedClasses['form']} */ ;
const { default: __VLS_20 } = __VLS_16.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_21;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
}));
const __VLS_23 = __VLS_22({
    modelValue: (__VLS_ctx.initialValues.name),
    name: "name",
    id: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_26;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
    modelValue: (__VLS_ctx.initialValues.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}));
const __VLS_28 = __VLS_27({
    modelValue: (__VLS_ctx.initialValues.description),
    name: "description",
    id: "description",
    placeholder: "Describe your artifact",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "form-item" },
});
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_31;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.initialValues.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_33 = __VLS_32({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.initialValues.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
let __VLS_36;
const __VLS_37 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_34;
var __VLS_35;
// @ts-ignore
[initialValues, initialValues, initialValues, initialValues, artifactEditResolver, saveChanges, autocompleteItems, searchTags,];
var __VLS_16;
var __VLS_17;
{
    const { footer: __VLS_38 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (__VLS_ctx.orbitsStore.getCurrentOrbitPermissions?.artifact.includes(__VLS_ctx.PermissionEnum.delete)) {
        let __VLS_39;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }));
        const __VLS_41 = __VLS_40({
            ...{ 'onClick': {} },
            variant: "outlined",
            severity: "warn",
            disabled: (__VLS_ctx.loading),
        }, ...__VLS_functionalComponentArgsRest(__VLS_40));
        let __VLS_44;
        const __VLS_45 = ({ click: {} },
            { onClick: (__VLS_ctx.onDeleteClick) });
        const { default: __VLS_46 } = __VLS_42.slots;
        // @ts-ignore
        [orbitsStore, PermissionEnum, loading, onDeleteClick,];
        var __VLS_42;
        var __VLS_43;
    }
    let __VLS_47;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "orbit-edit-form",
    }));
    const __VLS_49 = __VLS_48({
        type: "submit",
        loading: (__VLS_ctx.loading),
        form: "orbit-edit-form",
    }, ...__VLS_functionalComponentArgsRest(__VLS_48));
    const { default: __VLS_52 } = __VLS_50.slots;
    // @ts-ignore
    [loading,];
    var __VLS_50;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
