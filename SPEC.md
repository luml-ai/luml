# Proposals

When an experiment is created without an explicit name, the system currently falls back to using the experiment's UUID as the name (e.g., `550e8400-e29b-41d4-a716-446655440000`). This is not human-friendly — hard to remember, compare, or discuss.

**Proposed solution:** Generate a random human-readable name in the format `{adjective}-{noun}-{3-digit number}` (e.g., `swift-falcon-042`, `bright-gradient-817`). A standalone helper function with a static word dictionary produces the names. The `ExperimentTracker.start_experiment()` method calls this helper when no name is provided.

**Why this approach:**
- Standalone helper keeps naming logic decoupled from experiment tracking — testable and reusable.
- Static dictionaries (no external dependencies) keep the SDK lightweight.
- Format `adjective-noun-NNN` with ~200 adjectives × ~200 nouns × 1000 numbers = ~40M combinations — sufficient to minimize collisions without uniqueness checks.

# Design

## Name generator helper

- **Location:** `sdk/python/sdk/luml/utils/naming.py`
- **Function:** `generate_random_name() -> str`
  - Uses `random.choice()` to pick one adjective and one noun from static lists, and `random.randint(0, 999)` for the number.
  - Returns `f"{adjective}-{noun}-{number:03d}"`.
  - No parameters needed — the function is self-contained.

## Word dictionaries

Defined as module-level constants in `naming.py`:

- `ADJECTIVES: list[str]` — ~200 words. Mix of general positive/descriptive and ML/science-flavored adjectives (e.g., `swift`, `bright`, `deep`, `sparse`, `latent`, `stochastic`, `robust`, `calibrated`).
- `NOUNS: list[str]` — ~200 words. Mix of nature and ML/science-flavored nouns (e.g., `falcon`, `gradient`, `tensor`, `vector`, `photon`, `nebula`, `quasar`, `ridge`).

All words are lowercase, ASCII-only, no hyphens within words.

## Integration in tracker

- **File:** `sdk/python/sdk/luml/experiments/tracker.py`
- **Change:** In `start_experiment()`, when `name is None`, call `generate_random_name()` and use the result as the name passed to `self.backend.initialize_experiment()`.
- The backend interface and implementations remain unchanged — they already accept `name: str | None` and this will now always receive a string.

## Combinatorial space

200 adjectives × 200 nouns × 1000 numbers = **40,000,000** unique names. No uniqueness check against existing experiments — collision probability is negligible for practical usage.

# Scenarios

## Scenario: Experiment created without a name
**Given** a user creates an experiment without providing a name
**When** `tracker.start_experiment()` is called with `name=None`
**Then** the experiment is stored with a generated name matching the pattern `{adjective}-{noun}-{NNN}` (e.g., `swift-falcon-042`)

## Scenario: Experiment created with an explicit name
**Given** a user provides an explicit name
**When** `tracker.start_experiment(name="my_experiment")` is called
**Then** the explicit name is used, no random name is generated

## Scenario: Generated name format
**Given** the name generator is called
**When** `generate_random_name()` returns a name
**Then** the name consists of three parts separated by hyphens: a lowercase adjective, a lowercase noun, and a zero-padded 3-digit number (000–999)

## Scenario: Dictionary size
**Given** the static dictionaries in `naming.py`
**When** inspecting `ADJECTIVES` and `NOUNS`
**Then** each list contains at least 150 entries, all lowercase ASCII strings with no hyphens

## Scenario: Randomness
**Given** the name generator is called multiple times
**When** comparing the outputs
**Then** names vary across calls (not deterministic without seeding)

# Tasks

- [ ] Implement the random name generator
  - [ ] Create `sdk/python/sdk/luml/utils/naming.py` with `ADJECTIVES` list (~200 entries), `NOUNS` list (~200 entries), and `generate_random_name() -> str` function
  - [ ] Add tests in `sdk/python/sdk/tests/test_naming.py`: format validation (regex `^[a-z]+-[a-z]+-\d{3}$`), dictionary size assertions (≥150 each), all entries are lowercase ASCII without hyphens, multiple calls produce varying results (with statistical check)
  - [ ] Verify ruff and type checks pass

- [ ] Integrate name generator into ExperimentTracker
  - [ ] Modify `start_experiment()` in `sdk/python/sdk/luml/experiments/tracker.py` to call `generate_random_name()` when `name is None`
  - [ ] Add/update tests in `sdk/python/sdk/tests/experiments/` to verify: unnamed experiments get a generated name (not UUID), named experiments keep their explicit name
  - [ ] Verify ruff and type checks pass
