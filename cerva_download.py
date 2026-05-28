import requests
import os
import sys
from datetime import datetime

# ============================================================
# KONFIGURÁCIA - hodnoty sa načítajú z GitHub Secrets
# ============================================================

USERNAME   = os.environ.get('CERVA_USERNAME')
PASSWORD   = os.environ.get('CERVA_PASSWORD')
PARTNER_ID = os.environ.get('CERVA_PARTNER_ID')
COUNTRY    = 'sk'
LANG       = 'sk'

FEEDS_TO_DOWNLOAD = ['CATALOG', 'PRICES', 'DISPO']
OUTPUT_DIR = 'feeds'

# ============================================================
# FUNKCIE
# ============================================================

def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def get_token():
    log("Získavam token...")
    url = "https://www.cerva.com/authorizationserver/oauth/token"
    params = {
        'grant_type': 'password',
        'client_id':  'crvweb',
        'username':   USERNAME,
        'password':   PASSWORD,
        'partner':    PARTNER_ID,
    }
    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        token = response.json().get('access_token')
        if not token:
            log(f"CHYBA: Token nebol v odpovedi. Odpoveď: {response.text}")
            return None
        log("Token úspešne získaný.")
        return token
    except Exception as e:
        log(f"CHYBA pri získaní tokenu: {e}")
        return None

def get_feed_url(token, feed_name):
    log(f"Získavam URL pre feed: {feed_name}")
    url = f"https://www.cerva.com/api/{COUNTRY}/feed"
    params = {
        'partner': PARTNER_ID,
        'lang':    LANG,
    }
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Odpoveď môže byť zoznam alebo jeden objekt
        feeds = data if isinstance(data, list) else [data]

        for feed in feeds:
            name = (feed.get('name') or feed.get('type') or '').upper()
            if name == feed_name.upper():
                status = feed.get('status', '')
                if status == 'WAITING':
                    log(f"Feed {feed_name} má status WAITING - nie je ešte pripravený.")
                    return None
                if status != 'READY':
                    log(f"Feed {feed_name} má neznámy status: {status}")
                    return None
                download_path = feed.get('downloadUrl')
                if download_path:
                    if not download_path.startswith('http'):
                        return f"https://www.cerva.com/{download_path.lstrip('/')}"
                    return download_path

        log(f"Feed {feed_name} nebol nájdený. Celá odpoveď: {data}")
        return None

    except Exception as e:
        log(f"CHYBA pri získaní URL pre {feed_name}: {e}")
        return None

def download_feed(token, download_url, feed_name):
    log(f"Sťahujem XML pre {feed_name}...")
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(download_url, headers=headers, timeout=120)
        response.raise_for_status()

        if not response.content:
            log(f"CHYBA: Prázdna odpoveď pre {feed_name}")
            return False

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, f"{feed_name.lower()}.xml")

        with open(filepath, 'wb') as f:
            f.write(response.content)

        size_kb = len(response.content) / 1024
        log(f"OK: {feed_name} uložený ({size_kb:.1f} KB) → {filepath}")
        return True

    except Exception as e:
        log(f"CHYBA pri sťahovaní {feed_name}: {e}")
        return False

# ============================================================
# HLAVNÝ BEH
# ============================================================

def main():
    log("=== CERVA Feed Download START ===")

    # Kontrola či sú nastavené premenné
    if not all([USERNAME, PASSWORD, PARTNER_ID]):
        log("CHYBA: Chýbajú environment variables (CERVA_USERNAME, CERVA_PASSWORD, CERVA_PARTNER_ID)")
        sys.exit(1)

    # Krok 1: Token
    token = get_token()
    if not token:
        log("CHYBA: Nepodarilo sa získať token. Končím.")
        sys.exit(1)

    # Krok 2 + 3: Pre každý feed získaj URL a stiahni
    errors = []
    for feed_name in FEEDS_TO_DOWNLOAD:
        log(f"--- {feed_name} ---")
        download_url = get_feed_url(token, feed_name)
        if not download_url:
            errors.append(feed_name)
            continue
        success = download_feed(token, download_url, feed_name)
        if not success:
            errors.append(feed_name)

    log("=== CERVA Feed Download KONIEC ===")

    if errors:
        log(f"Feedy s chybou: {', '.join(errors)}")
        sys.exit(1)
    else:
        log("Všetky feedy úspešne stiahnuté!")

if __name__ == '__main__':
    main()
