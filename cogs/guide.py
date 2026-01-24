import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import json
from utils.logger import get_logger

GUIDE_FILE = "guide.json"

# Kategori emojileri
CATEGORY_EMOJIS = {
    "genel": "⚙️",
    "çekiliş": "🎉",
    "moderasyon": "🛡️",
    "ticket": "🎫",
    "yapayzeka": "🧠",
    "reaksiyon_rolleri": "✨",
    "otomatik_roller": "🤖",
    "starboard": "⭐",
    "öneriler": "💡",
    "hatırlatmalar": "⏰",
    "anketler": "📊",
    "eğlence": "🎲"
}


class KilavuzButtons(ui.View):
    def __init__(self, kilavuz_data, timeout=300):
        super().__init__(timeout=timeout)
        self.kilavuz_data = kilavuz_data
        self.kategori_listesi = list(kilavuz_data.keys())
        
        # Butonlar ekle
        for kategori, _ in kilavuz_data.items():
            emoji = CATEGORY_EMOJIS.get(kategori, "📖")
            button = ui.Button(
                label=kategori.upper(),
                emoji=emoji,
                custom_id=f"guide_{kategori}",
                style=discord.ButtonStyle.primary
            )
            # Lambda ile kategoriyi yakala ve callback'e geç
            button.callback = lambda interaction, k=kategori: self.kategori_secimi(interaction, k)
            self.add_item(button)
    
    async def kategori_secimi(self, interaction: discord.Interaction, kategori: str):
        """Kategori butonuna tıklandığında çağrılır."""
        await interaction.response.defer(ephemeral=True)
        
        if kategori not in self.kilavuz_data:
            await interaction.followup.send("❌ Kategori bulunamadı!", ephemeral=True)
            return
        
        embed = self.kategori_embed_olustur(kategori)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    def kategori_embed_olustur(self, kategori):
        """Kategori için embed oluşturur."""
        emoji = CATEGORY_EMOJIS.get(kategori, "📖")
        icerik = self.kilavuz_data[kategori]
        
        embed = discord.Embed(
            title=f"{emoji} {kategori.upper()}",
            description=icerik,
            color=discord.Color.random()
        )
        
        embed.set_footer(text="💡 TrAI Kullanım Kılavuzu | Başka bir kategori seçmek için komut çalıştırın.")
        return embed


class Guide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    def kilavuz_yukle(self):
        """Kılavuz verilerini JSON dosyasından yükler."""
        if os.path.exists(GUIDE_FILE):
            with open(GUIDE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    @app_commands.command(name="kılavuz", description="📚 Botun kullanım kılavuzunu gösterir.")
    @app_commands.describe(kategori="İsteğe bağlı: Belirli bir kategori görmek için")
    async def kilavuz(self, interaction: discord.Interaction, kategori: str = None):
        """Botun kullanım kılavuzunu gönderir."""
        kilavuz_data = self.kilavuz_yukle()

        if not kilavuz_data:
            await interaction.response.send_message(
                "❌ Kılavuz dosyası bulunamadı veya boş!", ephemeral=True
            )
            return
        
        # Eğer kategori belirtilmişse o kategoriyi göster
        if kategori:
            if kategori not in kilavuz_data:
                kategoriler = ", ".join(kilavuz_data.keys())
                await interaction.response.send_message(
                    f"❌ '{kategori}' kategorisi bulunamadı.\n\n"
                    f"Kullanılabilir kategoriler:\n{kategoriler}",
                    ephemeral=True
                )
                return
            
            emoji = CATEGORY_EMOJIS.get(kategori, "📖")
            embed = discord.Embed(
                title=f"{emoji} {kategori.upper()}",
                description=kilavuz_data[kategori],
                color=discord.Color.random()
            )
            embed.set_footer(text="💡 TrAI Kullanım Kılavuzu")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Ana kılavuz görünümü - tüm kategorileri butonlarla göster
        embed = discord.Embed(
            title="📚 TrAI Kullanım Kılavuzu",
            description="Lütfen aşağıdaki kategorilerden birini seçerek detaylı bilgi alın.",
            color=discord.Color.blue()
        )
        
        # Kategori listesi
        kategori_metni = "\n".join([
            f"{CATEGORY_EMOJIS.get(kat, '📖')} **{kat.upper()}**"
            for kat in kilavuz_data.keys()
        ])
        
        embed.add_field(
            name="📖 Mevcut Kategoriler",
            value=kategori_metni,
            inline=False
        )
        
        embed.add_field(
            name="💡 Nasıl Kullanılır?",
            value="Aşağıdaki butonlardan birini tıkla veya `/kılavuz [kategori]` yazarak belirli bir kategoriye ulaş.\n\n"
                  "Örnek: `/kılavuz kategori:moderasyon`",
            inline=False
        )
        
        embed.set_footer(text="✨ TrAI - Yapay Zeka Destekli Discord Botu")
        
        view = KilavuzButtons(kilavuz_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Guide(bot))
