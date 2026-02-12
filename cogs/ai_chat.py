import discord
from discord.ext import commands
from groq import Groq
import requests
import os
import re
import asyncio
import platform
import shutil
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

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

# chromedriver otomatik yükleme (opsiyonel)
try:
    import chromedriver_autoinstaller
    HAS_CHROMEDRIVER_AUTO = True
except ImportError:
    HAS_CHROMEDRIVER_AUTO = False

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
    HISTORY_LIMIT = 20

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY bulunamadı! Lütfen .env dosyanızı kontrol edin.")
        self.client = Groq(api_key=api_key)
        
        self.cooldown_suresi = 4
        self.odaklanilan_kisiler = {}
        self.user_last_call = {}
        self.odak_suresi = 60
        self.kilavuz_verisi = self.kilavuz_yukle()
        self.strip_emojis = strip_emojis
        self.web_cache = {}
        self.cache_ttl = 1800
        self._os_name = platform.system().lower()  # 'darwin', 'windows', 'linux'
        self.logger.info(f"İşletim sistemi algılandı: {self._os_name}")

    def _chrome_options(self):
        """İşletim sistemine göre uygun Chrome seçeneklerini oluşturur."""
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1200,800")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")

        if self._os_name == "windows":
            # Windows: log-level ayarla, bazı GPU hataları için
            opts.add_argument("--log-level=3")
            opts.add_argument("--disable-software-rasterizer")
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        elif self._os_name == "darwin":
            # macOS
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        else:
            # Linux (sunucu/VPS)
            opts.add_argument("--disable-setuid-sandbox")
            opts.add_argument("--single-process")
            ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        opts.add_argument(f"user-agent={ua}")
        opts.add_argument("--accept-lang=tr-TR,tr;q=0.9,en;q=0.8")
        return opts

    def _create_driver(self):
        """İşletim sistemine uygun ChromeDriver oluşturur."""
        opts = self._chrome_options()

        # 1) chromedriver-autoinstaller varsa kullan (en güvenilir)
        if HAS_CHROMEDRIVER_AUTO:
            try:
                chromedriver_autoinstaller.install()
                return webdriver.Chrome(options=opts)
            except Exception as e:
                self.logger.debug(f"chromedriver-autoinstaller başarısız: {e}")

        # 2) PATH'te chromedriver var mı kontrol et
        chromedriver_path = shutil.which("chromedriver")
        if chromedriver_path:
            try:
                service = Service(executable_path=chromedriver_path)
                return webdriver.Chrome(service=service, options=opts)
            except Exception as e:
                self.logger.debug(f"PATH chromedriver başarısız: {e}")

        # 3) Doğrudan dene (Selenium Manager otomatik bulur - Selenium 4.10+)
        try:
            return webdriver.Chrome(options=opts)
        except Exception as e:
            self.logger.warning(f"Chrome driver oluşturulamadı ({self._os_name}): {e}")
            raise

    def web_ara_google(self, sorgu, max_results=3):
        """Eski metod - geriye uyumluluk için tutuluyor ama artık _url_topla kullanılıyor."""
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

    def web_ara_duckduckgo_tr(self, sorgu, max_results=3):
        if not HAS_DDGS:
            return None
        cache_key = f"ddgs_tr_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]
        try:
            with DDGS() as ddgs:
                results_list = list(ddgs.text(sorgu, region='tr-tr', max_results=max_results))
                if not results_list:
                    return None
                results = []
                for r in results_list:
                    title = r.get('title', '')
                    body = r.get('body', '')[:200]
                    href = r.get('href', '')
                    results.append(f"{title}: {body}\n{href}")
                result = '\n\n'.join(results)
                self.web_cache[cache_key] = {"result": result, "time": time.time()}
                return result
        except Exception as e:
            self.logger.debug(f"DuckDuckGo TR hatası: {e}")
            return None

    def web_ara_duckduckgo_global(self, sorgu, max_results=3):
        if not HAS_DDGS:
            return None
        cache_key = f"ddgs_global_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]
        try:
            with DDGS() as ddgs:
                results_list = list(ddgs.text(sorgu, max_results=max_results))
                if not results_list:
                    return None
                results = []
                for r in results_list:
                    title = r.get('title', '')
                    body = r.get('body', '')[:200]
                    href = r.get('href', '')
                    results.append(f"{title}: {body}\n{href}")
                result = '\n\n'.join(results)
                self.web_cache[cache_key] = {"result": result, "time": time.time()}
                return result
        except Exception as e:
            self.logger.debug(f"DuckDuckGo Global hatası: {e}")
            return None

    def web_ara_selenium(self, sorgu, max_results=3):
        if not HAS_SELENIUM:
            return None
        cache_key = f"selenium_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]
        try:
            driver = self._create_driver()
            try:
                url = f"https://duckduckgo.com/?q={quote_plus(sorgu)}"
                driver.get(url)
                time.sleep(2)  # Sayfanın yüklenmesini bekle
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
                result = self._ozet_url_listesi(urls)
                self.web_cache[cache_key] = {"result": result, "time": time.time()}
                return result
            finally:
                driver.quit()
        except Exception as e:
            self.logger.debug(f"Selenium hatası: {e}")
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

    def _derin_icerik_cek(self, url, max_char=600):
        """Bir URL'den derin içerik çeker - daha fazla paragraf ve daha uzun metin."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml"
            }
            r = requests.get(url, timeout=10, headers=headers)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "lxml")
            # Gereksiz elementleri temizle
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                tag.decompose()
            title = soup.title.text.strip() if soup.title else ""
            # Article body varsa önce onu dene
            article = soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post|entry|main", re.I))
            if article:
                paragraphs = article.find_all("p")
            else:
                paragraphs = soup.find_all("p")
            # Kısa paragrafları atla, anlamlı olanları al
            texts = []
            for p in paragraphs:
                t = p.get_text(" ", strip=True)
                if len(t) > 30:  # Çok kısa paragrafları atla
                    texts.append(t)
                if sum(len(x) for x in texts) > max_char:
                    break
            full_text = " ".join(texts)
            if len(full_text) > max_char:
                full_text = full_text[:max_char] + "..."
            if not full_text or len(full_text) < 50:
                return None
            return {"title": title, "text": full_text, "url": url}
        except Exception as e:
            self.logger.debug(f"Derin içerik çekme hatası ({url}): {e}")
            return None

    def _derin_icerik_selenium(self, url, max_char=600):
        """Selenium ile JavaScript-rendered sayfalardan derin içerik çeker."""
        if not HAS_SELENIUM:
            return None
        try:
            driver = self._create_driver()
            try:
                driver.set_page_load_timeout(10)
                driver.get(url)
                time.sleep(2)
                html = driver.page_source
                soup = BeautifulSoup(html, "lxml")
                for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                title = soup.title.text.strip() if soup.title else ""
                article = soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post|entry|main", re.I))
                if article:
                    paragraphs = article.find_all("p")
                else:
                    paragraphs = soup.find_all("p")
                texts = []
                for p in paragraphs:
                    t = p.get_text(" ", strip=True)
                    if len(t) > 30:
                        texts.append(t)
                    if sum(len(x) for x in texts) > max_char:
                        break
                full_text = " ".join(texts)
                if len(full_text) > max_char:
                    full_text = full_text[:max_char] + "..."
                if not full_text or len(full_text) < 50:
                    return None
                return {"title": title, "text": full_text, "url": url}
            finally:
                driver.quit()
        except Exception as e:
            self.logger.debug(f"Selenium derin içerik hatası ({url}): {e}")
            return None

    def _url_topla(self, sorgu, max_results=5):
        """Birden fazla kaynaktan URL toplar ve tekilleştirir."""
        urls_seen = set()
        urls_ordered = []

        def _ekle(url):
            if url and url not in urls_seen:
                urls_seen.add(url)
                urls_ordered.append(url)

        # 1) Google Search (Türkçe)
        try:
            from googlesearch import search
            for url in search(sorgu, num_results=max_results, lang="tr"):
                _ekle(url)
                if len(urls_ordered) >= max_results:
                    break
        except Exception as e:
            self.logger.debug(f"Google URL toplama hatası: {e}")

        # 2) DuckDuckGo TR
        if len(urls_ordered) < max_results and HAS_DDGS:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(sorgu, region='tr-tr', max_results=max_results):
                        href = r.get('href', '')
                        if href:
                            _ekle(href)
                        if len(urls_ordered) >= max_results:
                            break
            except Exception as e:
                self.logger.debug(f"DDG URL toplama hatası: {e}")

        # 3) DuckDuckGo Global (yedek)
        if len(urls_ordered) < 2 and HAS_DDGS:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(sorgu, max_results=max_results):
                        href = r.get('href', '')
                        if href:
                            _ekle(href)
                        if len(urls_ordered) >= max_results:
                            break
            except Exception as e:
                self.logger.debug(f"DDG Global URL toplama hatası: {e}")

        return urls_ordered[:max_results]

    def _ddg_snippet_topla(self, sorgu, max_results=5):
        """DuckDuckGo'dan snippet bilgilerini toplar (URL çekmeden hızlı özet)."""
        snippets = []
        if not HAS_DDGS:
            return snippets
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(sorgu, region='tr-tr', max_results=max_results):
                    title = r.get('title', '')
                    body = r.get('body', '')
                    href = r.get('href', '')
                    if body and len(body) > 30:
                        snippets.append({"title": title, "text": body, "url": href})
        except Exception as e:
            self.logger.debug(f"DDG snippet hatası: {e}")
        return snippets

    def _sayfa_icerikleri_cek(self, urls, max_char=600):
        """URL listesinden derin içerik çeker. Requests başarısız olursa Selenium dener."""
        results = []
        for url in urls:
            icerik = self._derin_icerik_cek(url, max_char=max_char)
            if not icerik and HAS_SELENIUM:
                icerik = self._derin_icerik_selenium(url, max_char=max_char)
            if icerik:
                results.append(icerik)
        return results

    def _birlestir_ve_formatla(self, sayfa_icerikleri, ddg_snippets, wiki_ozet=None):
        """Tüm kaynakları birleştirip zengin bir bağlam metni oluşturur."""
        parcalar = []
        seen_urls = set()

        # Önce derin sayfa içeriklerini ekle (en değerli)
        for ic in sayfa_icerikleri:
            if ic["url"] not in seen_urls:
                seen_urls.add(ic["url"])
                parcalar.append(f"📌 {ic['title']}\n{ic['text']}\nKaynak: {ic['url']}")

        # DDG snippet'larını yedek olarak ekle (daha kısa ama hızlı)
        for sn in ddg_snippets:
            if sn["url"] not in seen_urls:
                seen_urls.add(sn["url"])
                parcalar.append(f"📎 {sn['title']}\n{sn['text']}\nKaynak: {sn['url']}")

        # Wikipedia
        if wiki_ozet:
            parcalar.append(f"📚 Wikipedia\n{wiki_ozet}")

        if not parcalar:
            return None

        return "\n\n---\n\n".join(parcalar[:5])  # En fazla 5 kaynak

    async def web_ara_asamali(self, sorgu, message=None, max_results=4):
        """
        Aşamalı web arama: Kullanıcıya aşamaları gösterir,
        birden fazla kaynağı birleştirir, derin içerik çeker.
        """
        cache_key = f"asamali_{sorgu.lower()}_{max_results}"
        if cache_key in self.web_cache:
            cached = self.web_cache[cache_key]
            if time.time() - cached["time"] < self.cache_ttl:
                return cached["result"]

        loop = asyncio.get_running_loop()
        progress_msg = None

        # ═══ AŞAMA 1: URL Toplama ═══
        try:
            if message:
                embed1 = discord.Embed(
                    description="🔍 **Aşama 1/3** — Web'de aranıyor...\n`Kaynaklar bulunuyor`",
                    color=discord.Color.blue()
                )
                progress_msg = await message.reply(embed=embed1)
        except Exception:
            pass

        try:
            urls = await asyncio.wait_for(
                loop.run_in_executor(None, self._url_topla, sorgu, max_results),
                timeout=12
            )
        except Exception:
            urls = []

        try:
            ddg_snippets = await asyncio.wait_for(
                loop.run_in_executor(None, self._ddg_snippet_topla, sorgu, max_results),
                timeout=8
            )
        except Exception:
            ddg_snippets = []

        if not urls and not ddg_snippets:
            # Son çare: Wikipedia
            wiki = None
            try:
                wiki = await loop.run_in_executor(None, self.web_ara_wikipedia, sorgu)
            except Exception:
                pass
            if progress_msg:
                try:
                    if wiki:
                        embed_done = discord.Embed(
                            description="✅ **Arama tamamlandı** — Sadece Wikipedia'dan sonuç bulundu.",
                            color=discord.Color.green()
                        )
                    else:
                        embed_done = discord.Embed(
                            description="❌ **Arama tamamlandı** — Hiçbir kaynak bulunamadı.",
                            color=discord.Color.red()
                        )
                    await progress_msg.edit(embed=embed_done)
                except Exception:
                    pass
            return wiki

        # ═══ AŞAMA 2: Sayfaları Oku ═══
        try:
            if progress_msg:
                embed2 = discord.Embed(
                    description=f"📄 **Aşama 2/3** — {len(urls)} sayfa okunuyor...\n`İçerikler çekiliyor`",
                    color=discord.Color.blue()
                )
                await progress_msg.edit(embed=embed2)
        except Exception:
            pass

        try:
            sayfa_icerikleri = await asyncio.wait_for(
                loop.run_in_executor(None, self._sayfa_icerikleri_cek, urls, 600),
                timeout=20
            )
        except Exception:
            sayfa_icerikleri = []

        # Wikipedia ek bilgi
        wiki_ozet = None
        try:
            wiki_ozet = await loop.run_in_executor(None, self.web_ara_wikipedia, sorgu)
        except Exception:
            pass

        # ═══ AŞAMA 3: Birleştirme ═══
        try:
            if progress_msg:
                embed3 = discord.Embed(
                    description=f"🧠 **Aşama 3/3** — Bilgiler analiz ediliyor...\n`{len(sayfa_icerikleri)} sayfa + {len(ddg_snippets)} snippet birleştiriliyor`",
                    color=discord.Color.blue()
                )
                await progress_msg.edit(embed=embed3)
        except Exception:
            pass

        sonuc = self._birlestir_ve_formatla(sayfa_icerikleri, ddg_snippets, wiki_ozet)

        # İlerleme mesajını güncelle
        try:
            if progress_msg:
                kaynak_sayisi = len(sayfa_icerikleri) + len(ddg_snippets) + (1 if wiki_ozet else 0)
                embed_bitti = discord.Embed(
                    description=f"✅ **Arama tamamlandı** — {kaynak_sayisi} kaynaktan bilgi toplandı.",
                    color=discord.Color.green()
                )
                await progress_msg.edit(embed=embed_bitti)
        except Exception:
            pass

        if sonuc:
            self.web_cache[cache_key] = {"result": sonuc, "time": time.time()}
        return sonuc

    # Eski metodların geriye uyumluluğu için wrapper
    def web_ara_birlesik(self, sorgu, max_results=3):
        """Senkron wrapper - eski kodla uyumluluk için."""
        urls = self._url_topla(sorgu, max_results=max_results)
        ddg_snippets = self._ddg_snippet_topla(sorgu, max_results=max_results)
        sayfa_icerikleri = self._sayfa_icerikleri_cek(urls)
        wiki = self.web_ara_wikipedia(sorgu)
        return self._birlestir_ve_formatla(sayfa_icerikleri, ddg_snippets, wiki)

    def _kur_metinden_cek(self, text):
        if not text:
            return None
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
        try:
            url = f"https://www.google.com/finance/quote/{base}-{target}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            r = requests.get(url, timeout=8, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                # Google Finance'daki fiyat elementi
                price_div = soup.find("div", {"class": "YMlKec fxKbKc"})
                if price_div:
                    price_text = price_div.text.strip().replace(",", ".")
                    try:
                        return float(price_text)
                    except Exception:
                        pass
        except Exception as e:
            self.logger.debug(f"Google Finance hatası: {e}")

        if HAS_SELENIUM:
            query = f"1 {base} to {target}"
            try:
                driver = self._create_driver()
                try:
                    driver.set_page_load_timeout(8)
                    driver.get(f"https://www.google.com/search?q={quote_plus(query)}")
                    time.sleep(1)
                    # Google'ın kur çevirici elementleri
                    selectors = [
                        "span.DFlfde",
                        "input.a61j6",
                        "div.BNeawe.iBp4i.AP7Wnd"
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
                finally:
                    driver.quit()
            except Exception as e:
                self.logger.debug(f"Selenium kur hatası: {e}")

        if HAS_DDGS:
            query = f"1 {base} to {target}"
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, region='tr-tr', max_results=3))
                    for r in results:
                        body = r.get('body', '') or ''
                        rate = self._kur_metinden_cek(body)
                        if rate:
                            return rate
            except Exception as e:
                self.logger.debug(f"DuckDuckGo kur hatası: {e}")

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
        # Eğer aktif kanal ayarlanmışsa sadece orada konuş, yoksa her kanalda etiketlendiğinde konuş
        if aktif_kanal_id:
            # Aktif kanal varsa sadece orada veya etiketlendiğinde
            if message.channel.id == aktif_kanal_id:
                konusma_izni = True
            elif etiketlendi or yanitlandi or odakta_mi:
                konusma_izni = True
                self.odaklanilan_kisiler[user_id] = current_time
        else:
            # Aktif kanal yoksa sadece etiketlendiğinde konuş
            if etiketlendi or yanitlandi or odakta_mi:
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
                    "fiyat", "kur", "dolar", "euro", "altın", "borsa", "hava durumu", "yarın",
                    "bugün", "şu an", "kaç", "ne zaman", "maç", "puan", "sonuç",
                    "deprem", "seçim", "skor", "lig", "şampiyon", "araştır", "ara",
                    "nüfus", "istatistik", "enflasyon", "faiz"
                ])
                # Wikipedia: tanım/kimdir/nedir gibi bilgi isteklerinde önce wiki
                need_wiki = any(k in lu for k in ["nedir", "kimdir", "ne demek", "tarihçe", "biyografi"])

                wiki_ozet = self.web_ara_wikipedia(user_input) if need_wiki else None
                web_sonuclari = None
                if not wiki_ozet and need_web:
                    # Aşamalı web arama: çoklu kaynak + ilerleme gösterir
                    web_sonuclari = await self.web_ara_asamali(user_input, message=message, max_results=4)
                elif need_web:
                    # Wiki varsa yine de web'den destekle ama sessizce
                    web_sonuclari = await self.web_ara_asamali(user_input, message=None, max_results=3)
                
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
                    system_prompt += f"\n\nWEB ARAMA SONUÇLARI (birden fazla kaynaktan toplanan güncel bilgi):\n{web_sonuclari}"
                    system_prompt += (
                        "\n\nKRİTİK KURAL: Yukarıdaki web arama sonuçlarından elde edilen bilgiyi mutlaka kullan."
                        " Kullanıcının sorusuna doğrudan, net ve kısa cevap ver."
                        " Rakamsal veri varsa (fiyat, kur, istatistik) aynen yaz."
                        " 'Bir siteyi ziyaret et' veya 'güncel veriye ulaşamadım' gibi kaçamak cevaplar KESINLIKLE VERME."
                        " Kaynak URL'leri de cevabının sonunda paylaş."
                        " Eğer sonuçlarda çelişkili bilgi varsa, en güncel ve güvenilir kaynağı tercih et."
                    )
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