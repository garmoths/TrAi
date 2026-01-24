import discord
from discord.ext import commands
import json
import datetime
from utils import db
from utils.logger import get_logger

# Pillow/easy_pil (optional)
try:
    from easy_pil import Editor, Canvas, Font, load_image_async
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

SETTINGS_FILE = "settings.json"


class Systems(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    def ayar_getir(self, guild_id, key):
        data = db.kv_get("settings", {}) or {}
        return data.get(str(guild_id), {}).get(key, False)

    # 👋 AKILLI RESİMLİ HOŞGELDİN
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Pillow yoksa resim özelliğini kapat
        if not HAS_PILLOW:
            self.logger.debug("Pillow yüklü değil, welcome image devre dışı")
            return
        
        # 1. Panelden özellik açık mı kontrol et
        if not self.ayar_getir(member.guild.id, "hosgeldin_resmi"):
            return

        # 2. Kanalı Otomatik Bul (Akıllı Arama)
        channel = None

        # Öncelikli İsim Listesi (En sık kullanılanlar)
        olasi_isimler = [
            "hosgeldin", "hoşgeldin",
            "gelen-giden", "gelenler",
            "welcome", "giriş-çıkış",
            "kayıt-odası", "welcome-to-server"
        ]

        # A) Tam Eşleşme Ara (Örn: kanal adı direkt "hosgeldin" ise)
        for isim in olasi_isimler:
            channel = discord.utils.get(member.guild.text_channels, name=isim)
            if channel: break

        # B) Eğer bulamazsa, içinde geçen kelimeye bak (Örn: "👋-hosgeldin-kardes")
        if not channel:
            for ch in member.guild.text_channels:
                if "hosgeldin" in ch.name.lower() or "hoşgeldin" in ch.name.lower() or "welcome" in ch.name.lower():
                    channel = ch
                    break

        # Hala kanal yoksa pes et
        if not channel:
            self.logger.warning(f"{member.guild.name} sunucunda uygun bir hoşgeldin kanalı bulunamadı.")
            return

        # 3. Resmi Hazırla
        background = Editor(Canvas((900, 300), color="#23272A"))

        try:
            profile_image = await load_image_async(str(member.avatar.url))
            profile = Editor(profile_image).resize((200, 200)).circle_image()
            background.paste(profile, (50, 50))
        except Exception as e:
            self.logger.debug("Failed to load welcome profile image: %s", e)

        try:
            font_big = Font.poppins(size=50, variant="bold")
            font_small = Font.poppins(size=30, variant="regular")
        except:
            self.logger.debug("Failed to load fonts for welcome image")
            font_big = None
            font_small = None

        background.text((300, 80), "HOŞGELDİN", color="#FFFFFF", font=font_big)
        background.text((300, 150), f"{member.name}", color="#00ffcc", font=font_big)
        background.text((300, 220), f"Seninle {len(member.guild.members)}. kişiyiz!", color="#AAAAAA", font=font_small)

        file = discord.File(fp=background.image_bytes, filename="welcome.png")
        await channel.send(f"👋 Aramıza hoşgeldin {member.mention}!", file=file)

    # 🛡️ OTO-MODERASYON (Link, Caps, Küfür)
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return

        icerik = message.content.lower()
        guild_id = str(message.guild.id)

        # LINK ENGEL
        if self.ayar_getir(guild_id, "link_engel"):
            if "discord.gg" in icerik or "http" in icerik or ".com" in icerik:
                if message.author.guild_permissions.manage_messages: return
                await message.delete()
                msg = await message.channel.send(f"🚫 {message.author.mention}, reklam yasak!")
                await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
                await msg.delete()
                return

        # CAPS ENGEL
        if self.ayar_getir(guild_id, "caps_engel"):
            if len(message.content) > 6 and message.content.isupper():
                if message.author.guild_permissions.manage_messages: return
                await message.delete()
                msg = await message.channel.send(f"🔠 {message.author.mention}, sakin ol şampiyon!")
                await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
                await msg.delete()
                return

        # KÜFÜR ENGEL
        if self.ayar_getir(guild_id, "kufur_engel"):
            yasakli = ["küfür1", "küfür2", "mk", "aq"]
            if any(k in icerik.split() for k in yasakli):
                if message.author.guild_permissions.manage_messages: return
                await message.delete()
                await message.channel.send(f"🤬 {message.author.mention}, o kelimeler yakışmıyor!", delete_after=3)


async def setup(bot):
    await bot.add_cog(Systems(bot))