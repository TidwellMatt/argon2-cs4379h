#!/usr/bin/env bash
# Optional helper, run manually in Linux/WSL. No system-wide changes or sudo.
# Requires git, gcc and libnettle installed. Source revisions logged.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
mkdir -p native native-src
if [[ ! -d native-src/Lyra/.git ]]; then git clone https://github.com/leocalm/Lyra.git native-src/Lyra; fi
if [[ ! -d native-src/catena/.git ]]; then git clone https://github.com/medsec/catena.git native-src/catena; fi
{
  git -C native-src/Lyra rev-parse HEAD
  git -C native-src/catena rev-parse HEAD
} > native/source_revisions.txt
# Lyra2 reference, scalar single-lane, 256 columns, 96-byte blocks.
(cd native-src/Lyra/Lyra2/src && gcc -shared -fPIC -O3 -std=gnu99 -fopenmp -DnPARALLEL=1 -DN_COLS=256 -DBLOCK_LEN_INT64=12 -DSPONGE=0 -DRHO=1 Lyra2.c Sponge.c -o "$ROOT/native/liblyra2.so")
# Catena-Dragonfly reference hash (reduced round as default upstream).
(cd native-src/catena/src && gcc -shared -fPIC -O3 -std=gnu99 -fgnu89-inline -DFAST -Iblake2-ref catena.c catena-helpers.c catena-blake2b-ref.c catena-BRG.c blake2-ref/blake2b-ref.c -o "$ROOT/native/libcatena.so")
printf 'Built optional libraries. Run the self-test before any benchmark.\n'
