"""
Enriquece um arquivo .jsonl de vídeos com título, data e canal reais via yt-dlp.
================================================================================

Reescreve o arquivo com os campos:
    title, event, date, yt_channel, home, away, alias

Uso:
    pip install yt-dlp
    python enriquecer_metadados.py --input data/cam_x_cru/videos_cam_x_cru_itatiaia.jsonl

    # Enriquecer todos os jsonls de uma vez:
    python enriquecer_metadados.py --all --data-dir data
"""

import json
import re
import subprocess
import argparse
import sys
from pathlib import Path

# ─── Mapa de competições ─────────────────────────────────────────────────────
COMPETITION_MAP = [
    (r"(campeonato mineiro|mineiro).*(2022)",         "Campeonato Mineiro 2022",    "MIN2022"),
    (r"(campeonato mineiro|mineiro).*(2023)",         "Campeonato Mineiro 2023",    "MIN2023"),
    (r"(campeonato mineiro|mineiro).*(2024)",         "Campeonato Mineiro 2024",    "MIN2024"),
    (r"(campeonato mineiro|mineiro).*(2025)",         "Campeonato Mineiro 2025",    "MIN2025"),
    (r"(campeonato mineiro|mineiro).*(2026)",         "Campeonato Mineiro 2026",    "MIN2026"),
    (r"(brasileiro|brasileirão).*(2022)",             "Campeonato Brasileiro 2022", "BRAS2022"),
    (r"(brasileiro|brasileirão).*(2023)",             "Campeonato Brasileiro 2023", "BRAS2023"),
    (r"(brasileiro|brasileirão).*(2024)",             "Campeonato Brasileiro 2024", "BRAS2024"),
    (r"(brasileiro|brasileirão).*(2025)",             "Campeonato Brasileiro 2025", "BRAS2025"),
    (r"(copa do brasil).*(2022)",                     "Copa do Brasil 2022",        "CDB2022"),
    (r"(copa do brasil).*(2023)",                     "Copa do Brasil 2023",        "CDB2023"),
    (r"(copa do brasil).*(2024)",                     "Copa do Brasil 2024",        "CDB2024"),
    (r"(copa do brasil).*(2025)",                     "Copa do Brasil 2025",        "CDB2025"),
    (r"(supercopa).*(2022)",                          "Supercopa 2022",             "SUP2022"),
    (r"(supercopa).*(2023)",                          "Supercopa 2023",             "SUP2023"),
    (r"(supercopa).*(2024)",                          "Supercopa 2024",             "SUP2024"),
    (r"(supercopa).*(2025)",                          "Supercopa 2025",             "SUP2025"),
    (r"(libertadores).*(2022)",                       "Copa Libertadores 2022",     "LIB2022"),
    (r"(libertadores).*(2023)",                       "Copa Libertadores 2023",     "LIB2023"),
    (r"(libertadores).*(2024)",                       "Copa Libertadores 2024",     "LIB2024"),
    (r"(libertadores).*(2025)",                       "Copa Libertadores 2025",     "LIB2025"),
    (r"(sul-americana|sulamericana).*(2022)",          "Copa Sul-Americana 2022",    "SULA2022"),
    (r"(sul-americana|sulamericana).*(2023)",          "Copa Sul-Americana 2023",    "SULA2023"),
    (r"(sul-americana|sulamericana).*(2024)",          "Copa Sul-Americana 2024",    "SULA2024"),
    (r"(carioca|campeonato carioca).*(2022)",          "Campeonato Carioca 2022",    "CAR2022"),
    (r"(carioca|campeonato carioca).*(2023)",          "Campeonato Carioca 2023",    "CAR2023"),
    (r"(carioca|campeonato carioca).*(2024)",          "Campeonato Carioca 2024",    "CAR2024"),
    (r"(carioca|campeonato carioca).*(2025)",          "Campeonato Carioca 2025",    "CAR2025"),
    (r"(paulistão|paulista|campeonato paulista).*(2022)", "Campeonato Paulista 2022","PAU2022"),
    (r"(paulistão|paulista|campeonato paulista).*(2023)", "Campeonato Paulista 2023","PAU2023"),
    (r"(paulistão|paulista|campeonato paulista).*(2024)", "Campeonato Paulista 2024","PAU2024"),
    (r"(paulistão|paulista|campeonato paulista).*(2025)", "Campeonato Paulista 2025","PAU2025"),
]

# Mapa de fragmentos de nome no título → sigla interna
TEAM_ALIASES = {
    r"atl[eé]tico.*(mg|mineiro)|galo":  "cam",
    r"cruzeiro|cru":                     "cru",
    r"flamengo|fla\b":                   "fla",
    r"fluminense|flu\b":                 "flu",
    r"corinthians|timão|cori":           "cor",
    r"palmeiras|verdão|pal\b":           "pal",
}

TEAM_FULL = {
    "cam": "Atletico-MG",
    "cru": "Cruzeiro",
    "fla": "Flamengo",
    "flu": "Fluminense",
    "cor": "Corinthians",
    "pal": "Palmeiras",
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    m = re.search(r"youtube\.com/live/([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m: return m.group(1)
    return None


def guess_event(title: str) -> str:
    t = title.lower()
    for pattern, event, _ in COMPETITION_MAP:
        if re.search(pattern, t):
            return event
    return title  # fallback: usa o próprio título


def guess_teams_from_title(title: str, fallback_home: str, fallback_away: str) -> tuple[str, str]:
    """
    Tenta inferir home/away do título.
    Detecta padrão 'Time A x Time B' e identifica quem joga em casa
    por ordem de aparição.
    Usa os fallbacks do jsonl original se não conseguir.
    """
    t = title.lower()

    found = []
    for pattern, sigla in TEAM_ALIASES.items():
        if re.search(pattern, t):
            pos = re.search(pattern, t).start()
            found.append((pos, sigla))

    found.sort(key=lambda x: x[0])

    if len(found) >= 2:
        return TEAM_FULL.get(found[0][1], found[0][1]), TEAM_FULL.get(found[1][1], found[1][1])

    return fallback_home, fallback_away


def fetch_meta(video_id: str) -> dict:
    try:
        r = subprocess.run(
            [
                "yt-dlp", "--no-download",
                "--print", "%(title)s|||%(upload_date)s|||%(channel)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split("|||")
            if len(parts) == 3:
                title, raw_date, channel = parts
                d = raw_date.strip()
                date = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
                return {"title": title.strip(), "date": date, "yt_channel": channel.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  yt-dlp erro: {e}")
    return {}


def enrich_file(jsonl_path: Path):
    print(f"\n📄 {jsonl_path}")
    lines   = jsonl_path.read_text(encoding="utf-8").splitlines()
    matches = [json.loads(l) for l in lines if l.strip()]

    updated = []
    for i, match in enumerate(matches):
        url      = match.get("url")
        video_id = extract_video_id(url) if url else None
        alias_   = match.get("alias", f"JOGO_{i+1:02d}")

        print(f"  [{i+1:02d}/{len(matches)}] {alias_} ({match.get('date', '?')}) ...", end=" ", flush=True)

        if not video_id:
            print("sem video_id — pulando")
            updated.append(match)
            continue

        meta = fetch_meta(video_id)

        if meta:
            title = meta["title"]
            home, away = guess_teams_from_title(
                title,
                match.get("home", ""),
                match.get("away", ""),
            )
            # Reconstrói alias com índice
            h3 = home[:3].upper()
            a3 = away[:3].upper()
            match.update({
                "title":      title,
                "event":      guess_event(title),
                "date":       meta.get("date", match.get("date", "")),
                "yt_channel": meta.get("yt_channel", match.get("channel", "")),
                "home":       home,
                "away":       away,
                "alias":      f"{h3}x{a3}_{i+1:02d}",
            })
            print(f"✓ {title[:55]}")
        else:
            print("sem metadado (yt-dlp não encontrado ou falhou)")

        updated.append(match)

    # Reescreve o arquivo
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for m in updated:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"  ✅ {jsonl_path} atualizado ({len(updated)} registros)")

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enriquece JSONLs com metadados do yt-dlp")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",    help="Arquivo .jsonl específico")
    group.add_argument("--all",      action="store_true", help="Enriquecer todos os videos_*.jsonl em --data-dir")
    parser.add_argument("--data-dir", default="data", help="Pasta de dados (usado com --all)")
    args = parser.parse_args()

    if args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"[ERRO] Arquivo não encontrado: {path}")
            sys.exit(1)
        enrich_file(path)
    else:
        data_dir = Path(args.data_dir)
        jsonl_files = sorted(data_dir.rglob("videos_*.jsonl"))
        if not jsonl_files:
            print(f"[ERRO] Nenhum videos_*.jsonl encontrado em '{data_dir}'")
            sys.exit(1)
        print(f"Encontrados {len(jsonl_files)} arquivo(s) para enriquecer...")
        for jf in jsonl_files:
            enrich_file(jf)

    print("\n✅ Enriquecimento concluído.")


if __name__ == "__main__":
    main()
