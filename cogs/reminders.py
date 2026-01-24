import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import get_logger
from utils import db
import datetime
import asyncio


class Reminders(commands.Cog):
    """Hatırlatma sistemi."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
        self.bot.loop.create_task(self.check_reminders())
    
    async def check_reminders(self):
        """Hatırlatmaları kontrol eder."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                reminders = db.kv_get("reminders", {}) or {}
                current_time = datetime.datetime.now().timestamp()
                
                to_remove = []
                
                for reminder_id, reminder in reminders.items():
                    if reminder["time"] <= current_time:
                        try:
                            user = await self.bot.fetch_user(reminder["user_id"])
                            
                            embed = discord.Embed(
                                title="⏰ Hatırlatma",
                                description=reminder["message"],
                                color=discord.Color.blue(),
                                timestamp=datetime.datetime.now()
                            )
                            
                            if "channel_id" in reminder:
                                try:
                                    channel = self.bot.get_channel(reminder["channel_id"])
                                    await channel.send(user.mention, embed=embed)
                                except:
                                    await user.send(embed=embed)
                            else:
                                await user.send(embed=embed)
                            
                            to_remove.append(reminder_id)
                        except Exception as e:
                            self.logger.error(f"Hatırlatma gönderme hatası: {e}")
                            to_remove.append(reminder_id)
                
                # Tamamlananları sil
                for reminder_id in to_remove:
                    reminders.pop(reminder_id, None)
                
                if to_remove:
                    db.kv_set("reminders", reminders)
                
            except Exception as e:
                self.logger.error(f"Hatırlatma kontrol hatası: {e}")
            
            await asyncio.sleep(10)  # Her 10 saniyede bir kontrol et
    
    @app_commands.command(name="hatırlat", description="⏰ Hatırlatma kur")
    @app_commands.describe(
        süre="Süre (örn: 10s, 5m, 2h, 1d)",
        mesaj="Hatırlatma mesajı"
    )
    async def hatirlat(
        self,
        interaction: discord.Interaction,
        süre: str,
        mesaj: str
    ):
        """Hatırlatma kurar."""
        # Süreyi parse et
        try:
            amount = int(süre[:-1])
            unit = süre[-1].lower()
            
            multipliers = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400
            }
            
            if unit not in multipliers:
                raise ValueError("Geçersiz zaman birimi")
            
            seconds = amount * multipliers[unit]
            
            if seconds < 10:
                await interaction.response.send_message(
                    "❌ Minimum hatırlatma süresi 10 saniyedir!",
                    ephemeral=True
                )
                return
            
            if seconds > 2592000:  # 30 gün
                await interaction.response.send_message(
                    "❌ Maximum hatırlatma süresi 30 gündür!",
                    ephemeral=True
                )
                return
            
        except:
            await interaction.response.send_message(
                "❌ Geçersiz süre formatı! Örnek: `10s`, `5m`, `2h`, `1d`",
                ephemeral=True
            )
            return
        
        reminders = db.kv_get("reminders", {}) or {}
        
        reminder_id = f"{interaction.user.id}_{int(datetime.datetime.now().timestamp())}"
        
        reminders[reminder_id] = {
            "user_id": interaction.user.id,
            "message": mesaj,
            "time": datetime.datetime.now().timestamp() + seconds,
            "channel_id": interaction.channel.id
        }
        
        db.kv_set("reminders", reminders)
        
        # Süreyi formatla
        if unit == 's':
            time_str = f"{amount} saniye"
        elif unit == 'm':
            time_str = f"{amount} dakika"
        elif unit == 'h':
            time_str = f"{amount} saat"
        else:
            time_str = f"{amount} gün"
        
        await interaction.response.send_message(
            f"⏰ Tamam! Seni **{time_str}** sonra hatırlatacağım.\n"
            f"📝 Mesaj: {mesaj}"
        )
    
    @app_commands.command(name="hatırlatmalarım", description="📋 Aktif hatırlatmalarını göster")
    async def hatirlatmalarim(self, interaction: discord.Interaction):
        """Kullanıcının aktif hatırlatmalarını gösterir."""
        reminders = db.kv_get("reminders", {}) or {}
        
        user_reminders = [
            (rid, r) for rid, r in reminders.items() 
            if r["user_id"] == interaction.user.id
        ]
        
        if not user_reminders:
            await interaction.response.send_message(
                "❌ Hiç aktif hatırlatman yok!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="⏰ Aktif Hatırlatmalar",
            color=discord.Color.blue()
        )
        
        for reminder_id, reminder in sorted(user_reminders, key=lambda x: x[1]["time"]):
            time_left = reminder["time"] - datetime.datetime.now().timestamp()
            
            if time_left < 60:
                time_str = f"{int(time_left)} saniye"
            elif time_left < 3600:
                time_str = f"{int(time_left / 60)} dakika"
            elif time_left < 86400:
                time_str = f"{int(time_left / 3600)} saat"
            else:
                time_str = f"{int(time_left / 86400)} gün"
            
            embed.add_field(
                name=f"📝 {reminder['message'][:50]}",
                value=f"⏰ {time_str} sonra",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reminders(bot))
