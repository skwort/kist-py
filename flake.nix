{
  description = "KIP development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    devShells.${system}.default = pkgs.mkShell {
      nativeBuildInputs = with pkgs; [
        # Python
        uv
        python313
        ruff

        # Tools
        jq
        just
      ];

      shellHook = ''
        echo "kip dev env"
      '';
    };
  };
}
