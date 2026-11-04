import { nextTick } from 'vue'

export async function settle(): Promise<void> {
  for (let round = 0; round < 4; round += 1) {
    for (let turn = 0; turn < 16; turn += 1) await Promise.resolve()
    await nextTick()
  }
}
