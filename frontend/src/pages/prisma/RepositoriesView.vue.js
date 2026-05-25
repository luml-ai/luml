/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../home/codie/.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed, onMounted, inject } from 'vue';
import { useConfirm } from 'primevue';
import { api } from '@/lib/api';
import { usePrismaStore } from '@/stores/prisma';
import { deleteRepositoryConfirmOptions } from '@/lib/primevue/data/confirm';
import RepositoryCard from '@/components/prisma/RepositoryCard.vue';
const store = usePrismaStore();
const confirm = useConfirm();
const repositories = computed(() => store.repositories);
const showNewRepository = inject('showNewRepository');
async function refresh() {
    store.repositories = await api.dataAgent.listRepositories();
}
function openNewRepository() {
    showNewRepository.value = true;
}
function onDeleteRepository(repositoryId, repositoryName) {
    confirm.require(deleteRepositoryConfirmOptions(async () => {
        await api.dataAgent.deleteRepository(repositoryId);
        await refresh();
    }, repositoryName));
}
onMounted(() => {
    refresh();
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "repositories-workspace" },
});
/** @type {__VLS_StyleScopedClasses['repositories-workspace']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "repositories-grid" },
});
/** @type {__VLS_StyleScopedClasses['repositories-grid']} */ ;
for (const [repo] of __VLS_vFor((__VLS_ctx.repositories))) {
    const __VLS_0 = RepositoryCard;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onDelete': {} },
        key: (repo.id),
        type: "default",
        data: (repo),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onDelete': {} },
        key: (repo.id),
        type: "default",
        data: (repo),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ delete: {} },
        { onDelete: (__VLS_ctx.onDeleteRepository) });
    var __VLS_3;
    var __VLS_4;
    // @ts-ignore
    [repositories, onDeleteRepository,];
}
if (__VLS_ctx.repositories.length === 0) {
    const __VLS_7 = RepositoryCard;
    // @ts-ignore
    const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
        ...{ 'onCreateNew': {} },
        type: "create",
    }));
    const __VLS_9 = __VLS_8({
        ...{ 'onCreateNew': {} },
        type: "create",
    }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    let __VLS_12;
    const __VLS_13 = ({ createNew: {} },
        { onCreateNew: (__VLS_ctx.openNewRepository) });
    var __VLS_10;
    var __VLS_11;
}
// @ts-ignore
[repositories, openNewRepository,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
