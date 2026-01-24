import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.logger import get_logger


class Fun(commands.Cog):
    """Eğlence komutları."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
    
    @app_commands.command(name="zar", description="🎲 Zar at")
    @app_commands.describe(
        sayı="Kaç zar (1-10)",
        yüz="Kaç yüzlü (1-100)"
    )
    async def zar(self, interaction: discord.Interaction, sayı: int = 1, yüz: int = 6):
        """Zar atar."""
        if sayı < 1 or sayı > 10:
            await interaction.response.send_message("❌ Zar sayısı 1-10 arası olmalı!", ephemeral=True)
            return
        
        if yüz < 1 or yüz > 100:
            await interaction.response.send_message("❌ Yüz sayısı 1-100 arası olmalı!", ephemeral=True)
            return
        
        zarlar = [random.randint(1, yüz) for _ in range(sayı)]
        toplam = sum(zarlar)
        
        embed = discord.Embed(
            title="🎲 Zar Atışı",
            description=f"**Zarlar:** {', '.join(map(str, zarlar))}\n**Toplam:** {toplam}",
            color=discord.Color.random()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="yazı-tura", description="🪙 Yazı-Tura at")
    async def yazi_tura(self, interaction: discord.Interaction):
        """Yazı-tura atar."""
        sonuc = random.choice(["Yazı", "Tura"])
        emoji = "📄" if sonuc == "Yazı" else "🪙"
        
        await interaction.response.send_message(f"{emoji} **{sonuc}**!")
    
    @app_commands.command(name="8ball", description="🎱 Sihirli 8ball'a sor")
    @app_commands.describe(soru="Sorun")
    async def eightball(self, interaction: discord.Interaction, soru: str):
        """8ball cevabı verir."""
        cevaplar = [
            "Kesinlikle evet", "Evet", "Büyük ihtimalle evet", "Görünüşe göre evet",
            "Belki", "Daha sonra tekrar sor", "Şimdi söyleyemem",
            "Pek sanmıyorum", "Hayır", "Kesinlikle hayır", "İmkansız",
            "Şansını başka zaman dene", "Çok şüpheli", "Kesin değil"
        ]
        
        embed = discord.Embed(
            title="🎱 Sihirli 8Ball",
            color=discord.Color.purple()
        )
        embed.add_field(name="Soru", value=soru, inline=False)
        embed.add_field(name="Cevap", value=random.choice(cevaplar), inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="seç", description="🤔 Rastgele seçim yap")
    @app_commands.describe(seçenekler="Seçenekler (virgülle ayır)")
    async def sec(self, interaction: discord.Interaction, seçenekler: str):
        """Seçeneklerden birini seçer."""
        liste = [s.strip() for s in seçenekler.split(",")]
        
        if len(liste) < 2:
            await interaction.response.send_message("❌ En az 2 seçenek girmelisin!", ephemeral=True)
            return
        
        secilen = random.choice(liste)
        
        embed = discord.Embed(
            title="🤔 Rastgele Seçim",
            description=f"**Seçtim:** {secilen}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ship", description="💕 İki kişi arasında uyum")
    @app_commands.describe(
        kişi1="İlk kişi",
        kişi2="İkinci kişi"
    )
    async def ship(self, interaction: discord.Interaction, kişi1: discord.Member, kişi2: discord.Member):
        """İki kişi arasındaki uyumu hesaplar."""
        random.seed(f"{kişi1.id}{kişi2.id}")
        uyum = random.randint(0, 100)
        random.seed()  # Reset seed
        
        if uyum >= 80:
            mesaj = "💖 Mükemmel Uyum!"
            renk = discord.Color.pink()
        elif uyum >= 60:
            mesaj = "💕 Çok İyi!"
            renk = discord.Color.red()
        elif uyum >= 40:
            mesaj = "❤️ İdare Eder"
            renk = discord.Color.orange()
        elif uyum >= 20:
            mesaj = "💔 Pek İyi Değil"
            renk = discord.Color.dark_orange()
        else:
            mesaj = "💀 Hiç Uyuşmuyor"
            renk = discord.Color.dark_red()
        
        bar_length = 10
        filled = int((uyum / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        embed = discord.Embed(
            title="💕 Ship Hesaplama",
            description=f"{kişi1.mention} 💞 {kişi2.mention}\n\n"
                        f"{bar} **{uyum}%**\n{mesaj}",
            color=renk
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="kelime-say", description="📝 Mesajdaki kelime sayısı")
    @app_commands.describe(metin="Metin")
    async def kelime_say(self, interaction: discord.Interaction, metin: str):
        """Metindeki kelime sayısını verir."""
        kelimeler = metin.split()
        karakter = len(metin)
        
        embed = discord.Embed(
            title="📝 Kelime Sayısı",
            color=discord.Color.blue()
        )
        embed.add_field(name="Kelime", value=str(len(kelimeler)), inline=True)
        embed.add_field(name="Karakter", value=str(karakter), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ters-çevir", description="🔄 Metni ters çevir")
    @app_commands.describe(metin="Çevrilecek metin")
    async def ters_cevir(self, interaction: discord.Interaction, metin: str):
        """Metni ters çevirir."""
        await interaction.response.send_message(f"🔄 **{metin[::-1]}**")
    
    @app_commands.command(name="yüzde", description="📊 Rastgele yüzde hesapla")
    @app_commands.describe(şey="Ne hakkında")
    async def yuzde(self, interaction: discord.Interaction, şey: str):
        """Rastgele yüzde hesaplar."""
        random.seed(f"{interaction.user.id}{şey}")
        yuzde = random.randint(0, 100)
        random.seed()
        
        bar_length = 10
        filled = int((yuzde / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        embed = discord.Embed(
            title="📊 Yüzde Hesaplama",
            description=f"**{interaction.user.mention}** ne kadar **{şey}**?\n\n{bar} **%{yuzde}**",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Fun(bot))
