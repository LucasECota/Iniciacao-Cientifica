"""
Estatísticas dos clássicos: CAM x CRU, PAL x COR, FLA x FLU
=============================================================
 
Lê os livechats_*.jsonl em data/ e produz uma tabela TXT com:
  - Clássico
  - Total de mensagens
  - Usuários únicos
 
Uso:
    python estatisticas_classicos.py
    python estatisticas_classicos.py --data-dir data
    python estatisticas_classicos.py --data-dir data --out-dir resultados
"""
 
import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict
 
# ─── Clássicos de interesse ───────────────────────────────────────────────────
 
CLASSICOS = {
    "cam_x_cru": "CAM x CRU",
    "cor_x_pal": "COR x PAL",
    "fla_x_flu": "FLA x FLU",
}
 
# ─── Helpers ──────────────────────────────────────────────────────────────────
 
def formatar_numero(n: int) -> str:
    return f"{n:,}".replace(",", ".")
 
 
def extrair_confronto_do_arquivo(path: Path) -> str:
    """livechats_cam_x_cru_itatiaia.jsonl → cam_x_cru"""
    stem = path.stem                        # livechats_cam_x_cru_itatiaia
    base = stem.replace("livechats_", "")   # cam_x_cru_itatiaia
    partes = base.split("_")
    return "_".join(partes[:-1])            # cam_x_cru
 
 
def processar_jsonl(path: Path) -> tuple[int, set]:
    """Retorna (total_mensagens, conjunto_de_channel_ids)."""
    mensagens = 0
    usuarios = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    mensagens += 1
                    channel_id = obj.get("author", {}).get("channelId", "")
                    if channel_id:
                        usuarios.add(channel_id)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"  [AVISO] Erro ao ler {path}: {e}", file=sys.stderr)
    return mensagens, usuarios
 
 
# ─── Coleta ───────────────────────────────────────────────────────────────────
 
def coletar(data_dir: Path) -> dict:
    """
    Retorna dict com dados agregados por clássico:
      { "cam_x_cru": {"mensagens": N, "usuarios": set(...)} , ... }
    """
    resultados = {k: {"mensagens": 0, "usuarios": set()} for k in CLASSICOS}
 
    arquivos = sorted(data_dir.rglob("livechats_*.jsonl"))
    if not arquivos:
        print(f"[ERRO] Nenhum livechats_*.jsonl encontrado em '{data_dir}'")
        sys.exit(1)
 
    for arq in arquivos:
        confronto = extrair_confronto_do_arquivo(arq)
        if confronto not in CLASSICOS:
            continue
 
        print(f"  Lendo: {arq.name}")
        msgs, users = processar_jsonl(arq)
        resultados[confronto]["mensagens"] += msgs
        resultados[confronto]["usuarios"]  |= users  # união dos sets
 
    return resultados
 
 
# ─── Saída TXT ────────────────────────────────────────────────────────────────
 
def gerar_txt(resultados: dict, out_path: Path):
    sep  = "─" * 62
    sep2 = "═" * 62
 
    linhas = []
    linhas.append(sep2)
    linhas.append("  ESTATÍSTICAS DOS CLÁSSICOS — LIVECHAT")
    linhas.append(sep2)
    linhas.append("")
 
    # Cabeçalho
    linhas.append(f"  {'Clássico':<15} {'Mensagens':>14} {'Usuários únicos':>16}")
    linhas.append(f"  {'─'*15} {'─'*14} {'─'*16}")
 
    total_msgs  = 0
    total_users: set = set()
 
    for key, label in CLASSICOS.items():
        d = resultados[key]
        msgs  = d["mensagens"]
        users = len(d["usuarios"])
        total_msgs  += msgs
        total_users |= d["usuarios"]
 
        linhas.append(f"  {label:<15} {formatar_numero(msgs):>14} {formatar_numero(users):>16}")
 
    linhas.append(f"  {'─'*15} {'─'*14} {'─'*16}")
    linhas.append(
        f"  {'TOTAL':<15} {formatar_numero(total_msgs):>14} {formatar_numero(len(total_users)):>16}"
    )
    linhas.append("")
    linhas.append(sep2)
    linhas.append("")
 
    conteudo = "\n".join(linhas)
 
    # Exibe no terminal também
    print()
    print(conteudo)
 
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(conteudo)
 
    print(f"✅ TXT salvo: {out_path}")
 
 
# ─── Main ─────────────────────────────────────────────────────────────────────
 
def main():
    parser = argparse.ArgumentParser(
        description="Estatísticas dos clássicos CAM x CRU, PAL x COR, FLA x FLU"
    )
    parser.add_argument("--data-dir", default="data",
                        help="Pasta de dados (padrão: data)")
    parser.add_argument("--out-dir",  default=".",
                        help="Pasta para salvar o TXT (padrão: .)")
    args = parser.parse_args()
 
    data_dir = Path(args.data_dir)
    out_dir  = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
 
    print(f"Buscando arquivos em '{data_dir}'...\n")
    resultados = coletar(data_dir)
 
    gerar_txt(resultados, out_dir / "estatisticas_classicos.txt")
 
 
if __name__ == "__main__":
    main()