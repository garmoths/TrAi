import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import get_logger
from utils import db
import datetime


class Suggestions(commands.Cog):
    """Öneri sistemi - Kullanıcılar öneri gönderebilir."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    def get_suggestion_settings(self, guild_id):
        """Öneri sistemi ayarlarını getirir."""
        settings = db.kv_get("settings", {}) or {}
        guild_settings = settings.get(str(guild_id), {})
        
        return {
            "enabled": guild_settings.get("suggestions_enabled", False),
            "channel_id": guild_settings.get("suggestions_channel"),
        }
    
    @app_commands.command(name="öneri", description="💡 Öneri gönder")
    @app_commands.describe(öneri="Önerin")
    async def oneri(self, interaction: discord.Interaction, öneri: str):
        """Öneri gönderir."""
        settings = self.get_suggestion_settings(interaction.guild.id)
        
        if not settings["enabled"] or not settings["channel_id"]:
            await interaction.response.send_message(
                "❌ Öneri sistemi bu sunucuda kapalı!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(settings["channel_id"])
        if not channel:
            await interaction.response.send_message(
                "❌ Öneri kanalı bulunamadı!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="💡 Yeni Öneri",
            description=öneri,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text=f"Kullanıcı ID: {interaction.user.id}")
        
        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        
        await interaction.response.send_message(
            f"✅ Önerini gönderdim! {channel.mention}",
            ephemeral=True
        )
    
    @app_commands.command(name="öneri-sistem", description="⚙️ Öneri sistemini kur/aç/kapat")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        durum="Açık/Kapalı",
        kanal="Öneri kanalı"
    )
    async def oneri_sistem(
        self,
        interaction: discord.Interaction,
        durum: bool,
        kanal: discord.TextChannel = None
    ):
        """Öneri sistemini ayarlar."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["suggestions_enabled"] = durum
        
        if kanal:
            settings[str(interaction.guild.id)]["suggestions_channel"] = kanal.id
        
        db.kv_set("settings", settings)
        
        status = "**açıldı** ✅" if durum else "**kapatıldı** ❌"
        msg = f"💡 Öneri sistemi {status}"
        
        if kanal:
            msg += f"\n📍 Kanal: {kanal.mention}"
        
        await interaction.response.send_message(msg)
    
    @app_commands.command(name="öneri-durum", description="🔄 Önerinin durumunu değiştir")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        mesaj_id="Öneri mesajının ID'si",
        durum="Onaylandı/Reddedildi/Düşünülüyor",
        sebep="Açıklama (opsiyonel)"
    )
    async def oneri_durum(
        self,
        interaction: discord.Interaction,
        mesaj_id: str,
        durum: str,
        sebep: str = None
    ):
        """Önerinin durumunu günceller."""
        settings = self.get_suggestion_settings(interaction.guild.id)
        
        if not settings["channel_id"]:
            await interaction.response.send_message(
                "❌ Öneri kanalı ayarlanmamış!",
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(settings["channel_id"])
        
        try:
            message = await channel.fetch_message(int(mesaj_id))
        except:
            await interaction.response.send_message(
                "❌ Mesaj bulunamadı!",
                ephemeral=True
            )
            return
        
        embed = message.embeds[0]
        
        if durum.lower() in ["onay", "onaylandı", "approved"]:
            embed.color = discord.Color.green()
            embed.title = "✅ Öneri Onaylandı"
        elif durum.lower() in ["red", "reddedildi", "rejected"]:
            embed.color = discord.Color.red()
            embed.title = "❌ Öneri Reddedildi"
        else:
            embed.color = discord.Color.orange()
            embed.title = "🤔 Öneri Düşünülüyor"
        
        if sebep:
            embed.add_field(name="Yetkili Notu", value=sebep, inline=False)
        
        embed.set_footer(text=f"Yetkili: {interaction.user.name} | {embed.footer.text}")
        
        await message.edit(embed=embed)
        await interaction.response.send_message("✅ Öneri güncellendi!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
