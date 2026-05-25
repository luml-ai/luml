/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { InputText, Button } from 'primevue';
import { FolderOpen, ArrowUp, Folder, Github, Check } from 'lucide-vue-next';
import { api } from '@/lib/api';
const model = defineModel({ default: '' });
const open = ref(false);
const loading = ref(false);
const current = ref('');
const parent = ref(null);
const dirs = ref([]);
const isGit = ref(false);
const error = ref('');
async function browse(path) {
    error.value = '';
    loading.value = true;
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        const result = await api.dataAgent.browsePath(path, { signal: controller.signal });
        clearTimeout(timeout);
        current.value = result.current;
        parent.value = result.parent;
        dirs.value = result.dirs;
        isGit.value = result.is_git;
    }
    catch (e) {
        if (e?.code === 'ERR_CANCELED' || e?.name === 'AbortError') {
            error.value = 'Request timed out — is the agent server running?';
        }
        else {
            error.value = e?.response?.data?.detail ?? 'Failed to browse';
        }
    }
    finally {
        loading.value = false;
    }
}
function toggle() {
    if (open.value) {
        open.value = false;
        return;
    }
    open.value = true;
    browse(model.value || undefined);
}
function selectDir(path) {
    model.value = path;
    open.value = false;
}
async function navigateTo(path) {
    await browse(path);
}
const __VLS_defaultModels = {
    'modelValue': '',
};
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
/** @type {__VLS_StyleScopedClasses['browse-item']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "folder-picker" },
});
/** @type {__VLS_StyleScopedClasses['folder-picker']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "input-row" },
});
/** @type {__VLS_StyleScopedClasses['input-row']} */ ;
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.InputText} */
InputText;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    modelValue: (__VLS_ctx.model),
    readonly: true,
    placeholder: "/home/user/repo",
    ...{ class: "path-input" },
}));
const __VLS_2 = __VLS_1({
    modelValue: (__VLS_ctx.model),
    readonly: true,
    placeholder: "/home/user/repo",
    ...{ class: "path-input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['path-input']} */ ;
let __VLS_5;
/** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
Button;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    ...{ 'onClick': {} },
    severity: "secondary",
    size: "small",
    ...{ class: "browse-btn" },
}));
const __VLS_7 = __VLS_6({
    ...{ 'onClick': {} },
    severity: "secondary",
    size: "small",
    ...{ class: "browse-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
let __VLS_10;
const __VLS_11 = ({ click: {} },
    { onClick: (__VLS_ctx.toggle) });
/** @type {__VLS_StyleScopedClasses['browse-btn']} */ ;
const { default: __VLS_12 } = __VLS_8.slots;
let __VLS_13;
/** @ts-ignore @type { | typeof __VLS_components.FolderOpen} */
FolderOpen;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    size: (14),
}));
const __VLS_15 = __VLS_14({
    size: (14),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
// @ts-ignore
[model, toggle,];
var __VLS_8;
var __VLS_9;
if (__VLS_ctx.open) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "browse-panel" },
    });
    /** @type {__VLS_StyleScopedClasses['browse-panel']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "browse-header" },
    });
    /** @type {__VLS_StyleScopedClasses['browse-header']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "browse-path" },
    });
    /** @type {__VLS_StyleScopedClasses['browse-path']} */ ;
    (__VLS_ctx.current || 'Loading...');
    if (__VLS_ctx.isGit) {
        let __VLS_18;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_20 = __VLS_19({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        let __VLS_23;
        const __VLS_24 = ({ click: {} },
            { onClick: (...[$event]) => {
                    if (!(__VLS_ctx.open))
                        return;
                    if (!(__VLS_ctx.isGit))
                        return;
                    __VLS_ctx.selectDir(__VLS_ctx.current);
                    // @ts-ignore
                    [open, current, current, isGit, selectDir,];
                } });
        const { default: __VLS_25 } = __VLS_21.slots;
        let __VLS_26;
        /** @ts-ignore @type { | typeof __VLS_components.Check} */
        Check;
        // @ts-ignore
        const __VLS_27 = __VLS_asFunctionalComponent1(__VLS_26, new __VLS_26({
            size: (14),
        }));
        const __VLS_28 = __VLS_27({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_27));
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        // @ts-ignore
        [];
        var __VLS_21;
        var __VLS_22;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "browse-list" },
    });
    /** @type {__VLS_StyleScopedClasses['browse-list']} */ ;
    if (__VLS_ctx.loading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "browse-empty" },
        });
        /** @type {__VLS_StyleScopedClasses['browse-empty']} */ ;
    }
    else {
        if (__VLS_ctx.parent != null) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.open))
                            return;
                        if (!!(__VLS_ctx.loading))
                            return;
                        if (!(__VLS_ctx.parent != null))
                            return;
                        __VLS_ctx.navigateTo(__VLS_ctx.parent);
                        // @ts-ignore
                        [loading, parent, parent, navigateTo,];
                    } },
                ...{ class: "browse-item browse-item--parent" },
            });
            /** @type {__VLS_StyleScopedClasses['browse-item']} */ ;
            /** @type {__VLS_StyleScopedClasses['browse-item--parent']} */ ;
            let __VLS_31;
            /** @ts-ignore @type { | typeof __VLS_components.ArrowUp} */
            ArrowUp;
            // @ts-ignore
            const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
                size: (14),
            }));
            const __VLS_33 = __VLS_32({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_32));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        }
        for (const [dir] of __VLS_vFor((__VLS_ctx.dirs))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.open))
                            return;
                        if (!!(__VLS_ctx.loading))
                            return;
                        __VLS_ctx.navigateTo(dir.path);
                        // @ts-ignore
                        [navigateTo, dirs,];
                    } },
                key: (dir.path),
                ...{ class: "browse-item" },
            });
            /** @type {__VLS_StyleScopedClasses['browse-item']} */ ;
            const __VLS_36 = (dir.is_git ? __VLS_ctx.Github : __VLS_ctx.Folder);
            // @ts-ignore
            const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
                size: (14),
            }));
            const __VLS_38 = __VLS_37({
                size: (14),
            }, ...__VLS_functionalComponentArgsRest(__VLS_37));
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "dir-name" },
            });
            /** @type {__VLS_StyleScopedClasses['dir-name']} */ ;
            (dir.name);
            if (dir.is_git) {
                let __VLS_41;
                /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
                Button;
                // @ts-ignore
                const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
                    ...{ 'onClick': {} },
                    size: "small",
                    ...{ class: "select-btn" },
                }));
                const __VLS_43 = __VLS_42({
                    ...{ 'onClick': {} },
                    size: "small",
                    ...{ class: "select-btn" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_42));
                let __VLS_46;
                const __VLS_47 = ({ click: {} },
                    { onClick: (...[$event]) => {
                            if (!(__VLS_ctx.open))
                                return;
                            if (!!(__VLS_ctx.loading))
                                return;
                            if (!(dir.is_git))
                                return;
                            __VLS_ctx.selectDir(dir.path);
                            // @ts-ignore
                            [selectDir, Github, Folder,];
                        } });
                /** @type {__VLS_StyleScopedClasses['select-btn']} */ ;
                const { default: __VLS_48 } = __VLS_44.slots;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
                // @ts-ignore
                [];
                var __VLS_44;
                var __VLS_45;
            }
            // @ts-ignore
            [];
        }
        if (__VLS_ctx.dirs.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "browse-empty" },
            });
            /** @type {__VLS_StyleScopedClasses['browse-empty']} */ ;
        }
    }
    if (__VLS_ctx.error) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "browse-error" },
        });
        /** @type {__VLS_StyleScopedClasses['browse-error']} */ ;
        (__VLS_ctx.error);
    }
}
// @ts-ignore
[dirs, error, error,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
