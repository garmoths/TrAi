import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv
from utils.logger import setup_logging, get_logger
from utils import db

missing_pkgs = []
try:
    import discord
except ImportError:
    missing_pkgs.append("discord.py")
try:
    from groq import Groq
except ImportError:
    missing_pkgs.append("groq")
try:
    from googlesearch import search
except ImportError:
    missing_pkgs.append("googlesearch-python")
try:
    import requests
except ImportError:
    missing_pkgs.append("requests")
try:
    from bs4 import BeautifulSoup
except ImportError:
    missing_pkgs.append("beautifulsoup4")

if missing_pkgs:
    print("❌ Eksik paket(ler) tespit edildi:", ", ".join(missing_pkgs))
    print("Lütfen aşağıdaki komutu çalıştırın ve tekrar deneyin:")
    print("python -m pip install -r requirements.txt")
    import sys
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