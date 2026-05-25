/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { useDeploymentsStore } from '@/stores/deployments';
import { computed, ref } from 'vue';
import { InputText, AutoComplete, Textarea } from 'primevue';
const __VLS_props = withDefaults(defineProps(), {
    showTitle: true,
});
const name = defineModel('name');
const tags = defineModel('tags');
const description = defineModel('description');
const deploymentsStore = useDeploymentsStore();
const existingTags = computed(() => {
    const tagsSet = deploymentsStore.deployments.reduce((acc, item) => {
        item.tags?.map((tag) => {
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
let __VLS_modelEmit;
const __VLS_defaults = {
    showTitle: true,
};
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
/** @type {__VLS_StyleScopedClasses['column']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column" },
});
/** @type {__VLS_StyleScopedClasses['column']} */ ;
if (__VLS_ctx.showTitle) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
        ...{ class: "column-title" },
    });
    /** @type {__VLS_StyleScopedClasses['column-title']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "fields" },
});
/** @type {__VLS_StyleScopedClasses['fields']} */ ;
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
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.name),
    id: "name",
    name: "name",
    placeholder: "Name your deployment",
    fluid: true,
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.name),
    id: "name",
    name: "name",
    placeholder: "Name your deployment",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "tags",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.AutoComplete | typeof __VLS_components.AutoComplete} */
AutoComplete;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags for deployment",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}));
const __VLS_7 = __VLS_6({
    ...{ 'onComplete': {} },
    modelValue: (__VLS_ctx.tags),
    id: "tags",
    name: "tags",
    placeholder: "Type to add tags for deployment",
    fluid: true,
    multiple: true,
    suggestions: (__VLS_ctx.autocompleteItems),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ complete: {} },
    { onComplete: (__VLS_ctx.searchTags) });
var __VLS_8;
var __VLS_9;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "description",
    ...{ class: "label" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
let __VLS_12;
/** @ts-ignore @type { | typeof __VLS_components.Textarea | typeof __VLS_components.Textarea} */
Textarea;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
    modelValue: (__VLS_ctx.description),
    id: "description",
    name: "description",
    placeholder: "Describe your deployment",
    fluid: true,
    ...{ class: "textarea" },
}));
const __VLS_14 = __VLS_13({
    modelValue: (__VLS_ctx.description),
    id: "description",
    name: "description",
    placeholder: "Describe your deployment",
    fluid: true,
    ...{ class: "textarea" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
/** @type {__VLS_StyleScopedClasses['textarea']} */ ;
// @ts-ignore
[showTitle, name, tags, autocompleteItems, searchTags, description,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
