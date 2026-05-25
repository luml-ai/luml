/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Dialog, Button, InputText, Select, AutoComplete, Textarea, useToast } from 'primevue';
import { Form } from '@primevue/forms';
import { computed, ref, watch } from 'vue';
import { OrbitCollectionTypeEnum, } from '@/lib/api/orbit-collections/interfaces';
import { useCollectionsStore } from '@/stores/collections';
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts';
import { collectionCreatorResolver } from '@/utils/forms/resolvers';
import { COLLECTION_CREATOR_DIALOG_PT, COLLECTION_TYPE_OPTIONS } from './collection.const';
const props = defineProps();
const collectionsStore = useCollectionsStore();
const toast = useToast();
const visible = defineModel('visible');
const formData = ref({
    description: '',
    name: '',
    type: OrbitCollectionTypeEnum.model,
    tags: [],
});
const loading = ref(false);
const existingTags = computed(() => {
    const tagsSet = collectionsStore.collectionsList.reduce((acc, item) => {
        item.tags.map((tag) => {
            acc.add(tag);
        });
        return acc;
    }, new Set());
    return Array.from(tagsSet);
});
const autocompleteItems = ref([]);
function searchTags(event) {
    autocompleteItems.value = [
        event.query,
        ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
    ];
}
function getRequestInfo() {
    if (props.organizationId && props.orbitId) {
        return { organizationId: props.organizationId, orbitId: props.orbitId };
    }
}
async function onSubmit({ valid }) {
    if (!valid)
        return;
    try {
        loading.value = true;
        await collectionsStore.createCollection({ ...formData.value }, getRequestInfo());
        visible.value = false;
        toast.add(simpleSuccessToast('Collection created'));
    }
    catch (e) {
        toast.add(simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create collection'));
    }
    finally {
        loading.value = false;
    }
}
watch(visible, (value) => {
    if (value) {
        formData.value = {
            description: '',
            name: '',
            type: OrbitCollectionTypeEnum.model,
            tags: [],
        };
    }
});
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
    header: "Create a new collection",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.COLLECTION_CREATOR_DIALOG_PT),
}));
const __VLS_2 = __VLS_1({
    visible: (__VLS_ctx.visible),
    header: "Create a new collection",
    modal: true,
    draggable: (false),
    pt: (__VLS_ctx.COLLECTION_CREATOR_DIALOG_PT),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5;
const { default: __VLS_6 } = __VLS_3.slots;
let __VLS_7;
/** @ts-ignore @type { | typeof __VLS_components.Form | typeof __VLS_components.Form} */
Form;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.collectionCreatorResolver),
}));
const __VLS_9 = __VLS_8({
    ...{ 'onSubmit': {} },
    initialValues: (__VLS_ctx.formData),
    resolver: (__VLS_ctx.collectionCreatorResolver),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
let __VLS_12;
const __VLS_13 = ({ submit: {} },
    { onSubmit: (__VLS_ctx.onSubmit) });
const { default: __VLS_14 } = __VLS_10.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "inputs" },
});
/** @type {__VLS_StyleScopedClasses['inputs']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "name",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_15;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your collection",
    fluid: true,
}));
const __VLS_17 = __VLS_16({
    modelValue: (__VLS_ctx.formData.name),
    id: "name",
    name: "name",
    placeholder: "Name your collection",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "type",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_20;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
    modelValue: (__VLS_ctx.formData.type),
    options: (__VLS_ctx.COLLECTION_TYPE_OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    placeholder: "Select artifact types",
    name: "type",
    id: "type",
}));
const __VLS_22 = __VLS_21({
    modelValue: (__VLS_ctx.formData.type),
    options: (__VLS_ctx.COLLECTION_TYPE_OPTIONS),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    placeholder: "Select artifact types",
    name: "type",
    id: "type",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_25;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your collection",
    ...{ style: {} },
}));
const __VLS_27 = __VLS_26({
    modelValue: (__VLS_ctx.formData.description),
    name: "description",
    id: "description",
    placeholder: "Describe your collection",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_32 = __VLS_31({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.formData.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
let __VLS_35;
const __VLS_36 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_33;
var __VLS_34;
let __VLS_37;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}));
const __VLS_39 = __VLS_38({
    type: "submit",
    fluid: true,
    rounded: true,
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
const { default: __VLS_42 } = __VLS_40.slots;
// @ts-ignore
[visible, COLLECTION_CREATOR_DIALOG_PT, formData, formData, formData, formData, formData, collectionCreatorResolver, onSubmit, COLLECTION_TYPE_OPTIONS, autocompleteItems, searchTags, loading,];
var __VLS_40;
// @ts-ignore
[];
var __VLS_10;
var __VLS_11;
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
