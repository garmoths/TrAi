import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv
from utils.logger import setup_logging, get_logger
from utils import db

# Kritik paket kontrolü
_missing = []
for _pkg, _imp in [("groq", "groq"), ("requests", "requests"), ("beautifulsoup4", "bs4")]:
    try:
        __import__(_imp)
    except ImportError:
        _missing.append(_pkg)
if _missing:
    print(f"❌ Eksik paket(ler): {', '.join(_missing)}")
    print("Çözüm: python -m pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()
setup_logging()
logger = get_logger(__name__)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

bot.ai_aktif = True

@bot.event
async def on_ready():
    logger.info(f'{bot.user} olarak giriş yapıldı!')

    await bot.change_presence(
        activity=discord.Game(name="@TrAI yardım | Yapay Zeka 🧠")
    )

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "__init__.py" and filename != "readme.py":
            ext_name = f"cogs.{filename[:-3]}"
            if ext_name in bot.extensions:
                logger.info(f"   ⏩ Zaten yüklü: {filename}")
                continue
            try:
                await bot.load_extension(ext_name)
                logger.info(f"   ➕ Yüklendi: {filename}")
            except Exception as e:
                logger.exception(f"   ❌ HATA - {filename} yüklenemedi:")

    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} slash komut Discord'a senkronize edildi!")
    except Exception as e:
        logger.error(f"❌ Slash komut sync hatası: {e}")

if __name__ == "__main__":
    db.init_db()
    if not TOKEN:
        logger.error("❌ HATA: .env dosyasında DISCORD_TOKEN bulunamadı!")
    else:
        bot.run(TOKEN)