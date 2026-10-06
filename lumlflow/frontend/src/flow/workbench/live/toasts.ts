import type { Transaction } from '@/flow/api/types'

const AUTO_ACTOR = 'auto'

export type ToastSeverity = 'secondary' | 'info' | 'warn' | 'error'

export interface ToastPlan {
  key: string
  summary: string
  detail: string
  severity: ToastSeverity
  count: number
}

export function coalesceTransactions(transactions: Transaction[]): ToastPlan[] {
  const plans: ToastPlan[] = []
  const byIntent = new Map<string, ToastPlan>()
  let refreshed: ToastPlan | undefined
  for (const transaction of transactions) {
    if (transaction.actor === AUTO_ACTOR) {
      if (failed(transaction)) continue
      if (refreshed === undefined) {
        refreshed = {
          key: 'auto',
          summary: 'Refreshed automatically',
          detail: '1 cell',
          severity: 'secondary',
          count: 1,
        }
        plans.push(refreshed)
        continue
      }
      refreshed.count += 1
      refreshed.detail = `${refreshed.count} cells`
      continue
    }
    if (failed(transaction)) {
      if (transaction.actor !== 'user') continue
      plans.push({
        key: `failed:${transaction.step}`,
        summary: 'Run failed',
        detail: transaction.intent,
        severity: 'error',
        count: 1,
      })
      continue
    }
    if (transaction.offline) {
      plans.push({
        key: `offline:${transaction.step}`,
        summary: 'Edits made while lumlflow was stopped',
        detail: transaction.intent,
        severity: 'warn',
        count: 1,
      })
      continue
    }
    const held = byIntent.get(transaction.intent)
    if (held !== undefined) {
      held.count += 1
      held.detail = `${transaction.actor} · ${held.count} transactions`
      continue
    }
    const plan: ToastPlan = {
      key: `intent:${transaction.intent}`,
      summary: transaction.intent,
      detail: transaction.actor,
      severity: 'secondary',
      count: 1,
    }
    byIntent.set(transaction.intent, plan)
    plans.push(plan)
  }
  return plans
}

function failed(transaction: Transaction): boolean {
  return transaction.ops.some((op) => op.op === 'run_recorded' && op.state === 'failed')
}
