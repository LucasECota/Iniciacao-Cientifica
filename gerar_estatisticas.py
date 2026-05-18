"""
Gera tabela de estatísticas dos livechats coletados.
=====================================================
 
Lê todos os livechats_*.jsonl em data/ e produz:
  - Total geral de comentários
  - Total por canal do YouTube (Itatiaia, Bandeirantes, Tupi...)
  - Total por confronto e canal
 
Uso:
    python gerar_estatisticas.py
    python gerar_estatisticas.py --data-dir data
    python gerar_estatisticas.py --data-dir data --formato csv
    python gerar_estatisticas.py --data-dir data --formato json
    python gerar_estatisticas.py --data-dir data --formato txt
"""
 
import json
import argparse
import csv
import sys
from pathlib import Path
from collections import defaultdict
 
# ─── Helpers ─────────────────────────────────────────────────────────────────
 
def confronto_legivel(key: str) -> str:
    """cam_x_cru → CAM x CRU"""
    return key.replace("_", " ").upper()
 
 
def canal_yt_legivel(channel: str) -> str:
    MAP = {
        "itatiaia":      "Itatiaia",
        "bandeirantes":  "Bandeirantes",
        "tupi":          "Tupi",
        "sbt":           "SBT",
        "globo":         "Globo",
        "sportv":        "SporTV",
        "premiere":      "Premiere",
    }
    return MAP.get(channel.lower(), channel.capitalize())
 
 
def extrair_canal_do_arquivo(path: Path) -> str:
    """
    Tira o canal do nome do arquivo.
    livechats_cam_x_cru_itatiaia.jsonl → itatiaia
    """
    stem = path.stem  # livechats_cam_x_cru_itatiaia
    # Remove prefixo
    base = stem.replace("livechats_", "")
    # Último token é o canal
    partes = base.split("_")
    return partes[-1]
 
 
def extrair_confronto_do_arquivo(path: Path) -> str:
    """
    livechats_cam_x_cru_itatiaia.jsonl → cam_x_cru
    """
    stem = path.stem
    base = stem.replace("livechats_", "")
    partes = base.split("_")
    # Remove o último token (canal)
    return "_".join(partes[:-1])
 
 
def contar_jsonl(path: Path) -> int:
    count = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception as e:
        print(f"  [AVISO] Erro ao ler {path}: {e}", file=sys.stderr)
    return count
 
 
def formatar_numero(n: int) -> str:
    return f"{n:,}".replace(",", ".")
 
# ─── Coleta de dados ──────────────────────────────────────────────────────────
 
def coletar_stats(data_dir: Path) -> dict:
    arquivos = sorted(data_dir.rglob("livechats_*.jsonl"))
 
    if not arquivos:
        print(f"[ERRO] Nenhum livechats_*.jsonl encontrado em '{data_dir}'")
        sys.exit(1)
 
    print(f"Encontrados {len(arquivos)} arquivo(s) de livechat...\n")
 
    total_geral = 0
    por_canal_yt: dict[str, int] = defaultdict(int)       # canal → total
    por_confronto: dict[str, dict] = defaultdict(dict)    # confronto → {canal: total}
 
    for arq in arquivos:
        canal      = extrair_canal_do_arquivo(arq)
        confronto  = extrair_confronto_do_arquivo(arq)
        canal_nome = canal_yt_legivel(canal)
        count      = contar_jsonl(arq)
 
        total_geral                           += count
        por_canal_yt[canal_nome]              += count
        por_confronto[confronto][canal_nome]   = count
 
        print(f"  {arq.name}: {formatar_numero(count)} comentários")
 
    return {
        "total_geral":   total_geral,
        "por_canal_yt":  dict(sorted(por_canal_yt.items(), key=lambda x: -x[1])),
        "por_confronto": {
            k: dict(sorted(v.items(), key=lambda x: -x[1]))
            for k, v in sorted(por_confronto.items())
        },
    }
 
# ─── Formatadores de saída ────────────────────────────────────────────────────
 
def imprimir_tabela(stats: dict):
    sep  = "─" * 60
    sep2 = "═" * 60
 
    print(f"\n{sep2}")
    print(f"  ESTATÍSTICAS DE LIVECHAT")
    print(f"{sep2}")
 
    # ── Total geral ──────────────────────────────────────────────
    print(f"\n{'TOTAL GERAL DE COMENTÁRIOS':.<45} {formatar_numero(stats['total_geral']):>10}")
 
    # ── Por canal do YouTube ─────────────────────────────────────
    print(f"\n{sep}")
    print(f"  TOTAL POR CANAL DO YOUTUBE")
    print(f"{sep}")
    print(f"  {'Canal':<30} {'Comentários':>12}  {'%':>6}")
    print(f"  {'─'*30} {'─'*12}  {'─'*6}")
    total = stats["total_geral"] or 1
    for canal, n in stats["por_canal_yt"].items():
        pct = n / total * 100
        print(f"  {canal:<30} {formatar_numero(n):>12}  {pct:>5.1f}%")
 
    # ── Por confronto e canal ────────────────────────────────────
    print(f"\n{sep}")
    print(f"  TOTAL POR CONFRONTO E CANAL")
    print(f"{sep}")
 
    subtotais = {
        k: sum(v.values())
        for k, v in stats["por_confronto"].items()
    }
    confrontos_ordenados = sorted(subtotais, key=lambda x: -subtotais[x])
 
    for confronto in confrontos_ordenados:
        canais   = stats["por_confronto"][confronto]
        subtotal = subtotais[confronto]
        label    = confronto_legivel(confronto)
        print(f"\n  {label}  (subtotal: {formatar_numero(subtotal)})")
        print(f"  {'─'*40}")
        for canal, n in canais.items():
            pct = n / subtotal * 100 if subtotal else 0
            print(f"    {canal:<28} {formatar_numero(n):>10}  {pct:>5.1f}%")
 
    print(f"\n{sep2}\n")
 
 
def salvar_txt(stats: dict, out_path: Path):
    """Salva a tabela formatada igual ao terminal em um arquivo .txt."""
    import io
    buffer = io.StringIO()
 
    sep  = "─" * 60
    sep2 = "═" * 60
 
    buffer.write(f"{sep2}\n")
    buffer.write(f"  ESTATÍSTICAS DE LIVECHAT\n")
    buffer.write(f"{sep2}\n")
 
    buffer.write(f"\n{'TOTAL GERAL DE COMENTÁRIOS':.<45} {formatar_numero(stats['total_geral']):>10}\n")
 
    buffer.write(f"\n{sep}\n")
    buffer.write(f"  TOTAL POR CANAL DO YOUTUBE\n")
    buffer.write(f"{sep}\n")
    buffer.write(f"  {'Canal':<30} {'Comentários':>12}  {'%':>6}\n")
    buffer.write(f"  {'─'*30} {'─'*12}  {'─'*6}\n")
    total = stats["total_geral"] or 1
    for canal, n in stats["por_canal_yt"].items():
        pct = n / total * 100
        buffer.write(f"  {canal:<30} {formatar_numero(n):>12}  {pct:>5.1f}%\n")
 
    buffer.write(f"\n{sep}\n")
    buffer.write(f"  TOTAL POR CONFRONTO E CANAL\n")
    buffer.write(f"{sep}\n")
 
    subtotais = {k: sum(v.values()) for k, v in stats["por_confronto"].items()}
    confrontos_ordenados = sorted(subtotais, key=lambda x: -subtotais[x])
 
    for confronto in confrontos_ordenados:
        canais   = stats["por_confronto"][confronto]
        subtotal = subtotais[confronto]
        label    = confronto_legivel(confronto)
        buffer.write(f"\n  {label}  (subtotal: {formatar_numero(subtotal)})\n")
        buffer.write(f"  {'─'*40}\n")
        for canal, n in canais.items():
            pct = n / subtotal * 100 if subtotal else 0
            buffer.write(f"    {canal:<28} {formatar_numero(n):>10}  {pct:>5.1f}%\n")
 
    buffer.write(f"\n{sep2}\n")
 
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(buffer.getvalue())
 
    print(f"✅ TXT salvo: {out_path}")
 
 
def salvar_csv(stats: dict, out_path: Path):
    rows = []
    for confronto, canais in stats["por_confronto"].items():
        for canal, n in canais.items():
            rows.append({
                "confronto":   confronto_legivel(confronto),
                "canal_yt":    canal,
                "comentarios": n,
            })
    # Totais por canal
    for canal, n in stats["por_canal_yt"].items():
        rows.append({
            "confronto":   "TOTAL",
            "canal_yt":    canal,
            "comentarios": n,
        })
    rows.append({
        "confronto":   "TOTAL GERAL",
        "canal_yt":    "—",
        "comentarios": stats["total_geral"],
    })
 
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["confronto", "canal_yt", "comentarios"])
        writer.writeheader()
        writer.writerows(rows)
 
    print(f"✅ CSV salvo: {out_path}")
 
 
def salvar_json(stats: dict, out_path: Path):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON salvo: {out_path}")
 
# ─── Main ────────────────────────────────────────────────────────────────────
 
def main():
    parser = argparse.ArgumentParser(description="Estatísticas dos livechats coletados")
    parser.add_argument("--data-dir", default="data", help="Pasta de dados (padrão: data)")
    parser.add_argument(
        "--formato",
        choices=["tabela", "csv", "json", "txt", "todos"],
        default="tabela",
        help="Formato de saída (padrão: tabela)",
    )
    parser.add_argument("--out-dir", default=".", help="Pasta para salvar CSV/JSON (padrão: .)")
    args = parser.parse_args()
 
    data_dir = Path(args.data_dir)
    out_dir  = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
 
    stats = coletar_stats(data_dir)
 
    fmt = args.formato
 
    if fmt in ("tabela", "todos"):
        imprimir_tabela(stats)
 
    if fmt in ("txt", "todos"):
        salvar_txt(stats, out_dir / "estatisticas_livechat.txt")
 
    if fmt in ("csv", "todos"):
        salvar_csv(stats, out_dir / "estatisticas_livechat.csv")
 
    if fmt in ("json", "todos"):
        salvar_json(stats, out_dir / "estatisticas_livechat.json")
 
    if fmt == "tabela":
        # Pergunta se quer salvar também
        pass
 
 
if __name__ == "__main__":
    main()