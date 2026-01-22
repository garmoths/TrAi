import discord
from discord.ext import commands
import os

README_FILE = "readme.txt"


class Readme(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def dosyayi_gonder(self, channel):
        """Readme dosyasını belirtilen kanala gönderir."""
        if not os.path.exists(README_FILE):
            return  # Dosya yoksa işlem yapma

        with open(README_FILE, "rb") as f:
            await channel.send(
                content="👋 **Merhaba! Ben TrAI.**\n\n"
                        "Sunucunuza yeni katıldım (veya beni çağırdınız). "
                        "Tüm özelliklerimi, komutlarımı ve nasıl çalıştığımı öğrenmek için "
                        "aşağıdaki **Kullanım Kılavuzu** dosyasını indirip okuyabilirsiniz. 👇",
                file=discord.File(f, "TrAI_Kullanim_Kilavuzu.txt")
            )

    # --- 1. SUNUCUYA KATILINCA OTOMATİK AT ---
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Mesaj atılabilecek ilk kanalı bul
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            await self.dosyayi_gonder(guild.system_channel)
        else:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await self.dosyayi_gonder(channel)
                    break

    # --- 2. KOMUT İLE İSTE ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.user.mentioned_in(message): return

        icerik = message.content.lower()
        tetikleyiciler = ["kılavuzu gönder", "beni oku", "readme", "nasıl kullanılır", "dosyayı at"]

        if any(t in icerik for t in tetikleyiciler):
            await self.dosyayi_gonder(message.channel)


async def setup(bot):
    await bot.add_cog(Readme(bot))