#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 2. Create a bin directory for tools
mkdir -p bin

# 3. Download static FFmpeg
if [ ! -f bin/ffmpeg ]; then
    echo "Downloading FFmpeg..."
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar -xJ -C bin --strip-components=1 "ffmpeg-*-amd64-static/ffmpeg" "ffmpeg-*-amd64-static/ffprobe"
    chmod +x bin/ffmpeg
    chmod +x bin/ffprobe
    echo "FFmpeg installed to $(pwd)/bin"
fi
