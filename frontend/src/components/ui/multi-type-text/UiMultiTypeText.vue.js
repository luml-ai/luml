/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import 'github-markdown-css/github-markdown.css';
import { computed, ref } from 'vue';
import { Select, Button } from 'primevue';
import { Copy, CopyCheck } from 'lucide-vue-next';
import { marked } from 'marked';
import { isYamlLike, jsonToYaml } from '@/helpers/helpers';
import DOMPurify from 'dompurify';
import { ContentTypeEnum } from './interfaces';
const props = withDefaults(defineProps(), {
    initialType: ContentTypeEnum.raw,
});
const contentType = ref(props.initialType);
const copied = ref(false);
const contentTypes = computed(() => [
    {
        label: 'YAML',
        value: ContentTypeEnum.yaml,
        disabled: !isYamlLike(JSON.stringify(props.text)),
    },
    {
        label: 'Markdown',
        value: ContentTypeEnum.markdown,
    },
    {
        label: 'Raw',
        value: ContentTypeEnum.raw,
    },
]);
const markdownText = computed(() => {
    const result = marked.parse(typeof props.text === 'object' ? JSON.stringify(props.text) : `${props.text}`);
    return DOMPurify.sanitize(result);
});
const yamlText = computed(() => jsonToYaml(props.text));
function copy() {
    navigator.clipboard.writeText(typeof props.text === 'object' ? JSON.stringify(props.text) : `${props.text}`);
    copied.value = true;
    setTimeout(() => {
        copied.value = false;
    }, 1000);
}
const __VLS_defaults = {
    initialType: ContentTypeEnum.raw,
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "item" },
});
/** @type {__VLS_StyleScopedClasses['item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)({
    ...{ class: "header" },
});
/** @type {__VLS_StyleScopedClasses['header']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
    ...{ class: "title" },
});
/** @type {__VLS_StyleScopedClasses['title']} */ ;
(__VLS_ctx.title);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "right" },
});
/** @type {__VLS_StyleScopedClasses['right']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.Select | typeof __VLS_components.Select} */
Select;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.contentType),
    options: (__VLS_ctx.contentTypes),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    size: "small",
    ...{ class: "select" },
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.contentType),
    options: (__VLS_ctx.contentTypes),
    optionLabel: "label",
    optionValue: "value",
    optionDisabled: "disabled",
    size: "small",
    ...{ class: "select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['select']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
    disabled: (__VLS_ctx.copied),
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    severity: "secondary",
    variant: "text",
    disabled: (__VLS_ctx.copied),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (__VLS_ctx.copy) });
__VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { left: true, }, value: ('Copy') }, null, null);
const { default: __VLS_12 } = __VLS_8.slots;
{
    const { icon: __VLS_13 } = __VLS_8.slots;
    const __VLS_14 = (__VLS_ctx.copied ? __VLS_ctx.CopyCheck : __VLS_ctx.Copy);
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
        size: (14),
    }));
    const __VLS_16 = __VLS_15({
        size: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    // @ts-ignore
    [title, contentType, contentTypes, copied, copied, copy, vTooltip, CopyCheck, Copy,];
}
// @ts-ignore
[];
var __VLS_8;
var __VLS_9;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "content" },
});
/** @type {__VLS_StyleScopedClasses['content']} */ ;
if (__VLS_ctx.contentType === __VLS_ctx.ContentTypeEnum.yaml) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "yaml-body" },
    });
    /** @type {__VLS_StyleScopedClasses['yaml-body']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({});
    (__VLS_ctx.yamlText);
}
else if (__VLS_ctx.contentType === __VLS_ctx.ContentTypeEnum.markdown) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "markdown-body" },
    });
    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.markdownText) }, null, null);
    /** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (__VLS_ctx.text);
}
// @ts-ignore
[contentType, contentType, ContentTypeEnum, ContentTypeEnum, yamlText, markdownText, text,];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};
