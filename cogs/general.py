import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="yardim", aliases=["yardım", "help"])
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🤖 TrAI Asistan - Komut Listesi",
            description="Merhaba! İşte şu an kullanabileceğin komutlar:",
            color=discord.Color.dark_blue()
        )

        # 1. BÖLÜM: YAPAY ZEKA
        embed.add_field(
            name="🧠 Yapay Zeka & Sohbet",
            value="• **Sohbet:** Beni etiketle veya direkt yaz. (Örn: *Naber?* veya *Dolar kaç?*)\n"
                  "• `!panel` : AI kontrol panelini açar.\n"
                  "• `!unut` : Sohbet geçmişimizi temizler.",
            inline=False
        )

        # 2. BÖLÜM: MODERASYON (Şu an aktif olanlar)
        embed.add_field(
            name="🛡️ Moderasyon (Yetkili)",
            value="• `!sil [sayı]` : Belirtilen sayıda mesajı temizler.\n"
                  "• `!at @kisi [sebep]` : Kullanıcıyı sunucudan atar (Kick).\n"
                  "• `!yasakla @kisi [sebep]` : Kullanıcıyı yasaklar (Ban).\n"
                  "• `!kaldır [ID]` : Kullanıcının yasağını kaldırır (Unban).\n"
                  "• `!uyar @kisi [sebep]` : Kullanıcıya özelden resmi uyarı atar.",
            inline=False
        )

        # 3. BÖLÜM: DİĞER
        embed.add_field(
            name="⚙️ Sistem",
            value="• `!ping` : Botun gecikme süresini gösterir.",
            inline=False
        )

        # Footer (Alt Bilgi)
        embed.set_footer(text=f"İsteyen: {ctx.author.name} | TrAI Bot Sürüm 1.0",
                         icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        # Botun avatarı varsa embed'in sağına koy
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="ping")
    async def ping(self, ctx):
        await ctx.reply(f"🏓 Pong! Gecikmem: **{round(self.bot.latency * 1000)}ms**")


async def setup(bot):
    await bot.add_cog(General(bot))