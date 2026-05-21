"""
Análise de CCDF (Complementary Cumulative Distribution Function)
de comentários por usuário em chats ao vivo do YouTube.
 
Metodologia baseada em:
- Locatelli et al. (2022) "Characterizing Vaccination Movements on YouTube"
  → Figura 3(b): CDF do número de comentários por usuário
- Costa et al. (2025) "Characterizing YouTube's Role in Online Gambling Promotion"
  → Figura 3(b): CDF do número de comentários por usuário (Favor vs Against)
 
A CCDF é definida como: P(X > x) = 1 - CDF(x)
Mostra a fração de usuários que postaram MAIS do que x comentários.
 
Estrutura de dados esperada:
  data/
    <confronto>/
      livechat_<alias>.jsonl   ← cada linha é um comentário com campo "channelId"
    ...
  links_<time>.txt ou links_<time> ← arquivo com metadados dos vídeos (opcional)
"""
 
import json
import os
import glob
from collections import Counter, defaultdict
 
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
 
# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÕES
# ---------------------------------------------------------------------------
 
DATA_DIR = "data"          # pasta raiz com os confrontos
OUTPUT_DIR = "outputs"     # pasta onde salvar as figuras
os.makedirs(OUTPUT_DIR, exist_ok=True)
 
# Paleta de cores neutra para os confrontos (expanda conforme necessário)
COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]
 
# ---------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------
 
def carregar_livechats(data_dir: str) -> dict:
    """
    Percorre data_dir recursivamente e lê todos os arquivos livechat_*.jsonl.
 
    Retorna um dict:
        { alias: {"comments": [...], "video_ids": set(), "match": str} }
    """
    dados = defaultdict(lambda: {"comments": [], "video_ids": set(), "match": ""})
 
    for fpath in sorted(glob.glob(os.path.join(data_dir, "**", "livechats_*.jsonl"),
                                  recursive=True)):
        # Extrai o alias do nome do arquivo: livechat_<alias>.jsonl
        fname = os.path.basename(fpath)
        alias = fname.replace("livechat_", "").replace(".jsonl", "")
 
        # O nome da pasta-pai é o confronto (ex: cru_x_flu)
        match_name = os.path.basename(os.path.dirname(fpath))
 
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    dados[alias]["comments"].append(obj)
                    if "video_id" in obj:
                        dados[alias]["video_ids"].add(obj["video_id"])
                    dados[alias]["match"] = match_name
                except json.JSONDecodeError:
                    pass
 
    return dict(dados)
 
 
def contar_comentarios_por_usuario(comments: list, campo_usuario: str = "channelId") -> Counter:
    """
    Dado uma lista de comentários (dicts), retorna um Counter:
        { user_id: n_comentarios }
 
    Tenta os campos: channelId, author.channelId, author_channel_id
    """
    contagem = Counter()
    for c in comments:
        uid = None
        # Tenta campo direto
        if campo_usuario in c:
            uid = c[campo_usuario]
        # Tenta dentro de "author"
        elif "author" in c and isinstance(c["author"], dict):
            uid = c["author"].get("channelId") or c["author"].get("channel_id")
        if uid:
            contagem[uid] += 1
    return contagem
 
 
def calcular_ccdf(counter: Counter) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula a CCDF de um Counter de comentários por usuário.
 
    Retorna (x, ccdf) onde:
        x    = valores únicos ordenados do número de comentários
        ccdf = P(X >= x)  (CCDF no sentido >= , comum em análises de redes)
    """
    if not counter:
        return np.array([]), np.array([])
 
    valores = np.array(sorted(counter.values()))
    n = len(valores)
    x_unicos = np.unique(valores)
    ccdf = np.array([np.sum(valores >= v) / n for v in x_unicos])
    return x_unicos, ccdf
 
 
def calcular_cdf(counter: Counter) -> tuple[np.ndarray, np.ndarray]:
    """Calcula a CDF (como em Locatelli et al., Fig 3b)."""
    if not counter:
        return np.array([]), np.array([])
 
    valores = np.array(sorted(counter.values()))
    n = len(valores)
    x_unicos = np.unique(valores)
    cdf = np.array([np.sum(valores <= v) / n for v in x_unicos])
    return x_unicos, cdf
 
 
# ---------------------------------------------------------------------------
# 3. ESTATÍSTICAS DESCRITIVAS
# ---------------------------------------------------------------------------
 
def estatisticas(counter: Counter, label: str = "") -> dict:
    if not counter:
        return {}
    v = np.array(list(counter.values()))
    stats = {
        "label": label,
        "n_usuarios": len(counter),
        "total_comentarios": int(v.sum()),
        "media": float(np.mean(v)),
        "mediana": float(np.median(v)),
        "p90": float(np.percentile(v, 90)),
        "p99": float(np.percentile(v, 99)),
        "max": int(v.max()),
        "usuarios_1_comentario": int(np.sum(v == 1)),
        "pct_1_comentario": float(np.mean(v == 1) * 100),
    }
    return stats
 
 
def imprimir_estatisticas(stats_list: list[dict]):
    print("\n" + "="*70)
    print(f"{'Alias':<25} {'Usuários':>10} {'Total':>10} {'Média':>8} "
          f"{'Mediana':>8} {'Max':>6} {'%1-msg':>8}")
    print("-"*70)
    for s in stats_list:
        if not s:
            continue
        print(f"{s['label']:<25} {s['n_usuarios']:>10,} {s['total_comentarios']:>10,} "
              f"{s['media']:>8.2f} {s['mediana']:>8.1f} {s['max']:>6} "
              f"{s['pct_1_comentario']:>7.1f}%")
    print("="*70)
 
 
# ---------------------------------------------------------------------------
# 4. PLOTS
# ---------------------------------------------------------------------------
 
def plot_ccdf_todos(dados_alias: dict, titulo: str = "CCDF – Comentários por Usuário",
                    figsize=(13, 7), salvar: str = None):
    """
    Plota a CCDF para todos os aliases num único gráfico (escala log-log),
    seguindo o estilo de Locatelli et al. (2022) Fig. 3(b).
    Legenda fora do gráfico, 2 colunas, label curto = alias (match).
    """
    fig, ax = plt.subplots(figsize=figsize)
 
    aliases = sorted(dados_alias.keys())
    for i, alias in enumerate(aliases):
        counter = dados_alias[alias]["counter"]
        if not counter:
            continue
        x, ccdf = calcular_ccdf(counter)
        match = dados_alias[alias]["match"]
        n = len(counter)
        cor = COLORS[i % len(COLORS)]
        label = match
        ax.plot(x, ccdf, drawstyle="steps-post", color=cor,
                linewidth=1.5, label=label)
 
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Número de comentários por usuário (x)", fontsize=13)
    ax.set_ylabel("P(X ≥ x)  –  CCDF", fontsize=13)
    ax.set_title(titulo, fontsize=14, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    ax.set_xlim(left=0.9)
    ax.set_ylim(top=1.2, bottom=1e-4)
 
    # Legenda fora do gráfico, à direita, 2 colunas
    ax.legend(fontsize=7.5, ncol=2, loc="upper left",
              bbox_to_anchor=(1.01, 1), borderaxespad=0,
              framealpha=0.9, handlelength=1.5)
 
    plt.tight_layout()
    if salvar:
        plt.savefig(salvar, dpi=150, bbox_inches="tight")
        print(f"  → Salvo: {salvar}")
    plt.show()
    plt.close()
 
 
def plot_ccdf_por_confronto(dados_alias: dict, figsize=(10, 7),
                             salvar_dir: str = None):
    """
    Agrupa aliases pelo campo 'match' (confronto) e plota um painel
    separado para cada confronto — útil quando há muitos aliases.
    """
    # Agrupar por confronto
    por_confronto = defaultdict(list)
    for alias, info in dados_alias.items():
        por_confronto[info["match"]].append(alias)
 
    confrontos = sorted(por_confronto.keys())
    ncols = 2
    nrows = (len(confrontos) + 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(figsize[0], figsize[1] * nrows // 2 + 2))
    axes = np.array(axes).flatten()
 
    for idx, confronto in enumerate(confrontos):
        ax = axes[idx]
        aliases_confronto = sorted(por_confronto[confronto])
 
        for j, alias in enumerate(aliases_confronto):
            counter = dados_alias[alias]["counter"]
            if not counter:
                continue
            x, ccdf = calcular_ccdf(counter)
            ax.plot(x, ccdf, drawstyle="steps-post",
                    color=COLORS[j % len(COLORS)],
                    linewidth=1.8, label=alias)
 
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Comentários por usuário", fontsize=10)
        ax.set_ylabel("CCDF", fontsize=10)
        ax.set_title(confronto, fontsize=11, fontweight="bold")
        ax.legend(fontsize=7)
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.set_xlim(left=0.9)
 
    # Esconder eixos sobrando
    for idx in range(len(confrontos), len(axes)):
        axes[idx].set_visible(False)
 
    fig.suptitle("CCDF – Comentários por Usuário por Confronto",
                 fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    if salvar_dir:
        fpath = os.path.join(salvar_dir, "ccdf_por_confronto.png")
        plt.savefig(fpath, dpi=150, bbox_inches="tight")
        print(f"  → Salvo: {fpath}")
    plt.show()
    plt.close()
 
 
def plot_ccdf_comparativo_times(dados_alias: dict,
                                 agrupamento: dict = None,
                                 figsize=(9, 6),
                                 salvar: str = None):
    """
    Permite comparar grupos de aliases (ex: jogos de um mesmo time).
 
    agrupamento: { 'NomeGrupo': [lista de aliases] }
    Se None, agrupa por 'match'.
    """
    if agrupamento is None:
        # Agrupa por confronto automaticamente
        agrupamento = defaultdict(list)
        for alias, info in dados_alias.items():
            agrupamento[info["match"]].append(alias)
        agrupamento = dict(agrupamento)
 
    # Determina número de confrontos para ajustar figura
    n_grupos = len(agrupamento)
    ncols_leg = 2 if n_grupos > 12 else 1
    fig_w = figsize[0] + (3.5 if ncols_leg == 2 else 2.5)
    fig, ax = plt.subplots(figsize=(fig_w, figsize[1]))
 
    for i, (grupo, aliases) in enumerate(sorted(agrupamento.items())):
        # Agrega todos os comentários do grupo
        counter_agg = Counter()
        for alias in aliases:
            if alias in dados_alias:
                counter_agg.update(dados_alias[alias]["counter"])
        if not counter_agg:
            continue
        x, ccdf = calcular_ccdf(counter_agg)
        cor = COLORS[i % len(COLORS)]
        n_users = len(counter_agg)
        ax.plot(x, ccdf, drawstyle="steps-post", color=cor,
                linewidth=2.0, label=grupo)
 
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Número de comentários por usuário (x)", fontsize=13)
    ax.set_ylabel("P(X ≥ x)  –  CCDF", fontsize=13)
    ax.set_title("CCDF Agregada – Comentários por Usuário por Confronto",
                 fontsize=13, fontweight="bold")
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    ax.set_xlim(left=0.9)
 
    # Legenda fora do gráfico, à direita
    ax.legend(fontsize=8, ncol=ncols_leg, loc="upper left",
              bbox_to_anchor=(1.01, 1), borderaxespad=0,
              framealpha=0.9, handlelength=1.5)
 
    plt.tight_layout()
    if salvar:
        plt.savefig(salvar, dpi=150, bbox_inches="tight")
        print(f"  → Salvo: {salvar}")
    plt.show()
    plt.close()
 
 
# ---------------------------------------------------------------------------
# 5. PIPELINE PRINCIPAL
# ---------------------------------------------------------------------------
 
def main():
    print("=" * 70)
    print("  Análise CCDF – Comentários por Usuário (Live Chat YouTube)")
    print("=" * 70)
 
    # 5.1 Carrega dados
    print(f"\n[1/4] Carregando livechats de '{DATA_DIR}' ...")
    dados_brutos = carregar_livechats(DATA_DIR)
 
    if not dados_brutos:
        print(f"\n  ⚠  Nenhum arquivo livechat_*.jsonl encontrado em '{DATA_DIR}'.")
        print("     Verifique o caminho DATA_DIR no início do script.")
        return
 
    print(f"      {len(dados_brutos)} alias(es) encontrados:")
    for alias, info in sorted(dados_brutos.items()):
        print(f"        • {alias:30s}  {len(info['comments']):>6,} comentários "
              f"  [{info['match']}]")
 
    # 5.2 Conta comentários por usuário para cada alias
    print("\n[2/4] Contando comentários por usuário ...")
    dados_alias = {}
    stats_list = []
 
    for alias, info in sorted(dados_brutos.items()):
        counter = contar_comentarios_por_usuario(info["comments"])
        dados_alias[alias] = {
            "counter": counter,
            "match": info["match"],
            "video_ids": info["video_ids"],
        }
        s = estatisticas(counter, label=alias)
        stats_list.append(s)
 
    imprimir_estatisticas(stats_list)
 
    # 5.3 Gera gráficos
    print("\n[3/4] Gerando gráficos ...")
 
    # (a) CCDF global – todos os aliases
    plot_ccdf_todos(
        dados_alias,
        titulo="CCDF – Comentários por Usuário (todos os jogos)",
        salvar=os.path.join(OUTPUT_DIR, "ccdf_todos_aliases.png"),
    )
 
    # (b) CCDF por confronto (painel)
    por_confronto = defaultdict(list)
    for alias in dados_alias:
        por_confronto[dados_alias[alias]["match"]].append(alias)
 
    if len(por_confronto) > 1:
        plot_ccdf_por_confronto(
            dados_alias,
            salvar_dir=OUTPUT_DIR,
        )
 
    # (c) CCDF agregada por confronto (uma curva por confronto)
    plot_ccdf_comparativo_times(
        dados_alias,
        salvar=os.path.join(OUTPUT_DIR, "ccdf_agregada_por_confronto.png"),
    )
 
    # 5.4 Salva tabela de estatísticas em CSV
    print("\n[4/4] Salvando estatísticas em CSV ...")
    import csv
    csv_path = os.path.join(OUTPUT_DIR, "estatisticas_ccdf.csv")
    campos = ["label", "n_usuarios", "total_comentarios", "media", "mediana",
              "p90", "p99", "max", "usuarios_1_comentario", "pct_1_comentario"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        for s in stats_list:
            if s:
                writer.writerow({k: s.get(k, "") for k in campos})
    print(f"  → Salvo: {csv_path}")
 
    print("\n✓ Análise concluída! Arquivos salvos em:", OUTPUT_DIR)
 
 
if __name__ == "__main__":
    main()