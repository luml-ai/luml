"""The Flow server's half of the browser contract for metric catalogs and buckets.

`tests/fixtures/metric_api_contract.json` pins each request body exactly as
`ExperimentSnapshotApiProvider` sends it and the server's answer. This test proves
the server gives those answers; `frontend/src/api/metric-api-contract.test.ts` feeds
the same answers through Flow's `apiService` into the provider's decoder. Set
`LUMLFLOW_UPDATE_CONTRACT=1` to rewrite the fixture after a deliberate change.
"""

import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any

from luml.experiments.tracker import ExperimentTracker

from tests.helpers.metrics import (
    LEGACY_INSERT,
    log_points,
    require_newer_reader,
    revision2_experiment,
    serve,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "metric_api_contract.json"


def contract_store(store: Path) -> dict[str, str]:
    setup = ExperimentTracker(f"sqlite://{store}")
    main = setup.start_experiment(name="main")
    log_points(
        setup,
        main,
        "train/loss",
        [(step, 2.0 - step / 100) for step in range(150)]
        + [(200, math.inf), (201, -math.inf), (202, math.nan)],
    )
    log_points(setup, main, "ünïcode/métric", [(-3, 0.5), (3, 1.5)])
    future = setup.start_experiment(name="future")
    log_points(setup, future, "train/loss", [(0, 1.0)])
    setup.end_experiment(main)
    setup.end_experiment(future)
    setup.backend.close()
    require_newer_reader(store / future / "exp.db")
    legacy, legacy_db = revision2_experiment(
        store, "train/loss", [(step, 2.0 - step / 100) for step in range(150)]
    )
    # Released SDKs stored a fractional step as given; the buckets count it.
    conn = sqlite3.connect(legacy_db)
    conn.execute(LEGACY_INSERT, ("train/loss", 1.0, 10.5, None))
    conn.commit()
    conn.close()
    return {"main": main, "future": future, "legacy": legacy}


def answer(client: Any, experiment_id: str, case: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN401
    path = f"/api/experiments/{experiment_id}/{case['endpoint']}"
    if case["method"] == "GET":
        response = client.get(path)
    else:
        response = client.post(path, json=case["request"])
    # Experiment ids are random; error messages name them.
    body = json.loads(response.text.replace(experiment_id, "<experiment>"))
    return {"status": response.status_code, "body": body}


def test_the_server_answers_the_pinned_contract(tmp_path: Path) -> None:
    store = tmp_path / "experiments"
    experiments = contract_store(store)
    tracker = ExperimentTracker(f"sqlite://{store}")
    client = serve(tracker)
    cases = json.loads(FIXTURE.read_text())

    answers = [
        {**case, "response": answer(client, experiments[case["experiment"]], case)}
        for case in cases
    ]
    tracker.backend.close()

    if os.environ.get("LUMLFLOW_UPDATE_CONTRACT") == "1":
        FIXTURE.write_text(json.dumps(answers, indent=2, ensure_ascii=False) + "\n")
    assert answers == cases
