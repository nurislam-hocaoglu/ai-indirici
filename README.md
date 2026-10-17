<div align="center">
  <h1>AI İndirici</h1>
  <p>Telegram üzerinden Radarr, Bazarr, Jellyfin ve TMDB ile entegre çalışan hafif, Docker ile konuşlandırılabilir bir medya otomasyon botu.</p>

  <p>
    <a href="https://github.com/nurislam-hocaoglu/ai-indirici/stargazers">
      <img src="https://img.shields.io/github/stars/nurislam-hocaoglu/ai-indirici?style=for-the-badge&color=2A7FC2" alt="GitHub yıldızları">
    </a>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
  </p>
</div>

---

Türkçe belgelerle hazırlanmış, kendinize ait medya altyapısını Telegram üzerinden kolayca yönetmenizi sağlayan bir proje. Radarr tetiklemelerini dinler, TMDB'den meta veri çeker, altyazıları Bazarr ile yönetir ve Jellyfin ile kütüphane sorgularını yapar.

Neden bu proje?
- Evdeki medya sunucularınızı tek bir sohbet arayüzünden yönetmek için hızlı ve ölçeklenebilir bir çözüm sunar.
- Docker Compose ile tüm servisleri (bot dahil) tek komutla ayağa kaldırabilirsiniz.
- Ortam değişkenleri ile yapılandırma; hassas bilgiler deponuza push edilmez.

Öne çıkan özellikler
- Telegram bot arayüzü: Komutlar ve interaktif klavyeler ile yönetim
- Radarr entegrasyonu: Filmler için arama, ekleme ve durum takibi
- Bazarr entegrasyonu: Altyazı arama ve indirme desteği
- Jellyfin entegrasyonu: Kütüphane sorguları ve medya bilgisi
- TMDB: Zengin meta veri (poster, açıklama, türler)
- Webhook dinleyici: Radarr/Bazarr tetiklemelerini otomatik işler
- Docker destekli: Dockerfile + docker-compose.yml ile üretim/development kolaylığı

İçerik tablosu
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Gereksinimler](#gereksinimler)
- [Kurulum (Docker Compose ile)](#kurulum-docker-compose-ile)
- [Yerel Geliştirme](#yerel-geliştirme)
- [Yapılandırma (.env)](#yapılandırma-env)
- [Komutlar & Kullanım](#komutlar--kullanım)
- [Proje Mimarisi](#proje-mimarisi)
- [Katkıda Bulunma](#katkıda-bulunma)
- [Lisans](#lisans)


## Hızlı Başlangıç

Kopyalayın ve kendi değerlerinizi girin:

```bash
git clone https://github.com/nurislam-hocaoglu/ai-indirici.git
cd ai-indirici
cp .env.example .env
# .env içine TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, TMDB_API_KEY, RADARR_API_KEY, BAZARR_API_KEY, JELLYFIN_API_KEY gibi değerleri girin

docker compose up --build -d
```

Bot, docker ağı içinde Radarr/Bazarr/Jellyfin hizmetleriyle iletişim kuracak şekilde yapılandırılmıştır. docker-compose.yml içindeki host ve port ayarlarını kendi ortamınıza göre gözden geçirin.


## Gereksinimler
- Docker & Docker Compose
- Python 3.11+
- Telegram Bot Token (BotFather üzerinden alınır)
- TMDB API Key
- Radarr, Bazarr, Jellyfin servisleri (aynı ağda veya erişilebilir)


## Kurulum (Docker Compose ile)

1. .env dosyasını yapılandırın (aşağıya bakın).
2. Aşağıdaki komutla hizmetleri çalıştırın:

```bash
docker compose up --build -d
```

3. Logları görmek için:

```bash
docker compose logs -f bot
```


## Yerel Geliştirme

1. Sanal ortam oluşturun ve bağımlılıkları yükleyin:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. .env dosyasını oluşturup doldurun.
3. Aşağıdaki komutla botu başlatın:

```bash
python -m bot.main
```


## Yapılandırma (.env)

Projedeki `.env.example` dosyasında yer alan değişkenleri doldurun. Öne çıkan alanlar:

- TELEGRAM_BOT_TOKEN — Telegram bot token
- ADMIN_CHAT_ID — Hata/uyarı bildirimlerinin gideceği Telegram chat ID
- ALLOWED_USER_IDS — Virgülle ayrılmış izinli kullanıcı ID'leri (boş bırakılırsa herkese izin verir)
- TMDB_API_KEY — TMDB API anahtarı
- RADARR_URL / RADARR_API_KEY — Radarr erişim bilgileri
- BAZARR_URL / BAZARR_API_KEY — Bazarr erişim bilgileri
- JELLYFIN_URL / JELLYFIN_API_KEY — Jellyfin erişim bilgileri
- WEBHOOK_HOST / WEBHOOK_PORT — İç ağdan gelecek webhooklar için botun dinleme adresi

Güvenlik: `.env` dosyanızı versiyon kontrolüne eklemeyin. Özel anahtarları, tokenleri veya hassas bilgileri asla herkese açık bir repoya yüklemeyin.


## Komutlar & Kullanım

Bot, Telegram üzerinden çalışan bir dizi komut ve etkileşim sunar. Örnek kullanım:

- /status — Hizmetlerin genel durumunu gösterir
- /search <film adı> — TMDB üzerinden film araması yapar
- /add <tmdb_id> — Radarr'a film ekler
- Webhooklar — Radarr tetiklediğinde bot bilgilendirme mesajı gönderir ve admin onayı ile ek işlemler başlatabilir

(Komutların tam listesi ve davranışları `bot/handlers.py` içinde açıklanmıştır.)


## Proje Mimarisi

```text
ai-indirici/
├── bot/                   # Telegram bot kodu (handlers, keyboards, main)
├── services/              # Radarr, Bazarr, Jellyfin, TMDB adaptörleri ve webhook listener
├── config.py              # Pydantic ile ortam temelli ayarlar
├── docker-compose.yml     # Tüm hizmetlerin Docker Compose tanımı
├── Dockerfile             # Bot konteyneri için build tanımı
└── .env.example           # Örnek ortam değişkenleri
```

Kod yapısı basit ve modüler tutulmuştur: `services/` içindeki dosyalar harici API'lerle konuşur, `bot/` Telegram tarafını yönetir, `config.py` merkezi konfigürasyonu sağlar.


## Entegre Edilecek Servisler ve Ağ Yapısı
- Tüm servisler `medianet` isimli Docker ağı üzerinden haberleşecek şekilde yapılandırılmıştır.
- Radarr, Bazarr, Jellyfin ve qBittorrent konteynerleri kalıcı hacimlerle (volumes) tanımlıdır.
- Bot konteyneri `env_file: .env` ile ortam değişkenlerini alır ve webhook endpointi açar.


## Katkıda Bulunma
Katkılar memnuniyetle karşılanır — hata bildirimi, iyileştirme önerileri veya pull requestler gönderin.

1. Forklayın
2. Branch açın: `feature/öneri-isim`
3. Değişiklik yapıp test edin
4. Pull request açın, açıklayıcı bir özet ekleyin


## SSS
- Docker içinde çalıştırırken servisler birbirini görmüyorsa, `docker compose ps` ile container isimlerini ve network ayarlarını kontrol edin.
- Tokenlerin çalıştığından emin olmak için bot loglarını takip edin: `docker compose logs -f bot`.


## Lisans
Depoda henüz lisans belirtilmemiştir. Projeyi dağıtmayı düşünüyorsanız uygun bir lisans (`MIT`, `Apache-2.0` vb.) eklemenizi öneririm.


---

Geliştirici: Nurislam HOCAOĞLU

