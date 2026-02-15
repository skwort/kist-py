{
  description = "Kist – Lightweight component library manager for KiCad";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    python = pkgs.python313;
  in {
    packages.${system} = rec {
      kist = python.pkgs.buildPythonApplication {
        pname = "kist";
        version = "0.1.0";
        pyproject = true;

        src = ./.;

        build-system = [ python.pkgs.hatchling ];

        # nixpkgs versions lag slightly behind uv pins
        pythonRelaxDeps = true;

        dependencies = with python.pkgs; [
          typer
          rich
          pydantic
          httpx
          textual
          structlog
          platformdirs
          tomlkit
        ];

        doCheck = false;
      };
      default = kist;
    };

    devShells.${system}.default = pkgs.mkShell {
      nativeBuildInputs = with pkgs; [
        # Python
        uv
        python313
        ruff

        # Tools
        jq
        just
        prek
      ];

      shellHook = ''
        echo "kip dev env"
      '';
    };
  };
}
