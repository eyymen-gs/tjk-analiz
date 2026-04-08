import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import pandas as pd
from datetime import datetime
import json
import time
from bs4 import BeautifulSoup

SEHIRLER = {
    "Istanbul":  1,
    "Izmir":     2,
    "Ankara":    3,
    "Bursa":     4,
    "Adana":     5,
    "Sanliurfa": 6,
    "Kocaeli":   7,
    "Antalya":   8,
    "Elazig":    9,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def bugun_tarih():
    return datetime.now().strftime("%d/%m/%Y")

def sehir_program_cek(sehir_adi, sehir_id, tarih):
    tarih_enc = tarih.replace("/", "%2F")
    url = (
        f"https://www.tjk.org/TR/YarisSever/Info/Sehir/GunlukYarisProgrami"
        f"?SehirId={sehir_id}&QueryParameter_Tarih={tarih_enc}"
        f"&SehirAdi={sehir_adi}&Era=today"
    )
    
    print(f"  URL: {url}")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  HTTP: {r.status_code}")
        
        if r.status_code != 200:
            return []
        
        soup = BeautifulSoup(r.text, "html.parser")
        kosular = []
        kosu_no = 0
        
        # Koşu başlıklarını bul
        kosu_basliklar = soup.find_all("h3", string=lambda x: x and "Koşu" in str(x))
        print(f"  Bulunan koşu sayısı: {len(kosu_basliklar)}")
        
        tablolar = soup.find_all("table")
        print(f"  Bulunan tablo sayısı: {len(tablolar)}")
        
        for tablo in tablolar:
            basliklar = tablo.find_all("th")
            if not basliklar:
                continue
            
            # At tablosu mu kontrol et
            baslik_metinleri = [b.text.strip() for b in basliklar]
            if "At İsmi" not in baslik_metinleri and "N" not in baslik_metinleri:
                continue
            
            kosu_no += 1
            satirlar = tablo.find_all("tr")[1:]
            
            for satir in satirlar:
                hucreler = satir.find_all("td")
                if len(hucreler) < 8:
                    continue
                
                try:
                    at_linki = satir.find("a", href=lambda x: x and "AtKosuBilgileri" in str(x))
                    at_adi   = at_linki.text.strip() if at_linki else ""
                    
                    at_id = None
                    if at_linki:
                        href = at_linki.get("href", "")
                        if "AtId=" in href:
                            at_id = href.split("AtId=")[-1].split("&")[0]
                    
                    jokey_linki    = satir.find("a", href=lambda x: x and "JokeyIstatistikleri" in str(x))
                    antrenor_linki = satir.find("a", href=lambda x: x and "AntrenorIstatistikleri" in str(x))
                    
                    jokey    = jokey_linki.text.strip()    if jokey_linki    else ""
                    antrenor = antrenor_linki.text.strip() if antrenor_linki else ""
                    
                    metinler = [h.text.strip() for h in hucreler]
                    
                    if not at_adi:
                        continue
                    
                    kosular.append({
                        "sehir":    sehir_adi,
                        "tarih":    tarih,
                        "kosu_no":  kosu_no,
                        "at_no":    metinler[1]  if len(metinler) > 1  else "",
                        "at_adi":   at_adi,
                        "at_id":    at_id,
                        "yas":      metinler[3]  if len(metinler) > 3  else "",
                        "siklet":   metinler[5]  if len(metinler) > 5  else "",
                        "jokey":    jokey,
                        "antrenor": antrenor,
                        "start":    metinler[9]  if len(metinler) > 9  else "",
                        "hp":       metinler[10] if len(metinler) > 10 else "",
                        "son6":     metinler[11] if len(metinler) > 11 else "",
                        "kgs":      metinler[12] if len(metinler) > 12 else "",
                        "en_iyi":   metinler[14] if len(metinler) > 14 else "",
                        "gny":      metinler[15] if len(metinler) > 15 else "",
                        "agf":      metinler[16] if len(metinler) > 16 else "",
                    })
                except Exception as e:
                    continue
        
        return kosular
    
    except Exception as e:
        print(f"  Hata: {e}")
        return []

def aktif_sehirleri_bul(tarih):
    """Bugün yarış olan şehirleri bul"""
    tarih_enc = tarih.replace("/", "%2F")
    url = f"https://www.tjk.org/TR/yarissever/Info/Page/GunlukYarisProgrami?QueryParameter_Tarih={tarih_enc}&Era=today"
    
    r    = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    
    sehirler = []
    linkler  = soup.find_all("a", href=lambda x: x and "SehirId=" in str(x) and "GunlukYarisProgrami" in str(x))
    
    goruldu = set()
    for link in linkler:
        href = link.get("href", "")
        sid  = href.split("SehirId=")[-1].split("&")[0]
        sadi_enc = href.split("SehirAdi=")[-1].split("&")[0] if "SehirAdi=" in href else ""
        
        # URL decode
        sadi = requests.utils.unquote(sadi_enc)
        
        if sid.isdigit() and sid not in goruldu:
            # Yabancı hipodromları filtrele (ID > 20)
            if int(sid) <= 20:
                goruldu.add(sid)
                sehirler.append({
                    "id":  int(sid),
                    "adi": sadi if sadi else link.text.strip()
                })
    
    return sehirler

# ─── Ana çalıştırma ──────────────────────────────────────────────────

if __name__ == "__main__":
    tarih = bugun_tarih()
    print(f"\n📅 {tarih} tarihli program çekiliyor...\n")
    
    # Bugün yarış olan şehirleri bul
    sehirler = aktif_sehirleri_bul(tarih)
    
    if not sehirler:
        print("❌ Bugün yarış bulunamadı veya site erişilemiyor.")
        exit()
    
    print(f"🏇 Bugün yarış olan şehirler:")
    for s in sehirler:
        print(f"   {s['adi']} (ID: {s['id']})")
    
    # Her şehir için veri çek
    tum_veri = {}
    
    for sehir in sehirler:
        print(f"\n⬇️  {sehir['adi']} çekiliyor...")
        kosular = sehir_program_cek(sehir['adi'], sehir['id'], tarih)
        
        if kosular:
            tum_veri[sehir['adi']] = kosular
            print(f"   ✅ {len(kosular)} at verisi alındı")
        else:
            print(f"   ❌ Veri alınamadı")
        
        time.sleep(2)
    
    # Kaydet
    with open("tjk_bugun.json", "w", encoding="utf-8") as f:
        json.dump(tum_veri, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Tamamlandı! tjk_bugun.json oluşturuldu.")
    toplam = sum(len(v) for v in tum_veri.values())
    print(f"✅ Toplam {toplam} at verisi kaydedildi.")
    
    if toplam == 0:
        print("\n⚠️  Veri gelmedi. Terminalde URL'yi kontrol et.")
        print("    TJK sitesine tarayıcıdan erişebildiğini doğrula.")