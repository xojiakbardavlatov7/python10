
import asyncio
import logging
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest



TOKEN = ("8809466266:AAGRfkX8dpRDiu88fqH1zAHmOddJehNcmXA")
MAX_SIZE = 49 * 1024 * 1024  # 49 MB

if not TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida topilmadi")

dp = Dispatcher()

ALLOWED_DOMAINS = {
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "pinterest.com",
    "pin.it",
}

URL_PATTERN = re.compile(r"https?://[^\s<>]+")


def valid_domain(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        return (
            parsed.scheme in ("http", "https")
            and any(
                host == domain or host.endswith("." + domain)
                for domain in ALLOWED_DOMAINS
            )
        )
    except ValueError:
        return False


def download_video(url: str, folder: str):
    options = {
        "format": (
            "best[ext=mp4][height<=720][filesize<49M]/"
            "best[height<=720][filesize<49M]/"
            "best[height<=480]/best"
        ),
        "outtmpl": os.path.join(folder, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 3,
        "merge_output_format": "mp4",
        "max_filesize": MAX_SIZE,
        "restrictfilenames": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    if not info:
        raise RuntimeError("Video ma'lumotlari olinmadi")

    files = [
        path for path in Path(folder).iterdir()
        if path.is_file()
        and path.suffix.lower() in {
            ".mp4", ".mkv", ".webm", ".mov"
        }
    ]

    if not files:
        raise RuntimeError("Video fayli topilmadi")

    video = max(files, key=lambda p: p.stat().st_size)

    if video.stat().st_size > MAX_SIZE:
        raise ValueError("Video 49 MB dan katta")

    title = info.get("title") or "Video"

    return video, title


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🎬 Video yuklovchi botga xush kelibsiz!\n\n"
        "📸 Instagram\n"
        "▶️ YouTube\n"
        "📌 Pinterest\n\n"
        "🔗 Video havolasini yuboring.\n"
        "📥 Men videoni yuklab beraman!"
    )


@dp.message(F.text)
async def video_handler(message: Message):
    text = message.text or ""
    match = URL_PATTERN.search(text)

    if not match:
        await message.answer(
            "❌ Iltimos, video havolasini yuboring."
        )
        return

    url = match.group(0).rstrip(".,)")

    if not valid_domain(url):
        await message.answer(
            "❌ Faqat Instagram, YouTube va "
            "Pinterest havolalari qabul qilinadi."
        )
        return

    status = await message.answer(
        "⏳ Video yuklanmoqda, kuting..."
    )

    try:
        with tempfile.TemporaryDirectory() as folder:
            video, title = await asyncio.to_thread(
                download_video, url, folder
            )

            await status.edit_text(
                "📤 Video Telegramga yuborilmoqda..."
            )

            caption = f"🎬 {title[:850]}"

            if video.suffix.lower() == ".mp4":
                try:
                    await message.answer_video(
                        video=FSInputFile(video),
                        caption=caption,
                        supports_streaming=True,
                    )
                except TelegramBadRequest:
                    await message.answer_document(
                        document=FSInputFile(video),
                        caption=caption,
                    )
            else:
                await message.answer_document(
                    document=FSInputFile(video),
                    caption=caption,
                )

        await status.delete()

    except ValueError as error:
        await status.edit_text(f"❌ {error}")

    except yt_dlp.utils.DownloadError:
        logging.exception("Yuklab olishda xatolik")
        await status.edit_text(
            "❌ Video yuklanmadi.\n"
            "Havola ochiq ekanini tekshiring. "
            "Platforma ushbu videoni cheklagan bo'lishi mumkin."
        )

    except Exception:
        logging.exception("Kutilmagan xatolik")
        await status.edit_text(
            "❌ Xatolik yuz berdi. Keyinroq urinib ko'ring."
        )


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=TOKEN)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
