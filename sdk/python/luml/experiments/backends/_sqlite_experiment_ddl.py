# flake8: noqa: E501

_DDL_EXPERIMENT_CREATE_STATIC = """
    CREATE TABLE IF NOT EXISTS static_params (
        key TEXT PRIMARY KEY,
        value TEXT,
        value_type TEXT
    )
"""

_DDL_EXPERIMENT_CREATE_DYNAMIC = """
    CREATE TABLE IF NOT EXISTS dynamic_metrics (
        key TEXT,
        value REAL,
        step INTEGER,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (key, step)
    )
"""

_DDL_EXPERIMENT_CREATE_ATTACHMENTS = """
    CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        file_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_EXPERIMENT_CREATE_SPANS = """
    CREATE TABLE IF NOT EXISTS spans (
        -- OTEL identifiers
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        parent_span_id TEXT,

        -- span details
        name TEXT NOT NULL,  -- OTEL uses 'name' instead of 'operation_name'
        kind INTEGER,        -- SpanKind: 0=UNSPECIFIED, 1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER
        dfs_span_type INTEGER NOT NULL DEFAULT 0,  -- SpanType: 0=DEFAULT

        -- Timing
        start_time_unix_nano BIGINT NOT NULL,
        end_time_unix_nano BIGINT NOT NULL,

        -- Status
        status_code INTEGER,    -- StatusCode: 0=UNSET, 1=OK, 2=ERROR
        status_message TEXT,

        -- Span data
        attributes TEXT,       -- JSON
        events TEXT,           -- JSON
        links TEXT,            -- JSON

        trace_flags INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (trace_id, span_id)
    );
"""

_DDL_EXPERIMENT_CREATE_EVALS = """
    CREATE TABLE IF NOT EXISTS evals (
        id TEXT NOT NULL,
        dataset_id TEXT NOT NULL,
        inputs TEXT NOT NULL, -- JSON
        outputs TEXT, -- JSON
        refs TEXT, -- JSON
        scores TEXT, -- JSON
        metadata TEXT, -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (dataset_id, id)
    )
"""

_DDL_EXPERIMENT_CREATE_EVAL_TRACES_BRIDGE = """
    CREATE TABLE IF NOT EXISTS eval_traces_bridge (
        id TEXT PRIMARY KEY,
        eval_dataset_id TEXT NOT NULL,
        eval_id TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""
