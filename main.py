# VideoEncoder 2025 - Modern Telegram Video Encoder Bot
# Redesigned with modern architecture and enhanced features

import os
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery
)
import motor.motor_asyncio
from dotenv import load_dotenv

# ==================== CONFIGURATION ====================

load_dotenv()

@dataclass
class Config:
    """Modern configuration using dataclass"""
    API_ID: int = int(os.getenv("API_ID"))
    API_HASH: str = os.getenv("API_HASH")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    MONGO_URI: str = os.getenv("MONGO_URI")
    AUTHORIZED_USER: int = int(os.getenv("AUTHORIZED_USER"))
    
    # Directories
    DOWNLOAD_DIR: Path = Path("downloads")
    ENCODE_DIR: Path = Path("encodes")
    THUMB_DIR: Path = Path("thumbnails")
    
    def __post_init__(self):
        """Create directories if they don't exist"""
        for directory in [self.DOWNLOAD_DIR, self.ENCODE_DIR, self.THUMB_DIR]:
            directory.mkdir(exist_ok=True)

config = Config()

# ==================== LOGGING SETUP ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== DATABASE ====================

class Database:
    """Modern async database handler"""
    
    def __init__(self, uri: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client.video_encoder
        self.users = self.db.users
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
        """Set global thumbnail for user"""
        await self.update_setting(user_id, "thumbnail", file_id)
    
    async def get_thumbnail(self, user_id: int) -> Optional[str]:
        """Get user's global thumbnail"""
        settings = await self.get_user_settings(user_id)
        return settings.get("thumbnail")

db = Database(config.MONGO_URI)

# ==================== PYROGRAM CLIENT ====================

app = Client(
    "video_encoder_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# ==================== DECORATORS ====================

def authorized_only(func):
    """Decorator to restrict access to authorized user only"""
    async def wrapper(client, message):
        if message.from_user.id != config.AUTHORIZED_USER:
            await message.reply_text(
                "🚫 **Access Denied**\n\n"
                "This bot is private and only accessible to the authorized user."
            )
            return
        return await func(client, message)
    return wrapper

# ==================== UI COMPONENTS ====================

class UI:
    """Modern UI with clean button layouts"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu with modern layout"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumb"),
                InlineKeyboardButton("🗑️ Clear Thumbnail", callback_data="clear_thumb")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ])
    
    @staticmethod
    def quality_selector() -> InlineKeyboardMarkup:
        """Quality selection menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 720p", callback_data="quality_720p"),
                InlineKeyboardButton("📱 480p", callback_data="quality_480p"),
                InlineKeyboardButton("📺 360p", callback_data="quality_360p")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def settings_menu(current_quality: str) -> InlineKeyboardMarkup:
        """Settings menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"📹 Quality: {current_quality}", 
                    callback_data="change_quality"
                )
            ],
            [
                InlineKeyboardButton("✏️ Custom Name", callback_data="set_custom_name")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def cancel_button() -> InlineKeyboardMarkup:
        """Cancel button for operations"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])

ui = UI()

# ==================== VIDEO PROCESSING ====================

class VideoEncoder:
    """Modern video encoding handler"""
    
    QUALITY_PRESETS = {
        "720p": {"width": 1280, "height": 720},
        "480p": {"width": 854, "height": 480},
        "360p": {"width": 640, "height": 360}
    }
    
    @staticmethod
    async def encode_video(
        input_path: Path,
        output_path: Path,
        quality: str,
        progress_callback=None
    ) -> bool:
        """Encode video with ffmpeg"""
        try:
            preset = VideoEncoder.QUALITY_PRESETS[quality]
            
            # FFmpeg command for optimal encoding
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-vf', f'scale={preset["width"]}:{preset["height"]}:force_original_aspect_ratio=decrease',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y', str(output_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
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

# ==================== HANDLERS ====================

@app.on_message(filters.command("start") & filters.private)
@authorized_only
async def start_handler(client, message: Message):
    """Modern start command with clean UI"""
    await message.reply_text(
        "🎬 **Video Encoder Bot 2025**\n\n"
        "Welcome to your personal video encoding assistant!\n\n"
        "✨ **Features:**\n"
        "• Multiple quality presets (720p, 480p, 360p)\n"
        "• Custom file naming\n"
        "• Global thumbnail support\n"
        "• Fast H.264 encoding\n\n"
        "📤 Send me a video to get started!",
        reply_markup=ui.main_menu()
    )

@app.on_message(filters.command("help") & filters.private)
@authorized_only
async def help_handler(client, message: Message):
    """Help command"""
    help_text = """
📖 **Help & Commands**

**Basic Usage:**
1. Send any video file
2. Choose your preferred quality
3. Optionally rename the output
4. Get your encoded video!

**Commands:**
• `/start` - Show main menu
• `/help` - Show this help message
• `/setthumb` - Set global thumbnail (reply to image)
• `/delthumb` - Delete global thumbnail
• `/settings` - View current settings

**Quality Options:**
• 720p - HD quality (1280x720)
• 480p - Standard quality (854x480)
• 360p - Low quality (640x360)

**Tips:**
• Set a global thumbnail to apply to all videos
• Use custom naming for better organization
• Encoded videos use H.264 codec for compatibility
    """
    await message.reply_text(help_text)

@app.on_message(filters.command("setthumb") & filters.private)
@authorized_only
async def set_thumbnail_handler(client, message: Message):
    """Set global thumbnail"""
    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.reply_text(
            "❌ Please reply to an image with `/setthumb` to set it as your global thumbnail."
        )
        return
    
    photo = message.reply_to_message.photo[-1]
    await db.set_thumbnail(message.from_user.id, photo.file_id)
    
    await message.reply_text(
        "✅ **Thumbnail Set Successfully!**\n\n"
        "This thumbnail will be used for all your encoded videos."
    )

@app.on_message(filters.command("delthumb") & filters.private)
@authorized_only
async def delete_thumbnail_handler(client, message: Message):
    """Delete global thumbnail"""
    await db.set_thumbnail(message.from_user.id, None)
    await message.reply_text("✅ Global thumbnail deleted successfully!")

@app.on_message(filters.command("settings") & filters.private)
@authorized_only
async def settings_handler(client, message: Message):
    """Show current settings"""
    settings = await db.get_user_settings(message.from_user.id)
    
    settings_text = f"""
⚙️ **Current Settings**

📹 **Quality:** {settings['quality']}
✏️ **Custom Name:** {settings['custom_name'] or 'Not set'}
🖼️ **Thumbnail:** {'Set' if settings['thumbnail'] else 'Not set'}
🎞️ **Codec:** {settings['codec'].upper()}
⚡ **Preset:** {settings['preset']}
🎚️ **CRF:** {settings['crf']}
    """
    
    await message.reply_text(
        settings_text,
        reply_markup=ui.settings_menu(settings['quality'])
    )

@app.on_message(filters.video & filters.private)
@authorized_only
async def video_handler(client, message: Message):
    """Handle incoming videos"""
    status_msg = await message.reply_text(
        "📥 **Processing your video...**\n\n"
        "⏳ Downloading...",
        reply_markup=ui.cancel_button()
    )
    
    try:
        # Get user settings
        settings = await db.get_user_settings(message.from_user.id)
        
        # Download video
        input_path = config.DOWNLOAD_DIR / f"{message.id}_{message.video.file_name}"
        await message.download(file_name=str(input_path))
        
        await status_msg.edit_text(
            "📥 **Processing your video...**\n\n"
            "✅ Downloaded\n"
            "🔄 Encoding..."
        )
        
        # Generate output filename
        output_filename = VideoEncoder.generate_output_filename(
            message.video.file_name,
            settings['quality'],
            settings['custom_name']
        )
        output_path = config.ENCODE_DIR / output_filename
        
        # Encode video
        success = await VideoEncoder.encode_video(
            input_path,
            output_path,
            settings['quality']
        )
        
        if not success:
            await status_msg.edit_text("❌ **Encoding failed!** Please try again.")
            return
        
        await status_msg.edit_text(
            "📥 **Processing your video...**\n\n"
            "✅ Downloaded\n"
            "✅ Encoded\n"
            "📤 Uploading..."
        )
        
        # Get thumbnail
        thumb_id = await db.get_thumbnail(message.from_user.id)
        thumb_path = None
        
        if thumb_id:
            thumb_path = config.THUMB_DIR / f"{message.from_user.id}.jpg"
            await client.download_media(thumb_id, file_name=str(thumb_path))
        
        # Upload encoded video
        await message.reply_video(
            video=str(output_path),
            caption=f"✅ **Encoded to {settings['quality']}**\n\n📁 {output_filename}",
            thumb=str(thumb_path) if thumb_path else None,
            supports_streaming=True
        )
        
        await status_msg.delete()
        
        # Cleanup
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        if thumb_path:
            thumb_path.unlink(missing_ok=True)
        
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        await status_msg.edit_text(
            f"❌ **An error occurred:**\n\n`{str(e)}`"
        )

@app.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    """Handle all callback queries"""
    data = callback.data
    user_id = callback.from_user.id
    
    if user_id != config.AUTHORIZED_USER:
        await callback.answer("Access denied!", show_alert=True)
        return
    
    # Main menu
    if data == "main_menu":
        await callback.message.edit_text(
            "🎬 **Video Encoder Bot 2025**\n\n"
            "Choose an option from the menu below:",
            reply_markup=ui.main_menu()
        )
    
    # Settings
    elif data == "settings":
        settings = await db.get_user_settings(user_id)
        await callback.message.edit_text(
            "⚙️ **Settings Menu**\n\n"
            f"Current quality: **{settings['quality']}**",
            reply_markup=ui.settings_menu(settings['quality'])
        )
    
    # Change quality
    elif data == "change_quality":
        await callback.message.edit_text(
            "📹 **Select Video Quality**\n\n"
            "Choose your preferred encoding quality:",
            reply_markup=ui.quality_selector()
        )
    
    # Quality selection
    elif data.startswith("quality_"):
        quality = data.split("_")[1]
        await db.update_setting(user_id, "quality", quality)
        await callback.answer(f"✅ Quality set to {quality}", show_alert=True)
        await callback.message.edit_text(
            "⚙️ **Settings Menu**\n\n"
            f"Current quality: **{quality}**",
            reply_markup=ui.settings_menu(quality)
        )
    
    # Stats
    elif data == "stats":
        settings = await db.get_user_settings(user_id)
        stats_text = f"""
📊 **Bot Statistics**

👤 **User ID:** `{user_id}`
📹 **Default Quality:** {settings['quality']}
🖼️ **Thumbnail:** {'Set' if settings['thumbnail'] else 'Not set'}
⏰ **Bot Uptime:** Active
🔧 **Version:** 2025.1.0
        """
        await callback.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]])
        )
    
    # Thumbnail actions
    elif data == "set_thumb":
        await callback.answer(
            "Reply to an image with /setthumb command",
            show_alert=True
        )
    
    elif data == "clear_thumb":
        await db.set_thumbnail(user_id, None)
        await callback.answer("✅ Thumbnail cleared!", show_alert=True)
    
    # Help
    elif data == "help":
        await help_handler(client, callback.message)
    
    # Custom name (requires text input - would need conversation handler)
    elif data == "set_custom_name":
        await callback.answer(
            "Feature coming soon! For now, files will use original names with quality suffix.",
            show_alert=True
        )
    
    # Cancel
    elif data == "cancel":
        await callback.message.delete()

# ==================== MAIN ====================

async def main():
    """Main function to run the bot"""
    logger.info("🚀 Starting Video Encoder Bot 2025...")
    await app.start()
    logger.info("✅ Bot is running!")
    
    # Send startup notification to authorized user
    try:
        await app.send_message(
            config.AUTHORIZED_USER,
            "🚀 **Bot Started Successfully!**\n\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "✅ All systems operational"
        )
    except Exception as e:
        logger.warning(f"Could not send startup notification: {e}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
