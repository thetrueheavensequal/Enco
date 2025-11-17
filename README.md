# 🎬 Video Encoder Bot 2025

A modern, efficient Telegram bot for encoding videos with multiple quality presets, custom naming, and global thumbnail support.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

## ✨ Features

- 🎯 **Multiple Quality Presets**: 720p, 480p, 360p
- ✏️ **Custom File Naming**: Rename videos during encoding
- 🖼️ **Global Thumbnail Support**: Set one thumbnail for all videos
- ⚡ **Fast H.264 Encoding**: Optimized for speed and quality
- 🔒 **Single User Access**: Private bot for personal use
- 🎨 **Modern UI**: Clean, intuitive button-based interface
- 💾 **MongoDB Storage**: Persistent user settings
- 📊 **Real-time Progress**: Track download, encoding, and upload progress

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- FFmpeg installed on your system
- MongoDB database (free tier available at MongoDB Atlas)
- Telegram API credentials

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/video-encoder-bot-2025.git
cd video-encoder-bot-2025
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install FFmpeg**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

4. **Configure the bot**

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here
AUTHORIZED_USER=your_telegram_user_id
MONGO_URI=your_mongodb_connection_string
```

5. **Run the bot**
```bash
python bot.py
```

## 📖 Usage

### Basic Workflow

1. **Start the bot**: Send `/start` command
2. **Send a video**: Upload any video file
3. **Choose quality**: Bot uses your default quality setting (changeable in settings)
4. **Receive encoded video**: Get your optimized video back

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Show main menu |
| `/help` | Display help message |
| `/settings` | View current settings |
| `/setthumb` | Set global thumbnail (reply to image) |
| `/delthumb` | Delete global thumbnail |

### Settings

Access settings from the main menu to configure:
- **Video Quality**: Choose between 720p, 480p, or 360p
- **Custom Naming**: Set default name prefix (coming soon)
- **Thumbnail**: Set/clear global thumbnail

## 🔧 Configuration

### Quality Presets

| Preset | Resolution | Use Case |
|--------|-----------|----------|
| 720p | 1280x720 | HD quality for most uses |
| 480p | 854x480 | Balanced quality and size |
| 360p | 640x360 | Smallest file size |

### Encoding Settings

The bot uses optimized FFmpeg settings:
- **Video Codec**: H.264 (libx264)
- **Preset**: Medium (balance speed/quality)
- **CRF**: 23 (good quality)
- **Audio Codec**: AAC at 128k
- **Compatibility**: Optimized for all devices

## 🏗️ Architecture

```
video-encoder-bot-2025/
├── bot.py                 # Main bot file
├── .env                   # Configuration (not in git)
├── .env.example          # Configuration template
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── downloads/           # Temporary download folder
├── encodes/             # Temporary encode folder
└── thumbnails/          # Thumbnail storage
```

## 🔐 Security

- **Single User Access**: Only the authorized user ID can use the bot
- **Private Operations**: No data shared with other users
- **Local Processing**: Videos processed on your server
- **Automatic Cleanup**: Temporary files deleted after processing

## 📊 Database Schema

### Settings Collection

```json
{
  "user_id": 123456789,
  "quality": "720p",
  "custom_name": null,
  "thumbnail": "file_id_here",
  "codec": "h264",
  "preset": "medium",
  "crf": 23
}
```

## 🐛 Troubleshooting

### Common Issues

**Bot doesn't respond:**
- Check if bot token is correct
- Verify AUTHORIZED_USER ID is correct
- Ensure bot is running (`python bot.py`)

**Encoding fails:**
- Verify FFmpeg is installed: `ffmpeg -version`
- Check disk space availability
- Review logs in `bot.log`

**Database errors:**
- Verify MongoDB URI is correct
- Check network connectivity
- Ensure database user has write permissions

## 🚀 Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Build and run:
```bash
docker build -t video-encoder-bot .
docker run -d --env-file .env video-encoder-bot
```

### Systemd Service (Linux)

Create `/etc/systemd/system/video-encoder-bot.service`:

```ini
[Unit]
Description=Video Encoder Bot 2025
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/video-encoder-bot-2025
ExecStart=/usr/bin/python3 /path/to/video-encoder-bot-2025/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable video-encoder-bot
sudo systemctl start video-encoder-bot
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Contact: your@email.com

## 🌟 Acknowledgments

- Original Video Encoder Bot by WeebTime
- Pyrogram framework
- FFmpeg for video processing
- MongoDB for data storage

## 📈 Changelog

### Version 2025.1.0 (Current)
- Complete rewrite with modern architecture
- Single-user authorization system
- Global thumbnail support
- Multiple quality presets
- Clean, modern UI with inline buttons
- Improved error handling
- Async/await throughout
- MongoDB integration
- Real-time progress tracking

---

Made with ❤️ for efficient video encoding
