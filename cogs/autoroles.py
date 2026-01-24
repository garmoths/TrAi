import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from utils.logger import get_logger
from utils import db


class AutoRoles(commands.Cog):
    """Otomatik rol verme sistemi - Üye katılınca otomatik rol."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    def get_autorole_settings(self, guild_id):
        """Sunucunun autorole ayarlarını getirir."""
        settings = db.kv_get("settings", {}) or {}
        guild_settings = settings.get(str(guild_id), {})
        
        return {
            "enabled": guild_settings.get("autorole_enabled", False),
            "roles": guild_settings.get("autorole_roles", []),
            "bot_roles": guild_settings.get("autorole_bot_roles", []),
            "delay": guild_settings.get("autorole_delay", 0),
        }
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Üye katılınca otomatik rol ver."""
        settings = self.get_autorole_settings(member.guild.id)
        
        if not settings["enabled"]:
            return
        
        if settings["delay"] > 0:
            await asyncio.sleep(settings["delay"])
        
        if member.bot:
            role_ids = settings["bot_roles"]
        else:
            role_ids = settings["roles"]
        
        if not role_ids:
            return
        
        for role_id in role_ids:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role, reason="AutoRole")
                    self.logger.info(f"AutoRole verildi: {member} -> {role.name}")
                except Exception as e:
                    self.logger.error(f"AutoRole hatası: {e}")
    
    @app_commands.command(name="autorole", description="🤖 Otomatik rol sistemini aç/kapat")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(durum="Açık/Kapalı")
    async def autorole_toggle(self, interaction: discord.Interaction, durum: bool):
        """AutoRole sistemini açar/kapatır."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["autorole_enabled"] = durum
        db.kv_set("settings", settings)
        
        status = "**açıldı** ✅" if durum else "**kapatıldı** ❌"
        await interaction.response.send_message(f"🤖 AutoRole sistemi {status}")
    
    @app_commands.command(name="autorole-rol-ekle", description="➕ AutoRole'e rol ekler")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        rol="Eklenecek rol",
        bot_için="Bu rol sadece botlar için mi? (varsayılan: Hayır)"
    )
    async def autorole_rol_ekle(
        self,
        interaction: discord.Interaction,
        rol: discord.Role,
        bot_için: bool = False
    ):
        """AutoRole listesine rol ekler."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        key = "autorole_bot_roles" if bot_için else "autorole_roles"
        
        if key not in settings[str(interaction.guild.id)]:
            settings[str(interaction.guild.id)][key] = []
        
        if rol.id in settings[str(interaction.guild.id)][key]:
            await interaction.response.send_message(
                f"❌ {rol.mention} zaten listede!",
                ephemeral=True
            )
            return
        
        settings[str(interaction.guild.id)][key].append(rol.id)
        db.kv_set("settings", settings)
        
        tip = "**bot** 🤖" if bot_için else "**normal üye** 👤"
        await interaction.response.send_message(
            f"✅ {rol.mention} AutoRole listesine eklendi! ({tip})"
        )
    
    @app_commands.command(name="autorole-rol-sil", description="➖ AutoRole'den rol siler")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        rol="Silinecek rol",
        bot_için="Bu rol bot listesinden mi silinecek?"
    )
    async def autorole_rol_sil(
        self,
        interaction: discord.Interaction,
        rol: discord.Role,
        bot_için: bool = False
    ):
        """AutoRole listesinden rol siler."""
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            await interaction.response.send_message(
                "❌ AutoRole ayarı yok!",
                ephemeral=True
            )
            return
        
        key = "autorole_bot_roles" if bot_için else "autorole_roles"
        
        if key not in settings[str(interaction.guild.id)] or rol.id not in settings[str(interaction.guild.id)][key]:
            await interaction.response.send_message(
                f"❌ {rol.mention} listede değil!",
                ephemeral=True
            )
            return
        
        settings[str(interaction.guild.id)][key].remove(rol.id)
        db.kv_set("settings", settings)
        
        await interaction.response.send_message(
            f"✅ {rol.mention} AutoRole listesinden silindi!"
        )
    
    @app_commands.command(name="autorole-delay", description="⏱️ AutoRole gecikmesini ayarlar")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(saniye="Kaç saniye sonra rol verilsin (0 = anında)")
    async def autorole_delay(self, interaction: discord.Interaction, saniye: int):
        """AutoRole delay ayarlar."""
        if saniye < 0 or saniye > 3600:
            await interaction.response.send_message(
                "❌ Gecikme 0-3600 saniye arasında olmalı!",
                ephemeral=True
            )
            return
        
        settings = db.kv_get("settings", {}) or {}
        
        if str(interaction.guild.id) not in settings:
            settings[str(interaction.guild.id)] = {}
        
        settings[str(interaction.guild.id)]["autorole_delay"] = saniye
        db.kv_set("settings", settings)
        
        if saniye == 0:
            await interaction.response.send_message("⚡ AutoRole artık **anında** çalışacak!")
        else:
            await interaction.response.send_message(f"⏱️ AutoRole **{saniye} saniye** sonra çalışacak!")
    
    @app_commands.command(name="autorole-durum", description="📊 AutoRole ayarlarını gösterir")
    async def autorole_durum(self, interaction: discord.Interaction):
        """AutoRole durumunu gösterir."""
        settings = self.get_autorole_settings(interaction.guild.id)
        
        embed = discord.Embed(
            title="📊 AutoRole Durumu",
            color=discord.Color.green() if settings["enabled"] else discord.Color.red()
        )
        
        status = "✅ Açık" if settings["enabled"] else "❌ Kapalı"
        embed.add_field(name="Durum", value=status, inline=True)
        embed.add_field(name="Gecikme", value=f"{settings['delay']} saniye", inline=True)
        
        normal_roles = []
        for role_id in settings["roles"]:
            role = interaction.guild.get_role(role_id)
            if role:
                normal_roles.append(role.mention)
        
        if normal_roles:
            embed.add_field(
                name="👤 Normal Üyeler",
                value="\n".join(normal_roles),
                inline=False
            )
        
        bot_roles = []
        for role_id in settings["bot_roles"]:
            role = interaction.guild.get_role(role_id)
            if role:
                bot_roles.append(role.mention)
        
        if bot_roles:
            embed.add_field(
                name="🤖 Botlar",
                value="\n".join(bot_roles),
                inline=False
            )
        
        if not normal_roles and not bot_roles:
            embed.description = "⚠️ Henüz rol eklenmemiş!"
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AutoRoles(bot))
