/**
 * Toasts, coalesced by transaction intent.
 *
 * An agent working produces bursts — twenty cells accepted under one intent,
 * then a run, then a fix. Forty toasts for that is forty interruptions for one
 * thing that happened, and a user who learns to dismiss them stops reading the
 * one that mattered. So a burst sharing an intent collapses to a single line
 * carrying its count, in the order the intents first appeared.
 *
 * Two things never collapse. **The user's own failures** get a toast every time,
 * because a second failure under the same intent is a second thing to look at.
 * And a **coarse offline transaction** — the one the daemon journals for edits
 * made while it was stopped — is labelled as what it is rather than rendered as
 * a normal burst that happens to be large.
 *
 * An **agent's** failure is demoted instead: the card's chip goes `failed` and
 * the traceback fills its logs, and that is the whole of it. An agent iterating
 * through a broken intermediate state is working, not breaking something, and
 * interrupting a user for each pass would train them to stop reading.
 *
 * **Reactivity's own runs** are one line however many cells it refreshed. Its
 * intents are per-cell — `ran features`, `ran plot` — so grouping by intent
 * would give one toast per cell for one thing that happened, and every edit
 * would arrive with a stack of them. It is background work by definition, so
 * it gets the background's volume: one line, a count, and no failure toast at
 * all — a cell reactivity could not run wears its own `failed` chip, and
 * reactivity will not try it again until the next edit.
 */

import type { Transaction } from '@/flow/api/types'

/** The actor the daemon journals a run nobody asked for under. */
const AUTO_ACTOR = 'auto'

export type ToastSeverity = 'secondary' | 'info' | 'warn' | 'error'

export interface ToastPlan {
  /** Stable across a burst, so a surface can replace rather than stack. */
  key: string
  summary: string
  detail: string
  severity: ToastSeverity
  /** Transactions folded into this one. */
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
