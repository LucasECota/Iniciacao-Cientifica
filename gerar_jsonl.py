"""
Gera arquivos JSONL de vídeos a partir dos arquivos .txt de links.
=================================================================

Lê os arquivos txt (links_cam.txt, links_cor.txt, etc.) e cria
um .jsonl por confronto dentro de data/<confronto>/.

Estrutura gerada:
    data/
      cam_x_cru/
        videos_cam_x_cru_itatiaia.jsonl
      cam_x_fla/
        videos_cam_x_fla_itatiaia.jsonl
      ...

Uso:
    python gerar_jsonl.py
    python gerar_jsonl.py --txt-dir ./links   # se os txts estiverem em outra pasta
    python gerar_jsonl.py --out-dir ./data    # pasta de saída (padrão: data)
"""

import re
import json
import argparse
from pathlib import Path
from datetime import datetime

# ─── Mapeamento de apelidos → nomes completos ────────────────────────────────
TEAM_NAMES = {
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


def parse_date(raw: str) -> str:
    """Converte DD/MM/YYYY → YYYY-MM-DD."""
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


def parse_header(line: str) -> dict | None:
    """
    Reconhece linhas como:
        'cam x cru itatiaia:'
        'fla x cor bandeirantes:'
        'flu x pal tupi:'
    Retorna dict com home, away, channel ou None.
    """
    line = line.strip().rstrip(":").lower()
    # padrão: <time1> x <time2> <canal>
    m = re.match(
        r"^([a-z]{2,4})\s+x\s+([a-z]{2,4})\s+(itatiaia|bandeirantes|tupi|sbt|globo|sportv|premiere)$",
        line,
    )
    if m:
        return {
            "home":    m.group(1),
            "away":    m.group(2),
            "channel": m.group(3).capitalize(),
        }
    return None


def parse_entry(line: str) -> dict | None:
    """
    Reconhece linhas com URL + data  ou  só data (sem URL).
    Retorna {"url": ..., "date": ...} ou {"url": None, "date": ...}.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    date_pattern = r"\b(\d{2}/\d{2}/\d{4})\b"
    url_pattern  = r"(https?://\S+)"

    url_m  = re.search(url_pattern,  line)
    date_m = re.search(date_pattern, line)

    if not date_m:
        return None  # linha sem data → ignora

    url  = url_m.group(1).rstrip("&") if url_m else None
    date = parse_date(date_m.group(1))
    return {"url": url, "date": date}


def slug(home: str, away: str) -> str:
    return f"{home}_x_{away}"


def alias(home: str, away: str, idx: int) -> str:
    h = TEAM_NAMES.get(home, home.upper())[:3].upper()
    a = TEAM_NAMES.get(away, away.upper())[:3].upper()
    return f"{h}x{a}_{idx:02d}"

# ─── Parser principal ────────────────────────────────────────────────────────

def parse_txt(path: Path) -> dict[str, list[dict]]:
    """
    Lê um arquivo txt e retorna dict:
        { "cam_x_cru": [{"url":..., "date":..., ...}, ...], ... }
    """
    results: dict[str, list[dict]] = {}
    current_meta: dict | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        header = parse_header(line)
        if header:
            current_meta = header
            key = slug(header["home"], header["away"])
            if key not in results:
                results[key] = []
            continue

        if current_meta is None:
            continue

        entry = parse_entry(line)
        if entry:
            key = slug(current_meta["home"], current_meta["away"])
            home_full = TEAM_NAMES.get(current_meta["home"], current_meta["home"])
            away_full = TEAM_NAMES.get(current_meta["away"], current_meta["away"])
            idx = len(results[key]) + 1
            record = {
                "url":        entry["url"],
                "date":       entry["date"],
                "home":       home_full,
                "away":       away_full,
                "channel":    current_meta["channel"],
                "alias":      alias(current_meta["home"], current_meta["away"], idx),
                "event":      "TBD",   # será preenchido pelo enriquecer_metadados.py
                "title":      "",
                "video_id":   extract_video_id(entry["url"]) if entry["url"] else None,
            }
            results[key].append(record)

    return results


def save_jsonl(records: list[dict], out_dir: Path, key: str, channel: str):
    channel_slug = channel.lower()
    folder = out_dir / key
    folder.mkdir(parents=True, exist_ok=True)
    out_file = folder / f"videos_{key}_{channel_slug}.jsonl"

    with open(out_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"  ✓ {out_file}  ({len(records)} vídeos)")
    return out_file

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gera JSONLs de vídeos a partir dos txts")
    parser.add_argument("--txt-dir", default=".", help="Pasta com os arquivos .txt (padrão: .)")
    parser.add_argument("--out-dir", default="data", help="Pasta de saída (padrão: data)")
    args = parser.parse_args()

    txt_dir = Path(args.txt_dir)
    out_dir = Path(args.out_dir)

    txt_files = sorted(txt_dir.glob("links_*.txt"))
    if not txt_files:
        print(f"[ERRO] Nenhum arquivo links_*.txt encontrado em '{txt_dir}'")
        return

    print(f"Encontrados {len(txt_files)} arquivo(s) txt em '{txt_dir}':\n")

    all_results: dict[str, list[dict]] = {}

    for txt_file in txt_files:
        print(f"Processando: {txt_file.name}")
        parsed = parse_txt(txt_file)
        for key, records in parsed.items():
            if key not in all_results:
                all_results[key] = []
            all_results[key].extend(records)

    print(f"\nGerando {len(all_results)} confronto(s):\n")

    for key, records in sorted(all_results.items()):
        # Ordena por data (mais antigo primeiro)
        records.sort(key=lambda r: r["date"] or "")

        # Reagrupa por canal (pode haver canais diferentes no mesmo confronto)
        by_channel: dict[str, list[dict]] = {}
        for r in records:
            ch = r["channel"]
            by_channel.setdefault(ch, []).append(r)

        for channel, recs in by_channel.items():
            save_jsonl(recs, out_dir, key, channel)

    print(f"\n✅ JSONLs gerados em '{out_dir}/'")


if __name__ == "__main__":
    main()
