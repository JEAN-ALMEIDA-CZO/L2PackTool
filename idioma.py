#!/usr/bin/env python3
"""
Traducao da interface do L2PackTool.

As traducoes ficam em arquivos .ini na pasta `idiomas/`, um por lingua, e nao
dentro do codigo. Assim da para corrigir uma frase mal traduzida, ou
acrescentar um idioma novo, sem recompilar nada -- basta editar o arquivo e
reabrir o programa.

A chave de cada frase e a propria frase em portugues, e nao um apelido do tipo
"botao.processar". Duas razoes praticas:

  - o codigo continua legivel: `t("Marcar todas")` diz o que aparece na tela,
    enquanto `t("btn.mark_all")` obriga a abrir outro arquivo para descobrir;
  - falta de traducao nao vira tela quebrada. Uma frase ainda nao traduzida sai
    em portugues -- pior do que o ideal, e muito melhor do que um apelido cru
    no meio da janela.

Formato do arquivo: uma secao numerada por frase, com o original e a traducao.

    [0007]
    pt = Marcar todas
    t = Select all

Secao numerada, e nao a frase como chave, porque chave de .ini nao aceita "="
nem quebra de linha -- e as frases tem os dois. As quebras aparecem como \\n
literal; quem edita nao precisa saber de continuacao indentada.
"""

import configparser
import os
import sys


IDIOMAS = (
    ("pt", "Portugues do Brasil"),
    ("en", "English"),
    ("es", "Espanol"),
)

PASTA = "idiomas"

# Idioma em uso. Trocado por escolher(); o padrao e o do proprio codigo.
_atual = "pt"

# {idioma: {frase em portugues: traducao}}
TEXTOS = {}


def _raizes():
    """
    Onde procurar a pasta `idiomas`, na ordem.

    Ao lado do executavel primeiro: e la que o usuario vai editar. Depois
    dentro do pacote congelado, que e a copia de fabrica -- assim apagar a
    pasta externa por engano nao deixa o programa sem texto nenhum.
    """
    lugares = []
    base = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__))
    lugares.append(base)
    interno = getattr(sys, "_MEIPASS", None)
    if interno:
        lugares.append(interno)
    return lugares


def carregar():
    """
    Le os .ini de todos os idiomas. Chamar uma vez, no arranque.

    Arquivo ausente ou malformado nao para o programa: aquele idioma fica sem
    traducao e as frases saem em portugues.
    """
    TEXTOS.clear()
    for codigo, _nome in IDIOMAS:
        if codigo == "pt":
            continue
        TEXTOS[codigo] = _ler_arquivo(codigo)
    return {c: len(d) for c, d in TEXTOS.items()}


def _ler_arquivo(codigo):
    """
    As traducoes de um idioma, somando as duas copias.

    A copia de fabrica (dentro do executavel) entra primeiro; a de fora, ao
    lado do programa, escreve por cima do que definir. Somar, e nao escolher
    uma: um arquivo externo de uma versao anterior nao conhece as frases novas,
    e se ele simplesmente vencesse, essas frases sairiam em portugues no meio
    de uma janela em ingles -- exatamente o que acontecia antes desta soma.

    Assim quem corrige uma frase no arquivo de fora continua mandando nela, e o
    que ele nao tiver vem da copia de dentro.
    """
    achados = {}
    for raiz in reversed(_raizes()):        # de fabrica primeiro, externa por cima
        caminho = os.path.join(raiz, PASTA, codigo + ".ini")
        if not os.path.exists(caminho):
            continue

        cfg = configparser.ConfigParser(interpolation=None)
        try:
            cfg.read(caminho, encoding="utf-8-sig")
        except configparser.Error:
            continue

        for secao in cfg.sections():
            original = cfg.get(secao, "pt", fallback="")
            traduzido = cfg.get(secao, "t", fallback="")
            if original and traduzido:
                achados[_desescapar(original)] = _desescapar(traduzido)

    return achados


def _escapar(texto):
    """
    Quebra de linha e tabulacao viram \\n e \\t, para caber numa linha do .ini.

    Espaco no comeco ou no fim vira \\s. Nao e capricho: o configparser apara o
    branco em volta do valor ao ler, e muita frase daqui e justamente um rotulo
    indentado ("  %d NPCs.") ou uma aba com margem ("  NPC Effects  "). Sem
    isso a frase volta do arquivo diferente de como saiu e deixa de casar com a
    chave -- a traducao existe e nunca aparece.
    """
    texto = texto.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")

    comeco = len(texto) - len(texto.lstrip(" "))
    fim = len(texto) - len(texto.rstrip(" "))
    if comeco:
        texto = "\\s" * comeco + texto[comeco:]
    if fim:
        texto = texto[:len(texto) - fim] + "\\s" * fim
    return texto


def _desescapar(texto):
    saida, i = [], 0
    while i < len(texto):
        if texto[i] == "\\" and i + 1 < len(texto):
            seguinte = texto[i + 1]
            saida.append({"n": "\n", "t": "\t", "s": " ", "\\": "\\"}
                         .get(seguinte, "\\" + seguinte))
            i += 2
        else:
            saida.append(texto[i])
            i += 1
    return "".join(saida)


def escolher(codigo):
    """Passa a traduzir para este idioma. Codigo desconhecido volta ao portugues."""
    global _atual
    _atual = codigo if codigo in dict(IDIOMAS) else "pt"
    return _atual


def atual():
    return _atual


def nome_do_idioma(codigo):
    return dict(IDIOMAS).get(codigo, codigo)


def t(frase):
    """
    A frase no idioma em uso.

    Sem traducao cadastrada, devolve o original. E de proposito: e o que
    permite traduzir aos poucos sem nunca deixar a janela com buraco.
    """
    if _atual == "pt":
        return frase
    return TEXTOS.get(_atual, {}).get(frase, frase)


def N_(frase):
    """
    Marca a frase para o catalogo sem traduzir agora.

    Serve para texto que nasce antes de o idioma ser escolhido -- tabela no
    topo do modulo, rotulo guardado numa constante. A frase fica em portugues
    ali, entra no catalogo pela varredura, e quem usa passa por t() na hora de
    mostrar. Sem isto a frase simplesmente nunca apareceria traduzida, e pior:
    nem apareceria na lista do tradutor.
    """
    return frase


def gravar_catalogo(frases, codigo, caminho, existentes=None):
    """
    Escreve o .ini de um idioma, com todas as frases e o que ja houver traduzido.

    Serve para gerar o esqueleto de um idioma novo e para acrescentar as frases
    que apareceram desde a ultima vez, sem perder o que ja estava traduzido.
    """
    existentes = existentes or {}
    cfg = configparser.ConfigParser(interpolation=None)
    for i, frase in enumerate(frases, 1):
        secao = "%04d" % i
        cfg.add_section(secao)
        cfg.set(secao, "pt", _escapar(frase))
        cfg.set(secao, "t", _escapar(existentes.get(frase, "")))

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("; Traducao do L2PackTool -- %s\n"
                "; 'pt' e o original e serve de chave: nao mexa nele.\n"
                "; 't' e a traducao. Vazio significa 'ainda em portugues'.\n"
                "; \\n e quebra de linha; %%s e %%d sao preenchidos pelo programa\n"
                "; e tem de aparecer na mesma ordem da frase original.\n\n"
                % nome_do_idioma(codigo))
        cfg.write(f)
    return len(frases)


def cobertura(frases):
    """Quantas frases cada idioma ja tem, contra a lista dada."""
    return {codigo: (sum(1 for f in frases if TEXTOS.get(codigo, {}).get(f)), len(frases))
            for codigo, _nome in IDIOMAS if codigo != "pt"}


# ---------------------------------------------------------------------------
# Preferencia gravada
# ---------------------------------------------------------------------------
def ler_preferencia(config, padrao="pt"):
    """O idioma escolhido da ultima vez, do config.ini."""
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        cfg.read(config, encoding="utf-8-sig")
        return cfg.get("interface", "idioma", fallback=padrao)
    except (configparser.Error, OSError):
        return padrao


def gravar_preferencia(config, codigo):
    """Guarda a escolha, preservando o resto do arquivo."""
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        cfg.read(config, encoding="utf-8-sig")
        if not cfg.has_section("interface"):
            cfg.add_section("interface")
        cfg.set("interface", "idioma", codigo)
        with open(config, "w", encoding="utf-8") as f:
            cfg.write(f)
    except (configparser.Error, OSError):
        pass        # sem permissao de escrita a interface segue funcionando
