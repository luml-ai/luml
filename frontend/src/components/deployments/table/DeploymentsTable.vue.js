/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { DataTable, Column, IconField, InputIcon, InputText, Tag, Button } from 'primevue';
import { FilterMatchMode } from '@primevue/core/api';
import { ref } from 'vue';
import { Search, Bolt, TriangleAlert } from 'lucide-vue-next';
import { DeploymentStatusEnum, } from '@/lib/api/deployments/interfaces';
import DeploymentsEditor from '../edit/DeploymentsEditor.vue';
import UiId from '@/components/ui/UiId.vue';
import DeploymentErrorModal from '../error/DeploymentErrorModal.vue';
const __VLS_props = defineProps();
const filters = ref();
const editableDeployment = ref(null);
const error = ref(null);
const initFilters = () => {
    filters.value = {
        global: { value: null, matchMode: FilterMatchMode.CONTAINS },
    };
};
function onSettingsClick(deployment) {
    editableDeployment.value = deployment;
}
initFilters();
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['p-datatable-header']} */ ;
/** @type {__VLS_StyleScopedClasses['p-datatable']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
let __VLS_0;
/** @ts-ignore @type { | typeof __VLS_components.DataTable | typeof __VLS_components.DataTable} */
DataTable;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    value: (__VLS_ctx.data),
    filters: (__VLS_ctx.filters),
}));
const __VLS_2 = __VLS_1({
    value: (__VLS_ctx.data),
    filters: (__VLS_ctx.filters),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
{
    const { header: __VLS_6 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h4, __VLS_intrinsics.h4)({
        ...{ class: "title" },
    });
    /** @type {__VLS_StyleScopedClasses['title']} */ ;
    (__VLS_ctx.data.length);
    let __VLS_7;
    /** @ts-ignore @type { | typeof __VLS_components.IconField | typeof __VLS_components.IconField} */
    IconField;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({}));
    const __VLS_9 = __VLS_8({}, ...__VLS_functionalComponentArgsRest(__VLS_8));
    const { default: __VLS_12 } = __VLS_10.slots;
    let __VLS_13;
    /** @ts-ignore @type { | typeof __VLS_components.InputText} */
    InputText;
    // @ts-ignore
    const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
        modelValue: (__VLS_ctx.filters['global'].value),
        size: "small",
        placeholder: "Search",
    }));
    const __VLS_15 = __VLS_14({
        modelValue: (__VLS_ctx.filters['global'].value),
        size: "small",
        placeholder: "Search",
    }, ...__VLS_functionalComponentArgsRest(__VLS_14));
    let __VLS_18;
    /** @ts-ignore @type { | typeof __VLS_components.InputIcon | typeof __VLS_components.InputIcon} */
    InputIcon;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({}));
    const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
    const { default: __VLS_23 } = __VLS_21.slots;
    let __VLS_24;
    /** @ts-ignore @type { | typeof __VLS_components.Search} */
    Search;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
        size: (12),
    }));
    const __VLS_26 = __VLS_25({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    // @ts-ignore
    [data, data, filters, filters,];
    var __VLS_21;
    // @ts-ignore
    [];
    var __VLS_10;
    // @ts-ignore
    [];
}
{
    const { empty: __VLS_29 } = __VLS_3.slots;
    // @ts-ignore
    [];
}
let __VLS_30;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
    header: "Deployment name",
    field: "name",
}));
const __VLS_32 = __VLS_31({
    header: "Deployment name",
    field: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
const { default: __VLS_35 } = __VLS_33.slots;
{
    const { body: __VLS_36 } = __VLS_33.slots;
    const [{ data }] = __VLS_vSlot(__VLS_36);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell cell--name" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    /** @type {__VLS_StyleScopedClasses['cell--name']} */ ;
    (data.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "id-row" },
    });
    /** @type {__VLS_StyleScopedClasses['id-row']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "id-text" },
    });
    /** @type {__VLS_StyleScopedClasses['id-text']} */ ;
    const __VLS_37 = UiId || UiId;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent1(__VLS_37, new __VLS_37({
        id: (data.id),
        ...{ class: "id-value" },
    }));
    const __VLS_39 = __VLS_38({
        id: (data.id),
        ...{ class: "id-value" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_38));
    /** @type {__VLS_StyleScopedClasses['id-value']} */ ;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_33;
let __VLS_42;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent1(__VLS_42, new __VLS_42({
    header: "Model",
    sortable: true,
    field: "model_artifact_name",
}));
const __VLS_44 = __VLS_43({
    header: "Model",
    sortable: true,
    field: "model_artifact_name",
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
const { default: __VLS_47 } = __VLS_45.slots;
{
    const { body: __VLS_48 } = __VLS_45.slots;
    const [{ data }] = __VLS_vSlot(__VLS_48);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    let __VLS_49;
    /** @ts-ignore @type { | typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
    RouterLink;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent1(__VLS_49, new __VLS_49({
        to: ({
            name: 'artifact',
            params: { collectionId: data.collection_id, artifactId: data.artifact_id },
        }),
        ...{ class: "link" },
    }));
    const __VLS_51 = __VLS_50({
        to: ({
            name: 'artifact',
            params: { collectionId: data.collection_id, artifactId: data.artifact_id },
        }),
        ...{ class: "link" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_50));
    /** @type {__VLS_StyleScopedClasses['link']} */ ;
    const { default: __VLS_54 } = __VLS_52.slots;
    (data.artifact_name);
    // @ts-ignore
    [];
    var __VLS_52;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_45;
let __VLS_55;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_56 = __VLS_asFunctionalComponent1(__VLS_55, new __VLS_55({
    header: "Satellite",
    sortable: true,
    field: "satellite_name",
}));
const __VLS_57 = __VLS_56({
    header: "Satellite",
    sortable: true,
    field: "satellite_name",
}, ...__VLS_functionalComponentArgsRest(__VLS_56));
const { default: __VLS_60 } = __VLS_58.slots;
{
    const { body: __VLS_61 } = __VLS_58.slots;
    const [{ data }] = __VLS_vSlot(__VLS_61);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (data.satellite_name);
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_58;
let __VLS_62;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent1(__VLS_62, new __VLS_62({
    header: "Status",
    sortable: true,
    field: "status",
}));
const __VLS_64 = __VLS_63({
    header: "Status",
    sortable: true,
    field: "status",
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
const { default: __VLS_67 } = __VLS_65.slots;
{
    const { body: __VLS_68 } = __VLS_65.slots;
    const [{ data }] = __VLS_vSlot(__VLS_68);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    if (data.status === __VLS_ctx.DeploymentStatusEnum.active) {
        let __VLS_69;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_70 = __VLS_asFunctionalComponent1(__VLS_69, new __VLS_69({
            severity: "success",
        }));
        const __VLS_71 = __VLS_70({
            severity: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_70));
        const { default: __VLS_74 } = __VLS_72.slots;
        // @ts-ignore
        [DeploymentStatusEnum,];
        var __VLS_72;
    }
    if (data.status === __VLS_ctx.DeploymentStatusEnum.pending) {
        let __VLS_75;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_76 = __VLS_asFunctionalComponent1(__VLS_75, new __VLS_75({
            severity: "warn",
        }));
        const __VLS_77 = __VLS_76({
            severity: "warn",
        }, ...__VLS_functionalComponentArgsRest(__VLS_76));
        const { default: __VLS_80 } = __VLS_78.slots;
        // @ts-ignore
        [DeploymentStatusEnum,];
        var __VLS_78;
    }
    if (data.status === __VLS_ctx.DeploymentStatusEnum.failed) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "tag-with-icon" },
        });
        /** @type {__VLS_StyleScopedClasses['tag-with-icon']} */ ;
        let __VLS_81;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_82 = __VLS_asFunctionalComponent1(__VLS_81, new __VLS_81({
            severity: "danger",
        }));
        const __VLS_83 = __VLS_82({
            severity: "danger",
        }, ...__VLS_functionalComponentArgsRest(__VLS_82));
        const { default: __VLS_86 } = __VLS_84.slots;
        // @ts-ignore
        [DeploymentStatusEnum,];
        var __VLS_84;
        if (data.error_message) {
            let __VLS_87;
            /** @ts-ignore @type { | typeof __VLS_components.TriangleAlert} */
            TriangleAlert;
            // @ts-ignore
            const __VLS_88 = __VLS_asFunctionalComponent1(__VLS_87, new __VLS_87({
                ...{ 'onClick': {} },
                size: (14),
                color: "var(--p-tag-danger-color)",
            }));
            const __VLS_89 = __VLS_88({
                ...{ 'onClick': {} },
                size: (14),
                color: "var(--p-tag-danger-color)",
            }, ...__VLS_functionalComponentArgsRest(__VLS_88));
            let __VLS_92;
            const __VLS_93 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!(data.status === __VLS_ctx.DeploymentStatusEnum.failed))
                            return;
                        if (!(data.error_message))
                            return;
                        __VLS_ctx.error = data.error_message;
                        // @ts-ignore
                        [error,];
                    } });
            __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Show error') }, null, null);
            var __VLS_90;
            var __VLS_91;
        }
    }
    if (data.status === __VLS_ctx.DeploymentStatusEnum.not_responding) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "tag-with-icon" },
        });
        /** @type {__VLS_StyleScopedClasses['tag-with-icon']} */ ;
        let __VLS_94;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_95 = __VLS_asFunctionalComponent1(__VLS_94, new __VLS_94({
            severity: "danger",
        }));
        const __VLS_96 = __VLS_95({
            severity: "danger",
        }, ...__VLS_functionalComponentArgsRest(__VLS_95));
        const { default: __VLS_99 } = __VLS_97.slots;
        // @ts-ignore
        [DeploymentStatusEnum, vTooltip,];
        var __VLS_97;
        if (data.error_message) {
            let __VLS_100;
            /** @ts-ignore @type { | typeof __VLS_components.TriangleAlert} */
            TriangleAlert;
            // @ts-ignore
            const __VLS_101 = __VLS_asFunctionalComponent1(__VLS_100, new __VLS_100({
                ...{ 'onClick': {} },
                size: (14),
                color: "var(--p-tag-danger-color)",
            }));
            const __VLS_102 = __VLS_101({
                ...{ 'onClick': {} },
                size: (14),
                color: "var(--p-tag-danger-color)",
            }, ...__VLS_functionalComponentArgsRest(__VLS_101));
            let __VLS_105;
            const __VLS_106 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!(data.status === __VLS_ctx.DeploymentStatusEnum.not_responding))
                            return;
                        if (!(data.error_message))
                            return;
                        __VLS_ctx.error = data.error_message;
                        // @ts-ignore
                        [error,];
                    } });
            __VLS_asFunctionalDirective(__VLS_directives.vTooltip, {})(null, { ...__VLS_directiveBindingRestFields, modifiers: { top: true, }, value: ('Show error') }, null, null);
            var __VLS_103;
            var __VLS_104;
        }
    }
    if (data.status === __VLS_ctx.DeploymentStatusEnum.deletion_pending) {
        let __VLS_107;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_108 = __VLS_asFunctionalComponent1(__VLS_107, new __VLS_107({
            severity: "warn",
        }));
        const __VLS_109 = __VLS_108({
            severity: "warn",
        }, ...__VLS_functionalComponentArgsRest(__VLS_108));
        const { default: __VLS_112 } = __VLS_110.slots;
        // @ts-ignore
        [DeploymentStatusEnum, vTooltip,];
        var __VLS_110;
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_65;
let __VLS_113;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent1(__VLS_113, new __VLS_113({
    header: "Creation time",
    sortable: true,
    field: "created_at",
}));
const __VLS_115 = __VLS_114({
    header: "Creation time",
    sortable: true,
    field: "created_at",
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
const { default: __VLS_118 } = __VLS_116.slots;
{
    const { body: __VLS_119 } = __VLS_116.slots;
    const [{ data }] = __VLS_vSlot(__VLS_119);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (new Date(data.created_at).toLocaleString());
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_116;
let __VLS_120;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent1(__VLS_120, new __VLS_120({
    header: "Created by",
    sortable: true,
    field: "created_by_user",
}));
const __VLS_122 = __VLS_121({
    header: "Created by",
    sortable: true,
    field: "created_by_user",
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
const { default: __VLS_125 } = __VLS_123.slots;
{
    const { body: __VLS_126 } = __VLS_123.slots;
    const [{ data }] = __VLS_vSlot(__VLS_126);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    (data.created_by_user);
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_123;
let __VLS_127;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_128 = __VLS_asFunctionalComponent1(__VLS_127, new __VLS_127({
    header: "Tags",
    field: "tags",
}));
const __VLS_129 = __VLS_128({
    header: "Tags",
    field: "tags",
}, ...__VLS_functionalComponentArgsRest(__VLS_128));
const { default: __VLS_132 } = __VLS_130.slots;
{
    const { body: __VLS_133 } = __VLS_130.slots;
    const [{ data }] = __VLS_vSlot(__VLS_133);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "tags" },
    });
    /** @type {__VLS_StyleScopedClasses['tags']} */ ;
    for (const [tag, index] of __VLS_vFor((data.tags))) {
        let __VLS_134;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_135 = __VLS_asFunctionalComponent1(__VLS_134, new __VLS_134({
            key: (index),
        }));
        const __VLS_136 = __VLS_135({
            key: (index),
        }, ...__VLS_functionalComponentArgsRest(__VLS_135));
        const { default: __VLS_139 } = __VLS_137.slots;
        (tag);
        // @ts-ignore
        [];
        var __VLS_137;
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_130;
let __VLS_140;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent1(__VLS_140, new __VLS_140({
    header: "Schema",
    field: "schema",
}));
const __VLS_142 = __VLS_141({
    header: "Schema",
    field: "schema",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
const { default: __VLS_145 } = __VLS_143.slots;
{
    const { body: __VLS_146 } = __VLS_143.slots;
    const [{ data }] = __VLS_vSlot(__VLS_146);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "cell" },
    });
    /** @type {__VLS_StyleScopedClasses['cell']} */ ;
    if (data.schemas && !!Object.keys(data.schemas).length) {
        let __VLS_147;
        /** @ts-ignore @type { | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link'] | typeof __VLS_components.routerLink | typeof __VLS_components.RouterLink | typeof __VLS_components['router-link']} */
        routerLink;
        // @ts-ignore
        const __VLS_148 = __VLS_asFunctionalComponent1(__VLS_147, new __VLS_147({
            to: ({ name: 'deployment-schema', params: { deploymentId: data.id } }),
            ...{ class: "link" },
        }));
        const __VLS_149 = __VLS_148({
            to: ({ name: 'deployment-schema', params: { deploymentId: data.id } }),
            ...{ class: "link" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_148));
        /** @type {__VLS_StyleScopedClasses['link']} */ ;
        const { default: __VLS_152 } = __VLS_150.slots;
        // @ts-ignore
        [];
        var __VLS_150;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_143;
let __VLS_153;
/** @ts-ignore @type { | typeof __VLS_components.Column | typeof __VLS_components.Column} */
Column;
// @ts-ignore
const __VLS_154 = __VLS_asFunctionalComponent1(__VLS_153, new __VLS_153({}));
const __VLS_155 = __VLS_154({}, ...__VLS_functionalComponentArgsRest(__VLS_154));
const { default: __VLS_158 } = __VLS_156.slots;
{
    const { body: __VLS_159 } = __VLS_156.slots;
    const [{ data }] = __VLS_vSlot(__VLS_159);
    let __VLS_160;
    /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
    Button;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent1(__VLS_160, new __VLS_160({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
    }));
    const __VLS_162 = __VLS_161({
        ...{ 'onClick': {} },
        severity: "secondary",
        variant: "text",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    let __VLS_165;
    const __VLS_166 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.onSettingsClick(data);
                // @ts-ignore
                [onSettingsClick,];
            } });
    const { default: __VLS_167 } = __VLS_163.slots;
    {
        const { icon: __VLS_168 } = __VLS_163.slots;
        let __VLS_169;
        /** @ts-ignore @type { | typeof __VLS_components.Bolt | typeof __VLS_components.Bolt} */
        Bolt;
        // @ts-ignore
        const __VLS_170 = __VLS_asFunctionalComponent1(__VLS_169, new __VLS_169({
            size: (14),
        }));
        const __VLS_171 = __VLS_170({
            size: (14),
        }, ...__VLS_functionalComponentArgsRest(__VLS_170));
        // @ts-ignore
        [];
    }
    // @ts-ignore
    [];
    var __VLS_163;
    var __VLS_164;
    // @ts-ignore
    [];
}
// @ts-ignore
[];
var __VLS_156;
// @ts-ignore
[];
var __VLS_3;
if (__VLS_ctx.editableDeployment) {
    const __VLS_174 = DeploymentsEditor || DeploymentsEditor;
    // @ts-ignore
    const __VLS_175 = __VLS_asFunctionalComponent1(__VLS_174, new __VLS_174({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.editableDeployment),
        data: (__VLS_ctx.editableDeployment),
    }));
    const __VLS_176 = __VLS_175({
        ...{ 'onUpdate:visible': {} },
        visible: (!!__VLS_ctx.editableDeployment),
        data: (__VLS_ctx.editableDeployment),
    }, ...__VLS_functionalComponentArgsRest(__VLS_175));
    let __VLS_179;
    const __VLS_180 = ({ 'update:visible': {} },
        { 'onUpdate:visible': (...[$event]) => {
                if (!(__VLS_ctx.editableDeployment))
                    return;
                __VLS_ctx.editableDeployment = null;
                // @ts-ignore
                [editableDeployment, editableDeployment, editableDeployment, editableDeployment,];
            } });
    var __VLS_177;
    var __VLS_178;
}
const __VLS_181 = DeploymentErrorModal || DeploymentErrorModal;
// @ts-ignore
const __VLS_182 = __VLS_asFunctionalComponent1(__VLS_181, new __VLS_181({
    ...{ 'onUpdate:visible': {} },
    error: (__VLS_ctx.error?.error || ''),
    reason: (__VLS_ctx.error?.reason || ''),
    visible: (!!__VLS_ctx.error),
}));
const __VLS_183 = __VLS_182({
    ...{ 'onUpdate:visible': {} },
    error: (__VLS_ctx.error?.error || ''),
    reason: (__VLS_ctx.error?.reason || ''),
    visible: (!!__VLS_ctx.error),
}, ...__VLS_functionalComponentArgsRest(__VLS_182));
let __VLS_186;
const __VLS_187 = ({ 'update:visible': {} },
    { 'onUpdate:visible': (...[$event]) => {
            __VLS_ctx.error = null;
            // @ts-ignore
            [error, error, error, error,];
        } });
var __VLS_184;
var __VLS_185;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
