"""
Enriquece videos_atletico_cruzeiro_itatiaia.jsonl com título e data reais.
Usa yt-dlp para buscar os metadados de cada vídeo e reescreve o arquivo.

Uso:
    pip install yt-dlp
    python enriquecer_metadados.py
"""

import json
import re
import subprocess
from pathlib import Path

INPUT_FILE = "data/atletico_cruzeiro/videos_atletico_cruzeiro_itatiaia.jsonl"


COMPETITION_MAP = [
    # (padrão no título, event, alias_prefix)
    (r"(campeonato mineiro|mineiro).*(2020)",         "Campeonato Mineiro 2020",   "MIN2020"),
    (r"(campeonato mineiro|mineiro).*(2021)",         "Campeonato Mineiro 2021",   "MIN2021"),
    (r"(campeonato mineiro|mineiro).*(2022)",         "Campeonato Mineiro 2022",   "MIN2022"),
    (r"(campeonato mineiro|mineiro).*(2023)",         "Campeonato Mineiro 2023",   "MIN2023"),
    (r"(campeonato mineiro|mineiro).*(2024)",         "Campeonato Mineiro 2024",   "MIN2024"),
    (r"(campeonato mineiro|mineiro).*(2025)",         "Campeonato Mineiro 2025",   "MIN2025"),
    (r"(brasileiro|brasileirão).*(2022)",             "Campeonato Brasileiro 2022","BRAS2022"),
    (r"(brasileiro|brasileirão).*(2023)",             "Campeonato Brasileiro 2023","BRAS2023"),
    (r"(brasileiro|brasileirão).*(2024)",             "Campeonato Brasileiro 2024","BRAS2024"),
    (r"(brasileiro|brasileirão).*(2025)",             "Campeonato Brasileiro 2025","BRAS2025"),
    (r"(copa do brasil).*(2022)",                    "Copa do Brasil 2022",       "CDB2022"),
    (r"(copa do brasil).*(2023)",                    "Copa do Brasil 2023",       "CDB2023"),
    (r"(copa do brasil).*(2024)",                    "Copa do Brasil 2024",       "CDB2024"),
    (r"(copa do brasil).*(2025)",                    "Copa do Brasil 2025",       "CDB2025"),
    (r"(supercopa).*(2022)",                         "Supercopa 2022",            "SUP2022"),
    (r"(supercopa).*(2023)",                         "Supercopa 2023",            "SUP2023"),
    (r"(supercopa).*(2024)",                         "Supercopa 2024",            "SUP2024"),
]


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


def guess_home_away(title: str) -> tuple[str, str]:
    t = title.lower()
    if re.search(r"cruzeiro.*x.*atl[eé]tico|cruzeiro.*vs.*atl[eé]tico", t):
        return "Cruzeiro", "Atletico-MG"
    return "Atletico-MG", "Cruzeiro"


def fetch_meta(video_id: str) -> dict:
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-download", "--print",
             "%(title)s|||%(upload_date)s|||%(channel)s",
             f"https://www.youtube.com/watch?v={video_id}"],
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


def main():
    lines = Path(INPUT_FILE).read_text(encoding="utf-8").splitlines()
    matches = [json.loads(l) for l in lines if l.strip()]

    updated = []
    for i, match in enumerate(matches):
        url      = match["url"]
        video_id = extract_video_id(url)
        print(f"[{i+1:02d}/{len(matches)}] {video_id} ...", end=" ", flush=True)

        meta = fetch_meta(video_id) if video_id else {}

        if meta:
            title   = meta["title"]
            home, away = guess_home_away(title)
            match.update({
                "title":      title,
                "event":      guess_event(title),
                "date":       meta.get("date", match.get("date", "")),
                "yt_channel": meta.get("yt_channel", match.get("channel", "Itatiaia")),
                "home":       home,
                "away":       away,
                "alias":      f"{home[:3].upper()}x{away[:3].upper()}_{match.get('alias','').split('_')[-1]}",
            })
            print(f"✓ {title[:60]}")
        else:
            print("sem metadado (yt-dlp não encontrado ou falhou)")

        updated.append(match)

    # Reescreve o arquivo
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        for m in updated:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"\n✅ Arquivo atualizado: {INPUT_FILE}")


if __name__ == "__main__":
    main()
