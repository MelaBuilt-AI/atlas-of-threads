#!/bin/sh
set -eu

here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
magick -background none "$here/atlas-of-threads.svg" \
  -define icon:auto-resize=256,128,64,48,32,24,16 \
  "$here/atlas-of-threads.ico"

corner="$(magick "$here/atlas-of-threads.ico[0]" -format '%[pixel:p{0,0}]' info:)"
case "$corner" in
  *",0)"|*",0.0)"|*",0%") ;;
  *) echo "icon corner is not transparent: $corner" >&2; exit 1 ;;
esac
