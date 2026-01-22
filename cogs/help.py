import discord
from discord.ext import commands
import json
import os

GUIDE_FILE = "guide.json"


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def kilavuz_oku(self):
        if not os.path.exists(GUIDE_FILE): return {}
        with open(GUIDE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # --- MENÜ SİSTEMİ (Detaylı Kılavuz İçin) ---
    class HelpSelect(discord.ui.Select):
        def __init__(self, data):
            self.data = data
            options = [
                discord.SelectOption(label="Çekiliş Sistemi", emoji="🎉", value="çekiliş",
                                     description="Başlatma, Reroll, Şartlı Çekiliş"),
                discord.SelectOption(label="Moderasyon", emoji="🛡️", value="moderasyon",
                                     description="Ban, Kick, Mute ve Af komutları"),
                discord.SelectOption(label="Ticket (Destek)", emoji="🎫", value="ticket",
                                     description="Kurulum ve Yetkili paneli"),
                discord.SelectOption(label="Genel Ayarlar", emoji="⚙️", value="genel",
                                     description="Kanal ve Log ayarlamaları"),
                discord.SelectOption(label="Yapay Zeka", emoji="🧠", value="yapayzeka", description="Sohbet özellikleri")
            ]
            super().__init__(placeholder="Detaylı bilgi için kategori seç...", min_values=1, max_values=1,
                             options=options)

        async def callback(self, interaction: discord.Interaction):
            secim = self.values[0]
            icerik = self.data.get(secim, "Bilgi bulunamadı.")

            embed = discord.Embed(
                title=f"📘 {secim.upper()} KILAVUZU",
                description=icerik,
                color=discord.Color.from_rgb(47, 49, 54)
            )
            embed.set_thumbnail(url=interaction.client.user.avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    class HelpView(discord.ui.View):
        def __init__(self, data):
            super().__init__()
            self.add_item(Help.HelpSelect(data))

    # --- ANA DİNLEYİCİ ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.user.mentioned_in(message): return

        icerik = message.content.lower()

        # 1. DURUM: HIZLI KOMUT LİSTESİ İSTERSE ("komutlar")
        if "komutlar" in icerik or "komut listesi" in icerik or "liste" in icerik:
            embed = discord.Embed(
                title="🤖 TrAI Hızlı Komut Paneli",
                description="Botu hem **!komut** ile hem de **sohbet ederek** kullanabilirsin.",
                color=discord.Color.brand_green()
            )

            embed.add_field(
                name="🛡️ Moderasyon",
                value="`!sil 10` / `Temizle`\n`!ban @Kişi` / `Yasakla`\n`!kick @Kişi` / `At`\n`!mute @Kişi 10dk` / `Sustur`\n`!uyar @Kişi` / `İkaz et`",
                inline=True
            )

            embed.add_field(
                name="🎉 Çekiliş (Giveaway)",
                value="`@TrAI çekiliş yap 10dk Ödül`\n`@TrAI çekiliş yap 10dk Ödül @Rol`\n`@TrAI çekilişi kapat [ID]`\n`@TrAI yeniden seç`",
                inline=True
            )

            embed.add_field(
                name="🧠 Yapay Zeka & Sistem",
                value="`!unut` (Hafızayı Sıfırla)\n`@TrAI ticket sistemini kur`\n`@TrAI log kanalı burası`\n`@TrAI senin kanalın burası`",
                inline=False
            )

            embed.set_footer(text="Detaylı kullanım örnekleri için '@TrAI kılavuz' yazabilirsin.")
            await message.channel.send(embed=embed)
            return

        # 2. DURUM: DETAYLI KILAVUZ İSTERSE ("kılavuz", "yardım")
        if "yardım" in icerik or "kılavuz" in icerik or "help" in icerik:
            data = self.kilavuz_oku()
            embed = discord.Embed(
                title="📚 TrAI Detaylı Kılavuz",
                description="Hangi sistemin nasıl çalıştığını öğrenmek için **menüden seçim yap.**",
                color=discord.Color.blurple()
            )
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            await message.channel.send(embed=embed, view=self.HelpView(data))


async def setup(bot):
    await bot.add_cog(Help(bot))