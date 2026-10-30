#!/usr/bin/env bash
# Encodes frames from record.ts into the portal preview videos (H.264 MP4, no audio).
set -euo pipefail
cd "$(dirname "$0")"
FFMPEG="${FFMPEG:-$HOME/.local/ffmpeg/ffmpeg}"
mkdir -p ../../portals/videos
for v in landscape portrait; do
  "$FFMPEG" -hide_banner -loglevel error -y -framerate 30 -i "frames/$v/frame-%05d.jpg" \
    -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart -an \
    "../../portals/videos/preview-$v.mp4"
  echo "wrote portals/videos/preview-$v.mp4"
done
