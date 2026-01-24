import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from utils.logger import get_logger
from utils import db


class ReactionRoles(commands.Cog):
    """Reaction roles sistemi - Emoji'ye basınca rol al/bırak."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    def get_reaction_roles(self, guild_id):
        """Sunucunun reaction role ayarlarını getirir."""
        data = db.kv_get("reaction_roles", {}) or {}
        return data.get(str(guild_id), {})
    
    def save_reaction_roles(self, guild_id, data):
        """Reaction role ayarlarını kaydeder."""
        all_data = db.kv_get("reaction_roles", {}) or {}
        all_data[str(guild_id)] = data
        db.kv_set("reaction_roles", all_data)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Reaction eklendiğinde rol ver."""
        if payload.member.bot:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        rr_data = self.get_reaction_roles(payload.guild_id)
        message_key = f"{payload.channel_id}_{payload.message_id}"
        
        if message_key not in rr_data:
            return
        
        emoji_str = str(payload.emoji)
        role_id = rr_data[message_key].get("roles", {}).get(emoji_str)
        
        if not role_id:
            return
        
        role = guild.get_role(int(role_id))
        if not role:
            return
        
        try:
            # Unique mode kontrolü
            if rr_data[message_key].get("unique", False):
                # Önce bu mesajdaki diğer rolleri çıkar
                for emoji, rid in rr_data[message_key].get("roles", {}).items():
                    if emoji != emoji_str:
                        other_role = guild.get_role(int(rid))
                        if other_role and other_role in payload.member.roles:
                            await payload.member.remove_roles(other_role)
            
            await payload.member.add_roles(role, reason="Reaction role")
            self.logger.info(f"Reaction role verildi: {payload.member} -> {role.name}")
        except Exception as e:
            self.logger.error(f"Reaction role verme hatası: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Reaction kaldırıldığında rolü çıkar."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        
        rr_data = self.get_reaction_roles(payload.guild_id)
        message_key = f"{payload.channel_id}_{payload.message_id}"
        
        if message_key not in rr_data:
            return
        
        emoji_str = str(payload.emoji)
        role_id = rr_data[message_key].get("roles", {}).get(emoji_str)
        
        if not role_id:
            return
        
        role = guild.get_role(int(role_id))
        if not role:
            return
        
        try:
            await member.remove_roles(role, reason="Reaction role kaldırıldı")
            self.logger.info(f"Reaction role çıkarıldı: {member} -> {role.name}")
        except Exception as e:
            self.logger.error(f"Reaction role çıkarma hatası: {e}")
    
    @app_commands.command(name="reactionrole-kur", description="🎭 Reaction role mesajı oluşturur")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        kanal="Mesajın gönderileceği kanal",
        başlık="Embed başlığı",
        açıklama="Embed açıklaması",
        unique="Sadece 1 rol seçilebilir mi? (varsayılan: Hayır)"
    )
    async def reactionrole_kur(
        self, 
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        başlık: str,
        açıklama: str,
        unique: bool = False
    ):
        """Reaction role mesajı oluşturur."""
        embed = discord.Embed(
            title=başlık,
            description=açıklama,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Emoji'ye tıklayarak rol alabilirsin!")
        
        msg = await kanal.send(embed=embed)
        
        # Veritabanına kaydet
        rr_data = self.get_reaction_roles(interaction.guild.id)
        message_key = f"{kanal.id}_{msg.id}"
        rr_data[message_key] = {
            "roles": {},
            "unique": unique,
            "message_id": msg.id,
            "channel_id": kanal.id
        }
        self.save_reaction_roles(interaction.guild.id, rr_data)
        
        mode = "**Unique mode** (Sadece 1 rol)" if unique else "**Multiple mode** (Çoklu rol)"
        await interaction.response.send_message(
            f"✅ Reaction role mesajı oluşturuldu!\n"
            f"📍 {kanal.mention}\n"
            f"🔗 [Mesaja Git]({msg.jump_url})\n"
            f"⚙️ Mod: {mode}\n\n"
            f"Şimdi `/reactionrole-ekle` ile emoji ve rol ekleyin!",
            ephemeral=True
        )
    
    @app_commands.command(name="reactionrole-ekle", description="➕ Mesaja emoji ve rol ekler")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        mesaj_id="Reaction role mesajının ID'si",
        emoji="Kullanılacak emoji",
        rol="Verilecek rol"
    )
    async def reactionrole_ekle(
        self,
        interaction: discord.Interaction,
        mesaj_id: str,
        emoji: str,
        rol: discord.Role
    ):
        """Reaction role mesajına emoji + rol ekler."""
        rr_data = self.get_reaction_roles(interaction.guild.id)
        
        # Mesajı bul
        message_key = None
        for key, value in rr_data.items():
            if str(value["message_id"]) == mesaj_id:
                message_key = key
                break
        
        if not message_key:
            await interaction.response.send_message(
                "❌ Bu ID'ye sahip reaction role mesajı bulunamadı!",
                ephemeral=True
            )
            return
        
        # Rolü ekle
        rr_data[message_key]["roles"][emoji] = rol.id
        self.save_reaction_roles(interaction.guild.id, rr_data)
        
        # Mesaja emoji ekle
        try:
            channel = interaction.guild.get_channel(rr_data[message_key]["channel_id"])
            message = await channel.fetch_message(int(mesaj_id))
            await message.add_reaction(emoji)
        except Exception as e:
            self.logger.error(f"Emoji ekleme hatası: {e}")
        
        await interaction.response.send_message(
            f"✅ {emoji} → {rol.mention} eklendi!",
            ephemeral=True
        )
    
    @app_commands.command(name="reactionrole-sil", description="🗑️ Mesajdan emoji ve rol siler")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        mesaj_id="Reaction role mesajının ID'si",
        emoji="Silinecek emoji"
    )
    async def reactionrole_sil(
        self,
        interaction: discord.Interaction,
        mesaj_id: str,
        emoji: str
    ):
        """Reaction role'den emoji + rol siler."""
        rr_data = self.get_reaction_roles(interaction.guild.id)
        
        message_key = None
        for key, value in rr_data.items():
            if str(value["message_id"]) == mesaj_id:
                message_key = key
                break
        
        if not message_key or emoji not in rr_data[message_key]["roles"]:
            await interaction.response.send_message(
                "❌ Bu emoji bulunamadı!",
                ephemeral=True
            )
            return
        
        del rr_data[message_key]["roles"][emoji]
        self.save_reaction_roles(interaction.guild.id, rr_data)
        
        # Mesajdan emoji'yi kaldır
        try:
            channel = interaction.guild.get_channel(rr_data[message_key]["channel_id"])
            message = await channel.fetch_message(int(mesaj_id))
            await message.clear_reaction(emoji)
        except Exception:
            pass
        
        await interaction.response.send_message(
            f"✅ {emoji} silindi!",
            ephemeral=True
        )
    
    @app_commands.command(name="reactionrole-liste", description="📋 Sunucudaki tüm reaction role'leri listeler")
    async def reactionrole_liste(self, interaction: discord.Interaction):
        """Reaction role listesi."""
        rr_data = self.get_reaction_roles(interaction.guild.id)
        
        if not rr_data:
            await interaction.response.send_message(
                "❌ Bu sunucuda reaction role yok.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📋 Reaction Roles",
            color=discord.Color.blue()
        )
        
        for key, value in rr_data.items():
            channel_id = value["channel_id"]
            message_id = value["message_id"]
            unique = value.get("unique", False)
            
            roles_text = []
            for emoji, role_id in value["roles"].items():
                role = interaction.guild.get_role(role_id)
                if role:
                    roles_text.append(f"{emoji} → {role.mention}")
            
            mode = "🔒 Unique" if unique else "✨ Multiple"
            embed.add_field(
                name=f"Mesaj ID: {message_id}",
                value=f"{mode}\n<#{channel_id}>\n" + "\n".join(roles_text[:5]),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
