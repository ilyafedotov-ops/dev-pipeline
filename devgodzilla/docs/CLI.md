# DevGodzilla CLI Reference

DevGodzilla provides a Click-based CLI for all operations.

## Global Options

```bash
devgodzilla [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--verbose`, `-v` | Enable verbose output |
| `--json` | Output in JSON format |
| `--help` | Show help message |

---

## SpecKit Commands

### `spec init`

Initialize SpecKit in a project directory.

```bash
devgodzilla spec init [DIRECTORY] [OPTIONS]

Options:
  -p, --project-id INTEGER    Link to project ID in database
  -c, --constitution PATH     Path to custom constitution file
```

**Example:**
```bash
devgodzilla spec init .
devgodzilla spec init . --constitution my-rules.md
```

### `spec specify`

Generate a feature specification from a description.

```bash
devgodzilla spec specify DESCRIPTION [OPTIONS]

Options:
  -d, --directory PATH        Project directory (default: .)
  -n, --name TEXT             Feature name (auto-generated if not provided)
  -p, --project-id INTEGER    Project ID in database
```

**Example:**
```bash
devgodzilla spec specify "Add user authentication with OAuth2"
devgodzilla spec specify "Add payment integration" --name payment-system
```

### `spec plan`

Generate an implementation plan from a specification.

```bash
devgodzilla spec plan SPEC_PATH [OPTIONS]

Options:
  -d, --directory PATH        Project directory
  -p, --project-id INTEGER    Project ID
```

**Example:**
```bash
devgodzilla spec plan .specify/specs/001-auth/spec.md
```

### `spec tasks`

Generate a task list from a plan.

```bash
devgodzilla spec tasks PLAN_PATH [OPTIONS]

Options:
  -d, --directory PATH        Project directory
  -p, --project-id INTEGER    Project ID
```

**Example:**
```bash
devgodzilla spec tasks .specify/specs/001-auth/plan.md
```

### `spec list`

List all specifications in a project.

```bash
devgodzilla spec list [DIRECTORY]
```

### `spec status`

Show SpecKit status for a project.

```bash
devgodzilla spec status [DIRECTORY]
```

### `spec constitution`

Show or edit the project constitution.

```bash
devgodzilla spec constitution [DIRECTORY] [OPTIONS]

Options:
  -e, --edit    Open in editor
```

### `spec show`

Show contents of a spec file.

```bash
devgodzilla spec show SPEC_NAME [DIRECTORY] [OPTIONS]

Options:
  -f, --file [spec|plan|tasks|data-model]    File to show (default: spec)
```

---

## Protocol Commands

### `protocol create`

Create a new protocol run.

```bash
devgodzilla protocol create PROJECT_ID NAME [OPTIONS]

Options:
  -d, --description TEXT    Protocol description
  -b, --branch TEXT         Git branch name
```

**Example:**
```bash
devgodzilla protocol create 1 "implement-auth" --description "Add OAuth2"
```

### `protocol start`

Start a protocol run.

```bash
devgodzilla protocol start PROTOCOL_ID
```

### `protocol status`

Get the status of a protocol.

```bash
devgodzilla protocol status PROTOCOL_ID
```

### `protocol pause`

Pause a running protocol (use `resume` to continue).

```bash
# Note: pause command implemented; check available subcommands
devgodzilla protocol --help
```

### `protocol cancel`

Cancel a protocol.

```bash
devgodzilla protocol cancel PROTOCOL_ID [OPTIONS]

Options:
  --force    Force cancellation
```

### `protocol list`

List protocol runs.

```bash
devgodzilla protocol list [OPTIONS]

Options:
  -p, --project INTEGER    Filter by project ID
  -s, --status TEXT        Filter by status
  -l, --limit INTEGER      Max results (default: 20)
```

---

## Project Commands

### `project create`

Create a new project.

```bash
devgodzilla project create NAME [OPTIONS]

Options:
  -r, --repo TEXT         Git repository URL (required)
  -b, --branch TEXT       Base branch (default: main)
```

### `project list`

List all projects.

```bash
devgodzilla project list
```

### `project show`

Show project details.

```bash
devgodzilla project show PROJECT_ID
```

---

## Agent Commands

### `agent list`

List available AI agents.

```bash
devgodzilla agent list
```

### `agent test`

Test an agent's availability.

```bash
devgodzilla agent test AGENT_ID
```

---

## Clarification Commands

### `clarify list`

List pending clarifications.

```bash
devgodzilla clarify list [OPTIONS]

Options:
  -p, --project-id INTEGER      Filter by project
  -r, --protocol-id INTEGER     Filter by protocol
  -s, --status [open|answered]  Filter by status
```

### `clarify answer`

Answer a clarification.

```bash
devgodzilla clarify answer CLARIFICATION_ID ANSWER
```

---

## Step Commands

### `step run`

Execute a step.

```bash
devgodzilla step run STEP_ID
```

### `step qa`

Run QA on a step.

```bash
devgodzilla step qa STEP_ID [OPTIONS]

Options:
  -g, --gates TEXT    Comma-separated list of gates to run
```

### `step status`

Get step status.

```bash
devgodzilla step status STEP_ID
```

### `step retry`

Retry a failed step.

```bash
devgodzilla step retry STEP_ID
```

---

## QA Commands

### `qa evaluate`

Evaluate QA gates standalone.

```bash
devgodzilla qa evaluate [OPTIONS]

Options:
  -w, --workspace PATH    Workspace directory
  -s, --step-name TEXT    Step name for context
  -g, --gates TEXT        Comma-separated list of gates
```

### `qa gates`

List available QA gates.

```bash
devgodzilla qa gates
```

---

## Utility Commands

### `version`

Show version information.

```bash
devgodzilla version
```

### `banner`

Show the DevGodzilla banner.

```bash
devgodzilla banner
```
