import discord
from discord.ext import commands
from groq import Groq
import requests
import os
import re
import asyncio
from utils.helpers import strip_emojis, is_recent_message, mark_recent_message, safe_load_json
from utils.logger import get_logger
import datetime
import json
import time
import warnings
import locale
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import wikipedia
from ddgs import DDGS

# Türkçe Tarih Ayarı (Linux/Windows uyumlu)
try:
    locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
    except Exception as e:
        logging.getLogger(__name__).debug("Could not set Turkish locale: %s", e)

warnings.filterwarnings("ignore")
SETTINGS_FILE = "settings.json"
GUIDE_FILE = "guide.json"


class AIChat(commands.Cog):
    # Hafıza: son 20 mesajla sınırlandırılmış kanal özeti
    HISTORY_LIMIT = 20

    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY bulunamadı! Lütfen .env dosyanızı kontrol edin.")
        self.client = Groq(api_key=api_key)

        self.cooldown_suresi = 4
        self.odaklanilan_kisiler = {}
        self.user_last_call = {}
        self.odak_suresi = 60
        self.kilavuz_verisi = self.kilavuz_yukle()
        # strip_emojis yardımcı fonksiyonunu örnek olarak sakla
        self.strip_emojis = strip_emojis
        self.logger = get_logger(__name__)
        self.web_cache = {}  # {sorgu: {"result": data, "time": timestamp}}
        self.cache_ttl = 1800  # 30 dakika cache

    def web_ara_duckduckgo(self, sorgu, max_results=3):
        # Cache kontrol
        cache_key = f"ddg_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]
        
        try:
            ddgs = DDGS()
            results = []
            for r in ddgs.text(sorgu, region='tr-tr', safesearch='Moderate', max_results=max_results):
                results.append(f"{r.get('title','')}: {r.get('body','')}\n{r.get('href','')}")
                if len(results) >= max_results:
                    break
            result = '\n\n'.join(results) if results else None
            self.web_cache[cache_key] = {"result": result, "time": time.time()}
            return result
        except Exception as e:
            self.logger.warning(f"Web arama hatası: {e}")
            return None

    def web_ara_google(self, sorgu, max_results=3):
        # Cache kontrol
        cache_key = f"google_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]
        
        try:
            from googlesearch import search
            urls = []
            for url in search(sorgu, num_results=max_results, lang="tr"):
                urls.append(url)
                if len(urls) >= max_results:
                    break
            if not urls:
                return None
            result = self._ozet_url_listesi(urls)
            self.web_cache[cache_key] = {"result": result, "time": time.time()}
            return result
        except Exception as e:
            self.logger.warning(f"Google arama hatası: {e}")
            return None

    def web_ara_selenium(self, sorgu, max_results=3):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=1200,800")

            driver = webdriver.Chrome(options=options)
            try:
                url = f"https://duckduckgo.com/?q={quote_plus(sorgu)}"
                driver.get(url)
                links = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
                urls = []
                for l in links:
                    href = l.get_attribute("href")
                    if href:
                        urls.append(href)
                    if len(urls) >= max_results:
                        break
                if not urls:
                    return None
                return self._ozet_url_listesi(urls)
            finally:
                driver.quit()
        except Exception as e:
            self.logger.warning(f"Selenium arama hatası: {e}")
            return None

    def _ozet_url_listesi(self, urls):
        results = []
        for url in urls:
            try:
                r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                title = soup.title.text.strip() if soup.title else "Başlık"
                text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:3])
                snippet = text[:220] + ("..." if len(text) > 220 else "")
                results.append(f"{title}: {snippet}\n{url}")
            except Exception:
                continue
        return "\n\n".join(results) if results else None

    def web_ara_birlesik(self, sorgu, max_results=3):
        # Önce Google (TR), sonra DuckDuckGo (TR), en son Selenium fallback
        sonuc = self.web_ara_google(sorgu, max_results=max_results)
        if sonuc:
            return sonuc
        sonuc = self.web_ara_duckduckgo(sorgu, max_results=max_results)
        if sonuc:
            return sonuc
        return self.web_ara_selenium(sorgu, max_results=max_results)

    def tr_ilk_sonuclari_getir(self, sorgu, max_results=3):
        # Türkiye odaklı ilk sonuçları getir
        urls = []
        try:
            from googlesearch import search
            for url in search(sorgu, num_results=max_results, lang="tr"):
                urls.append(url)
                if len(urls) >= max_results:
                    break
        except Exception as e:
            self.logger.warning(f"TR Google arama hatası: {e}")

        if urls:
            return urls

        try:
            ddgs = DDGS()
            for r in ddgs.text(sorgu, region='tr-tr', safesearch='Moderate', max_results=max_results):
                href = r.get('href')
                if href:
                    urls.append(href)
                if len(urls) >= max_results:
                    break
        except Exception as e:
            self.logger.warning(f"TR DuckDuckGo arama hatası: {e}")

        return urls

    def tr_ilk_siteden_ozet_selenium(self, sorgu):
        urls = self.tr_ilk_sonuclari_getir(sorgu, max_results=1)
        if not urls:
            return None
        first_url = urls[0]
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=1200,800")

            driver = webdriver.Chrome(options=options)
            try:
                driver.set_page_load_timeout(5)
                driver.get(first_url)
                html = driver.page_source
                soup = BeautifulSoup(html, "lxml")
                title = soup.title.text.strip() if soup.title else "Başlık"
                text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:4])
                snippet = text[:350] + ("..." if len(text) > 350 else "")
                if snippet:
                    return f"{title}: {snippet}\n{first_url}"
            finally:
                driver.quit()
        except Exception as e:
            self.logger.warning(f"TR Selenium özet hatası: {e}")
        return None

    async def tr_ilk_siteden_ozet_selenium_async(self, sorgu, timeout=5):
        try:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, self.tr_ilk_siteden_ozet_selenium, sorgu),
                timeout=timeout,
            )
        except Exception:
            return None

    def _kur_metinden_cek(self, text):
        if not text:
            return None
        # Türkçe/İngilizce biçimleri yakala
        patterns = [
            r"(\d+[\.,]\d+)\s*TL",
            r"(\d+[\.,]\d+)\s*Türk\s*Lirası",
            r"(\d+[\.,]\d+)\s*Turkish\s*Lira",
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                val = m.group(1).replace(".", "").replace(",", ".")
                try:
                    return float(val)
                except Exception:
                    continue
        return None

    def kur_webden_getir(self, base="USD", target="TRY"):
        query = f"1 {base} to {target}"
        # Selenium ile Google (öncelikli)
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=1200,800")
            driver = webdriver.Chrome(options=options)
            try:
                driver.set_page_load_timeout(8)
                driver.get(f"https://www.google.com/search?q={quote_plus(query)}")
                selectors = [
                    "span.DFlfde",
                    "input.a61j6"
                ]
                for sel in selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        val = el.get_attribute("value") or el.text
                        if val:
                            val = val.replace(".", "").replace(",", ".")
                            return float(val)
                    except Exception:
                        continue

                page = driver.page_source
                rate = self._kur_metinden_cek(page)
                if rate:
                    return rate
            finally:
                driver.quit()
        except Exception:
            pass

        # Bing (requests) fallback
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                rate = self._kur_metinden_cek(r.text)
                if rate:
                    return rate
        except Exception:
            pass

        # DuckDuckGo (ddgs) fallback
        try:
            ddgs = DDGS()
            for r in ddgs.text(query, region='tr-tr', safesearch='Moderate', max_results=5):
                body = r.get('body', '') or ''
                rate = self._kur_metinden_cek(body)
                if rate:
                    return rate
        except Exception:
            pass
        return None

    async def kur_webden_getir_async(self, base="USD", target="TRY", timeout=5):
        try:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, self.kur_webden_getir, base, target),
                timeout=timeout,
            )
        except Exception:
            return None

    def web_ara_wikipedia(self, sorgu, sentences=2):
        try:
            wikipedia.set_lang("tr")
            return wikipedia.summary(sorgu, sentences=sentences, auto_suggest=True, redirect=True)
        except Exception as e:
            self.logger.warning(f"Wikipedia arama hatası: {e}")
            return None

    def finans_kur_getir(self, base="USD", target="TRY"):
        try:
            url = f"https://api.exchangerate.host/latest?base={base}&symbols={target}"
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                rate = data.get("rates", {}).get(target)
                if rate:
                    return rate
        except Exception as e:
            self.logger.warning(f"Kur sorgu hatası: {e}")
        return None

    def ayar_getir(self, guild_id):
        data = safe_load_json(SETTINGS_FILE, {})
        return data.get(str(guild_id), {})

    def kilavuz_yukle(self):
        from utils import db
        return db.kv_get("guide", {}) or {}

    @commands.command(name="unut", aliases=["hafıza", "reset", "sıfırla"])
    async def unut_komut(self, ctx):
        if ctx.author.id in self.odaklanilan_kisiler:
            del self.odaklanilan_kisiler[ctx.author.id]

        embed = discord.Embed(
            description="🤯 **Hafızam sıfırlandı!** Az önce ne konuşuyorduk? Mod değiştirmeye hazırım.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    async def kanal_gecmisini_getir(self, channel, limit=None):
        messages = []
        try:
            lim = limit or self.HISTORY_LIMIT
            async for msg in channel.history(limit=lim):
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
        return bilgi

    def metni_temizle(self, metin):
        # Gereksiz düşünme etiketlerini temizle (DeepSeek vb. modeller için)
        temiz = re.sub(r'<think>.*?</think>', '', metin, flags=re.DOTALL)
        return re.sub(r"[\u4e00-\u9fff]", "", temiz).strip()

    def hava_durumu_al(self, sorgu):
        try:
            url = f"https://wttr.in/Turkey?format=%l:+%C+%t&lang=tr"
            r = requests.get(url)
            return f"METEOROLOJİ VERİSİ: {r.text}" if r.status_code == 200 else None
        except:
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if is_recent_message(message.id): return
        if not self.bot.ai_aktif: return
        if message.content.startswith("!"): return

        # --- İzin ve Odak Kontrolleri ---
        ayarlar = self.ayar_getir(message.guild.id)
        aktif_kanal_id = ayarlar.get("aktif_kanal", None)
        user_id = message.author.id
        current_time = time.time()

        # Per-user cooldown: kısa süre içinde tekrar sorulursa cevabı reddet
        last = self.user_last_call.get(user_id, 0)
        if current_time - last < self.cooldown_suresi:
            try:
                kalan_sure = int(self.cooldown_suresi - (current_time - last))
                await message.reply(f"⏳ Biraz yavaş! {kalan_sure} saniye sonra tekrar sorabilirsin.")
                mark_recent_message(message.id)
            except Exception:
                pass
            return

        etiketlendi = self.bot.user.mentioned_in(message)
        yanitlandi = (message.reference and message.reference.resolved and
                      message.reference.resolved.author.id == self.bot.user.id)

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

        # Yasaklı kelimeler (AI bunlara cevap verirse komutlarla çakışabilir)
        yasakli_kelimeler = ["!ban", "!kick", "!sil", "!temizle", "!unban"]
        if any(k in message.content.lower() for k in yasakli_kelimeler): return

        async with message.channel.typing():
            try:
                user_input = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not user_input: return

                # Ek Bilgiler
                rehber_bilgisi = self.rehberden_bilgi_getir(user_input)
                hava_durumu = self.hava_durumu_al(user_input) if "hava" in user_input.lower() else None
                lu = user_input.lower()
                # Web aramayı sadece güncel/volatil bilgi istendiğinde tetikle
                # "bugün" ve "şimdi" kaldırıldı - çok fazla false positive veriyordu
                need_web = any(k in lu for k in [
                    "haber", "güncel", "son dakika", "webde", "internette", "site", "kaynak",
                    "fiyat", "kur", "dolar", "euro", "altın", "borsa", "hava durumu", "yarın"
                ])
                # Wikipedia: tanım/kimdir/nedir gibi bilgi isteklerinde önce wiki
                need_wiki = any(k in lu for k in ["nedir", "kimdir", "ne demek", "tarihçe", "biyografi"])

                wiki_ozet = self.web_ara_wikipedia(user_input) if need_wiki else None
                web_sonuclari = None
                if not wiki_ozet:
                    # Türkiye odaklı ilk sonuçtan Selenium ile özet çek
                    web_sonuclari = await self.tr_ilk_siteden_ozet_selenium_async(user_input)
                    if not web_sonuclari and need_web:
                        # En son global DuckDuckGo fallback
                        try:
                            web_sonuclari = self.web_ara_duckduckgo(user_input, max_results=3)
                        except Exception:
                            web_sonuclari = None
                
                # Kur bilgisi AI'ya ek bilgi olarak verilecek
                kur_bilgi = None
                if "dolar" in lu or "usd" in lu:
                    rate = await self.kur_webden_getir_async("USD", "TRY")
                    if rate:
                        kur_bilgi = f"Güncel kur: 1 USD = {rate:.2f} TL (Kaynak: Google Finance)"
                elif "euro" in lu or "eur" in lu:
                    rate = await self.kur_webden_getir_async("EUR", "TRY")
                    if rate:
                        kur_bilgi = f"Güncel kur: 1 EUR = {rate:.2f} TL (Kaynak: Google Finance)"
                
                gecmis = await self.kanal_gecmisini_getir(message.channel, limit=20)
                tarih = datetime.datetime.now().strftime('%d %B %Y, %A')

                # --- 🎭 3 KİŞİLİKLİ SİSTEM PROMPT ---
                system_prompt = (
                    f"Sen 'TrAI'. Discord sunucusunun gelişmiş yapay zekasısın. Tarih: {tarih}.\n"
                    "Senin 3 farklı kişiliğin var. Kullanıcının mesajına ve konuya göre en uygun role bürün:\n\n"

                    "1. 🎓 ÖĞRETMEN MODU: Kullanıcı 'nedir', 'nasıl', 'ne zaman', 'bilgi ver' gibi öğretici şeyler sorarsa;\n"
                    "   - Üslup: Bilgilendirici, sabırlı, açıklayıcı, düzgün Türkçe ve kibar.\n"
                    "   - Görev: Konuyu net bir şekilde açıkla.\n\n"

                    "2. 🛡️ MODERATÖR MODU: Konu sunucu kuralları, güvenlik veya ciddiyet gerektiriyorsa;\n"
                    "   - Üslup: Sakin, açıklayıcı, gereksiz uyarı vermekten kaçınan, sadece ciddi ihlallerde uyarı yapan.\n"
                    "   - Görev: Sadece gerçekten kural ihlali varsa kibarca uyar. Gereksiz yere 'saygı ve nezaket' uyarısı verme.\n\n"

                    "3. 😎 KANKA/ARKADAŞ MODU: Kullanıcı 'naber', 'selam', oyunlar, geyik muhabbeti veya havadan sudan konuşuyorsa;\n"
                    "   - Üslup: Samimi, esprili, 'kanka/dostum' diyen, emoji kullanan, rahat ve eğlenceli.\n"
                    "   - Görev: Sohbeti sürdür ve makara yap.\n\n"

                    "⚠️ ÖNEMLİ KURALLAR:\n"
                    "- Hangi moda gireceğine sen karar ver ama asla 'Şimdi öğretmen moduna geçiyorum' deme. Direkt o rolde konuş.\n"
                    "- Eğer hava durumu sorulursa meteorolog gibi ciddi cevap ver.\n"
                    "- Kısa ve öz cevaplar ver, destan yazma.\n"
                    "- Gereksiz yere kullanıcıya 'saygı ve nezaket kurallarına uymadın' gibi uyarılar yazma. Sadece gerçekten ciddi bir ihlal varsa uyar."
                )
                # Eğer kur bilgisi bulunduysa, modeli beklemeden hızlı yanıt ver
                if kur_bilgi:
                    try:
                        await message.reply(kur_bilgi)
                        mark_recent_message(message.id)
                        self.user_last_call[user_id] = time.time()
                        return
                    except Exception:
                        pass

                if web_sonuclari:
                    system_prompt += f"\n\nWEB ARAMA SONUÇLARI (güncel bilgi, özetle):\n{web_sonuclari}"
                    system_prompt += ("\n\nKURAL: Eğer yukarıda web arama sonucu varsa, mutlaka bu sonuçlardan güncel rakamsal değeri veya cevabı doğrudan, net ve kısa şekilde kullanıcıya yaz. 'Bir döviz sitesi ziyaret et' veya 'güncel veriye ulaşamadım' gibi kaçamak cevaplar VERME. Web sonucunda rakam veya bilgi varsa onu yazmak ZORUNDASIN. Sadece web_sonuclari tamamen boşsa 'güncel veriye ulaşamadım' diyebilirsin.")
                if wiki_ozet:
                    system_prompt += f"\n\nWİKİPEDİ ÖZETİ:\n{wiki_ozet}"

                # Dil ve emoji kısıtlaması: cevap tamamen Türkçe olmalı, İngilizce kelime kullanma ve emoji kullanma yasaktır.
                system_prompt += (
                    "\n\nDİL KURALI: Cevaplarını SADECE Türkçe olarak ver. İngilizce kelime, kısaltma veya yabancı ifade kullanma."
                    " Yazım kurallarına dikkat et ve gereksiz emoji kullanma."
                )

                # Ek verileri prompt'a ekle
                if rehber_bilgisi: system_prompt += f"\n\nKILAVUZ BİLGİSİ (Buna göre cevapla):\n{rehber_bilgisi}"
                if hava_durumu: system_prompt += f"\n\nMETEOROLOJİ Raporu:\n{hava_durumu}"

                system_prompt += f"\n\nSOHBET GEÇMİŞİ:\n{gecmis}"

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]

                chat = self.client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    max_tokens=450,
                    temperature=0.7  # Yaratıcılık ve tutarlılık dengesi
                )

                cevap = self.metni_temizle(chat.choices[0].message.content)

                # AI'den gelen yanıtı fazla emoji içeriyorsa temizle
                try:
                    cevap = self.strip_emojis(cevap)
                except Exception:
                    pass

                # Eğer model boş cevap döndürdüyse, boş mesaj hatasını önlemek için yedek bir cevap ayarla
                if not cevap or not str(cevap).strip():
                    cevap = "😵 Üzgünüm, şu an yanıt üretemiyorum. Biraz sonra tekrar dene!"

                try:
                    if message.channel.id != aktif_kanal_id:
                        await message.reply(cevap)
                    else:
                        if etiketlendi or yanitlandi:
                            await message.reply(cevap)
                        else:
                            await message.channel.send(cevap)
                    mark_recent_message(message.id)
                    self.user_last_call[user_id] = time.time()
                except Exception as e:
                    self.logger.exception("❌ AI yanıt gönderme hatası")

            except Exception as e:
                self.logger.exception("❌ AI ana işlem hatası")


async def setup(bot):
    await bot.add_cog(AIChat(bot))