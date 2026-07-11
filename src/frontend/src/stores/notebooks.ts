import { ref } from 'vue'
import { defineStore } from 'pinia'
import { DatabaseService } from '@/lib/databases/DatabaseService'
import { v4 as uuid } from 'uuid'
import type { Notebook } from '@/lib/databases/database.interfaces'

export const useNotebooksStore = defineStore('notebooks', () => {
  const notebooks = ref<Notebook[] | null>(null)

  async function getNotebooks() {
    notebooks.value = await DatabaseService.getDatabasesWithMetadata()
  }

  async function create(payload: { fullname: string }) {
    const createdDatabase = await DatabaseService.createDatabase(uuid(), {
      createdAt: Date.now(),
      fullname: payload.fullname,
    })
    const notebook = await DatabaseService.getDatabaseInfo(createdDatabase.name)
    notebooks.value?.push(notebook)
  }

  async function remove(name: string) {
    await DatabaseService.deleteDatabase(name)
    notebooks.value = notebooks.value?.filter((notebook) => notebook.name !== name) || null
  }

  async function edit(info: Partial<Notebook>) {
    if (!info.name || !info.fullname || !info.createdAt) return
    await DatabaseService.editDatabase(info.name, {
      fullname: info.fullname,
      createdAt: info.createdAt,
    })
    const updatedNotebook = await DatabaseService.getDatabaseInfo(info.name)
    if (!notebooks.value) return
    notebooks.value = notebooks.value.map((notebook) =>
      notebook.name === updatedNotebook.name ? updatedNotebook : notebook,
    )
  }

  async function createBackup(name: string) {
    await DatabaseService.createBackup(name)
  }

  return {
    notebooks,
    getNotebooks,
    create,
    remove,
    edit,
    createBackup,
  }
})
