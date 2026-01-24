# 🎯 Discord Slash Komutlar Rehberi

## ✅ Başarıyla Eklendi!

Botunuz artık Discord'un modern **slash komut sistemi** ile çalışıyor. Kullanıcılar Discord'da `/` yazarak tüm komutları görebilir ve otomatik tamamlama özelliği ile kolayca kullanabilir.

---

## 📋 Mevcut Slash Komutlar

### 🎛️ Panel & Ayarlar

#### `/panel`
- **Açıklama**: Sunucu ayar panelini açar (moderasyon, çekiliş, bilet, sohbet)
- **Yetki**: Administrator
- **Kullanım**: `/panel`
- **Özellikler**:
  - 🛡️ Moderasyon ayarları (Link/Caps/Küfür engel)
  - ⚠️ Uyarı sistemi (Eşik, Süre, DM)
  - 🎉 Çekiliş komutları
  - 🎫 Bilet sistemi
  - 💬 Sohbet ayarları (Hoşgeldin, Level)

#### `/ayarlar`
- **Açıklama**: Sunucu ayarlarını gösterir
- **Yetki**: Herkes (ephemeral, sadece sen görürsün)
- **Kullanım**: `/ayarlar`
- **Gösterir**:
  - Moderasyon durumları
  - Uyarı eşikleri ve süreleri
  - Hoşgeldin mesajı
  - AI kanalı

---

### 🛡️ Moderasyon Komutları

#### `/sil`
- **Açıklama**: Belirtilen sayıda mesajı siler
- **Yetki**: Manage Messages
- **Kullanım**: `/sil miktar:100`
- **Parametreler**:
  - `miktar`: Silinecek mesaj sayısı (max 1000)
- **Not**: 14 günden eski mesajlar silinemez

#### `/uyar`
- **Açıklama**: Kullanıcıyı uyarır
- **Yetki**: Manage Messages
- **Kullanım**: `/uyar uye:@Kullanıcı sebep:Spam`
- **Parametreler**:
  - `uye`: Uyarılacak kullanıcı
  - `sebep`: Uyarı sebebi (opsiyonel)
- **Özellikler**:
  - Otomatik uyarı ID oluşturur
  - DM ile kullanıcıya bildirim gönderir
  - Otomatik susturma sistemi (eşik aşılırsa)

#### `/ban`
- **Açıklama**: Kullanıcıyı sunucudan yasaklar
- **Yetki**: Ban Members
- **Kullanım**: `/ban uye:@Kullanıcı sebep:Kurallara uymadı`
- **Parametreler**:
  - `uye`: Yasaklanacak kullanıcı
  - `sebep`: Yasaklama sebebi (opsiyonel)

#### `/kick`
- **Açıklama**: Kullanıcıyı sunucudan atar
- **Yetki**: Kick Members
- **Kullanım**: `/kick uye:@Kullanıcı sebep:Uyarısız davranış`
- **Parametreler**:
  - `uye`: Atılacak kullanıcı
  - `sebep`: Atma sebebi (opsiyonel)

#### `/sustur`
- **Açıklama**: Kullanıcıyı geçici olarak susturur
- **Yetki**: Moderate Members
- **Kullanım**: `/sustur uye:@Kullanıcı sure:10`
- **Parametreler**:
  - `uye`: Susturulacak kullanıcı
  - `sure`: Süre (dakika cinsinden)
- **Örnek**: `/sustur uye:@Spam sure:30` → 30 dakika susturur

#### `/susturma-kaldir`
- **Açıklama**: Kullanıcının susturmasını kaldırır
- **Yetki**: Moderate Members
- **Kullanım**: `/susturma-kaldir uye:@Kullanıcı`
- **Parametreler**:
  - `uye`: Susturması kaldırılacak kullanıcı

#### `/uyarilar`
- **Açıklama**: Kullanıcının veya sunucunun uyarılarını listeler
- **Yetki**: Manage Messages
- **Kullanım**: 
  - `/uyarilar` → Tüm sunucu uyarıları
  - `/uyarilar uye:@Kullanıcı` → Belirli kullanıcının uyarıları
- **Parametreler**:
  - `uye`: Uyarıları görüntülenecek kullanıcı (opsiyonel)

---

## 🎯 Kullanım Örnekleri

### Panel Açma
```
/panel
```
Discord'un otomatik menüsünde tüm ayarları görebilir ve butonlarla düzenleyebilirsiniz.

### Moderasyon Senaryoları

**Senaryo 1**: Spam yapan kullanıcı
```
/uyar uye:@SpamKullanici sebep:Spam yapmak yasak
```

**Senaryo 2**: Aşırı spam - susturma
```
/sustur uye:@SpamKullanici sure:60
```

**Senaryo 3**: Kurallara uymayan kullanıcı
```
/kick uye:@ProblemiKullanici sebep:Tekrarlayan kural ihlali
```

**Senaryo 4**: Ciddi ihlal
```
/ban uye:@KotuKullanici sebep:Hakaret ve ağır küfür
```

**Senaryo 5**: Mesaj temizliği
```
/sil miktar:50
```

**Senaryo 6**: Kullanıcı uyarılarını kontrol etme
```
/uyarilar uye:@Kullanici
```

---

## ⚙️ Teknik Detaylar

### Senkronizasyon
- Bot başlatıldığında otomatik olarak slash komutlar Discord'a senkronize edilir
- Log çıktısı: `✅ 7 slash komut Discord'a senkronize edildi!`

### Yetki Kontrolü
- Tüm komutlarda hiyerarşi kontrolü yapılır
- Sunucu sahibine işlem yapılamaz
- Üst rütbedekilere işlem yapılamaz
- Bot yetkisinin üstündekilere işlem yapılamaz

### Ephemeral Mesajlar
- `/panel` ve `/ayarlar` sadece komutu kullanan kişi tarafından görülür
- `/uyarilar` sadece yetkili tarafından görülür

### Prefix Komutlar
- Eski prefix komutlar (`!sil`, `!uyar` vb.) hala çalışıyor
- Hem slash hem prefix komutlar aynı anda kullanılabilir
- Natural language commands (Türkçe) de aktif

---

## 🚀 Avantajlar

### Kullanıcı Dostu
✅ Otomatik tamamlama  
✅ Parametre açıklamaları  
✅ Hata ayıklama kolaylığı  
✅ Discord native arayüz  

### Profesyonel Görünüm
✅ Modern Discord standardı  
✅ Mobil uyumlu  
✅ Kolay keşfedilebilir  
✅ İnteraktif panel butonları  

### Güvenlik
✅ Yetki kontrolleri  
✅ Hiyerarşi sistemi  
✅ Audit log entegrasyonu  
✅ DM bildirimleri  

---

## 📊 İstatistikler

- **Toplam Slash Komut**: 7 adet
- **Panel Komutları**: 2 adet (/panel, /ayarlar)
- **Moderasyon Komutları**: 5 adet (/sil, /uyar, /ban, /kick, /sustur, /susturma-kaldir, /uyarilar)
- **Otomatik Sync**: ✅ Aktif
- **Prefix Uyumluluk**: ✅ Hibrit sistem

---

## 🔧 Sorun Giderme

### Komutlar görünmüyor?
1. Botun `applications.commands` yetkisi olduğundan emin olun
2. Botu yeniden davet edin: [Davet Linki](https://discord.com/oauth2/authorize?client_id=BOT_ID&permissions=8&scope=bot%20applications.commands)
3. Log'da sync mesajını kontrol edin: `✅ 7 slash komut Discord'a senkronize edildi!`

### Yetki hatası alıyorum?
- Administrator yetkisi gerekiyor mu kontrol edin
- Hiyerarşi düzeninizi kontrol edin (üst rütbedekilere işlem yapılamaz)

### Panel butonları çalışmıyor?
- Botun mesaj gönderme yetkisi olduğundan emin olun
- Embed gönderme yetkisi olmalı

---

## 📝 Notlar

- Slash komutlar Discord'un cache'ine göre 1 saat içinde aktif hale gelir
- Global komutlar tüm sunucularda çalışır
- Komutlar her bot yeniden başlatıldığında otomatik sync edilir
- Panel butonları timeout yok (kalıcı)

---

## 🎉 Başarılı Kurulum!

Botunuz artık profesyonel Discord slash komut sistemi ile donatıldı. Kullanıcılar Discord'da `/` yazarak tüm komutları görebilir ve kolayca kullanabilir!

**Teknik Destek**: Herhangi bir sorunla karşılaşırsanız log dosyalarını kontrol edin.
