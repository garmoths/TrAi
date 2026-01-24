import discord
from discord.ext import commands
import json
import os
from utils.helpers import safe_load_json, safe_write_json
from utils.logger import get_logger

SETTINGS_FILE = "settings.json"


class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    def ayar_yukle(self):
        return safe_load_json(SETTINGS_FILE, {})

    def ayar_kaydet(self, veri):
        try:
            safe_write_json(SETTINGS_FILE, veri)
        except Exception:
            self.logger.exception("Ayar kaydetme hatası")

    # 🗣️ KANAL AYARLAMA
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.user.mentioned_in(message): return

        # Sadece Yönetici
        if not message.author.guild_permissions.administrator: return

        icerik = message.content.lower().replace(f"<@{self.bot.user.id}>", "").strip()
        guild_id = str(message.guild.id)
        channel_id = message.channel.id

        # KOMUT: "@TrAI senin kanalın burası"
        aktif_kelimeler = ["senin kanalın", "burada konuş", "aktif ol", "mekanın", "burası senin"]

        if any(k in icerik for k in aktif_kelimeler):
            veriler = self.ayar_yukle()
            if guild_id not in veriler: veriler[guild_id] = {}

            veriler[guild_id]["aktif_kanal"] = channel_id
            self.ayar_kaydet(veriler)

            await message.channel.send(
                f"✅ Anlaşıldı Patron! Artık sadece **{message.channel.mention}** kanalında sohbet edeceğim.\nDiğer kanallarda sadece görev (ban, mute vb.) yaparım.")


async def setup(bot):
    await bot.add_cog(Management(bot))