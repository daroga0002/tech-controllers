# Contributing to TECH Controllers integration for Home Assistant

:+1::tada: First off all, many thanks for taking the time to contribute! Appreciated! :tada::+1:

The following is a set of guidelines for contributing to this integration. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Reporting Bugs

This section guides you through submitting a bug report for the integration. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

Before creating bug reports, please check [this issues list](https://github.com/mariusz-ostoja-swierczynski/tech-controllers/issues) as you might find out that you don't need to create one. When you are creating a bug report, please **include as many details as possible**:

* **Use a clear and descriptive title** for the issue to identify the problem.
* **Describe the exact steps which reproduce the problem** in as many details as possible.
* **Provide specific examples to demonstrate the steps.**
* **Describe the behavior you observed after following the steps** and point out what exactly is the problem with that behavior.
* **Explain which behavior you expected to see instead and why.**
* **Provide both HA and integration software version numbers.**
* **Please try to include logs**

### Getting logs from your Home Assistant

1. Enable debug logs for "tech" component by going to `Devices & Services` -> Tech Controllers and clicking on `Enable debug logging`:

    ![HA TECH LOGS](images/ha-tech-logs-ex2.png)

2. Try to trigger the issue to gather the logs.

3. Disable logging in the same place as in step 1. Download the created file and attach to the issue.

### Getting JSON data from emodul

Getting actual raw JSON data directly from emodul can be very helpful in debugging issues.

1. Go to your emodul site [emodul.pl](https://emodul.pl)/[emodul.eu](https://emodul.eu) while logged in, open Developer Tools (F12), Network tab.

2. Refresh the page and then look for XHR type request to your module id. Click on it and get the JSON response:

    ![HA TECH LOGS](images/ha-tech-logs-ex3.png)

3. Save in a file and attach to the issue or if it's too big, save in a service like [Pastebin]( https://pastebin.com) and attach the link in the issue.

### Getting HA data

Sometimes it can also be helpful to get Home Assistant config entries, device registry and entity registry to check what was ultimately created for the integration.

1. Go to `<HA installation folder>/config/.storage`.

2. Download all three files: `core.device_registry`, `core.entity_registry`, `core.config_entry`

3. Edit the files to contain only `tech` domain items.

4. :exclamation: Edit the files to remove all sensitive information like passwords :exclamation:

5. Pack the files into a .zip file and attach to the issue.

> [!CAUTION]
> :warning: Always remember to remove any sensitive and personal information from the logs! Especially remove/redact your `email`, `username`, `password`, `user_id` and `token`!.

## Developing

Dependencies are managed with [uv](https://docs.astral.sh/uv/). All dependencies and dependency groups are declared in `pyproject.toml` and pinned in `uv.lock`, so every environment installs exactly the same, reproducible set of packages.

The available dependency groups are:

* `dev` - tooling for local development (`pre-commit`, `ruff`, `colorlog`)
* `test_api` - dependencies for running the API test suite
* `test` - everything in `test_api` plus `pytest-homeassistant-custom-component` for the full component test suite

There are three supported ways to set up a development environment. All of them ultimately use `uv` to install the dependencies.

### Option 1: Dev Container

This integration follows the [Home Assistant Development Workflow](https://developers.home-assistant.io/docs/development_environment) using VSCode + [Dev Container](https://containers.dev/).

1. Install [Docker](https://www.docker.com/) and the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) VSCode extension.
2. Open the repository in VSCode and, when prompted, choose **Reopen in Container** (or run the *Dev Containers: Reopen in Container* command).

The container image already includes `uv` (added via the `uv` dev container feature) and runs `scripts/setup` on creation, which executes `uv sync --group dev --group test_api`. Once it finishes, the `.venv` is ready and selected as the interpreter. Home Assistant is forwarded on <http://localhost:8123>.

### Option 2: Local setup with uv

If you prefer to work directly on your machine, [install uv](https://docs.astral.sh/uv/getting-started/installation/) and then run:

```bash
# Install the project together with the test dependencies into .venv
uv sync --group test_api

# Run the test suite
uv run pytest tests/tests_api --cov-report=term-missing --cov=custom_components.tech.tech tests/

# Run the linter
uv run ruff check . --fix
```

`uv sync` creates and manages a local `.venv`, so there is no need to create or activate a virtual environment manually. uv also installs the correct Python version automatically (the project requires Python 3.14+). Prefix commands with `uv run` to execute them inside that environment. The convenience script `scripts/setup` runs `uv sync --group dev --group test_api`.

### Option 3: Nix with devenv

If you are using [nix](https://nixos.org/) you can use [devenv](https://devenv.sh/) and [direnv](https://direnv.net/) via the provided `devenv.nix` file.

1. Install [nix](https://nixos.org/download/), [devenv](https://devenv.sh/getting-started/) and [direnv](https://direnv.net/docs/installation.html).
2. Clone the repo, enter the directory and run `direnv allow`.

direnv enters the devenv shell automatically (configured in `.envrc`), which provisions Python and calls `uv sync` for you. The following commands are then available:

* `setup` - install the required python packages (`uv sync --group test_api`)
* `test` - run the test suite
* `lint` - run the `ruff` lint check
* `develop` - run Home Assistant with the integration (available on <http://localhost:8123>)
