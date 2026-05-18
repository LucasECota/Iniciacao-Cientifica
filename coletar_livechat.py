"""
Coleta de Live Chat - Script Genérico
======================================

Coleta o live chat de qualquer confronto a partir de um arquivo .jsonl
gerado pelo gerar_jsonl.py.

Instalação:
    pip install pytchat yt-dlp

Uso:
    # Coleta todos os vídeos de um confronto
    python coletar_livechat.py --input data/cam_x_cru/videos_cam_x_cru_itatiaia.jsonl

    # Coleta intervalo específico (índices base-0)
    python coletar_livechat.py --input data/cam_x_cru/videos_cam_x_cru_itatiaia.jsonl --start 0 --end 3

    # Sem enriquecimento via yt-dlp
    python coletar_livechat.py --input data/fla_x_flu/videos_fla_x_flu_tupi.jsonl --no-ytdlp

Saída (derivada automaticamente do --input):
    data/cam_x_cru/livechats_cam_x_cru_itatiaia.jsonl
    data/cam_x_cru/coleta_cam_x_cru_itatiaia.log
"""

import pytchat
import json
import datetime
import argparse
import re
import subprocess
import sys
from pathlib import Path

# ─── Helpers ─────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Suporta /watch?v=ID, /live/ID e youtu.be/ID."""
    m = re.search(r"youtube\.com/live/([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    return None


def fetch_metadata_ytdlp(video_id: str) -> dict:
    """Busca título, data e canal via yt-dlp (sem baixar o vídeo)."""
    try:
        result = subprocess.run(
            [
                "yt-dlp", "--no-download",
                "--print", "%(title)s|||%(upload_date)s|||%(channel)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|||")
            if len(parts) == 3:
                title, raw_date, channel = parts
                d = raw_date.strip()
                date = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
                return {
                    "title":      title.strip(),
                    "date":       date,
                    "yt_channel": channel.strip(),
                }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {}


def load_matches(path: Path) -> list[dict]:
    matches = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                matches.append(json.loads(line))
    return matches


def clean_message(data: dict, alias: str, event: str, video_id: str) -> dict:
    """Injeta metadados do jogo e remove campos irrelevantes."""
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
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    if log_f:
        log_f.write(line + "\n")
        log_f.flush()


def derive_output_paths(input_path: Path) -> tuple[Path, Path]:
    """
    A partir de 'data/cam_x_cru/videos_cam_x_cru_itatiaia.jsonl'
    deriva:
        output → 'data/cam_x_cru/livechats_cam_x_cru_itatiaia.jsonl'
        log    → 'data/cam_x_cru/coleta_cam_x_cru_itatiaia.log'
    """
    stem = input_path.stem  # 'videos_cam_x_cru_itatiaia'
    base = re.sub(r"^videos_", "", stem)   # 'cam_x_cru_itatiaia'
    folder = input_path.parent
    output = folder / f"livechats_{base}.jsonl"
    log_f  = folder / f"coleta_{base}.log"
    return output, log_f

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Coleta live chat de um confronto")
    parser.add_argument("--input",    required=True, help="Arquivo .jsonl de vídeos (gerado por gerar_jsonl.py)")
    parser.add_argument("--start",    type=int, default=0,    help="Índice inicial (base 0)")
    parser.add_argument("--end",      type=int, default=None, help="Índice final exclusivo")
    parser.add_argument("--no-ytdlp", action="store_true",   help="Não usar yt-dlp para enriquecer metadados")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {input_path}")
        sys.exit(1)

    output_path, log_path = derive_output_paths(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    matches = load_matches(input_path)
    subset  = matches[args.start : args.end]

    if not subset:
        print("Nenhum jogo no intervalo especificado.")
        sys.exit(0)

    total_msgs = 0

    with (
        open(output_path, "a", encoding="utf-8") as out_f,
        open(log_path,    "a", encoding="utf-8") as log_f,
    ):
        log(f"Iniciando coleta: {len(subset)} jogo(s) | índices [{args.start}:{args.end}]", log_f)
        log(f"Input:  {input_path}", log_f)
        log(f"Output: {output_path}", log_f)

        for i, match in enumerate(subset, start=args.start):
            url   = match.get("url")
            alias = match.get("alias", f"JOGO_{i:02d}")
            event = match.get("event", "TBD")
            date  = match.get("date", "")

            if not url:
                log(f"[AVISO] Jogo {i+1} sem URL ({date}) — pulando.", log_f)
                continue

            video_id = extract_video_id(url)
            if not video_id:
                log(f"[ERRO] Não foi possível extrair video_id de '{url}' — pulando.", log_f)
                continue

            # ── Enriquecimento via yt-dlp ────────────────────────────────────
            if not args.no_ytdlp and (event in ("TBD", "", None) or not match.get("title")):
                meta = fetch_metadata_ytdlp(video_id)
                if meta:
                    event           = meta.get("title", event)
                    match["title"]  = meta.get("title", "")
                    match["date"]   = meta.get("date",  date)
                    match["yt_channel"] = meta.get("yt_channel", "")
                    log(f"yt-dlp: {video_id} → '{event}' ({match['date']})", log_f)

            log(
                f"[{i+1}/{len(matches)}] {alias}\n"
                f"  event={event}\n"
                f"  date={date} | url={url}",
                log_f,
            )

            # ── Coleta do chat ───────────────────────────────────────────────
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
        log(f"   Saída: {output_path}", log_f)


if __name__ == "__main__":
    main()
