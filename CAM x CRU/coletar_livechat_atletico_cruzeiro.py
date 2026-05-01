"""
Coleta de Live Chat - Clássico Atlético x Cruzeiro (Itatiaia)
=============================================================

Fluxo:
  1. Lê videos_atletico_cruzeiro_itatiaia.jsonl
  2. Para cada vídeo, tenta buscar título/data via yt-dlp (opcional)
  3. Coleta o live chat com pytchat
  4. Salva em data/atletico_cruzeiro/livechats_atletico_cruzeiro.jsonl

Instalação:
    pip install pytchat yt-dlp

Execução:
    python coletar_livechat_atletico_cruzeiro.py

    # Para rodar só alguns vídeos (por índice, base-0):
    python coletar_livechat_atletico_cruzeiro.py --start 0 --end 5
"""

import pytchat
import json
import datetime
import argparse
import re
import subprocess
import sys
from pathlib import Path

# ─── Configuração ────────────────────────────────────────────────────────────
INPUT_FILE  = "data/atletico_cruzeiro/videos_atletico_cruzeiro_itatiaia.jsonl"
OUTPUT_FILE = "data/atletico_cruzeiro/livechats_atletico_cruzeiro.jsonl"
LOG_FILE    = "data/atletico_cruzeiro/coleta.log"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Suporta /watch?v=ID, /live/ID e youtu.be/ID."""
    # /live/ID
    m = re.search(r"youtube\.com/live/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # /watch?v=ID
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # youtu.be/ID
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    return None


def fetch_metadata_ytdlp(video_id: str) -> dict:
    """
    Busca título e data de upload via yt-dlp (sem baixar o vídeo).
    Retorna {} se yt-dlp não estiver instalado ou falhar.
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-download",
                "--print", "%(title)s|||%(upload_date)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|||")
            if len(parts) == 2:
                title, raw_date = parts
                # raw_date: YYYYMMDD
                date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else raw_date
                return {"title": title.strip(), "date": date}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {}


def load_matches(path: str) -> list[dict]:
    matches = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                matches.append(json.loads(line))
    return matches


def clean_message(data: dict, alias: str, event: str, video_id: str) -> dict:
    """Injeta metadados do jogo e remove campos indesejados."""
    data["alias"]    = alias
    data["event"]    = event
    data["video_id"] = video_id

    author = data.get("author", {})
    for campo in ("imageUrl", "bgColor", "channelUrl", "badgeUrl"):
        author.pop(campo, None)

    for campo in ("messageEx", "amountString"):
        data.pop(campo, None)

    return data


def log(msg: str, log_f):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    log_f.write(line + "\n")
    log_f.flush()

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Coleta live chat Atlético x Cruzeiro")
    parser.add_argument("--start", type=int, default=0,   help="Índice inicial (base 0)")
    parser.add_argument("--end",   type=int, default=None, help="Índice final exclusivo")
    parser.add_argument("--no-ytdlp", action="store_true", help="Não usar yt-dlp para metadados")
    args = parser.parse_args()

    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    matches = load_matches(INPUT_FILE)
    subset  = matches[args.start : args.end]

    if not subset:
        print("Nenhum jogo no intervalo especificado.")
        sys.exit(0)

    total_msgs = 0

    with (
        open(OUTPUT_FILE, "a", encoding="utf-8") as out_f,
        open(LOG_FILE,    "a", encoding="utf-8") as log_f,
    ):
        log(f"Iniciando coleta: {len(subset)} jogo(s) | índices [{args.start}:{args.end}]", log_f)

        for i, match in enumerate(subset, start=args.start):
            url   = match["url"]
            alias = match.get("alias", f"ATLxCRU_{i:02d}")
            event = match.get("event", "TBD")

            video_id = extract_video_id(url)
            if not video_id:
                log(f"[ERRO] Não foi possível extrair video_id de '{url}' — pulando.", log_f)
                continue

            # ── Enriquecimento de metadados via yt-dlp ──────────────────────
            if not args.no_ytdlp and event == "TBD":
                meta = fetch_metadata_ytdlp(video_id)
                if meta:
                    event = meta.get("title", event)
                    match["date"]  = meta.get("date", match.get("date", ""))
                    match["title"] = meta.get("title", "")
                    log(f"yt-dlp: {video_id} → '{event}' ({match['date']})", log_f)

            log(
                f"[{i+1}/{len(matches)}] Coletando: {alias}\n"
                f"  event={event}\n"
                f"  url={url}  video_id={video_id}",
                log_f,
            )

            # ── Coleta do chat ──────────────────────────────────────────────
            try:
                chat = pytchat.create(video_id=video_id)
            except Exception as exc:
                log(f"[ERRO] pytchat falhou para {video_id}: {exc}", log_f)
                continue

            if not chat.is_alive():
                log(
                    f"[AVISO] Chat indisponível para video_id={video_id}.\n"
                    "  Possíveis causas: vídeo muito antigo, chat desabilitado ou URL inválida.",
                    log_f,
                )
                continue

            msgs_neste_jogo = 0
            while chat.is_alive():
                for msg in chat.get().items:
                    data = json.loads(msg.json())
                    data = clean_message(data, alias, event, video_id)
                    out_f.write(json.dumps(data, ensure_ascii=False) + "\n")
                    msgs_neste_jogo += 1
                    total_msgs      += 1

                    if total_msgs % 50_000 == 0:
                        log(f"Mensagens coletadas (total): {total_msgs:,}", log_f)

            log(f"✓ {alias} concluído — {msgs_neste_jogo:,} mensagens.", log_f)

        log(f"\n{'─'*60}", log_f)
        log(f"✅ Coleta finalizada. Total geral: {total_msgs:,} mensagens.", log_f)
        log(f"   Saída: {OUTPUT_FILE}", log_f)


if __name__ == "__main__":
    main()
