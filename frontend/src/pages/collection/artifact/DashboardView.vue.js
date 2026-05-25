/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
import { Tag, Button } from 'primevue';
import { ArtifactStatusEnum } from '@/lib/api/artifacts/interfaces';
import { getSizeText } from '@/helpers/helpers';
import { ref } from 'vue';
import { useArtifactsStore } from '@/stores/artifacts';
import ModelManifestModal from '@/components/model/ModelManifestModal.vue';
const artifactsStore = useArtifactsStore();
const manifestVisible = ref(false);
const statusSeverity = computed(() => {
    if (!artifactsStore.currentArtifact)
        return null;
    else if ([ArtifactStatusEnum.deletion_failed, ArtifactStatusEnum.upload_failed].includes(artifactsStore.currentArtifact.status))
        return 'danger';
    else if ([ArtifactStatusEnum.pending_deletion, ArtifactStatusEnum.pending_upload].includes(artifactsStore.currentArtifact.status))
        return 'warn';
    else if (artifactsStore.currentArtifact.status === ArtifactStatusEnum.uploaded)
        return 'success';
});
function showManifest() {
    manifestVisible.value = true;
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.artifactsStore.currentArtifact) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details" },
    });
    /** @type {__VLS_StyleScopedClasses['details']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__part" },
    });
    /** @type {__VLS_StyleScopedClasses['details__part']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    (__VLS_ctx.artifactsStore.currentArtifact.id);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    (__VLS_ctx.artifactsStore.currentArtifact.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    if (__VLS_ctx.statusSeverity) {
        let __VLS_0;
        /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
        Tag;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
            severity: (__VLS_ctx.statusSeverity),
            value: (__VLS_ctx.artifactsStore.currentArtifact.status),
            ...{ class: "tag" },
        }));
        const __VLS_2 = __VLS_1({
            severity: (__VLS_ctx.statusSeverity),
            value: (__VLS_ctx.artifactsStore.currentArtifact.status),
            ...{ class: "tag" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        /** @type {__VLS_StyleScopedClasses['tag']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    (new Date(__VLS_ctx.artifactsStore.currentArtifact.created_at).toLocaleString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    (__VLS_ctx.artifactsStore.currentArtifact.description || '-');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__tags" },
    });
    /** @type {__VLS_StyleScopedClasses['details__tags']} */ ;
    if (__VLS_ctx.artifactsStore.currentArtifact.tags?.length) {
        for (const [tag] of __VLS_vFor((__VLS_ctx.artifactsStore.currentArtifact.tags))) {
            let __VLS_5;
            /** @ts-ignore @type { | typeof __VLS_components.Tag | typeof __VLS_components.Tag} */
            Tag;
            // @ts-ignore
            const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
                value: (tag),
                ...{ class: "tag" },
            }));
            const __VLS_7 = __VLS_6({
                value: (tag),
                ...{ class: "tag" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_6));
            /** @type {__VLS_StyleScopedClasses['tag']} */ ;
            // @ts-ignore
            [artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, artifactsStore, statusSeverity, statusSeverity,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    if (__VLS_ctx.artifactsStore.currentArtifact?.manifest) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__item" },
            ...{ style: {} },
        });
        /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__label" },
        });
        /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__value" },
        });
        /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
        let __VLS_10;
        /** @ts-ignore @type { | typeof __VLS_components.Button | typeof __VLS_components.Button} */
        Button;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
            ...{ 'onClick': {} },
            variant: "text",
            size: "small",
            severity: "secondary",
        }));
        const __VLS_12 = __VLS_11({
            ...{ 'onClick': {} },
            variant: "text",
            size: "small",
            severity: "secondary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        let __VLS_15;
        const __VLS_16 = ({ click: {} },
            { onClick: (__VLS_ctx.showManifest) });
        const { default: __VLS_17 } = __VLS_13.slots;
        // @ts-ignore
        [artifactsStore, showManifest,];
        var __VLS_13;
        var __VLS_14;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__part" },
    });
    /** @type {__VLS_StyleScopedClasses['details__part']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__item" },
    });
    /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__label" },
    });
    /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "details__value" },
    });
    /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
    (__VLS_ctx.getSizeText(__VLS_ctx.artifactsStore.currentArtifact.size));
    for (const [metric] of __VLS_vFor((Object.entries(__VLS_ctx.artifactsStore.currentArtifact.extra_values)))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__item" },
        });
        /** @type {__VLS_StyleScopedClasses['details__item']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__label" },
        });
        /** @type {__VLS_StyleScopedClasses['details__label']} */ ;
        (metric[0]);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "details__value" },
        });
        /** @type {__VLS_StyleScopedClasses['details__value']} */ ;
        (metric[1]);
        // @ts-ignore
        [artifactsStore, artifactsStore, getSizeText,];
    }
}
if (__VLS_ctx.artifactsStore.currentArtifact?.manifest) {
    const __VLS_18 = ModelManifestModal || ModelManifestModal;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent1(__VLS_18, new __VLS_18({
        visible: (__VLS_ctx.manifestVisible),
        manifest: (__VLS_ctx.artifactsStore.currentArtifact.manifest),
    }));
    const __VLS_20 = __VLS_19({
        visible: (__VLS_ctx.manifestVisible),
        manifest: (__VLS_ctx.artifactsStore.currentArtifact.manifest),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
}
// @ts-ignore
[artifactsStore, artifactsStore, manifestVisible,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
