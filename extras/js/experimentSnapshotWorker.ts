/// <reference lib="webworker" />

import type {
  ExperimentSnapshotModelSource,
  SnapshotCallContext,
  SnapshotSourceLocation,
} from "@luml/experiments";
import {
  ExperimentSnapshotDatabaseProvider,
  redactSecrets,
  snapshotErrorFields,
} from "@luml/experiments";
import sqliteWasmUrl from "@sqlite.org/sqlite-wasm/sqlite3.wasm?url";

type InitPayloadItem = ExperimentSnapshotModelSource;

interface ReopenPayload {
  modelId: string;
  source: SnapshotSourceLocation;
}

interface CallPayload<
  M extends keyof ExperimentSnapshotDatabaseProvider =
    keyof ExperimentSnapshotDatabaseProvider,
> {
  method: M;
  args?: ExperimentSnapshotDatabaseProvider[M] extends (
    ...args: infer A
  ) => unknown
    ? A
    : never[];
}

interface CallMessage {
  payload: CallPayload;
  /** When the caller, or else the proxy, stops waiting for the answer (epoch ms). */
  deadline?: number;
  context?: Omit<SnapshotCallContext, "deadline">;
}

let provider: ExperimentSnapshotDatabaseProvider | null = null;

const activeRequests = new Map<string, AbortController>();
// The failures version the proxy last heard of. A per-call baseline would lose the change of
// a call that was cancelled (its answer is never posted): the next call starts from it.
let reportedFailuresVersion = 0;

function post(
  requestId: string,
  data: unknown,
  extra: Record<string, unknown> = {},
) {
  if (!activeRequests.has(requestId)) return;
  self.postMessage({ type: "result", requestId, data, ...extra });
}

/**
 * Set on the answer, or the error, of the first call posted after an experiment of a comparison
 * was left out or read again: the proxy then tells the views to read the statuses again.
 */
function statusesChanged(requestId: string): { statusesChanged?: true } {
  if (!provider || !activeRequests.has(requestId)) return {};
  const version = provider.readFailuresVersion;
  if (version === reportedFailuresVersion) return {};
  reportedFailuresVersion = version;
  return { statusesChanged: true };
}

async function init(
  payload: InitPayloadItem[],
  requestId: string,
  signal: AbortSignal,
) {
  provider = new ExperimentSnapshotDatabaseProvider();
  reportedFailuresVersion = provider.readFailuresVersion;
  const failures = await provider.init(
    { modelsInfo: payload, sqliteWasmUrl },
    signal,
  );
  post(requestId, failures);
}

async function reopen(
  payload: ReopenPayload,
  requestId: string,
  signal: AbortSignal,
) {
  if (!provider) throw new Error("Provider not initialized");
  post(
    requestId,
    await provider.reopenSnapshot(payload.modelId, payload.source, signal),
  );
}

async function call(
  { payload, deadline, context }: CallMessage,
  requestId: string,
) {
  const { method, args } = payload;
  // Calls queue behind a read that blocks the thread; one whose caller gave up meanwhile is
  // not run, so the reads after it are not delayed.
  if (deadline !== undefined && Date.now() >= deadline) {
    throw new Error("Experiment snapshot worker request timed out");
  }
  if (!provider) {
    throw new Error("Provider not initialized");
  }
  const target = provider;
  const fn = target[method] as (...args: unknown[]) => unknown;
  if (typeof fn !== "function") {
    throw new Error(`Provider method "${method}" does not exist`);
  }
  const result = await target.runCall({ ...context, deadline }, () =>
    fn.apply(target, args ?? []),
  );
  post(requestId, result, statusesChanged(requestId));
}

self.onmessage = async (event) => {
  const { type, payload, requestId } = event.data;
  if (type === "cancel") {
    // Stops downloads of an abandoned init or reopen; the answer is not posted.
    activeRequests.get(requestId)?.abort();
    activeRequests.delete(requestId);
    return;
  }
  const controller = new AbortController();
  activeRequests.set(requestId, controller);
  try {
    switch (type) {
      case "init":
        await init(payload, requestId, controller.signal);
        break;
      case "reopen":
        await reopen(payload, requestId, controller.signal);
        break;
      case "call":
        await call(event.data, requestId);
        break;
    }
  } catch (err: unknown) {
    const { message } = (err ?? {}) as { message?: unknown };
    self.postMessage({
      type: "error",
      requestId,
      error: redactSecrets(typeof message === "string" ? message : String(err)),
      ...snapshotErrorFields(err),
      ...(type === "call" ? statusesChanged(requestId) : {}),
    });
  } finally {
    activeRequests.delete(requestId);
  }
};
