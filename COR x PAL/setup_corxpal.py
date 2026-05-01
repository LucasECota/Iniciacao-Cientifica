"""
Geração do JSONL + Coleta de Live Chat — Corinthians x Palmeiras (Jovem Pan Esportes)
======================================================================================
Passo 1:  python setup_corxpal.py --gerar
          → busca título de cada vídeo via yt-dlp, extrai a data do título e salva o JSONL

Passo 2:  python setup_corxpal.py --coletar
          → lê o JSONL e coleta os live chats com pytchat

Ou tudo de uma vez:
          python setup_corxpal.py --gerar --coletar

Dependências:
    pip install pytchat yt-dlp
"""

import json
import re
import subprocess
import datetime
import argparse
from pathlib import Path

# ─── Vídeos ───────────────────────────────────────────────────────────────────
VIDEO_IDS = [
    "ZK9nQfCB-0U", "sT_OxoYRh04", "4vghM8ZXj8c",  "QsiG3NL4Jiw",
    "-z2lJj9n16Q", "3a2BZ-U9sKw", "CNKHW4v1jJ0",  "leLxORFyI9o",
    "EEtj18GHIPw", "ejJoYRNhZoo", "JnC8bUTQf-M",  "VWntSTwnrGU",
    "TIa092-wrKk", "usk3Umnhxf4", "urlInVo2epE",
]

JSONL_FILE  = "data/corxpal/videos_corxpal_band.jsonl"
OUTPUT_FILE = "data/corxpal/livechats_corxpal_band.jsonl"
LOG_FILE    = "data/corxpal/coleta_band.log"

# ─── Helpers ──────────────────────────────────────────────────────────────────

YTDLP_EXTRA = []
# Se precisar de cookies descomente a linha abaixo e ajuste o browser:
# YTDLP_EXTRA = ["--cookies-from-browser", "chrome"]
# Ou com arquivo de cookies:
# YTDLP_EXTRA = ["--cookies", "cookies.txt"]


def fetch_title_and_date(video_id: str) -> tuple[str, str]:
    """
    Busca título e data de upload via yt-dlp.
    Retorna (título, "YYYY-MM-DD").
    """
    try:
        r = subprocess.run(
            ["yt-dlp"] + YTDLP_EXTRA + [
                "--no-download", "--print", "%(title)s|||%(upload_date)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split("|||")
            if len(parts) == 2:
                title, raw = parts
                d = raw.strip()
                date = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else "0000-00-00"
                return title.strip(), date
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "", "0000-00-00"


def extract_date_from_title(title: str) -> str:
    """
    Tenta extrair a data do título do vídeo.
    Suporta formatos comuns: DD/MM/YYYY, DD/MM/YY, DD.MM.YYYY, YYYY-MM-DD
    """
    # DD/MM/YYYY ou DD/MM/YY
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", title)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    # YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", title)
    if m:
        return m.group(0)
    return None


def clean_message(data: dict, alias: str, event: str, video_id: str) -> dict:
    data["alias"]    = alias
    data["event"]    = event
    data["video_id"] = video_id
    author = data.get("author", {})
    for campo in ("imageUrl", "bgColor", "channelUrl", "badgeUrl"):
        author.pop(campo, None)
    for campo in ("messageEx", "amountString"):
        data.pop(campo, None)
    return data


def log(msg: str, log_f=None):
    now  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    if log_f:
        log_f.write(line + "\n")
        log_f.flush()

# ─── Passo 1: gerar JSONL ─────────────────────────────────────────────────────

def gerar_jsonl():
    Path(JSONL_FILE).parent.mkdir(parents=True, exist_ok=True)

    matches = []
    for i, vid in enumerate(VIDEO_IDS, 1):
        print(f"[{i:02d}/{len(VIDEO_IDS)}] {vid} ... buscando título", end=" ", flush=True)

        title, upload_date = fetch_title_and_date(vid)

        # Tenta extrair a data do título primeiro (mais precisa para data do jogo)
        date_from_title = extract_date_from_title(title) if title else None
        date = date_from_title or upload_date

        alias = f"CORxPAL - {date}"
        entry = {
            "event"   : alias,
            "alias"   : alias,
            "url"     : f"https://www.youtube.com/watch?v={vid}",
            "date"    : date,
            "title"   : title,
            "home"    : "Corinthians",
            "away"    : "Palmeiras",
            "channel" : "Jovem Pan Esportes",
        }
        matches.append(entry)
        print(f"→ {alias}  |  {title[:60]}")

    # Ordena por data
    matches.sort(key=lambda x: x["date"])

    with open(JSONL_FILE, "w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"\n✅ JSONL salvo em: {JSONL_FILE}")
    print(f"   {len(matches)} partidas | {matches[0]['date']} → {matches[-1]['date']}")

# ─── Passo 2: coletar live chats ──────────────────────────────────────────────

def coletar():
    import pytchat

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    matches = []
    with open(JSONL_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                matches.append(json.loads(line))

    total_msgs = 0

    with (
        open(OUTPUT_FILE, "a", encoding="utf-8") as out_f,
        open(LOG_FILE,    "a", encoding="utf-8") as log_f,
    ):
        log(f"Iniciando coleta: {len(matches)} vídeos", log_f)

        for i, match in enumerate(matches, 1):
            alias    = match["alias"]
            event    = match["event"]
            url      = match["url"]
            # Extrai video_id da URL (suporta ?v= e /live/)
            m = re.search(r"(?:watch\?v=|live/)([A-Za-z0-9_-]{11})", url)
            video_id = m.group(1) if m else url.split("=")[-1]

            log(f"[{i:02d}/{len(matches)}] {alias}  (video_id={video_id})", log_f)

            try:
                chat = pytchat.create(video_id=video_id)
            except Exception as exc:
                log(f"  [ERRO] pytchat: {exc}", log_f)
                continue

            if not chat.is_alive():
                log(f"  [AVISO] Chat indisponível para {video_id}", log_f)
                continue

            msgs_jogo = 0
            while chat.is_alive():
                for msg in chat.get().items:
                    data = json.loads(msg.json())
                    data = clean_message(data, alias, event, video_id)
                    out_f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    msgs_jogo  += 1
                    total_msgs += 1
                    if total_msgs % 50_000 == 0:
                        log(f"  Total acumulado: {total_msgs:,}", log_f)

            log(f"  ✓ {msgs_jogo:,} mensagens coletadas", log_f)

        log(f"\n{'─'*60}", log_f)
        log(f"✅ Coleta concluída. Total: {total_msgs:,} → {OUTPUT_FILE}", log_f)

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta live chat Corinthians x Palmeiras")
    parser.add_argument("--gerar",   action="store_true", help="Gera o JSONL com datas reais")
    parser.add_argument("--coletar", action="store_true", help="Coleta os live chats")
    args = parser.parse_args()

    if not args.gerar and not args.coletar:
        parser.print_help()
    if args.gerar:
        gerar_jsonl()
    if args.coletar:
        coletar()
