import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import get_logger
from utils import db
import datetime


class Polls(commands.Cog):
    """Anket sistemi."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    @app_commands.command(name="anket", description="📊 Anket oluştur")
    @app_commands.describe(
        soru="Anket sorusu",
        secenek1="1. seçenek",
        secenek2="2. seçenek",
        secenek3="3. seçenek (opsiyonel)",
        secenek4="4. seçenek (opsiyonel)",
        secenek5="5. seçenek (opsiyonel)",
        süre="Anket süresi (örn: 5m, 2h, 1d)"
    )
    async def anket(
        self,
        interaction: discord.Interaction,
        soru: str,
        secenek1: str,
        secenek2: str,
        secenek3: str = None,
        secenek4: str = None,
        secenek5: str = None,
        süre: str = None
    ):
        """Anket oluşturur."""
        secenekler = [secenek1, secenek2]
        if secenek3:
            secenekler.append(secenek3)
        if secenek4:
            secenekler.append(secenek4)
        if secenek5:
            secenekler.append(secenek5)
        
        emojiler = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        
        embed = discord.Embed(
            title="📊 " + soru,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        description = ""
        for i, secenek in enumerate(secenekler):
            description += f"{emojiler[i]} {secenek}\n"
        
        embed.description = description
        embed.set_footer(text=f"Anket: {interaction.user.name}")
        
        if süre:
            try:
                amount = int(süre[:-1])
                unit = süre[-1].lower()
                
                multipliers = {
                    'm': 60,
                    'h': 3600,
                    'd': 86400
                }
                
                if unit in multipliers:
                    seconds = amount * multipliers[unit]
                    end_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                    
                    if unit == 'm':
                        time_str = f"{amount} dakika"
                    elif unit == 'h':
                        time_str = f"{amount} saat"
                    else:
                        time_str = f"{amount} gün"
                    
                    embed.add_field(
                        name="⏰ Süre",
                        value=f"{time_str} ({end_time.strftime('%d.%m.%Y %H:%M')})",
                        inline=False
                    )
            except:
                pass
        
        await interaction.response.send_message(embed=embed)
        
        message = await interaction.original_response()
        
        # Emojileri ekle
        for i in range(len(secenekler)):
            await message.add_reaction(emojiler[i])
    
    @app_commands.command(name="evet-hayır", description="✅ Evet/Hayır anketi")
    @app_commands.describe(soru="Soru")
    async def evet_hayir(self, interaction: discord.Interaction, soru: str):
        """Basit evet/hayır anketi oluşturur."""
        embed = discord.Embed(
            title="📊 " + soru,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.set_footer(text=f"Anket: {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)
        
        message = await interaction.original_response()
        await message.add_reaction("✅")
        await message.add_reaction("❌")


async def setup(bot):
    await bot.add_cog(Polls(bot))
