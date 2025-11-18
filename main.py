# bot.py - Video Encoder Bot 2025 - Webhook Mode for Render
# Fixed version with proper webhook handling

import os
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import time
import math
import subprocess
import json

from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Update
)
import motor.motor_asyncio
from dotenv import load_dotenv
from flask import Flask, request

# ==================== CONFIGURATION ====================

load_dotenv()

@dataclass
class Config:
    """Bot configuration"""
    API_ID: int = int(os.getenv("API_ID"))
    API_HASH: str = os.getenv("API_HASH")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    MONGO_URI: str = os.getenv("MONGO_URI")
    WEBHOOK_URL: str = os.getenv("RENDER_EXTERNAL_URL", "")
    PORT: int = int(os.getenv("PORT", 10000))
    
    # Directories
    DOWNLOAD_DIR: Path = Path("/tmp/downloads")
    ENCODE_DIR: Path = Path("/tmp/encodes")
    THUMB_DIR: Path = Path("/tmp/thumbnails")
    
    def __post_init__(self):
        """Create directories"""
        for directory in [self.DOWNLOAD_DIR, self.ENCODE_DIR, self.THUMB_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

config = Config()

# ==================== LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================

flask_app = Flask(__name__)

# Global variable for the bot client
bot = None

@flask_app.route('/')
def health_check():
    """Health check endpoint"""
    return {'status': 'ok', 'bot': 'running'}, 200

@flask_app.route('/health')
def health():
    """Alternative health endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200

@flask_app.route(f'/webhook/{config.BOT_TOKEN}', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        if request.headers.get('content-type') == 'application/json':
            update = request.get_json(force=True)
            logger.info(f"Received update: {json.dumps(update)[:100]}...")
            
            if bot:
                # Create update object and process it
                asyncio.run(bot.handle_raw_update(update))
            
            return 'OK', 200
        else:
            logger.error("Invalid content type")
            return 'Invalid content type', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return str(e), 500

# ==================== DATABASE ====================

class Database:
    """Database handler"""
    
    def __init__(self, uri: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client.video_encoder
        self.settings = self.db.settings
    
    async def get_user_settings(self, user_id: int) -> dict:
        """Get user settings with defaults"""
        settings = await self.settings.find_one({"user_id": user_id})
        if not settings:
            default_settings = {
                "user_id": user_id,
                "quality": "720p",
                "custom_name": None,
                "thumbnail": None,
                "codec": "h264",
                "preset": "medium",
                "crf": 23
            }
            await self.settings.insert_one(default_settings)
            return default_settings
        return settings
    
    async def update_setting(self, user_id: int, key: str, value):
        """Update a specific setting"""
        await self.settings.update_one(
            {"user_id": user_id},
            {"$set": {key: value}},
            upsert=True
        )
    
    async def set_thumbnail(self, user_id: int, file_id: str):
        """Set global thumbnail"""
        await self.update_setting(user_id, "thumbnail", file_id)
    
    async def get_thumbnail(self, user_id: int) -> Optional[str]:
        """Get user's thumbnail"""
        settings = await self.get_user_settings(user_id)
        return settings.get("thumbnail")

db = Database(config.MONGO_URI)

# ==================== UTILITIES ====================

def format_time(seconds: int) -> str:
    """Format seconds to readable time"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def format_bytes(size: int) -> str:
    """Format bytes to readable size"""
    if size == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_names[i]}"

async def progress_callback(current, total, message, start_time, text):
    """Progress callback for upload/download"""
    now = time.time()
    diff = now - start_time
    
    if diff < 3:
        return
    
    percentage = current * 100 / total
    speed = current / diff
    eta = (total - current) / speed if speed > 0 else 0
    
    progress_bar = "".join(["█" for _ in range(math.floor(percentage / 10))])
    progress_bar += "".join(["░" for _ in range(10 - math.floor(percentage / 10))])
    
    progress_text = (
        f"{text}\n\n"
        f"[{progress_bar}] {percentage:.1f}%\n\n"
        f"📊 {format_bytes(current)} / {format_bytes(total)}\n"
        f"⚡ Speed: {format_bytes(int(speed))}/s\n"
        f"⏱️ ETA: {format_time(eta)}"
    )
    
    try:
        await message.edit_text(progress_text)
    except:
        pass

# ==================== UI COMPONENTS ====================

class UI:
    """UI Components"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumb"),
                InlineKeyboardButton("🗑️ Clear Thumb", callback_data="clear_thumb")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ])
    
    @staticmethod
    def quality_selector() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 720p", callback_data="quality_720p"),
                InlineKeyboardButton("📱 480p", callback_data="quality_480p"),
                InlineKeyboardButton("📺 360p", callback_data="quality_360p")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="settings")
            ]
        ])
    
    @staticmethod
    def settings_menu(current_quality: str, has_thumb: bool) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"📹 Quality: {current_quality}", 
                    callback_data="change_quality"
                )
            ],
            [
                InlineKeyboardButton(
                    f"🖼️ Thumbnail: {'✅' if has_thumb else '❌'}", 
                    callback_data="thumb_info"
                )
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def cancel_button() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])

ui = UI()

# ==================== VIDEO ENCODING ====================

class VideoEncoder:
    """Video encoding handler"""
    
    QUALITY_PRESETS = {
        "720p": {"width": 1280, "height": 720, "bitrate": "2000k"},
        "480p": {"width": 854, "height": 480, "bitrate": "1000k"},
        "360p": {"width": 640, "height": 360, "bitrate": "500k"}
    }
    
    @staticmethod
    async def get_video_info(file_path: str) -> dict:
        """Get video information"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            str(file_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)
            
            duration = float(info['format'].get('duration', 0))
            size = int(info['format'].get('size', 0))
            
            for stream in info['streams']:
                if stream['codec_type'] == 'video':
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    return {
                        'duration': duration,
                        'size': size,
                        'width': width,
                        'height': height
                    }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
        
        return {'duration': 0, 'size': 0, 'width': 0, 'height': 0}
    
    @staticmethod
    async def encode_video(
        input_path: Path,
        output_path: Path,
        quality: str,
        progress_msg: Message
    ) -> bool:
        """Encode video with FFmpeg"""
        try:
            preset = VideoEncoder.QUALITY_PRESETS[quality]
            
            # Get video duration for progress
            info = await VideoEncoder.get_video_info(str(input_path))
            total_duration = info['duration']
            
            # FFmpeg command
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-vf', f'scale={preset["width"]}:{preset["height"]}:force_original_aspect_ratio=decrease',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-progress', 'pipe:1',
                '-y', str(output_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress
            start_time = time.time()
            last_update = 0
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line = line.decode().strip()
                
                # Parse time from ffmpeg output
                if line.startswith('out_time_ms='):
                    try:
                        time_ms = int(line.split('=')[1])
                        current_time = time_ms / 1000000
                        
                        if total_duration > 0:
                            percentage = (current_time / total_duration) * 100
                            
                            # Update every 5 seconds
                            now = time.time()
                            if now - last_update >= 5:
                                progress_bar = "".join(["█" for _ in range(math.floor(percentage / 10))])
                                progress_bar += "".join(["░" for _ in range(10 - math.floor(percentage / 10))])
                                
                                await progress_msg.edit_text(
                                    f"🔄 **Encoding Video**\n\n"
                                    f"[{progress_bar}] {percentage:.1f}%\n\n"
                                    f"⏱️ Time: {format_time(current_time)} / {format_time(total_duration)}\n"
                                    f"📹 Quality: {quality}"
                                )
                                last_update = now
                    except:
                        pass
            
            await process.wait()
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return False
    
    @staticmethod
    def generate_output_filename(
        original_name: str,
        quality: str,
        custom_name: Optional[str] = None
    ) -> str:
        """Generate output filename"""
        if custom_name:
            base = custom_name
        else:
            base = Path(original_name).stem
        
        return f"{base}_{quality}.mp4"

encoder = VideoEncoder()

# ==================== BOT INITIALIZATION ====================

def create_bot():
    """Create and configure the bot"""
    global bot
    
    bot = Client(
        "video_encoder_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        workdir="/tmp"
    )
    
    # Register handlers
    
    @bot.on_message(filters.command("start") & filters.private)
    async def start_handler(client, message: Message):
        """Start command"""
        logger.info(f"Received /start from user {message.from_user.id}")
        await message.reply_text(
            "🎬 **Video Encoder Bot 2025**\n\n"
            "Welcome! I'm a video encoding assistant.\n\n"
            "✨ **Features:**\n"
            "• Multiple quality presets (720p, 480p, 360p)\n"
            "• Global thumbnail support\n"
            "• Fast H.264 encoding\n\n"
            "📤 **Send me a video to get started!**",
            reply_markup=ui.main_menu()
        )
    
    @bot.on_message(filters.command("help") & filters.private)
    async def help_handler(client, message: Message):
        """Help command"""
        help_text = """
📖 **Help & Commands**

**Commands:**
• `/start` - Show main menu
• `/help` - Show this help
• `/settings` - View/change settings
• `/setthumb` - Set thumbnail (reply to image)
• `/delthumb` - Delete thumbnail

**Quality Options:**
• **720p** - HD quality
• **480p** - Standard quality
• **360p** - Low quality

**How to use:**
1. Send any video file
2. Bot encodes it automatically
3. Get your optimized video back!
        """
        await message.reply_text(help_text, reply_markup=ui.main_menu())
    
    @bot.on_message(filters.command("settings") & filters.private)
    async def settings_handler(client, message: Message):
        """Settings command"""
        user_id = message.from_user.id
        settings = await db.get_user_settings(user_id)
        
        await message.reply_text(
            f"⚙️ **Current Settings**\n\n"
            f"📹 **Quality:** {settings['quality']}\n"
            f"🖼️ **Thumbnail:** {'Set ✅' if settings['thumbnail'] else 'Not set ❌'}",
            reply_markup=ui.settings_menu(settings['quality'], bool(settings['thumbnail']))
        )
    
    @bot.on_message(filters.command("setthumb") & filters.private)
    async def set_thumbnail_handler(client, message: Message):
        """Set thumbnail"""
        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply_text(
                "❌ **Please reply to an image** with `/setthumb`."
            )
            return
        
        photo = message.reply_to_message.photo[-1]
        await db.set_thumbnail(message.from_user.id, photo.file_id)
        
        await message.reply_text(
            "✅ **Thumbnail Set Successfully!**",
            reply_markup=ui.main_menu()
        )
    
    @bot.on_message(filters.command("delthumb") & filters.private)
    async def delete_thumbnail_handler(client, message: Message):
        """Delete thumbnail"""
        await db.set_thumbnail(message.from_user.id, None)
        await message.reply_text(
            "✅ **Thumbnail deleted!**",
            reply_markup=ui.main_menu()
        )
    
    @bot.on_message(filters.video & filters.private)
    async def video_handler(client, message: Message):
        """Handle video uploads"""
        logger.info(f"Video received from user {message.from_user.id}")
        
        status_msg = await message.reply_text(
            "📥 **Processing Video**\n\n⏳ Initializing...",
            reply_markup=ui.cancel_button()
        )
        
        start_time = time.time()
        input_path = None
        output_path = None
        thumb_path = None
        
        try:
            # Get settings
            settings = await db.get_user_settings(message.from_user.id)
            
            # Download video
            await status_msg.edit_text("📥 **Downloading Video**\n\n⏳ Please wait...")
            
            input_path = config.DOWNLOAD_DIR / f"{message.id}_{message.video.file_name}"
            
            download_start = time.time()
            await message.download(
                file_name=str(input_path),
                progress=progress_callback,
                progress_args=(status_msg, download_start, "📥 **Downloading Video**")
            )
            
            # Generate output filename
            output_filename = encoder.generate_output_filename(
                message.video.file_name,
                settings['quality'],
                settings['custom_name']
            )
            output_path = config.ENCODE_DIR / output_filename
            
            # Encode
            await status_msg.edit_text(
                "🔄 **Encoding Video**\n\n"
                f"📹 Quality: {settings['quality']}\n"
                "⏳ This may take a while..."
            )
            
            success = await encoder.encode_video(
                input_path,
                output_path,
                settings['quality'],
                status_msg
            )
            
            if not success:
                await status_msg.edit_text("❌ **Encoding failed!** Please try again.")
                return
            
            # Get thumbnail
            thumb_id = await db.get_thumbnail(message.from_user.id)
            if thumb_id:
                thumb_path = config.THUMB_DIR / f"{message.from_user.id}.jpg"
                await client.download_media(thumb_id, file_name=str(thumb_path))
            
            # Upload
            await status_msg.edit_text("📤 **Uploading**\n\n⏳ Please wait...")
            
            upload_start = time.time()
            total_time = time.time() - start_time
            
            caption = (
                f"✅ **Encoded Successfully!**\n\n"
                f"📁 **File:** `{output_filename}`\n"
                f"📹 **Quality:** {settings['quality']}\n"
                f"⏱️ **Time:** {format_time(total_time)}\n"
                f"📊 **Size:** {format_bytes(output_path.stat().st_size)}"
            )
            
            await message.reply_video(
                video=str(output_path),
                caption=caption,
                thumb=str(thumb_path) if thumb_path and thumb_path.exists() else None,
                supports_streaming=True,
                progress=progress_callback,
                progress_args=(status_msg, upload_start, "📤 **Uploading Video**")
            )
            
            await status_msg.delete()
            
        except Exception as e:
            logger.error(f"Video processing error: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")
        
        finally:
            # Cleanup
            if input_path and input_path.exists():
                input_path.unlink()
            if output_path and output_path.exists():
                output_path.unlink()
            if thumb_path and thumb_path.exists():
                thumb_path.unlink()
    
    @bot.on_callback_query()
    async def callback_handler(client, callback: CallbackQuery):
        """Handle callbacks"""
        data = callback.data
        user_id = callback.from_user.id
        
        logger.info(f"Callback received: {data} from user {user_id}")
        
        if data == "main_menu":
            await callback.message.edit_text(
                "🎬 **Video Encoder Bot 2025**\n\nChoose an option:",
                reply_markup=ui.main_menu()
            )
        
        elif data == "settings":
            settings = await db.get_user_settings(user_id)
            await callback.message.edit_text(
                "⚙️ **Settings**\n\n"
                f"Current quality: **{settings['quality']}**",
                reply_markup=ui.settings_menu(settings['quality'], bool(settings['thumbnail']))
            )
        
        elif data == "change_quality":
            await callback.message.edit_text(
                "📹 **Select Video Quality**",
                reply_markup=ui.quality_selector()
            )
        
        elif data.startswith("quality_"):
            quality = data.split("_")[1]
            await db.update_setting(user_id, "quality", quality)
            await callback.answer(f"✅ Quality set to {quality}", show_alert=True)
            
            settings = await db.get_user_settings(user_id)
            await callback.message.edit_text(
                "⚙️ **Settings**\n\n"
                f"Quality updated to **{quality}**",
                reply_markup=ui.settings_menu(quality, bool(settings['thumbnail']))
            )
        
        elif data == "stats":
            settings = await db.get_user_settings(user_id)
            stats_text = (
                f"📊 **Bot Statistics**\n\n"
                f"👤 **User ID:** `{user_id}`\n"
                f"📹 **Default Quality:** {settings['quality']}\n"
                f"🖼️ **Thumbnail:** {'Set ✅' if settings['thumbnail'] else 'Not set ❌'}\n"
                f"🔧 **Version:** 2025.1.0"
            )
            await callback.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]])
            )
        
        elif data == "set_thumb":
            await callback.answer(
                "Reply to an image with /setthumb command",
                show_alert=True
            )
        
        elif data == "clear_thumb":
            await db.set_thumbnail(user_id, None)
            await callback.answer("✅ Thumbnail cleared!", show_alert=True)
            await callback.message.edit_text(
                "🎬 **Video Encoder Bot 2025**\n\nThumbnail cleared!",
                reply_markup=ui.main_menu()
            )
        
        elif data == "help":
            await callback.message.edit_text(
                "📖 **Help**\n\nSend a video to encode it!\nUse /settings to change quality.",
                reply_markup=ui.main_menu()
            )
        
        elif data == "thumb_info":
            settings = await db.get_user_settings(user_id)
            if settings['thumbnail']:
                await callback.answer("✅ Thumbnail is set", show_alert=True)
            else:
                await callback.answer("❌ No thumbnail set", show_alert=True)
        
        elif data == "cancel":
            await callback.message.delete()
    
    return bot

# ==================== MAIN ====================

async def setup_webhook():
    """Set up webhook"""
    if not config.WEBHOOK_URL:
        logger.error("❌ RENDER_EXTERNAL_URL not set!")
        return False
    
    webhook_url = f"{config.WEBHOOK_URL}/webhook/{config.BOT_TOKEN}"
    
    try:
        await bot.set_webhook(webhook_url)
        webhook_info = await bot.get_webhook_info()
        logger.info(f"✅ Webhook set: {webhook_info.url}")
        logger.info(f"   Pending updates: {webhook_info.pending_update_count}")
        if webhook_info.last_error_message:
            logger.warning(f"   Last error: {webhook_info.last_error_message}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
        return False

def run_flask():
    """Run Flask in main thread"""
    flask_app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=False,
        use_reloader=False
    )

async def main():
    """Main async function"""
    logger.info("🚀 Starting Video Encoder Bot 2025...")
    logger.info(f"📋 Configuration:")
    logger.info(f"   API_ID: {config.API_ID}")
    logger.info(f"   BOT_TOKEN: ...{config.BOT_TOKEN[-10:]}")
    logger.info(f"   WEBHOOK_URL: {config.WEBHOOK_URL}")
    logger.info(f"   PORT: {config.PORT}")
    
    # Create bot instance
    create_bot()
    
    # Start bot
    await bot.start()
    logger.info(f"✅ Bot started: @{(await bot.get_me()).username}")
    
    # Set up webhook
    webhook_ok = await setup_webhook()
    if not webhook_ok:
        logger.error("❌ Webhook setup failed!")
        return
    
    logger.info("✅ Bot is ready and listening for webhooks!")
    logger.info(f"🌐 Flask running on port {config.PORT}")
    
    # Keep bot running
    await idle()

if __name__ == "__main__":
    # Run Flask in a thread and bot in main thread
    import threading
    
    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run bot in main thread
    asyncio.run(main())
