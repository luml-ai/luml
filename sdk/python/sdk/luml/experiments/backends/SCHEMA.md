# Database Schema

Final schema after all migrations (v1–v4).

---

## experiments

| Column          | Type      | Notes                          |
|-----------------|-----------|--------------------------------|
| `id`            | TEXT      | Primary key                    |
| `name`          | TEXT      |                                |
| `created_at`    | TIMESTAMP | Default: current timestamp     |
| `status`        | TEXT      | Default: `'active'`            |
| `tags`          | TEXT      | JSON string                    |
| `group_id`      | TEXT      | FK → `experiment_groups.id`    |
| `static_params` | TEXT      | JSON string                    |
| `dynamic_params`| TEXT      | JSON string                    |
| `duration`      | REAL      |                                |
| `description`   | TEXT      |                                |
| `source`        | TEXT      | Added in migration 004         |

---

## models

| Column          | Type      | Notes                                        |
|-----------------|-----------|----------------------------------------------|
| `id`            | TEXT      | Primary key                                  |
| `name`          | TEXT      |                                              |
| `created_at`    | TIMESTAMP | Default: current timestamp                   |
| `tags`          | TEXT      | JSON string                                  |
| `path`          | TEXT      |                                              |
| `experiment_id` | TEXT      | FK → `experiments.id` ON DELETE CASCADE      |
| `size`          | INTEGER   | Added in migration 003                       |
| `source`        | TEXT      | Added in migration 004                       |
| `description`   | TEXT      | Added in migration 004                       |

---

## experiment_groups

| Column          | Type      | Notes                          |
|-----------------|-----------|--------------------------------|
| `id`            | TEXT      | Primary key                    |
| `name`          | TEXT      | Unique index                   |
| `description`   | TEXT      |                                |
| `created_at`    | TIMESTAMP | Default: current timestamp     |
| `tags`          | TEXT      | Added in migration 002         |
| `last_modified` | TIMESTAMP | Default: current timestamp, added in migration 002 |

---

## schema_migrations

| Column       | Type      | Notes                      |
|--------------|-----------|----------------------------|
| `version`    | INTEGER   | Primary key                |
| `applied_at` | TIMESTAMP | Default: current timestamp |

---

## Relationships

```
experiment_groups
    └── experiments (group_id → experiment_groups.id)
            └── models (experiment_id → experiments.id, ON DELETE CASCADE)
```

---

## Migration history

| Version | Description                                   |
|---------|-----------------------------------------------|
| 001     | Initial schema (experiments, experiment_groups) |
| 002     | Fixed group relationship, added models table  |
| 003     | Added `size` column to models                 |
| 004     | Added `source` to experiments and models, `description` to models |