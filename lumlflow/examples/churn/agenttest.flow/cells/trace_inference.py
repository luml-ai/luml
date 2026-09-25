class TraceInference:
    """Run the model sample by sample and log one trace per sample.

    Every trace has a root `infer_sample` span with three nested spans:
    `preprocess`, `predict` and `score`. Latency and hit-rate go to metrics.
    """
    uid = "01M36VS713F4JW29MD0SJ741RB"

    consumes = {"model": "train_model.model", "x_test": "features.x_test"}
    produces = {"experiment": "experiment", "traces": "asset"}
    params = {"samples": 12, "seed": 42}

    def materialize(self, ctx, model, x_test):
        import time
        import uuid

        import numpy as np

        ctx.seed()
        sdk = ctx.tracker._client
        experiment_id = ctx.tracker.experiment_id
        columns = [c for c in x_test.columns if c != "target"]
        picked = x_test.sample(n=self.params["samples"], random_state=self.params["seed"])

        def span(trace_id, name, start, end, parent=None, attributes=None, status=0):
            span_id = uuid.uuid4().hex[:16]
            sdk.log_span(
                trace_id=trace_id,
                span_id=span_id,
                name=name,
                start_time_unix_nano=start,
                end_time_unix_nano=end,
                parent_span_id=parent,
                status_code=status,
                attributes=attributes or {},
                experiment_id=experiment_id,
            )
            return span_id

        rows = []
        latencies = []
        hits = 0
        for index, row in picked.iterrows():
            trace_id = uuid.uuid4().hex
            t0 = time.time_ns()
            root = span(
                trace_id, "infer_sample", t0, t0,
                attributes={"gen_ai.operation.name": "invoke_agent", "sample.index": int(index)},
            )

            t1 = time.time_ns()
            x = row[columns].to_numpy(dtype=float).reshape(1, -1)
            t2 = time.time_ns()
            span(trace_id, "preprocess", t1, t2, parent=root,
                 attributes={"gen_ai.operation.name": "execute_tool", "features": len(columns)})

            t3 = time.time_ns()
            pred = int(model.predict(x)[0])
            proba = float(model.predict_proba(x)[0, 1])
            t4 = time.time_ns()
            span(trace_id, "predict", t3, t4, parent=root,
                 attributes={"gen_ai.operation.name": "chat", "model": type(model).__name__,
                             "prediction": pred, "proba": round(proba, 4)})

            t5 = time.time_ns()
            truth = int(row["target"])
            hit = pred == truth
            hits += int(hit)
            t6 = time.time_ns()
            span(trace_id, "score", t5, t6, parent=root,
                 attributes={"truth": truth, "hit": hit}, status=1 if hit else 2)

            t7 = time.time_ns()
            sdk.log_span(
                trace_id=trace_id, span_id=root, name="infer_sample",
                start_time_unix_nano=t0, end_time_unix_nano=t7,
                attributes={"gen_ai.operation.name": "invoke_agent", "sample.index": int(index),
                            "prediction": pred, "truth": truth},
                status_code=1 if hit else 2, experiment_id=experiment_id,
            )
            latencies.append((t7 - t0) / 1e6)
            rows.append({"trace_id": trace_id, "sample": int(index), "prediction": pred,
                         "truth": truth, "proba": round(proba, 4), "latency_ms": round(latencies[-1], 3)})

        ctx.tracker.log_params({"model": type(model).__name__, "samples": len(rows)})
        ctx.tracker.log_metrics({
            "hit_rate": hits / len(rows),
            "latency_ms_mean": float(np.mean(latencies)),
            "latency_ms_p95": float(np.percentile(latencies, 95)),
        })
        return {"experiment": ctx.tracker.record, "traces": rows}
