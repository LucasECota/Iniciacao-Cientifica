import json
import re
import pandas as pd

from unidecode import unidecode

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

# =====================================================
# ARQUIVO PARA TESTE
# =====================================================

ARQUIVO = "data/cam_x_pal/livechats_cam_x_pal_itatiaia.jsonl"

# =====================================================
# LIMPEZA
# =====================================================

def limpar_texto(texto):

    texto = texto.lower()

    texto = unidecode(texto)

    texto = re.sub(r"http\\S+", "", texto)

    texto = re.sub(r"[^a-zA-Z0-9\\s]", " ", texto)

    texto = re.sub(r"\\s+", " ", texto).strip()

    return texto

# =====================================================
# LEITURA
# =====================================================

comentarios = []

with open(ARQUIVO, "r", encoding="utf-8") as f:

    for linha in f:

        try:
            obj = json.loads(linha)

            mensagem = obj.get("message", "")

            # remove mensagens muito pequenas
            if len(mensagem.split()) < 2:
                continue

            mensagem_limpa = limpar_texto(mensagem)

            comentarios.append(mensagem_limpa)

        except:
            pass

print(f"Comentários carregados: {len(comentarios)}")

# =====================================================
# MODELO
# =====================================================

embedding_model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

topic_model = BERTopic(
    embedding_model=embedding_model,
    language="multilingual",
    min_topic_size=15,
    verbose=True
)

topics, probs = topic_model.fit_transform(comentarios)

# =====================================================
# INFORMAÇÕES DOS TÓPICOS
# =====================================================

info = topic_model.get_topic_info()

print(info)

# =====================================================
# SALVAR TXT
# =====================================================

with open("resultado_topicos.txt", "w", encoding="utf-8") as f:

    f.write("=== TÓPICOS ENCONTRADOS ===\n\n")

    for topic_id in info["Topic"]:

        # ignora outliers
        if topic_id == -1:
            continue

        f.write(f"\nTOPICO {topic_id}\n")

        palavras = topic_model.get_topic(topic_id)

        for palavra, peso in palavras:

            f.write(f"{palavra} ({peso:.4f})\n")

        f.write("\n")

print("\nArquivo salvo: resultado_topicos.txt")