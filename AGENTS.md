# AGENTS.md

This project uses the instructions defined in CLAUDE.md.

Read CLAUDE.md first.

If a rule in this file conflicts with CLAUDE.md, follow CLAUDE.md.

# Agent workflow

Before writing code:

1. Understand the existing implementation.
2. Search for similar patterns already used in the project.
3. Reuse existing code before creating new abstractions.
4. Keep the change as small as possible.

During implementation:

- Prefer modifying existing files.
- Do not introduce unrelated refactoring.
- Keep commits focused on one logical change.
- Prefer the smallest change that solves the problem.
- Avoid "improving" unrelated code.

Before finishing:

- Run formatting.
- Run relevant tests.
- Check for regressions.
- Explain any trade-offs.

Ask before:

- changing architecture
- introducing new dependencies
- changing public APIs
- deleting existing code
- making database schema changes outside the requested task


Never:

- rewrite large files unnecessarily
- rename public APIs unless requested
- modify generated files
- modify old migration files
- change dependencies without a reason
- create helper functions used only once
- introduce new abstractions without repetition
- commit or open a pull request unless explicitly requested

Priority order:

1. Correctness
2. Security
3. Readability
4. Maintainability
5. Performance
