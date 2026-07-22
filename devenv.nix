{
  pkgs,
  lib,
  config,
  ...
}: {
  name = "tech-controllers";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.ruff
    pkgs.ffmpeg
    pkgs.libpcap
    pkgs.libjpeg
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.14";
    uv.enable = true;
    uv.sync.enable = true;
    uv.sync.groups = ["test_api"];
  };

  # https://devenv.sh/scripts/
  scripts.setup = {
    exec = ''
      echo '🛠️ Running setup'
      uv sync --group test_api
    '';
    description = "Install dependencies";
  };

  scripts.develop = {
    exec = ''
      export PYTHONPATH="$PYTHONPATH:$PWD/custom_components"

      if [[ ! -d "$PWD/config" ]]; then
          mkdir -p "$PWD/config"
          hass --config "$PWD/config" --script ensure_config
      fi
      if [[ ! -L "$PWD/config/custom_components" ]]; then
          ln -s "$PWD/custom_components/" "$PWD/config/custom_components"
      fi

      exec hass --config "$PWD/config" --debug
    '';
    description = "Start Home Assistant";
  };

  scripts.tests = {
    exec = ''
      echo '🧪 Running tests'
      pytest tests/ --cov-report=term-missing --cov=custom_components.tech.tech
    '';
    description = "Test integration";
  };

  scripts.lint = {
    exec = ''
      echo '🚨 Run lint'
      ruff check . --fix
    '';
    description = "Run lint";
  };

  enterShell = ''
    echo Entering development environment for tech-controllers...
    export PYTHONPATH="$PYTHONPATH:$PWD/custom_components"

    # Remove Nix's externally-managed marker so uv can install into the venv freely
    find "$DEVENV_STATE/venv" -name "EXTERNALLY-MANAGED" -delete 2>/dev/null || true

    echo $PYTHONPATH
    echo
    echo 🦾 Available scripts:
    echo 🦾
    ${pkgs.gnused}/bin/sed -e 's| |••|g' -e 's|=| |' <<EOF | ${pkgs.util-linuxMinimal}/bin/column -t | ${pkgs.gnused}/bin/sed -e 's|^|🦾 |' -e 's|••| |g'
    ${lib.generators.toKeyValue {} (lib.mapAttrs (name: value: value.description) config.scripts)}
    EOF
    echo
  '';

  # https://devenv.sh/tests/
  enterTest = ''
    tests
  '';
}
