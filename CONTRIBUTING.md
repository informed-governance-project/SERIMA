Contributions are welcome and there are many ways to participate to the
project. You can contribute by:

- reporting bugs;
- suggesting enhancements or new features;
- improving the documentation;
- proposing code changes.

## Getting started

Clone the repository and the theme, install the dependencies, and install the
Git hook scripts:

```bash
$ git clone https://github.com/informed-governance-project/SERIMA
$ cd SERIMA/
$ git checkout dev
$ git clone https://github.com/informed-governance-project/default-theme.git theme
$ (cd theme && git checkout dev)
$ poetry install
$ poetry run pre-commit install
$ poetry run pre-commit run --all-files
```

The [Development page](https://serima.readthedocs.io/en/latest/technical/development.html)
of the technical guide covers the rest: the configuration, running the
application and the tests, the code quality checks and the useful commands.

## Branches and pull requests

- `main` holds the released versions and only changes when a release is made.
- `dev` is where development happens: open your pull requests against `dev`.
- Develop features and fixes in their own branches (`feat/…`, `fix/…`), then
  open a pull request to merge them into `dev`.
- Prefix commit messages with the area they touch: `[GOV]`, `[NI]`, `[SO]` or
  `[RG]`, or use `feat:`, `fix:`, `docs:`…
- If your change is visible to users, add an entry under `[Unreleased]` in
  `CHANGELOG.md`.
- If your contribution requires documentation changes, include them in the same
  pull request.
- The interface lives in a separate repository, cloned into `theme/`: changes
  to it need a pull request there as well.

## Code style

[Django](https://www.djangoproject.com) is used for the backend.
Use [ruff](https://github.com/astral-sh/ruff) to lint and format your Python
code; the pre-commit hooks run it for you before each commit.
