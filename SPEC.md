# Proposals

Create a file `hello-codie.txt` in the repository root with the content `Hi!`. This is a simple test spec to verify that the agent can create a file with specific content.

# Design

- Create a single plain-text file at the repository root: `hello-codie.txt`
- The file contains exactly one line: `Hi!` (no trailing newline beyond what the editor naturally adds)
- No dependencies, no frameworks, no additional configuration

# Scenarios

## Scenario: File creation with correct content
**Given** the repository does not contain `hello-codie.txt`
**When** the agent runs the task
**Then** `hello-codie.txt` exists at the repository root with the content `Hi!`

## Scenario: File is a plain text file
**Given** the task has been completed
**When** inspecting `hello-codie.txt`
**Then** it is a plain UTF-8 text file containing only `Hi!`

# Tasks

- [x] Create `hello-codie.txt`
  - [x] Create the file `hello-codie.txt` in the repository root with content `Hi!`
  - [x] Verify the file exists and has the correct content