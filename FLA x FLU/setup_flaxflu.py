"""
Geração do JSONL + Coleta de Live Chat — Fla x Flu (Tupi Esportes)
===================================================================
Passo 1:  python setup_flaxflu.py --gerar
          → busca a data real de cada vídeo via yt-dlp e salva o JSONL

Passo 2:  python setup_flaxflu.py --coletar
          → lê o JSONL e coleta os live chats com pytchat

Ou tudo de uma vez:
          python setup_flaxflu.py --gerar --coletar

Dependências:
    pip install pytchat yt-dlp
"""

import json
import re
import subprocess
import datetime
import argparse
from pathlib import Path

# ─── Configuração ─────────────────────────────────────────────────────────────
VIDEO_IDS = [
    "5VRw-skCzfc", "Sg5yNvzsqrA", "mLacZfK8rK8", "nLIc_wEQktU",
    "XlZWT79uGY4", "iHdqdd9DhKA", "6zPziQpIzcU", "cU1HKoobg6Q",
    "Nm59HxTRsqs", "KU74kwrdqYA", "9gutrrkfZe0", "nq8YcVX5Pi0",
    "EA4RX8yj5Xc", "6mJ1RO_nBic", "FAYmE_Djn98", "de8Ct9tBXlE",
    "eQJCbu16uvc", "_nQ1m_tgtFA", "js_oDFmqkZQ", "CzxiMu4wrCg",
    "CcVMRectX3g", "9kNVNAl5Ads", "8-WCdinuULc", "mMwRSv9BCcc",
]

JSONL_FILE  = "data/flaxflu/videos_flaxflu.jsonl"
OUTPUT_FILE = "data/flaxflu/livechats_flaxflu.jsonl"
LOG_FILE    = "data/flaxflu/coleta.log"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fetch_date(video_id: str) -> str:
    """Retorna a data de upload no formato YYYY-MM-DD via yt-dlp."""
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-download", "--print", "%(upload_date)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            d = r.stdout.strip()
            if len(d) == 8 and d.isdigit():
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "0000-00-00"


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
        print(f"[{i:02d}/{len(VIDEO_IDS)}] {vid} ... buscando data", end=" ", flush=True)
        date  = fetch_date(vid)
        alias = f"FLAxFLU - {date}"
        entry = {
            "event"  : alias,
            "alias"  : alias,
            "url"    : f"https://www.youtube.com/watch?v={vid}",
            "date"   : date,
            "home"   : "Flamengo",
            "away"   : "Fluminense",
            "channel": "Tupi Esportes",
        }
        matches.append(entry)
        print(f"→ {alias}")

    # Ordena por data
    matches.sort(key=lambda x: x["date"])

    with open(JSONL_FILE, "w", encoding="utf-8") as f:
        for m in matches:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"\n✅ JSONL salvo em: {JSONL_FILE}")
    print(f"   {len(matches)} partidas, período: {matches[0]['date']} → {matches[-1]['date']}")

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
            video_id = re.search(r"[?&v=/]([A-Za-z0-9_-]{11})$", url)
            video_id = video_id.group(1) if video_id else url.split("/")[-1].split("?v=")[-1]

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
        log(f"✅ Coleta concluída. Total: {total_msgs:,} mensagens → {OUTPUT_FILE}", log_f)

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gerar",   action="store_true", help="Gera o JSONL com datas reais")
    parser.add_argument("--coletar", action="store_true", help="Coleta os live chats")
    args = parser.parse_args()

    if not args.gerar and not args.coletar:
        parser.print_help()
    if args.gerar:
        gerar_jsonl()
    if args.coletar:
        coletar()
