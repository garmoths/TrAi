import discord
from discord.ext import commands
from groq import Groq
import requests
import os
import re
import asyncio
import datetime
import json
import time
import warnings

warnings.filterwarnings("ignore")
SETTINGS_FILE = "settings.json"
GUIDE_FILE = "guide.json"


class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)

        self.cooldown_suresi = 4
        self.last_message_time = {}
        # Odaklanılan kişiler (Beni dürttüysen seni dinliyorum listesi)
        self.odaklanilan_kisiler = {}
        self.odak_suresi = 60
        self.kilavuz_verisi = self.kilavuz_yukle()

    def ayar_getir(self, guild_id):
        if not os.path.exists(SETTINGS_FILE): return {}
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get(str(guild_id), {})

    def kilavuz_yukle(self):
        if not os.path.exists(GUIDE_FILE): return {}
        with open(GUIDE_FILE, "r", encoding="utf-8") as f: return json.load(f)

    # --- YENİ EKLENEN KOMUT: !unut ---
    @commands.command(name="unut", aliases=["hafıza", "reset", "sıfırla"])
    async def unut_komut(self, ctx):
        """Botun odaklanma modunu ve o anki sohbet bağlamını sıfırlar."""
        temizlendi = False

        # 1. Odaklanma listesinden çıkar
        if ctx.author.id in self.odaklanilan_kisiler:
            del self.odaklanilan_kisiler[ctx.author.id]
            temizlendi = True

        # 2. Kullanıcıya tepki ver
        embed = discord.Embed(
            description="🤯 **Hafızam sıfırlandı!** Az önce ne konuşuyorduk? Seni tanımıyorum.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    # --- GEÇMİŞİ OKUMA ---
    async def kanal_gecmisini_getir(self, channel, limit=8):
        messages = []
        try:
            async for msg in channel.history(limit=limit):
                if msg.author.bot and msg.author.id != self.bot.user.id: continue
                if msg.content.startswith("!"): continue

                isim = "TrAI" if msg.author.id == self.bot.user.id else msg.author.name
                temiz_icerik = msg.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if temiz_icerik:
                    messages.append(f"{isim}: {temiz_icerik}")
            messages.reverse()
            return "\n".join(messages)
        except:
            return ""

    def rehberden_bilgi_getir(self, sorgu):
        sorgu = sorgu.lower()
        bilgi = ""
        if "çekiliş" in sorgu or "giveaway" in sorgu: bilgi += self.kilavuz_verisi.get("çekiliş", "") + "\n"
        if "ticket" in sorgu or "destek" in sorgu: bilgi += self.kilavuz_verisi.get("ticket", "") + "\n"
        # Moderasyon için kısa bilgi
        if any(x in sorgu for x in ["kanal", "log", "ayarla"]): bilgi += self.kilavuz_verisi.get("genel", "") + "\n"
        return bilgi

    def metni_temizle(self, metin):
        return re.sub(r"[\u4e00-\u9fff]", "", metin)

    def hava_durumu_al(self, sorgu):
        try:
            url = f"https://wttr.in/Turkey?format=%l:+%C+%t&lang=tr"
            r = requests.get(url)
            return f"METEOROLOJİ: {r.text}" if r.status_code == 200 else None
        except:
            return None

    async def akilli_cevap(self, sorgu):
        if "hava" in sorgu: return self.hava_durumu_al(sorgu)
        return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if not self.bot.ai_aktif: return
        if message.content.startswith("!"): return

        ayarlar = self.ayar_getir(message.guild.id)
        aktif_kanal_id = ayarlar.get("aktif_kanal", None)
        user_id = message.author.id
        current_time = time.time()

        # Tetikleyiciler
        etiketlendi = self.bot.user.mentioned_in(message)
        yanitlandi = False
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if ref.author.id == self.bot.user.id and not (ref.embeds or ref.components):
                yanitlandi = True

        odakta_mi = False
        if user_id in self.odaklanilan_kisiler:
            if current_time - self.odaklanilan_kisiler[user_id] < self.odak_suresi:
                odakta_mi = True
            else:
                del self.odaklanilan_kisiler[user_id]

        konusma_izni = False
        if message.channel.id == aktif_kanal_id:
            konusma_izni = True
        elif etiketlendi or yanitlandi or odakta_mi:
            konusma_izni = True
            self.odaklanilan_kisiler[user_id] = current_time

        if not konusma_izni: return

        # 🔥 YASAKLI KELİMELER (AI CEVAP VERMESİN DİYE) 🔥
        yasakli_kelimeler = [
            "ban", "yasakla", "sustur", "kapat", "at", "kov", "paketle", "uçur",
            "kick", "mute", "unban", "unmute", "aç", "affet",
            "sil", "temizle", "süpür", "yok et", "clear", "purge", "delete",
            "uyar", "ikaz", "warn",
            "panel", "senin kanalın", "log", "ayarla",
            "unut", "sıfırla"  # Kendi komutuna da AI ile cevap vermesin
        ]

        if any(k in message.content.lower() for k in yasakli_kelimeler):
            return

        async with message.channel.typing():
            try:
                clean_content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not clean_content: return

                rehber_bilgisi = self.rehberden_bilgi_getir(clean_content)
                gecmis_sohbet = await self.kanal_gecmisini_getir(message.channel, limit=8)

                system_prompt = f"Sen TrAI, samimi bir Discord botusun. Tarih: {datetime.datetime.now().strftime('%d %B %Y')}."
                system_prompt += f"\n\nKONUŞMA GEÇMİŞİ:\n{gecmis_sohbet}"

                if rehber_bilgisi:
                    system_prompt += f"\n\nKILAVUZ BİLGİSİ:\n{rehber_bilgisi}"
                else:
                    veriler = await self.akilli_cevap(clean_content)
                    if veriler: system_prompt += f" Ek Bilgi: {veriler}"

                messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": clean_content}]

                chat = self.client.chat.completions.create(
                    messages=messages, model="llama-3.3-70b-versatile", max_tokens=400
                )
                cevap = self.metni_temizle(chat.choices[0].message.content)

                if message.channel.id != aktif_kanal_id:
                    await message.reply(cevap)
                else:
                    if etiketlendi or yanitlandi:
                        await message.reply(cevap)
                    else:
                        await message.channel.send(cevap)

            except Exception as e:
                print(e)


async def setup(bot):
    await bot.add_cog(AIChat(bot))