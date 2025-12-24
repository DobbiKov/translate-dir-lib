# Contributing

Before contributing, make sure to read [the profound explanation](./docs/tool-profound-explanation.md) in order to understand how the tool work and its idea.

Each pull request must contain the following sections:

- **Motivation** - describes why this pull request is created in the first place (can be one sentence short).
- **Explanation** - explains what does the pull request change in the project's code base or architecture.

If you want to contribute but don't know what to start with, read the ToDo section in the [README](README.md).

All pull requests, ideas and suggestions are welcome!

## Logging and CLI output

This project standardizes diagnostics on Loguru and keeps user-facing CLI output as prints:

- **Default CLI behavior**: show user-facing `print` output plus Loguru warnings/errors on stderr.
- **Verbose mode (`--verbose` / `-v`)**: show both `print` output and all Loguru logs (including debug/trace).

Conventions:

- Use `print` only for user-facing CLI messages (results, progress, prompts).
- Use `loguru.logger` for diagnostics (debug/info/warn/error, stack traces, internal state).
- Library code should not configure Loguru; the CLI entrypoint wires log sinks and verbosity.
