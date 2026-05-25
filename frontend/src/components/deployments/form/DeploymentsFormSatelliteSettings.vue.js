/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { SatelliteFieldTypeEnum } from '@/lib/api/satellites/interfaces';
import { getErrorMessage } from '@/helpers/helpers';
import { simpleErrorToast } from '@/lib/primevue/data/toasts';
import { useSatellitesStore } from '@/stores/satellites';
import { Select, useToast, InputText, InputNumber, ToggleButton } from 'primevue';
import { computed, nextTick, onBeforeMount, ref } from 'vue';
import { useRoute } from 'vue-router';
import { FormField } from '@primevue/forms';
import { Rocket, Info } from 'lucide-vue-next';
import { useSatelliteFields } from '@/hooks/satellites/useSatelliteFields';
import { watch } from 'vue';
const props = defineProps();
const satellitesStore = useSatellitesStore();
const route = useRoute();
const toast = useToast();
const { fields: fieldsForShowing, setFields } = useSatelliteFields();
const satelliteId = defineModel('satelliteId');
const fields = defineModel('fields');
const ignoreWatch = ref(false);
const filteredSatellites = computed(() => {
    const model = props.selectedModel;
    if (!model)
        return [];
    return satellitesStore.satellitesList.filter((satellite) => !!satellite.capabilities.deploy);
});
const satellitesOptions = computed(() => {
    const model = props.selectedModel;
    if (!model)
        return [];
    return filteredSatellites.value.map((satellite) => {
        const variantValid = !!satellite.capabilities.deploy?.supported_variants?.includes(model.manifest.variant);
        const supportedTagsEmpty = !satellite.capabilities.deploy?.supported_tags_combinations;
        const tagsSupported = !!satellite.capabilities.deploy?.supported_tags_combinations?.find((combination) => {
            return combination.every((tag) => model.manifest.producer_tags.includes(tag));
        });
        const tagsValid = supportedTagsEmpty || tagsSupported;
        return {
            ...satellite,
            disabled: !variantValid || !tagsValid,
            errorMessage: getSatelliteErrorMessage(variantValid, tagsValid),
        };
    });
});
const satellitesGroups = computed(() => {
    const disabled = satellitesOptions.value.filter((satellite) => satellite.disabled);
    const enabled = satellitesOptions.value.filter((satellite) => !satellite.disabled);
    const groups = [];
    if (enabled.length > 0) {
        groups.push({
            label: 'Available satellites',
            items: enabled,
        });
    }
    if (disabled.length > 0) {
        groups.push({
            label: 'Incompatible satellites',
            items: disabled,
        });
    }
    return groups;
});
function getSatelliteErrorMessage(variantValid, tagsValid) {
    if (!variantValid)
        return 'The satellite does not support this model variant';
    if (!tagsValid)
        return 'The model does not contain a combination of tags required by the satellite';
    return null;
}
async function getSatellites() {
    try {
        const organizationIdParam = route.params.organizationId;
        const orbitIdParam = route.params.id;
        const organizationId = typeof organizationIdParam === 'string' ? organizationIdParam : organizationIdParam[0];
        const orbitId = typeof orbitIdParam === 'string' ? orbitIdParam : orbitIdParam[0];
        const list = await satellitesStore.loadSatellites(organizationId, orbitId);
        satellitesStore.setList(list);
    }
    catch (e) {
        toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')));
    }
}
function updateFields() {
    const satellite = satellitesStore.satellitesList.find((satellite) => satellite.id === satelliteId.value) || null;
    setFields(satellite, props.selectedModel, fields.value?.reduce((acc, field) => {
        acc[field.key] = field.value;
        return acc;
    }, {}) || {});
}
function getFieldInfo(data) {
    return {
        key: data.name,
        value: null,
        label: data.name,
        required: data.required,
        validators: data.validators,
        values: data.values,
        type: data.type,
    };
}
function removeOldFields(currentFields) {
    const updatedFields = fields.value?.filter((field) => {
        return currentFields.includes(field.key);
    });
    fields.value = updatedFields;
}
function addNewFields(newFields) {
    const notExistingFields = newFields.filter((field) => {
        return !fields.value?.some((f) => f.key === field.name);
    });
    fields.value = [...(fields.value || []), ...notExistingFields.map(getFieldInfo)];
}
watch([() => props.selectedModel, () => satelliteId.value, () => fields.value], (values, prevValues) => {
    const isModelChanged = values[0] !== prevValues[0];
    const isSatelliteChanged = values[1] !== prevValues[1];
    const isFieldsChanged = JSON.stringify(values[2]) !== JSON.stringify(prevValues[2]);
    const someDataChanged = isModelChanged || isSatelliteChanged || isFieldsChanged;
    if (ignoreWatch.value || !someDataChanged)
        return;
    updateFields();
}, { deep: true });
watch(fieldsForShowing, (newFields) => {
    ignoreWatch.value = true;
    removeOldFields(newFields.map((field) => field.name));
    nextTick(() => {
        addNewFields(newFields);
        ignoreWatch.value = false;
    });
});
onBeforeMount(() => {
    getSatellites();
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
/** @type {__VLS_StyleScopedClasses['custom-variables']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "column" },
});
/** @type {__VLS_StyleScopedClasses['column']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "column-title" },
});
/** @type {__VLS_StyleScopedClasses['column-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "fields" },
});
/** @type {__VLS_StyleScopedClasses['fields']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "field" },
});
/** @type {__VLS_StyleScopedClasses['field']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    for: "satelliteId",
    ...{ class: "label required" },
});
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.satelliteId),
    id: "satelliteId",
    name: "satelliteId",
    placeholder: "Select satellite",
    fluid: true,
    options: (__VLS_ctx.satellitesGroups),
    optionLabel: "name",
    optionValue: "id",
    optionDisabled: "disabled",
    optionGroupLabel: "label",
    optionGroupChildren: "items",
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.satelliteId),
    id: "satelliteId",
    name: "satelliteId",
    placeholder: "Select satellite",
    fluid: true,
    options: (__VLS_ctx.satellitesGroups),
    optionLabel: "name",
    optionValue: "id",
    optionDisabled: "disabled",
    optionGroupLabel: "label",
    optionGroupChildren: "items",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { option: __VLS_6 } = __VLS_3.slots;
    const [{ option }] = __VLS_vSlot(__VLS_6);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "option" },
    });
    /** @type {__VLS_StyleScopedClasses['option']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "option-text" },
    });
    /** @type {__VLS_StyleScopedClasses['option-text']} */ ;
    (option.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "option-icons" },
    });
    /** @type {__VLS_StyleScopedClasses['option-icons']} */ ;
    if (option.capabilities.deploy) {
        let __VLS_7;
        /** @ts-ignore @type { | typeof __VLS_components.Rocket | typeof __VLS_components.Rocket} */
        Rocket;
        // @ts-ignore
        const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
            size: (16),
            color: "var(--p-icon-muted-color)",
        }));
        const __VLS_9 = __VLS_8({
            size: (16),
            color: "var(--p-icon-muted-color)",
        }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    }
    if (option.errorMessage) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "option-message" },
        });
        /** @type {__VLS_StyleScopedClasses['option-message']} */ ;
        let __VLS_12;
        /** @ts-ignore @type { | typeof __VLS_components.Info} */
        Info;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
            size: (12),
            ...{ class: "option-message-icon" },
        }));
        const __VLS_14 = __VLS_13({
            size: (12),
            ...{ class: "option-message-icon" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        /** @type {__VLS_StyleScopedClasses['option-message-icon']} */ ;
        (option.errorMessage);
    }
    // @ts-ignore
    [satelliteId, satellitesGroups,];
}
// @ts-ignore
[];
var __VLS_3;
if (__VLS_ctx.fields?.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "custom-variables" },
    });
    /** @type {__VLS_StyleScopedClasses['custom-variables']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "custom-variables__content" },
    });
    /** @type {__VLS_StyleScopedClasses['custom-variables__content']} */ ;
    for (const [field, index] of __VLS_vFor((__VLS_ctx.fields))) {
        let __VLS_17;
        /** @ts-ignore @type { | typeof __VLS_components.FormField | typeof __VLS_components.FormField} */
        FormField;
        // @ts-ignore
        const __VLS_18 = __VLS_asFunctionalComponent1(__VLS_17, new __VLS_17({
            key: (field.key),
            name: (`satelliteFields.${index}.value`),
            ...{ class: "field" },
        }));
        const __VLS_19 = __VLS_18({
            key: (field.key),
            name: (`satelliteFields.${index}.value`),
            ...{ class: "field" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_18));
        /** @type {__VLS_StyleScopedClasses['field']} */ ;
        const { default: __VLS_22 } = __VLS_20.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "label" },
            ...{ class: ({ required: field.required }) },
        });
        /** @type {__VLS_StyleScopedClasses['label']} */ ;
        /** @type {__VLS_StyleScopedClasses['required']} */ ;
        (field.label);
        if (field.type === __VLS_ctx.SatelliteFieldTypeEnum.boolean) {
            let __VLS_23;
            /** @ts-ignore @type { | typeof __VLS_components.ToggleButton | typeof __VLS_components.ToggleButton} */
            ToggleButton;
            // @ts-ignore
            const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
                ...{ 'onChange': {} },
                modelValue: field.value,
                size: "small",
            }));
            const __VLS_25 = __VLS_24({
                ...{ 'onChange': {} },
                modelValue: field.value,
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_24));
            let __VLS_28;
            const __VLS_29 = ({ change: {} },
                { onChange: (__VLS_ctx.updateFields) });
            var __VLS_26;
            var __VLS_27;
        }
        else if (field.type === __VLS_ctx.SatelliteFieldTypeEnum.dropdown) {
            let __VLS_30;
            /** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
            Select;
            // @ts-ignore
            const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
                ...{ 'onChange': {} },
                modelValue: (field.value),
                options: (field.values || []),
                required: (field.required),
                size: "small",
                optionLabel: "label",
                optionValue: "value",
                placeholder: "Select value",
            }));
            const __VLS_32 = __VLS_31({
                ...{ 'onChange': {} },
                modelValue: (field.value),
                options: (field.values || []),
                required: (field.required),
                size: "small",
                optionLabel: "label",
                optionValue: "value",
                placeholder: "Select value",
            }, ...__VLS_functionalComponentArgsRest(__VLS_31));
            let __VLS_35;
            const __VLS_36 = ({ change: {} },
                { onChange: (__VLS_ctx.updateFields) });
            var __VLS_33;
            var __VLS_34;
        }
        else if (field.type === __VLS_ctx.SatelliteFieldTypeEnum.number) {
            let __VLS_37;
            /** @ts-ignore @type { | typeof __VLS_components.InputNumber | typeof __VLS_components.InputNumber} */
            InputNumber;
            // @ts-ignore
            const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
                ...{ 'onChange': {} },
                modelValue: field.value,
                placeholder: "Enter value",
                size: "small",
                required: (field.required),
            }));
            const __VLS_39 = __VLS_38({
                ...{ 'onChange': {} },
                modelValue: field.value,
                placeholder: "Enter value",
                size: "small",
                required: (field.required),
            }, ...__VLS_functionalComponentArgsRest(__VLS_38));
            let __VLS_42;
            const __VLS_43 = ({ change: {} },
                { onChange: (__VLS_ctx.updateFields) });
            var __VLS_40;
            var __VLS_41;
        }
        else {
            let __VLS_44;
            /** @ts-ignore @type { | typeof __VLS_components.InputText | typeof __VLS_components.InputText} */
            InputText;
            // @ts-ignore
            const __VLS_45 = __VLS_asFunctionalComponent1(__VLS_44, new __VLS_44({
                ...{ 'onChange': {} },
                modelValue: field.value,
                placeholder: "Enter value",
                size: "small",
                required: (field.required),
            }));
            const __VLS_46 = __VLS_45({
                ...{ 'onChange': {} },
                modelValue: field.value,
                placeholder: "Enter value",
                size: "small",
                required: (field.required),
            }, ...__VLS_functionalComponentArgsRest(__VLS_45));
            let __VLS_49;
            const __VLS_50 = ({ change: {} },
                { onChange: (__VLS_ctx.updateFields) });
            var __VLS_47;
            var __VLS_48;
        }
        // @ts-ignore
        [fields, fields, SatelliteFieldTypeEnum, SatelliteFieldTypeEnum, SatelliteFieldTypeEnum, updateFields, updateFields, updateFields, updateFields,];
        var __VLS_20;
        // @ts-ignore
        [];
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
