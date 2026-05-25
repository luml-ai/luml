/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { Select, Button } from 'primevue';
import { Plus } from 'lucide-vue-next';
import { ref } from 'vue';
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue';
const __VLS_props = defineProps();
const modelValue = defineModel('modelValue');
const isCreating = ref(false);
function initCreateSecret() {
    isCreating.value = true;
}
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.modelValue),
    options: (__VLS_ctx.secretsList),
    filter: true,
    filterPlaceholder: "Select secret",
    optionLabel: "name",
    optionValue: "id",
    placeholder: "Select secret",
    size: "small",
    fluid: true,
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.modelValue),
    options: (__VLS_ctx.secretsList),
    filter: true,
    filterPlaceholder: "Select secret",
    optionLabel: "name",
    optionValue: "id",
    placeholder: "Select secret",
    size: "small",
    fluid: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { footer: __VLS_6 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "select-footer" },
    });
    /** @type {__VLS_StyleScopedClasses['select-footer']} */ ;
    let __VLS_7;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        ...{ 'onClick': {} },
        variant: "text",
    }));
    const __VLS_9 = __VLS_8({
        ...{ 'onClick': {} },
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    let __VLS_12;
    const __VLS_13 = ({ click: {} },
        { onClick: (__VLS_ctx.initCreateSecret) });
    const { default: __VLS_14 } = __VLS_10.slots;
    let __VLS_15;
    /** @ts-ignore @type { | typeof __VLS_components.Plus | typeof __VLS_components.Plus} */
    Plus;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent1(__VLS_15, new __VLS_15({
        size: (14),
    }));
    const __VLS_17 = __VLS_16({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    // @ts-ignore
    [modelValue, secretsList, initCreateSecret,];
    var __VLS_10;
    var __VLS_11;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_3;
if (__VLS_ctx.isCreating) {
    const __VLS_20 = SecretCreator || SecretCreator;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent1(__VLS_20, new __VLS_20({
        visible: (__VLS_ctx.isCreating),
        organizationId: (String(__VLS_ctx.$route.params.organizationId)),
        orbitId: (String(__VLS_ctx.$route.params.id)),
    }));
    const __VLS_22 = __VLS_21({
        visible: (__VLS_ctx.isCreating),
        organizationId: (String(__VLS_ctx.$route.params.organizationId)),
        orbitId: (String(__VLS_ctx.$route.params.id)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
// @ts-ignore
[isCreating, isCreating, $route, $route,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
