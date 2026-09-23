class EvalPredictions:
    """Score the model on a held-out eval set and record evals with traces.

    Every sample is one eval row and one trace. The trace mirrors what the
    SDK's `evaluate()` records: `eval_request` with `inference_fn` and
    `eval_scoring` under it, and the eval sample is linked to that trace.
    The card shows both: `evals` is the scored samples, `traces` is one row
    per trace with its spans and latency.
    """
    uid = "01M372T067TDD3BN60GKVGXF0H"

    consumes = {"model": "train_model.model", "x_test": "features.x_test"}
    produces = {"experiment": "experiment", "evals": "asset", "traces": "asset"}
    params = {"samples": 20, "seed": 7, "dataset_id": "breast_cancer_holdout_v1"}

    def materialize(self, ctx, model, x_test):
        import time
        import uuid

        import numpy as np

        ctx.seed()
        sdk = ctx.tracker._client
        experiment_id = ctx.tracker.experiment_id
        dataset_id = self.params["dataset_id"]
        columns = [c for c in x_test.columns if c != "target"]
        picked = x_test.sample(n=self.params["samples"], random_state=self.params["seed"])

        def span(trace_id, name, start, end, parent=None, attributes=None, status=0):
            span_id = uuid.uuid4().hex[:16]
            sdk.log_span(
                trace_id=trace_id, span_id=span_id, name=name,
                start_time_unix_nano=start, end_time_unix_nano=end,
                parent_span_id=parent, status_code=status,
                attributes=attributes or {}, experiment_id=experiment_id,
            )
            return span_id

        evals = []
        traces = []
        for n, (index, row) in enumerate(picked.iterrows()):
            eval_id = f"sample_{n:02d}"
            trace_id = uuid.uuid4().hex
            inputs = {c: round(float(row[c]), 4) for c in columns[:5]}
            expected = int(row["target"])

            t0 = time.time_ns()
            root = span(trace_id, "eval_request", t0, t0,
                        attributes={"eval.id": eval_id, "eval.dataset_id": dataset_id})

            t1 = time.time_ns()
            x = row[columns].to_numpy(dtype=float).reshape(1, -1)
            pred = int(model.predict(x)[0])
            proba = float(model.predict_proba(x)[0, 1])
            t2 = time.time_ns()
            span(trace_id, "inference_fn", t1, t2, parent=root,
                 attributes={"gen_ai.operation.name": "chat", "model": type(model).__name__,
                             "prediction": pred, "proba": round(proba, 4)})

            t3 = time.time_ns()
            scores = {
                "correct": pred == expected,
                "confidence": round(max(proba, 1 - proba), 4),
                "abs_error": round(abs(proba - expected), 4),
            }
            t4 = time.time_ns()
            span(trace_id, "eval_scoring", t3, t4, parent=root,
                 attributes={f"eval.score.{k}": v for k, v in scores.items()})

            t5 = time.time_ns()
            sdk.log_span(
                trace_id=trace_id, span_id=root, name="eval_request",
                start_time_unix_nano=t0, end_time_unix_nano=t5,
                attributes={"eval.id": eval_id, "eval.dataset_id": dataset_id},
                status_code=1 if scores["correct"] else 2, experiment_id=experiment_id,
            )
            sdk.log_eval_sample(
                eval_id=eval_id, dataset_id=dataset_id,
                inputs=inputs, outputs={"prediction": pred, "proba": round(proba, 4)},
                references={"expected": expected}, scores=scores,
                metadata={"sample_index": int(index)}, experiment_id=experiment_id,
            )
            sdk.link_eval_sample_to_trace(
                eval_dataset_id=dataset_id, eval_id=eval_id, trace_id=trace_id,
                experiment_id=experiment_id,
            )
            evals.append({"eval_id": eval_id, "expected": expected, "prediction": pred,
                          **scores, "trace_id": trace_id})
            traces.append({
                "trace_id": trace_id,
                "eval_id": eval_id,
                "spans": 3,
                "status": "OK" if scores["correct"] else "ERROR",
                "inference_ms": round((t2 - t1) / 1e6, 3),
                "scoring_ms": round((t4 - t3) / 1e6, 3),
                "total_ms": round((t5 - t0) / 1e6, 3),
            })

        ctx.tracker.log_params({"model": type(model).__name__, "dataset_id": dataset_id,
                                "samples": len(evals)})
        ctx.tracker.log_metrics({
            "eval_accuracy": float(np.mean([r["correct"] for r in evals])),
            "eval_mean_confidence": float(np.mean([r["confidence"] for r in evals])),
            "eval_mean_abs_error": float(np.mean([r["abs_error"] for r in evals])),
            "trace_total_ms_mean": float(np.mean([t["total_ms"] for t in traces])),
        })
        return {"experiment": ctx.tracker.record, "evals": evals, "traces": traces}
