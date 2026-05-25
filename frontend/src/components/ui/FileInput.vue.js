/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, ref } from 'vue';
import { Download, BadgeCheck, BadgeX } from 'lucide-vue-next';
import { useToast } from 'primevue';
import { incorrectFileTypeErrorToast } from '@/lib/primevue/data/toasts';
const toast = useToast();
const props = defineProps();
const emit = defineEmits();
const dropzoneRef = ref();
const inputRef = ref(null);
const dropzoneActive = ref(false);
const currentState = computed(() => {
    if (props.loading)
        return 'loading';
    else if (props.error)
        return 'error';
    else if (props.file.name && props.file.size)
        return 'success';
    else
        return 'default';
});
const iconComponent = computed(() => {
    switch (currentState.value) {
        case 'success':
            return BadgeCheck;
        case 'error':
            return BadgeX;
        default:
            return Download;
    }
});
const sizeText = computed(() => {
    if (!props.file.size)
        return `0 KB`;
    if (props.file.size < 1024 * 1024)
        return `${(props.file.size / 1024).toFixed(3)} KB`;
    else
        return `${(props.file.size / (1024 * 1024)).toFixed(3)} MB`;
});
function onDragenter() {
    dropzoneActive.value = true;
}
function onDragleave(e) {
    if (dropzoneRef.value && !dropzoneRef.value.contains(e.relatedTarget)) {
        dropzoneActive.value = false;
    }
}
function onDragover() { }
function onDrop(e) {
    dropzoneActive.value = false;
    const file = e.dataTransfer?.files?.[0];
    if (file)
        selectFile(file);
}
function inputChange(e) {
    const target = e.target;
    const file = target.files?.[0];
    if (file)
        selectFile(file);
}
function selectFile(file) {
    if (props.accept && !props.accept.includes(file.type))
        toast.add(incorrectFileTypeErrorToast);
    else
        emit('selectFile', file);
}
function removeFile() {
    emit('removeFile');
    const input = inputRef.value;
    if (input)
        input.value = '';
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
/** @type {__VLS_StyleScopedClasses['dropzone']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon']} */ ;
/** @type {__VLS_StyleScopedClasses['accent']} */ ;
/** @type {__VLS_StyleScopedClasses['dropzone']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onDragenter: (__VLS_ctx.onDragenter) },
    ...{ onDragover: (__VLS_ctx.onDragover) },
    ...{ onDragleave: (__VLS_ctx.onDragleave) },
    ...{ onDrop: (__VLS_ctx.onDrop) },
    ref: "dropzoneRef",
    ...{ class: "dropzone" },
    ...{ class: ({ active: __VLS_ctx.dropzoneActive }) },
});
/** @type {__VLS_StyleScopedClasses['dropzone']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "loading-view" },
    });
    /** @type {__VLS_StyleScopedClasses['loading-view']} */ ;
    let __VLS_0;
    /** @ts-ignore @type { | typeof __VLS_components.progressSpinner | typeof __VLS_components.ProgressSpinner | typeof __VLS_components['progress-spinner']} */
    progressSpinner;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ style: {} },
    }));
    const __VLS_2 = __VLS_1({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    (__VLS_ctx.loadingMessage ? __VLS_ctx.loadingMessage : 'Loading');
}
else {
    const __VLS_5 = (__VLS_ctx.iconComponent);
    // @ts-ignore
    const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
        width: "48",
        height: "48",
        ...{ class: "icon" },
        ...{ class: (__VLS_ctx.currentState) },
    }));
    const __VLS_7 = __VLS_6({
        width: "48",
        height: "48",
        ...{ class: "icon" },
        ...{ class: (__VLS_ctx.currentState) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_6));
    /** @type {__VLS_StyleScopedClasses['icon']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "content" },
    });
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    if (__VLS_ctx.currentState === 'success') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "file-info" },
        });
        /** @type {__VLS_StyleScopedClasses['file-info']} */ ;
        if (__VLS_ctx.successMessageOnly) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
            (__VLS_ctx.successMessageOnly);
            __VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
            if (__VLS_ctx.successRemoveText) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: (__VLS_ctx.removeFile) },
                    type: "button",
                    ...{ class: "link" },
                });
                /** @type {__VLS_StyleScopedClasses['link']} */ ;
                (__VLS_ctx.successRemoveText);
            }
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "file-name" },
            });
            /** @type {__VLS_StyleScopedClasses['file-name']} */ ;
            (__VLS_ctx.file.name);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "file-size" },
            });
            /** @type {__VLS_StyleScopedClasses['file-size']} */ ;
            (__VLS_ctx.sizeText);
            let __VLS_10;
            /** @ts-ignore @type { | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button'] | typeof __VLS_components.dButton | typeof __VLS_components.DButton | typeof __VLS_components['d-button']} */
            dButton;
            // @ts-ignore
            const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
                ...{ 'onClick': {} },
                severity: "danger",
                rounded: true,
                variant: "text",
            }));
            const __VLS_12 = __VLS_11({
                ...{ 'onClick': {} },
                severity: "danger",
                rounded: true,
                variant: "text",
            }, ...__VLS_functionalComponentArgsRest(__VLS_11));
            let __VLS_15;
            const __VLS_16 = ({ click: {} },
                { onClick: (__VLS_ctx.removeFile) });
            const { default: __VLS_17 } = __VLS_13.slots;
            {
                const { icon: __VLS_18 } = __VLS_13.slots;
                let __VLS_19;
                /** @ts-ignore @type { | typeof __VLS_components.trash2 | typeof __VLS_components.Trash2} */
                trash2;
                // @ts-ignore
                const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
                    width: "14",
                    height: "14",
                }));
                const __VLS_21 = __VLS_20({
                    width: "14",
                    height: "14",
                }, ...__VLS_functionalComponentArgsRest(__VLS_20));
                // @ts-ignore
                [onDragenter, onDragover, onDragleave, onDrop, dropzoneActive, loading, loadingMessage, loadingMessage, iconComponent, currentState, currentState, successMessageOnly, successMessageOnly, successRemoveText, successRemoveText, removeFile, removeFile, file, sizeText,];
            }
            // @ts-ignore
            [];
            var __VLS_13;
            var __VLS_14;
        }
    }
    else if (__VLS_ctx.currentState === 'error') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            for: (__VLS_ctx.id),
            ...{ class: "accent" },
        });
        /** @type {__VLS_StyleScopedClasses['accent']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "title" },
        });
        /** @type {__VLS_StyleScopedClasses['title']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "drag-drop-text" },
        });
        /** @type {__VLS_StyleScopedClasses['drag-drop-text']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            for: (__VLS_ctx.id),
            ...{ class: "accent" },
        });
        /** @type {__VLS_StyleScopedClasses['accent']} */ ;
        (__VLS_ctx.uploadText);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "help-text" },
        });
        /** @type {__VLS_StyleScopedClasses['help-text']} */ ;
        (__VLS_ctx.acceptText);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        ...{ onChange: (__VLS_ctx.inputChange) },
        ref: "inputRef",
        id: (__VLS_ctx.id),
        type: "file",
    });
}
// @ts-ignore
[currentState, id, id, id, uploadText, acceptText, inputChange,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
