#!/bin/sh
set -eu

case "$(uname -m)" in
  x86_64|amd64) artifact="atlas-of-threads-linux-x86_64" ;;
  *)
    echo "Atlas of Threads currently provides a Linux x86_64 package." >&2
    exit 1
    ;;
esac

download_base="${ATLAS_DOWNLOAD_BASE_URL:-https://downloads.atlasofthreads.com/releases/latest}"
port="${ATLAS_PORT:-7462}"
install_root="${XDG_DATA_HOME:-$HOME/.local/share}/atlas-of-threads"
binary="$install_root/atlas-of-threads"
store="$install_root/personal-atlas"
service_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
service="$service_root/atlas-of-threads.service"
desktop_root="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
unit_path="$(printf '%s' "$PATH" | sed 's/%/%%/g; s/\\/\\\\/g; s/"/\\"/g')"

echo "Installing Atlas of Threads…"
curl -fsSL "$download_base/$artifact" -o "$temporary/$artifact"
curl -fsSL "$download_base/$artifact.sha256" -o "$temporary/$artifact.sha256"
(cd "$temporary" && sha256sum -c "$artifact.sha256")

mkdir -p "$install_root" "$service_root" "$desktop_root"
install -m 0755 "$temporary/$artifact" "$binary"

cat > "$service" <<EOF
[Unit]
Description=Atlas of Threads local application

[Service]
Type=simple
Environment=TA_WORKER_BACKEND=systemd
Environment="PATH=$unit_path"
ExecStart="$binary" --store "$store" launch --no-browser --port $port
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

cat > "$desktop_root/atlas-of-threads.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Atlas of Threads
Comment=Enter an idea. Walk its architecture.
Exec=env TA_WORKER_BACKEND=application "$binary" --store "$store" launch --port $port
Terminal=false
Categories=Education;Utility;
EOF

if systemctl --user daemon-reload >/dev/null 2>&1 &&
   systemctl --user enable --now atlas-of-threads.service >/dev/null 2>&1; then
  systemctl --user restart atlas-of-threads.service >/dev/null 2>&1
else
  TA_WORKER_BACKEND=application nohup "$binary" --store "$store" launch --no-browser --port "$port" \
    > "$install_root/atlas.log" 2>&1 &
fi

url="http://127.0.0.1:$port/"
attempt=0
while [ "$attempt" -lt 30 ]; do
  if curl -fsS "$url/api/sessions" >/dev/null 2>&1; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 0.2
done

echo
echo "Atlas of Threads is ready:"
printf '\033]8;;%s\033\\%s\033]8;;\033\\\n' "$url" "$url"
