import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import get_logger


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

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

    # =========================================================================
    # SLASH KOMUTLAR
    # =========================================================================

    @app_commands.command(name="yardım", description="📖 Bot komutlarını ve özelliklerini gösterir")
    async def yardim_slash(self, interaction: discord.Interaction):
        """Slash komut ile yardım menüsü."""
        embed = discord.Embed(
            title="🤖 TrAI Asistan - Komut Rehberi",
            description="Discord'un modern slash komut sistemini kullanıyoruz! `/` yazarak tüm komutları görebilirsin.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🧠 Yapay Zeka",
            value=(
                "• Beni etiketle veya direkt yaz\n"
                "• `/panel` - Sunucu ayar paneli\n"
                "• `!unut` - Sohbet geçmişini sil"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Moderasyon",
            value=(
                "• `/sil` - Mesajları toplu sil\n"
                "• `/uyar` - Kullanıcı uyar\n"
                "• `/ban` - Kullanıcı yasakla\n"
                "• `/kick` - Kullanıcı at\n"
                "• `/sustur` - Geçici sustur\n"
                "• `/uyarilar` - Uyarı listesi"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Level & Sıralama",
            value=(
                "• `/level` - Seviyeni gör\n"
                "• `/rank` - Sıralamadaki yerin\n"
                "• `/lider-tablosu` - En yüksek seviyeler"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Bilgi",
            value=(
                "• `/ping` - Bot gecikmesi\n"
                "• `/sunucu-bilgi` - Sunucu istatistikleri\n"
                "• `/kullanıcı-bilgi` - Kullanıcı profili\n"
                "• `/avatar` - Avatar göster"
            ),
            inline=False
        )

        embed.set_footer(text=f"TrAI Bot | {interaction.user.name} tarafından istendi")
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="🏓 Botun gecikme süresini gösterir")
    async def ping_slash(self, interaction: discord.Interaction):
        """Slash komut ile ping."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Gecikmem: **{latency}ms**", ephemeral=True)

    @app_commands.command(name="sunucu-bilgi", description="📊 Sunucu hakkında detaylı bilgi gösterir")
    async def sunucu_bilgi_slash(self, interaction: discord.Interaction):
        """Sunucu bilgilerini gösterir."""
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.purple()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="👑 Sahip", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="🆔 ID", value=guild.id, inline=True)
        embed.add_field(name="📅 Kurulma", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        
        embed.add_field(name="👥 Üyeler", value=guild.member_count, inline=True)
        embed.add_field(name="💬 Kanallar", value=len(guild.channels), inline=True)
        embed.add_field(name="🎭 Roller", value=len(guild.roles), inline=True)
        
        embed.add_field(name="😀 Emojiler", value=len(guild.emojis), inline=True)
        embed.add_field(name="🚀 Boost", value=f"Seviye {guild.premium_tier} ({guild.premium_subscription_count} boost)", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kullanıcı-bilgi", description="👤 Bir kullanıcı hakkında bilgi gösterir")
    @app_commands.describe(kullanıcı="Bilgisi görüntülenecek kullanıcı (boş bırakılırsa kendin)")
    async def kullanici_bilgi_slash(self, interaction: discord.Interaction, kullanıcı: discord.Member = None):
        """Kullanıcı bilgilerini gösterir."""
        user = kullanıcı or interaction.user
        
        embed = discord.Embed(
            title=f"👤 {user.name}",
            color=user.color
        )
        
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        embed.add_field(name="🆔 ID", value=user.id, inline=True)
        embed.add_field(name="📅 Hesap Açılışı", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="📆 Sunucuya Katılma", value=f"<t:{int(user.joined_at.timestamp())}:R>", inline=True)
        
        roles = [role.mention for role in user.roles[1:]]  # @everyone hariç
        if roles:
            embed.add_field(name=f"🎭 Roller ({len(roles)})", value=" ".join(roles[:10]), inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="🖼️ Kullanıcının avatarını gösterir")
    @app_commands.describe(kullanıcı="Avatarı görüntülenecek kullanıcı")
    async def avatar_slash(self, interaction: discord.Interaction, kullanıcı: discord.Member = None):
        """Kullanıcı avatarını gösterir."""
        user = kullanıcı or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {user.name} - Avatar",
            color=discord.Color.blue()
        )
        
        if user.avatar:
            embed.set_image(url=user.avatar.url)
            embed.add_field(name="🔗 Link", value=f"[Tıkla]({user.avatar.url})", inline=False)
        else:
            embed.description = "❌ Bu kullanıcının avatarı yok."
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))