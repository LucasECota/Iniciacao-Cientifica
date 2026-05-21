"""
Nuvem de Palavras e Nuvem de Emojis
Confrontos: CRU x CAM | FLA x FLU | PAL x COR
 
Correções v2:
  - Palavras: remove shortcodes :emoji_name: ANTES de tokenizar
              (evita palavras como 'smiling', 'face', 'waving')
  - Emojis:   renderizados com PIL + NotoColorEmoji (coloridos, sem caixas)
  - Pastas:   busca livechats_*.jsonl e livechat_*.jsonl
"""
 
import json
import os
import re
import glob
import math
from collections import Counter
 
import emoji
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from PIL import Image, ImageDraw, ImageFont
 
# ---------------------------------------------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------------------------------------------
 
DATA_DIR   = "data"
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
 
CONFRONTOS_ALVO = ["cam_x_cru", "fla_x_flu", "cor_x_pal"]
 
LABELS = {
    "cam_x_cru": "Cruzeiro × Atlético-MG",
    "fla_x_flu": "Flamengo × Fluminense",
    "cor_x_pal": "Palmeiras × Corinthians",
    "geral":     "Geral",
}
 
ESTILOS = {
    "cam_x_cru": {"bg": "#0d1b2a", "colormap": "Blues"},
    "fla_x_flu": {"bg": "#1a0000", "colormap": "Reds"},
    "cor_x_pal": {"bg": "#0a1a0a", "colormap": "Greens"},
    "geral":     {"bg": "#111111", "colormap": "viridis"},
}
 
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
# Tamanho nativo do NotoColorEmoji (múltiplos de 109)
EMOJI_NATIVE_SIZE = 109
 
STOPWORDS_PT = {
    "de","da","do","das","dos","e","a","o","as","os","em","para","com",
    "por","que","um","uma","uns","umas","se","na","no","nas","nos","ao",
    "aos","à","às","mais","mas","ou","ele","ela","eles","elas","eu","tu",
    "nós","vós","me","te","lhe","nos","vos","lhes","meu","minha","teu",
    "tua","seu","sua","nosso","nossa","este","esta","esse","essa","aquele",
    "aquela","isso","isto","aquilo","já","não","sim","foi","é","ser","ter",
    "era","tem","vai","vou","aqui","ali","lá","como","quando","onde","quem",
    "qual","porque","pois","então","também","muito","pouco","bem","mal",
    "ainda","só","até","desde","depois","antes","agora","sempre","nunca",
    "todo","toda","todos","todas","cada","outro","outra","mesmo","mesma",
    "maior","menor","né","pra","pro","tá","ta","vc","vcs","aí","cara",
    "aqui","isso","tudo","nada","nós","vamos","vamo","vai","kkk","rs","rsrs",
    "hahaha","hahah","hehe","heh","kk","k","lol","kkkk","kkkkk","kkkkkk",
}
 
# ---------------------------------------------------------------------------
# CARREGAMENTO
# ---------------------------------------------------------------------------
 
def carregar_confrontos(data_dir, confrontos):
    dados = {c: [] for c in confrontos}
    for confronto in confrontos:
        pasta = os.path.join(data_dir, confronto)
        if not os.path.isdir(pasta):
            print(f"  ⚠  Pasta não encontrada: {pasta}")
            continue
 
        # Busca qualquer .jsonl na pasta que contenha "livechat" no nome
        arquivos = glob.glob(os.path.join(pasta, "*.jsonl"))
        arquivos = [a for a in arquivos if "livechat" in os.path.basename(a).lower()]
 
        if not arquivos:
            # Fallback: qualquer .jsonl na pasta
            arquivos = glob.glob(os.path.join(pasta, "*.jsonl"))
 
        if not arquivos:
            print(f"  ⚠  Nenhum .jsonl em: {pasta}")
            print(f"       Arquivos existentes: {os.listdir(pasta)}")
            continue
 
        for fpath in sorted(arquivos):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg = obj.get("message", "")
                        if msg:
                            dados[confronto].append(msg)
                    except json.JSONDecodeError:
                        pass
            print(f"    {os.path.basename(fpath)}: {len(dados[confronto]):,} msgs acumuladas")
 
        print(f"  {confronto}: {len(dados[confronto]):,} mensagens no total")
    return dados
 
# ---------------------------------------------------------------------------
# PROCESSAMENTO
# ---------------------------------------------------------------------------
 
def extrair_emojis(texto):
    """Extrai emojis: converte shortcodes :name: → unicode, depois coleta."""
    conv = emoji.emojize(texto, language="alias")
    return [t.chars for t in emoji.analyze(conv)]
 
def limpar_texto(texto):
    """
    Remove shortcodes :emoji_name: ANTES de tudo (evita 'smiling','face' etc.),
    depois remove emojis unicode, URLs, pontuação, números.
    """
    # 1. Remove shortcodes do YouTube (ex: :blue_heart:, :rolling_on_the_floor_laughing:)
    texto = re.sub(r":[a-zA-Z0-9_\-]+:", " ", texto)
    # 2. Remove URLs e menções
    texto = re.sub(r"http\S+|www\S+", "", texto)
    texto = re.sub(r"[@#]\w+", "", texto)
    # 3. Remove emojis unicode restantes
    texto = emoji.replace_emoji(texto, replace=" ")
    # 4. Remove pontuação e números
    texto = re.sub(r"[^\w\sáéíóúâêîôûãõçàèìòùäëïöü]", " ", texto, flags=re.UNICODE)
    texto = re.sub(r"\d+", "", texto)
    return re.sub(r"\s+", " ", texto).strip().lower()
 
def construir_freq_palavras(mensagens, min_len=3):
    counter = Counter()
    for msg in mensagens:
        limpo = limpar_texto(msg)
        tokens = [t for t in limpo.split()
                  if len(t) >= min_len and t not in STOPWORDS_PT]
        counter.update(tokens)
    return counter
 
def construir_freq_emojis(mensagens):
    counter = Counter()
    for msg in mensagens:
        counter.update(extrair_emojis(msg))
    return counter
 
# ---------------------------------------------------------------------------
# NUVEM DE PALAVRAS
# ---------------------------------------------------------------------------
 
def gerar_wordcloud(freq, titulo, estilo, fpath, max_words=150):
    if not freq:
        print(f"  ⚠  Sem dados para: {titulo}")
        return
    wc = WordCloud(
        width=1400, height=800,
        background_color=estilo["bg"],
        colormap=estilo["colormap"],
        max_words=max_words,
        collocations=False,
        prefer_horizontal=0.85,
        min_font_size=10,
    ).generate_from_frequencies(freq)
 
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(titulo, fontsize=16, fontweight="bold",
                 color="white", pad=14)
    fig.patch.set_facecolor(estilo["bg"])
    plt.tight_layout()
    plt.savefig(fpath, dpi=150, bbox_inches="tight", facecolor=estilo["bg"])
    plt.close()
    print(f"  → {fpath}")
 
# ---------------------------------------------------------------------------
# TRADUÇÃO DE NOMES DE EMOJIS → PORTUGUÊS
# ---------------------------------------------------------------------------
 
# Dicionário manual para os emojis mais comuns em chats de futebol.
# Fallback: nome em inglês limpo (ex: "fire", "blue heart").
NOMES_PT = {
    "😂": "risada com lágrima",
    "🤣": "rolando de rir",
    "😭": "choro intenso",
    "😢": "rosto triste",
    "😮": "boca aberta",
    "😡": "rosto furioso",
    "😍": "apaixonado",
    "🤦": "mão na testa",
    "🙄": "olhos revirados",
    "😎": "óculos de sol",
    "🥱": "bocejo",
    "🤮": "vomitando",
    "😬": "dentes cerrados",
    "🤬": "xingando",
    "😴": "dormindo",
    "🥳": "comemorando",
    "🤯": "cabeça explodindo",
    "😱": "gritando de medo",
    "🫡": "continência",
    "🫠": "derretendo",
    "❤️": "coração vermelho",
    "💙": "coração azul",
    "💚": "coração verde",
    "🖤": "coração preto",
    "🤍": "coração branco",
    "💛": "coração amarelo",
    "🧡": "coração laranja",
    "💜": "coração roxo",
    "💔": "coração partido",
    "❤️‍🔥": "coração em chamas",
    "🔥": "fogo",
    "⚽": "bola de futebol",
    "🏆": "troféu",
    "🥇": "medalha de ouro",
    "🎉": "festa",
    "🎊": "confete",
    "👏": "palmas",
    "👊": "soco",
    "✊": "punho erguido",
    "💪": "músculo",
    "🙏": "mãos juntas",
    "👎": "polegar baixo",
    "👍": "polegar cima",
    "🤝": "aperto de mão",
    "🫶": "coração com mãos",
    "✌️": "paz",
    "🤞": "dedos cruzados",
    "🖕": "dedo do meio",
    "🐔": "galinha",
    "🐓": "galo",
    "🦅": "águia",
    "🐷": "porco",
    "🦊": "raposa",
    "🐂": "touro",
    "🐯": "tigre",
    "🦁": "leão",
    "🐺": "lobo",
    "🦆": "pato",
    "🤡": "palhaço",
    "💀": "caveira",
    "🤌": "belíssimo",
    "🫵": "você",
    "👀": "olhos",
    "💩": "cocô",
    "🍿": "pipoca",
    "🧃": "suco",
    "🍺": "cerveja",
    "⭐": "estrela",
    "🌟": "estrela brilhante",
    "💫": "faísca",
    "✨": "brilhos",
    "💥": "explosão",
    "⚡": "raio",
    "🚨": "sirene",
    "📢": "megafone",
    "🎯": "alvo",
    "📉": "queda",
    "📈": "alta",
    "🔴": "círculo vermelho",
    "🟢": "círculo verde",
    "🔵": "círculo azul",
    "⚫": "círculo preto",
    "⚪": "círculo branco",
    "🟡": "círculo amarelo",
}
 
 
def emoji_para_nome(em: str) -> str:
    """Retorna o nome PT do emoji; fallback = nome EN limpo."""
    if em in NOMES_PT:
        return NOMES_PT[em]
    data = emoji.EMOJI_DATA.get(em, {})
    en = data.get("en", "").strip(":").replace("_", " ")
    return en if en else em
 
 
def freq_emojis_para_nomes(freq: Counter) -> Counter:
    """Converte Counter de emojis unicode → Counter de nomes."""
    nomes = Counter()
    for em, count in freq.items():
        nome = emoji_para_nome(em)
        if nome:
            nomes[nome] += count
    return nomes
 
 
# ---------------------------------------------------------------------------
# NUVEM DE EMOJIS — usa WordCloud com os NOMES dos emojis
# ---------------------------------------------------------------------------
 
def gerar_emoji_cloud_pil(freq, titulo, estilo, fpath,
                           max_emojis=50, img_w=1400, img_h=800):
    """
    Nuvem de palavras usando os NOMES dos emojis (em português),
    com tamanho proporcional à frequência.
    Usa WordCloud padrão — sem dependência de fonte especial.
    """
    if not freq:
        print(f"  ⚠  Sem emojis para: {titulo}")
        return
 
    # Converte emojis → nomes e limita ao top N
    freq_nomes = freq_emojis_para_nomes(freq)
    if not freq_nomes:
        return
 
    freq_top = Counter(dict(freq_nomes.most_common(max_emojis)))
 
    wc = WordCloud(
        width=img_w,
        height=img_h,
        background_color=estilo["bg"],
        colormap=estilo["colormap"],
        max_words=max_emojis,
        collocations=False,
        prefer_horizontal=0.7,
        min_font_size=12,
        relative_scaling=0.6,
    ).generate_from_frequencies(freq_top)
 
    fig, ax = plt.subplots(figsize=(img_w / 100, img_h / 100))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(titulo, fontsize=16, fontweight="bold",
                 color="white", pad=14)
    fig.patch.set_facecolor(estilo["bg"])
    plt.tight_layout()
    plt.savefig(fpath, dpi=100, bbox_inches="tight", facecolor=estilo["bg"])
    plt.close()
    print(f"  → {fpath}")
 
# ---------------------------------------------------------------------------
# PAINÉIS 2×2
# ---------------------------------------------------------------------------
 
def gerar_painel_palavras(freq_dict, fpath):
    """Painel 2×2 de nuvens de palavras."""
    fig, axes = plt.subplots(2, 2, figsize=(20, 12))
    axes = axes.flatten()
    entradas = [("geral", "Geral")] + [(c, LABELS[c]) for c in CONFRONTOS_ALVO]
 
    for idx, (chave, titulo) in enumerate(entradas):
        ax = axes[idx]
        freq  = freq_dict.get(chave, Counter())
        estilo = ESTILOS.get(chave, ESTILOS["geral"])
        ax.set_facecolor(estilo["bg"])
 
        if freq:
            wc = WordCloud(
                width=900, height=550,
                background_color=estilo["bg"],
                colormap=estilo["colormap"],
                max_words=100, collocations=False,
            ).generate_from_frequencies(freq)
            ax.imshow(wc, interpolation="bilinear")
        else:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                    fontsize=14, color="gray", transform=ax.transAxes)
 
        ax.axis("off")
        ax.set_title(titulo, fontsize=13, fontweight="bold", color="white", pad=8)
 
    fig.patch.set_facecolor("#0a0a0a")
    fig.suptitle("Nuvem de Palavras – Geral e por Confronto",
                 fontsize=17, fontweight="bold", color="white", y=1.01)
    plt.tight_layout()
    plt.savefig(fpath, dpi=150, bbox_inches="tight", facecolor="#0a0a0a")
    plt.close()
    print(f"  → {fpath}")
 
 
def gerar_painel_emojis(freq_dict, fpath, img_w=1400, img_h=800):
    """Painel 2×2 de nuvens de nomes de emojis (WordCloud)."""
    entradas = [("geral", "Geral")] + [(c, LABELS[c]) for c in CONFRONTOS_ALVO]
 
    fig, axes = plt.subplots(2, 2, figsize=(20, 12))
    axes = axes.flatten()
 
    for idx, (chave, titulo) in enumerate(entradas):
        ax = axes[idx]
        freq   = freq_dict.get(chave, Counter())
        estilo = ESTILOS.get(chave, ESTILOS["geral"])
        ax.set_facecolor(estilo["bg"])
 
        freq_nomes = freq_emojis_para_nomes(freq)
        if freq_nomes:
            wc = WordCloud(
                width=900, height=550,
                background_color=estilo["bg"],
                colormap=estilo["colormap"],
                max_words=50, collocations=False,
                prefer_horizontal=0.7,
                relative_scaling=0.6,
            ).generate_from_frequencies(freq_nomes)
            ax.imshow(wc, interpolation="bilinear")
        else:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                    fontsize=14, color="gray", transform=ax.transAxes)
 
        ax.axis("off")
        ax.set_title(titulo, fontsize=13, fontweight="bold", color="white", pad=8)
 
    fig.patch.set_facecolor("#0a0a0a")
    fig.suptitle("Nuvem de Emojis (por nome) – Geral e por Confronto",
                 fontsize=17, fontweight="bold", color="white", y=1.01)
    plt.tight_layout()
    plt.savefig(fpath, dpi=150, bbox_inches="tight", facecolor="#0a0a0a")
    plt.close()
    print(f"  → {fpath}")
 
# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
 
def main():
    print("=" * 65)
    print("  Nuvem de Palavras e Emojis – CRU×CAM | FLA×FLU | PAL×COR")
    print("=" * 65)
 
    print(f"\n[1/4] Carregando mensagens de '{DATA_DIR}' ...")
    dados = carregar_confrontos(DATA_DIR, CONFRONTOS_ALVO)
    todas = [m for msgs in dados.values() for m in msgs]
    print(f"  Total: {len(todas):,} mensagens")
 
    print("\n[2/4] Calculando frequências ...")
    freq_palavras = {"geral": construir_freq_palavras(todas)}
    freq_emojis   = {"geral": construir_freq_emojis(todas)}
    for c, msgs in dados.items():
        freq_palavras[c] = construir_freq_palavras(msgs)
        freq_emojis[c]   = construir_freq_emojis(msgs)
        print(f"  {c} → top palavras: {freq_palavras[c].most_common(5)}")
        print(f"  {c} → top emojis:   {freq_emojis[c].most_common(5)}")
 
    print("\n[3/4] Gerando nuvens individuais ...")
 
    # Palavras
    for chave in ["geral"] + CONFRONTOS_ALVO:
        gerar_wordcloud(
            freq_palavras[chave],
            titulo=f"Nuvem de Palavras – {LABELS.get(chave, chave)}",
            estilo=ESTILOS.get(chave, ESTILOS["geral"]),
            fpath=os.path.join(OUTPUT_DIR, f"nuvem_palavras_{chave}.png"),
        )
 
    # Emojis
    for chave in ["geral"] + CONFRONTOS_ALVO:
        gerar_emoji_cloud_pil(
            freq_emojis[chave],
            titulo=f"Nuvem de Emojis – {LABELS.get(chave, chave)}",
            estilo=ESTILOS.get(chave, ESTILOS["geral"]),
            fpath=os.path.join(OUTPUT_DIR, f"nuvem_emojis_{chave}.png"),
        )
 
    print("\n[4/4] Gerando painéis 2×2 ...")
    gerar_painel_palavras(freq_palavras,
                          os.path.join(OUTPUT_DIR, "painel_nuvem_palavras.png"))
    gerar_painel_emojis(freq_emojis,
                        os.path.join(OUTPUT_DIR, "painel_nuvem_emojis.png"))
 
    print("\n✓ Concluído! Arquivos em:", OUTPUT_DIR)
 
if __name__ == "__main__":
    main()