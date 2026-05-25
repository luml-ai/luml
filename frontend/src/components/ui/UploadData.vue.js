/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import CSVIcon from '@/assets/img/icons/csv.svg';
import FileInput from '@/components/ui/FileInput.vue';
const emit = defineEmits();
const props = defineProps();
const hasError = computed(() => {
    const errors = props.errors;
    if (!errors)
        return false;
    for (const key in errors) {
        if (errors[key])
            return true;
    }
    return false;
});
async function selectSample() {
    const fileUrl = `/data/${props.sampleFileName}`;
    const response = await fetch(fileUrl);
    const text = await response.text();
    const file = new File([text], props.sampleFileName, { type: 'text/csv' });
    if (file)
        emit('selectFile', file);
}
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
/** @type {__VLS_StyleScopedClasses['area']} */ ;
/** @type {__VLS_StyleScopedClasses['info']} */ ;
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['info']} */ ;
/** @type {__VLS_StyleScopedClasses['area']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "wrapper" },
});
/** @type {__VLS_StyleScopedClasses['wrapper']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "headings" },
});
/** @type {__VLS_StyleScopedClasses['headings']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "main-title" },
});
/** @type {__VLS_StyleScopedClasses['main-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "sub-title" },
});
/** @type {__VLS_StyleScopedClasses['sub-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "area" },
});
/** @type {__VLS_StyleScopedClasses['area']} */ ;
const __VLS_0 = FileInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "table",
    file: __VLS_ctx.file,
    error: (__VLS_ctx.hasError),
    accept: (['text/csv']),
    acceptText: "Supports CSV file format",
    uploadText: "upload CSV",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSelectFile': {} },
    ...{ 'onRemoveFile': {} },
    id: "table",
    file: __VLS_ctx.file,
    error: (__VLS_ctx.hasError),
    accept: (['text/csv']),
    acceptText: "Supports CSV file format",
    uploadText: "upload CSV",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
const __VLS_6 = ({ selectFile: {} },
    { onSelectFile: ((e) => __VLS_ctx.$emit('selectFile', e)) });
const __VLS_7 = ({ removeFile: {} },
    { onRemoveFile: (...[$event]) => {
            __VLS_ctx.$emit('removeFile');
            // @ts-ignore
            [file, hasError, $emit, $emit,];
        } });
var __VLS_3;
var __VLS_4;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "info-title" },
});
/** @type {__VLS_StyleScopedClasses['info-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
    ...{ class: "info-list" },
});
/** @type {__VLS_StyleScopedClasses['info-list']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item-body" },
});
/** @type {__VLS_StyleScopedClasses['info-item-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
if (__VLS_ctx.isTableExist) {
    if (__VLS_ctx.errors.size) {
        let __VLS_8;
        /** @ts-ignore @type { | typeof __VLS_components.x | typeof __VLS_components.X} */
        x;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }));
        const __VLS_10 = __VLS_9({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_9));
        /** @type {__VLS_StyleScopedClasses['danger']} */ ;
    }
    if (!__VLS_ctx.errors.size) {
        let __VLS_13;
        /** @ts-ignore @type { | typeof __VLS_components.check | typeof __VLS_components.Check} */
        check;
        // @ts-ignore
        const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }));
        const __VLS_15 = __VLS_14({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_14));
        /** @type {__VLS_StyleScopedClasses['success']} */ ;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item-body" },
});
/** @type {__VLS_StyleScopedClasses['info-item-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.minColumnsCount);
if (__VLS_ctx.isTableExist) {
    if (__VLS_ctx.errors.columns) {
        let __VLS_18;
        /** @ts-ignore @type { | typeof __VLS_components.x | typeof __VLS_components.X} */
        x;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }));
        const __VLS_20 = __VLS_19({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        /** @type {__VLS_StyleScopedClasses['danger']} */ ;
    }
    if (!__VLS_ctx.errors.columns) {
        let __VLS_23;
        /** @ts-ignore @type { | typeof __VLS_components.check | typeof __VLS_components.Check} */
        check;
        // @ts-ignore
        const __VLS_24 = __VLS_asFunctionalComponent1(__VLS_23, new __VLS_23({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }));
        const __VLS_25 = __VLS_24({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_24));
        /** @type {__VLS_StyleScopedClasses['success']} */ ;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
    ...{ class: "info-item" },
});
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info-item-body" },
});
/** @type {__VLS_StyleScopedClasses['info-item-body']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
(__VLS_ctx.minRowsCount);
if (__VLS_ctx.isTableExist) {
    if (__VLS_ctx.errors.rows) {
        let __VLS_28;
        /** @ts-ignore @type { | typeof __VLS_components.x | typeof __VLS_components.X} */
        x;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent1(__VLS_28, new __VLS_28({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }));
        const __VLS_30 = __VLS_29({
            width: "20",
            height: "20",
            ...{ class: "danger" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        /** @type {__VLS_StyleScopedClasses['danger']} */ ;
    }
    if (!__VLS_ctx.errors.rows) {
        let __VLS_33;
        /** @ts-ignore @type { | typeof __VLS_components.check | typeof __VLS_components.Check} */
        check;
        // @ts-ignore
        const __VLS_34 = __VLS_asFunctionalComponent1(__VLS_33, new __VLS_33({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }));
        const __VLS_35 = __VLS_34({
            width: "20",
            height: "20",
            ...{ class: "success" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_34));
        /** @type {__VLS_StyleScopedClasses['success']} */ ;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "middle-divider" },
});
/** @type {__VLS_StyleScopedClasses['middle-divider']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "empty" },
});
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sample" },
});
/** @type {__VLS_StyleScopedClasses['sample']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sample-title" },
});
/** @type {__VLS_StyleScopedClasses['sample-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.img)({
    src: (__VLS_ctx.CSVIcon),
    alt: "CSV File",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "sample-text" },
});
/** @type {__VLS_StyleScopedClasses['sample-text']} */ ;
let __VLS_38;
/** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
dButton;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent1(__VLS_38, new __VLS_38({
    ...{ 'onClick': {} },
    label: "use sample",
}));
const __VLS_40 = __VLS_39({
    ...{ 'onClick': {} },
    label: "use sample",
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
let __VLS_43;
const __VLS_44 = ({ click: {} },
    { onClick: (__VLS_ctx.selectSample) });
var __VLS_41;
var __VLS_42;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "info" },
});
/** @type {__VLS_StyleScopedClasses['info']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "info-title" },
});
/** @type {__VLS_StyleScopedClasses['info-title']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
    ...{ class: "info-list" },
});
/** @type {__VLS_StyleScopedClasses['info-list']} */ ;
for (const [resource] of __VLS_vFor((__VLS_ctx.resources))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "info-item" },
    });
    /** @type {__VLS_StyleScopedClasses['info-item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
        href: (resource.link),
        target: "_blank",
        ...{ class: "info-item-body link" },
    });
    /** @type {__VLS_StyleScopedClasses['info-item-body']} */ ;
    /** @type {__VLS_StyleScopedClasses['link']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (resource.label);
    let __VLS_45;
    /** @ts-ignore @type { | typeof __VLS_components.externalLink | typeof __VLS_components.ExternalLink | typeof __VLS_components['external-link']} */
    externalLink;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent1(__VLS_45, new __VLS_45({
        width: "14",
        height: "14",
        ...{ class: "link-icon" },
    }));
    const __VLS_47 = __VLS_46({
        width: "14",
        height: "14",
        ...{ class: "link-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    /** @type {__VLS_StyleScopedClasses['link-icon']} */ ;
    // @ts-ignore
    [isTableExist, isTableExist, isTableExist, errors, errors, errors, errors, errors, errors, minColumnsCount, minRowsCount, CSVIcon, selectSample, resources,];
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
