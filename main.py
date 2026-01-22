from keep_alive import keep_alive
import discord
from discord.ext import commands
import os
import sys
import subprocess
from dotenv import load_dotenv


# --- 1. OTO-YÜKLEYİCİ ---
def install_package(package):
    print(f"🔧 OTO-TAMİR: '{package}' eksik, yükleniyor...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    print(f"✅ '{package}' yüklendi! Bot yeniden başlatılıyor...")
    os.execv(sys.executable, ['python'] + sys.argv)

required_packages = ["discord.py", "groq", "googlesearch-python", "requests", "beautifulsoup4", "easy-pil"]
try:
    import discord
    from groq import Groq
    from googlesearch import search
    import requests
    from bs4 import BeautifulSoup
    from easy_pil import Editor
except ImportError as e:
    missing_pkg = str(e).split("'")[-2]
    if missing_pkg == "googlesearch": missing_pkg = "googlesearch-python"
    if missing_pkg == "PIL": missing_pkg = "pillow"
    if missing_pkg == "bs4": missing_pkg = "beautifulsoup4"
    install_package(missing_pkg)

# --- 2. AYARLAR ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# 🔥 İŞTE EKSİK OLAN PARÇA BU! 🔥
bot.ai_aktif = True  # Bot varsayılan olarak KONUŞUR durumda başlasın.

# --- 3. BOT OLAYLARI ---
@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')

    # Botun durumu: "Oynuyor: @TrAI yardım | v3.0"
    await bot.change_presence(
        activity=discord.Game(name="@TrAI yardım | Yapay Zeka 🧠")
    )

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            if filename == "__init__.py": continue
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"   ➕ Yüklendi: {filename}")
            except Exception as e:
                print(f"   ❌ HATA - {filename} yüklenemedi: {e}")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ HATA: .env dosyasında DISCORD_TOKEN bulunamadı!")
    else:
        bot.run(TOKEN)