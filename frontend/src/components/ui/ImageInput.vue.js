/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import avatarPlaceholder from '@/assets/img/avatar-placeholder.png';
import { ref } from 'vue';
const __VLS_props = defineProps({
    image: {
        type: String,
        default: avatarPlaceholder,
    },
    label: {
        type: String,
        default: 'Change photo',
    },
    shape: {
        type: String,
        default: 'circle',
    },
});
const emit = defineEmits();
const inputRef = ref();
const newImage = ref('');
const onInputChange = (event) => {
    const input = event.target;
    if (!input.files || !(input.files.length > 0)) {
        emit('onImageChange', null);
        newImage.value = '';
        return;
    }
    const file = input.files[0];
    emit('onImageChange', file);
    const reader = new FileReader();
    reader.onload = (e) => {
        newImage.value = e.target?.result || '';
    };
    reader.readAsDataURL(file);
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.inputRef?.click();
            // @ts-ignore
            [inputRef,];
        } },
    ...{ class: "area" },
});
/** @type {__VLS_StyleScopedClasses['area']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.dAvatar | typeof __VLS_components.DAvatar | typeof __VLS_components['d-avatar']} */
dAvatar;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    image: (__VLS_ctx.newImage || __VLS_ctx.image),
    size: "xlarge",
    shape: (__VLS_ctx.shape),
    ...{ style: {} },
    ...{ class: ({ square: __VLS_ctx.shape === 'square' }) },
}));
const __VLS_2 = __VLS_1({
    image: (__VLS_ctx.newImage || __VLS_ctx.image),
    size: "xlarge",
    shape: (__VLS_ctx.shape),
    ...{ style: {} },
    ...{ class: ({ square: __VLS_ctx.shape === 'square' }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['square']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onChange: (__VLS_ctx.onInputChange) },
    ref: "inputRef",
    type: "file",
    id: "avatar",
    name: "avatar",
    accept: "image/png, image/jpeg, image/webp",
    ...{ class: "input" },
});
/** @type {__VLS_StyleScopedClasses['input']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "link" },
});
/** @type {__VLS_StyleScopedClasses['link']} */ ;
(__VLS_ctx.label);
// @ts-ignore
[newImage, image, shape, shape, onInputChange, label,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    props: {
        image: {
            type: String,
            default: avatarPlaceholder,
        },
        label: {
            type: String,
            default: 'Change photo',
        },
        shape: {
            type: String,
            default: 'circle',
        },
    },
});
export default {};
