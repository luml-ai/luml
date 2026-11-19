# Apply log

- **Add the file API to the daemon** — spec not followed: The read limit for inspection names only the manifest, dataset info and tar index. Model detection also reads the environment, manifest patches and model metadata JSON because the required fnnx Reader uses them to validate a model. Model weights and dataset chunks stay unread.
- **Add the file API to the daemon** — decided: A listing request above the 2,000-entry limit receives a capped page and the offset for the next page. This lets a caller continue paging with the same requested limit.
- **Add the file API to the daemon** — decided: A dataset with a readable manifest and malformed split metadata still exposes its manifest and archive contents. Its split list is empty when the split definitions cannot be validated, and an unreadable optional row count is reported as unknown.
- **Add the file API to the daemon** — The CLI-delete scenario calls for a bare command with no prompt, while the Design preserves the existing CLI behavior. Deleting a notebook still asks once for destructive confirmation unless invoked with `--yes`. Both forms request `close_open` so an open session needs no second confirmation.
