/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, reactive } from 'vue';
import { Button, Tag } from 'primevue';
import { useSecretsStore } from '@/stores/orbit-secrets';
import SecretEditor from './SecretsEditor.vue';
import SecretModal from './SecretModal.vue';
import { Eye, Bolt } from 'lucide-vue-next';
const secretsStore = useSecretsStore();
const visibleSecrets = reactive({});
const editDialogVisible = ref(false);
const secretToEdit = ref(null);
const secretModalVisible = ref(false);
const currentSecret = ref(null);
const __VLS_props = defineProps();
const editSecret = (secret) => {
    secretToEdit.value = secret;
    editDialogVisible.value = true;
};
function showSecretModal(secret) {
    currentSecret.value = secret;
    secretModalVisible.value = true;
}
function maskSecret(value) {
    if (!value)
        return '*'.repeat(15);
    return value.length > 15 ? '*'.repeat(15) : '*'.repeat(value.length);
}
function normalizeTags(tags) {
    if (!tags)
        return [];
    if (Array.isArray(tags)) {
        return tags.map((tag) => (typeof tag === 'string' ? tag : (tag.name ?? '')));
    }
    if (typeof tags === 'string') {
        return tags.split(',').map((tag) => tag.trim());
    }
    return [];
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
/** @type {__VLS_StyleScopedClasses['simple-table__row']} */ ;
/** @type {__VLS_StyleScopedClasses['table-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "table-wrapper" },
});
/** @type {__VLS_StyleScopedClasses['table-wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table" },
});
/** @type {__VLS_StyleScopedClasses['simple-table']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__header" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__row" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__row']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "simple-table__rows" },
});
/** @type {__VLS_StyleScopedClasses['simple-table__rows']} */ ;
if (!__VLS_ctx.secretsStore.secretsList.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "simple-table__placeholder" },
    });
    /** @type {__VLS_StyleScopedClasses['simple-table__placeholder']} */ ;
}
for (const [secret] of __VLS_vFor((__VLS_ctx.secretsStore.secretsList))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (secret.id),
        ...{ class: "simple-table__row" },
    });
    /** @type {__VLS_StyleScopedClasses['simple-table__row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "secret-name" },
    });
    /** @type {__VLS_StyleScopedClasses['secret-name']} */ ;
    (secret.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "secret-key" },
    });
    /** @type {__VLS_StyleScopedClasses['secret-key']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        ...{ class: "eye-button" },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
        ...{ class: "eye-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.showSecretModal(secret);
                // @ts-ignore
                [secretsStore, secretsStore, showSecretModal,];
            } });
    /** @type {__VLS_StyleScopedClasses['eye-button']} */ ;
    const { default: __VLS_7 } = __VLS_3.slots;
    {
        const { icon: __VLS_8 } = __VLS_3.slots;
        let __VLS_9;
        /** @ts-ignore @type { | typeof __VLS_components.Eye} */
        Eye;
        // @ts-ignore
        const __VLS_10 = __VLS_asFunctionalComponent1(__VLS_9, new __VLS_9({
            size: (15),
        }));
        const __VLS_11 = __VLS_10({
            size: (15),
        }, ...__VLS_functionalComponentArgsRest(__VLS_10));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_3;
    var __VLS_4;
    if (!__VLS_ctx.visibleSecrets[secret.id]) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "secret-hidden" },
        });
        /** @type {__VLS_StyleScopedClasses['secret-hidden']} */ ;
        (__VLS_ctx.maskSecret(secret.value));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "secret-revealed" },
        });
        /** @type {__VLS_StyleScopedClasses['secret-revealed']} */ ;
        (secret.value);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "tags" },
    });
    /** @type {__VLS_StyleScopedClasses['tags']} */ ;
    for (const [tag] of __VLS_vFor((__VLS_ctx.normalizeTags(secret.tags)))) {
        let __VLS_14;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
            key: (tag),
            ...{ class: "tag" },
        }));
        const __VLS_16 = __VLS_15({
            key: (tag),
            ...{ class: "tag" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        /** @type {__VLS_StyleScopedClasses['tag']} */ ;
        const { default: __VLS_19 } = __VLS_17.slots;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (tag);
        // @ts-ignore
        [visibleSecrets, maskSecret, normalizeTags,];
        var __VLS_17;
        // @ts-ignore
        [];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "updated-date" },
    });
    /** @type {__VLS_StyleScopedClasses['updated-date']} */ ;
    (secret.updated_at
        ? new Date(secret.updated_at).toLocaleString()
        : new Date().toLocaleString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "actions" },
    });
    /** @type {__VLS_StyleScopedClasses['actions']} */ ;
    let __VLS_20;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
        variant: "text",
        severity: "secondary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_25;
    const __VLS_26 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.editSecret(secret);
                // @ts-ignore
                [editSecret,];
            } });
    const { default: __VLS_27 } = __VLS_23.slots;
    {
        const { icon: __VLS_28 } = __VLS_23.slots;
        let __VLS_29;
        /** @ts-ignore @type { | typeof __VLS_components.Bolt} */
        Bolt;
        // @ts-ignore
        const __VLS_30 = __VLS_asFunctionalComponent1(__VLS_29, new __VLS_29({
            size: (14),
        }));
        const __VLS_31 = __VLS_30({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_30));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_23;
    var __VLS_24;
    // @ts-ignore
    [];
}
const __VLS_34 = SecretModal;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent1(__VLS_34, new __VLS_34({
    visible: (__VLS_ctx.secretModalVisible),
    secret: (__VLS_ctx.currentSecret),
}));
const __VLS_36 = __VLS_35({
    visible: (__VLS_ctx.secretModalVisible),
    secret: (__VLS_ctx.currentSecret),
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
const __VLS_39 = SecretEditor;
// @ts-ignore
const __VLS_40 = __VLS_asFunctionalComponent1(__VLS_39, new __VLS_39({
    visible: (__VLS_ctx.editDialogVisible),
    secret: (__VLS_ctx.secretToEdit),
}));
const __VLS_41 = __VLS_40({
    visible: (__VLS_ctx.editDialogVisible),
    secret: (__VLS_ctx.secretToEdit),
}, ...__VLS_functionalComponentArgsRest(__VLS_40));
// @ts-ignore
[secretModalVisible, currentSecret, editDialogVisible, secretToEdit,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
