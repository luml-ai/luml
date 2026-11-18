<template>
  <MainTemplate>
    <div>
      <HomeTabs active="workspaces" class="tabs" />
      <div>
        <div class="heading">
          <div class="heading-row">
            <div class="heading-title">
              <span>Notebooks</span>
              <UiPreviewBadge />
            </div>
            <OpenFlowsSummary :open-flows="openFlows" :totals="openFlowsTotals" />
          </div>
          <WorkspacePath :directory="directory" />
        </div>
        <div class="content" :class="{ 'content-split': viewer }">
          <div class="listing">
            <WorkspaceFolder
              :items="items"
              :open-flows="openFlows"
              :loading="loading"
              :menu-open-id="menuOpenId"
              :renaming-id="renamingId"
              :rename-value="renameValue"
              :selected-id="viewer?.file.path ?? null"
              class="folder"
            />
            <!-- product:PROP-004 B-14: new folder and new file next to "New notebook". -->
            <div v-if="!loading" class="create-row">
              <CreateNewFlow />
              <Button variant="text">
                <FolderPlus :size="16" />
                <span> New folder</span>
              </Button>
              <Button variant="text">
                <FilePlus :size="16" />
                <span> New file</span>
              </Button>
            </div>
          </div>
          <WorkspaceFileViewer
            v-if="viewer"
            :file="viewer.file"
            :text-content="viewer.textContent"
            :pretty-content="viewer.prettyContent"
            :view="viewer.view"
            :table="viewer.table"
            :image="viewer.image"
            :svg="viewer.svg"
            :media="viewer.media"
            :pdf="viewer.pdf"
            :html="viewer.html"
            :preview-state="viewer.previewState"
            :luml="viewer.luml"
            :editing="viewer.editing"
            :conflict="viewer.conflict"
            :agent="viewer.agent"
          />
        </div>
      </div>
    </div>

    <!-- B-14 dialogs. Same 600px dialog as "Create new notebook". -->
    <LumlflowDialog
      v-if="dialog === 'new-folder' || dialog === 'new-file'"
      layout="create-flow"
      visible
      :header="dialog === 'new-folder' ? 'CREATE NEW FOLDER' : 'CREATE NEW FILE'"
      dismissable-mask
    >
      <form id="create-entry-form">
        <label for="entry-name" class="label required">Name</label>
        <InputText
          id="entry-name"
          :model-value="dialogName"
          fluid
          :placeholder="dialog === 'new-folder' ? 'Name your folder' : 'Name your file, e.g. notes.md'"
          :invalid="!!dialogError"
        />
        <Message v-if="dialogError" severity="error" size="small" variant="simple">{{ dialogError }}</Message>
      </form>
      <template #footer>
        <Button
          type="submit"
          :label="dialog === 'new-folder' ? 'Create folder' : 'Create file'"
          :disabled="!dialogName"
          form="create-entry-form"
          fluid
          rounded
        />
      </template>
    </LumlflowDialog>

    <LumlflowDialog v-if="dialog === 'move'" layout="create-flow" visible header="MOVE TO" dismissable-mask>
      <form id="move-form">
        <p class="move-subject">
          Move <strong>{{ dialogTarget }}</strong> to:
        </p>
        <Select :model-value="moveTo" :options="moveFolders" fluid placeholder="Choose a folder" />
      </form>
      <template #footer>
        <Button type="submit" label="Move" :disabled="!moveTo" form="move-form" fluid rounded />
      </template>
    </LumlflowDialog>

    <LumlflowConfirmDialog
      v-if="dialog === 'delete-file'"
      :header="`Delete ${dialogTarget}?`"
      message="This action is permanent and cannot be undone. Cells that read this file will fail the next time they run."
      :accept-props="{ label: 'Delete file', severity: 'warn', variant: 'outlined' }"
      :reject-props="{ label: 'Cancel' }"
    />
    <LumlflowConfirmDialog
      v-if="dialog === 'delete-folder'"
      :header="`Delete ${dialogTarget}?`"
      message="The folder and everything in it are deleted. This action is permanent and cannot be undone."
      :accept-props="{ label: 'Delete folder', severity: 'warn', variant: 'outlined' }"
      :reject-props="{ label: 'Cancel' }"
    />
  </MainTemplate>
</template>

<script setup lang="ts">
import { FilePlus, FolderPlus } from 'lucide-vue-next'
import { Button, InputText, Message, Select } from '@/ui'
import LumlflowDialog from '@/ui/LumlflowDialog.vue'
import LumlflowConfirmDialog from '@/ui/LumlflowConfirmDialog.vue'
import UiPreviewBadge from '@/components/UiPreviewBadge/UiPreviewBadge.vue'
import type { OpenFlow, OpenFlowsTotals } from '@/components/FlowStateMarker/openFlows'
import type { WorkspaceFolderItem } from '@/blocks/WorkspaceFolder/interface'
import OpenFlowsSummary from '@/blocks/OpenFlowsSummary/OpenFlowsSummary.vue'
import MainTemplate from '@/pages/lumlflow/HomePage/MainTemplate.vue'
import HomeTabs from '@/pages/lumlflow/HomePage/HomeTabs.vue'
import WorkspacePath from '@/pages/lumlflow/WorkspacesPage/WorkspacePath.vue'
import CreateNewFlow from '@/pages/lumlflow/WorkspacesPage/CreateNewFlow.vue'
import WorkspaceFolder from '../WorkspaceFolder/WorkspaceFolder.vue'
import WorkspaceFileViewer, {
  type ViewerFile,
  type ViewerState,
  type ViewerTable,
  type ViewerView,
} from './WorkspaceFileViewer.vue'
import type { LumlPackage } from './LumlPackagePreview.vue'

type Props = {
  directory: string
  items: WorkspaceFolderItem[]
  openFlows?: OpenFlow[]
  openFlowsTotals?: OpenFlowsTotals
  loading?: boolean
  /** The open file preview; none: the listing takes the full width, as today. */
  viewer?: {
    file: ViewerFile
    textContent?: string
    prettyContent?: string
    view?: ViewerView
    table?: ViewerTable
    image?: string
    svg?: string
    media?: 'audio' | 'video'
    pdf?: boolean
    html?: string
    previewState?: ViewerState
    luml?: LumlPackage
    editing?: boolean
    conflict?: boolean
    agent?: { label: string; color: string }
  } | null
  /** B-14: the row whose ⋮ menu is open, the row being renamed, as in the current page. */
  menuOpenId?: string | null
  renamingId?: string | null
  renameValue?: string
  /** B-14: the dialog opened from a row menu or the create buttons. */
  dialog?: 'new-folder' | 'new-file' | 'move' | 'delete-file' | 'delete-folder' | null
  /** The file or folder name the dialog is about. */
  dialogTarget?: string
  dialogName?: string
  dialogError?: string | null
  moveFolders?: string[]
  moveTo?: string | null
}

withDefaults(defineProps<Props>(), {
  openFlows: () => [],
  openFlowsTotals: () => ({ open_flows: 0, running_kernels: 0 }),
  loading: false,
  viewer: null,
  menuOpenId: null,
  renamingId: null,
  renameValue: '',
  dialog: null,
  dialogTarget: '',
  dialogName: '',
  dialogError: null,
  moveFolders: () => [],
  moveTo: null,
})
</script>

<style scoped>
.tabs,
.heading {
  margin-bottom: 1.5rem;
}

.heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.25rem;
}

.heading-title {
  display: flex;
  align-items: center;
}

.folder {
  margin-bottom: 1rem;
}

.create-row {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.label {
  display: inline-block;
  margin-bottom: 0.5rem;
}

.move-subject {
  margin: 0 0 0.75rem;
}

/* UIP-002: with a file open, the listing narrows to the left and the preview fills the rest. */
.content-split {
  display: grid;
  grid-template-columns: 400px minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
</style>
