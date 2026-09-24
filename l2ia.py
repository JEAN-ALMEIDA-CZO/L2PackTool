#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerar arte com IA: icone, botao e borda -- e a animacao deles.

## O que cada provedor faz, sem meio-termo

    Gemini   gera imagem. E hoje o unico dos dois que gera.
    Claude   NAO gera imagem. A API dele e de texto -- serve para escrever e
             melhorar o pedido, traduzir, descrever. Pedir arte a ele nao
             devolve arte, devolve uma descricao.

Isto esta escrito aqui porque a tela precisa dizer a verdade: escolher Claude
e pedir um icone nao pode dar um erro tecnico dez segundos depois. A tela
pergunta antes o que o provedor escolhido sabe fazer.

## Modelo nao vem escrito no codigo

O nome do modelo e um campo de texto, guardado na configuracao. As empresas
aposentam modelo sem avisar, e um nome fixo no codigo transforma isso numa
atualizacao do programa. Assim o usuario troca uma linha e segue.

## A animacao nao vem da IA

Pedir quadros animados a um gerador de imagem da quadros PARECIDOS, nao
quadros de uma animacao: cada chamada desenha de novo, e o resultado pisca.
Entao a arte vem da IA e o movimento e feito aqui, sobre ela -- pulso, giro,
varredura. Sao transformacoes determinicas: o quadro 7 e sempre o mesmo, e a
volta ao quadro 1 fecha.

O pacote .utx sai com os quadros como objetos numerados, que e como o cliente
espera uma sequencia.
"""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

import motor

try:
    from PIL import Image, ImageChops, ImageEnhance
except ImportError:                                 # noqa: BLE001
    Image = None

SECAO = "ia"

# O que cada provedor sabe fazer. A tela pergunta isto antes de oferecer.
PROVEDORES = {
    "gemini": {
        "nome": "Google Gemini",
        "imagem": True,
        "texto": True,
        "site_da_chave": "https://aistudio.google.com/app/apikey",
        "site_dos_modelos": "https://ai.google.dev/gemini-api/docs/models",
        "dica_de_modelo": "ex.: gemini-2.5-flash-image",
    },
    "claude": {
        "nome": "Anthropic Claude",
        "imagem": False,
        "texto": True,
        "site_da_chave": "https://console.anthropic.com/settings/keys",
        "site_dos_modelos": "https://docs.claude.com/en/docs/about-claude/models",
        "dica_de_modelo": "ex.: claude-sonnet-4-5",
    },
}

TEMPO_LIMITE = 180


class ErroDeIA(Exception):
    pass


# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
def provedor():
    return (motor.ler_opcao(SECAO, "provedor", "gemini") or "gemini").lower()


def chave(qual=None):
    """A chave daquele provedor. Fica no config.ini, em texto puro."""
    return motor.ler_opcao(SECAO, "chave_%s" % (qual or provedor()), "")


def modelo(qual=None):
    return motor.ler_opcao(SECAO, "modelo_%s" % (qual or provedor()), "")


def guardar(qual, chave_nova=None, modelo_novo=None, escolher=True):
    """Guarda a chave e o modelo daquele provedor, e opcionalmente o escolhe."""
    if escolher:
        motor.gravar_opcao(SECAO, "provedor", qual)
    if chave_nova is not None:
        motor.gravar_opcao(SECAO, "chave_%s" % qual, chave_nova.strip())
    if modelo_novo is not None:
        motor.gravar_opcao(SECAO, "modelo_%s" % qual, modelo_novo.strip())


def pronto(qual=None, para="imagem"):
    """
    (da, por que nao) -- o provedor escolhido consegue fazer isso agora?

    Tres motivos para nao dar, e cada um pede uma acao diferente: o provedor
    nao faz aquilo, falta a chave, ou falta dizer o modelo.
    """
    qual = qual or provedor()
    ficha = PROVEDORES.get(qual)
    if ficha is None:
        return False, "provedor desconhecido: %s" % qual
    if not ficha.get(para):
        return False, ("%s não gera imagem: a API dele é de texto. Escolha o "
                       "Gemini em Configurações para gerar arte."
                       % ficha["nome"])
    if not chave(qual):
        return False, ("falta a chave da API do %s. Ponha em Configurações — "
                       "o botão leva ao site onde ela é criada."
                       % ficha["nome"])
    if not modelo(qual):
        return False, ("falta dizer o modelo do %s em Configurações (%s)."
                       % (ficha["nome"], ficha["dica_de_modelo"]))
    return True, ""


# ---------------------------------------------------------------------------
# O pedido que vai para a IA
# ---------------------------------------------------------------------------
# O que e fixo no pedido, e por que:
#
#   32x32 e o tamanho do icone do jogo. Pedir maior e reduzir depois borra o
#   traco fino, que e o que se ve num icone desse tamanho;
#   fundo transparente, porque o icone entra sobre a moldura do inventario;
#   luz de cima e sombra curta dao volume sem custar pixel;
#   nada de texto na arte: letra em 32x32 vira sujeira.
BASE_DO_PROMPT = (
    "Ícone de item para MMORPG de fantasia medieval sombria, no estilo de "
    "Lineage II, porém MODERNO: traço limpo, silhueta legível em tamanho "
    "pequeno, volume por luz e sombra e não por contorno grosso.\n"
    "Enquadramento: objeto único, centralizado, em três quartos, ocupando "
    "quase todo o quadro, sem cenário e sem moldura.\n"
    "Luz principal vindo de cima e à esquerda, sombra curta, brilho "
    "especular discreto no metal.\n"
    "Cores saturadas o suficiente para aparecer sobre fundo escuro; "
    "contraste alto entre o objeto e o vazio.\n"
    "Fundo TRANSPARENTE, sem sombra projetada no chão.\n"
    "Sem texto, sem letras, sem marca d'água, sem borda, sem mockup.\n"
    "Imagem quadrada, pensada para ser vista a 32x32 pixels."
)

BASE_DO_BOTAO = (
    "Textura de botão de interface para MMORPG de fantasia medieval sombria, "
    "estilo Lineage II porém MODERNO: superfície limpa, cantos definidos, "
    "material de metal escuro com detalhe em dourado envelhecido.\n"
    "Formato retangular, preenchendo todo o quadro, sem sobras nas bordas.\n"
    "Sem texto e sem ícone dentro: o botão é só a superfície.\n"
    "Iluminação de cima, leve relevo nas bordas, centro mais escuro para o "
    "texto do jogo aparecer por cima.\n"
    "Fundo TRANSPARENTE fora da área do botão."
)

BASE_DA_BORDA = (
    "Moldura decorativa para interface de MMORPG de fantasia medieval "
    "sombria, estilo Lineage II porém MODERNO: filete de metal com ornamento "
    "discreto nos cantos.\n"
    "A moldura ocupa as bordas do quadro e o CENTRO É COMPLETAMENTE "
    "TRANSPARENTE -- é por ele que o conteúdo do jogo aparece.\n"
    "Sem texto, sem fundo, sem sombra projetada.\n"
    "Espessura constante, cantos simétricos."
)

MOLDES = {"icone": BASE_DO_PROMPT, "botao": BASE_DO_BOTAO,
          "borda": BASE_DA_BORDA}


def montar_prompt(tipo, observacoes="", nome_do_item=""):
    """
    O pedido completo: a parte fixa, o que o item e, e o que o usuario pediu.

    A parte fixa vem primeiro e nao e editavel na tela de proposito -- e ela
    que mantem o resultado utilizavel como icone. O que o usuario escreve
    entra depois, como detalhe, e nao como substituto.
    """
    partes = [MOLDES.get(tipo, BASE_DO_PROMPT)]
    if nome_do_item.strip():
        partes.append("O objeto é: %s." % nome_do_item.strip())
    if observacoes.strip():
        partes.append("Pedido de quem encomendou: %s" % observacoes.strip())
    return "\n\n".join(partes)


# ---------------------------------------------------------------------------
# As chamadas
# ---------------------------------------------------------------------------
def _pedir(url, corpo, cabecalhos):
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(url, data=dados, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        detalhe = ""
        try:
            detalhe = erro.read().decode("utf-8", "replace")[:400]
        except Exception:                           # noqa: BLE001
            pass
        raise ErroDeIA("a API respondeu %s. %s" % (erro.code, detalhe))
    except urllib.error.URLError as erro:
        raise ErroDeIA("não consegui falar com a API: %s" % erro.reason)


def gerar_imagem(prompt, referencias=(), qual=None, aolog=None):
    """
    Gera uma imagem e devolve os bytes dela (PNG).

    `referencias` sao caminhos de imagem que entram no pedido como exemplo do
    que se quer -- o modelo olha e segue o estilo.
    """
    qual = qual or provedor()
    da, porque = pronto(qual, "imagem")
    if not da:
        raise ErroDeIA(porque)
    if aolog:
        aolog("Pedindo a imagem ao %s (%s)…"
              % (PROVEDORES[qual]["nome"], modelo(qual)))

    partes = [{"text": prompt}]
    for caminho in referencias:
        dados = Path(caminho).read_bytes()
        partes.append({"inline_data": {
            "mime_type": _tipo_da_imagem(caminho),
            "data": base64.b64encode(dados).decode("ascii")}})

    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "%s:generateContent" % modelo(qual))
    resposta = _pedir(url,
                      {"contents": [{"parts": partes}],
                       "generationConfig": {
                           "responseModalities": ["IMAGE", "TEXT"]}},
                      {"Content-Type": "application/json",
                       "x-goog-api-key": chave(qual)})

    for candidato in resposta.get("candidates", []):
        for parte in candidato.get("content", {}).get("parts", []):
            dados = (parte.get("inlineData") or parte.get("inline_data") or {})
            if dados.get("data"):
                return base64.b64decode(dados["data"])
    raise ErroDeIA("a resposta não trouxe imagem nenhuma. O modelo escolhido "
                   "gera imagem? Veja a lista de modelos em Configurações.")


def melhorar_texto(pedido, qual=None):
    """Passa um texto pela IA -- para refinar o pedido, traduzir, descrever."""
    qual = qual or provedor()
    da, porque = pronto(qual, "texto")
    if not da:
        raise ErroDeIA(porque)

    if qual == "claude":
        resposta = _pedir(
            "https://api.anthropic.com/v1/messages",
            {"model": modelo(qual), "max_tokens": 1024,
             "messages": [{"role": "user", "content": pedido}]},
            {"Content-Type": "application/json",
             "x-api-key": chave(qual),
             "anthropic-version": "2023-06-01"})
        partes = resposta.get("content") or []
        return "".join(p.get("text", "") for p in partes).strip()

    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "%s:generateContent" % modelo(qual))
    resposta = _pedir(url, {"contents": [{"parts": [{"text": pedido}]}]},
                      {"Content-Type": "application/json",
                       "x-goog-api-key": chave(qual)})
    for candidato in resposta.get("candidates", []):
        for parte in candidato.get("content", {}).get("parts", []):
            if parte.get("text"):
                return parte["text"].strip()
    return ""


def testar(qual=None):
    """Uma chamada curta, so para dizer se a chave e o modelo funcionam."""
    qual = qual or provedor()
    ficha = PROVEDORES.get(qual, {})
    if ficha.get("texto"):
        resposta = melhorar_texto("Responda apenas: ok", qual)
        return bool(resposta), (resposta or "")[:120]
    return False, "este provedor não responde texto"


def _tipo_da_imagem(caminho):
    fim = Path(caminho).suffix.lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".bmp": "image/bmp"}.get(fim, "image/png")


# ---------------------------------------------------------------------------
# A animacao, feita aqui e nao pela IA
# ---------------------------------------------------------------------------
# Os modos, e o que cada um serve:
#
#   pulso      brilho sobe e desce. Serve para botao que "respira".
#   giro       a arte gira. Serve para moldura circular e para selo.
#   varredura  um brilho atravessa a imagem. Serve para borda de botao.
MODOS = ("pulso", "giro", "varredura")


def animar(imagem, modo="pulso", quadros=8, forca=0.6):
    """
    Devolve `quadros` imagens a partir de uma so, em ciclo fechado.

    Ciclo fechado quer dizer que o ultimo quadro leva de volta ao primeiro
    sem salto -- e o que faz a animacao do cliente nao piscar. Por isso as
    contas usam seno: no fim da volta o valor e o mesmo do comeco.
    """
    if Image is None:
        raise ErroDeIA("falta o Pillow para montar a animação.")
    import math

    base = imagem.convert("RGBA") if hasattr(imagem, "convert") \
        else Image.open(imagem).convert("RGBA")
    saida = []
    for i in range(quadros):
        fase = 2 * math.pi * i / quadros
        if modo == "giro":
            quadro = base.rotate(360.0 * i / quadros, resample=Image.BICUBIC)
        elif modo == "varredura":
            quadro = _varrer(base, i / float(quadros), forca)
        else:
            fator = 1.0 + forca * 0.5 * (1 + math.sin(fase)) / 2.0
            quadro = ImageEnhance.Brightness(base).enhance(fator)
        saida.append(quadro)
    return saida


def _varrer(base, posicao, forca):
    """Um brilho diagonal atravessando a imagem, em ciclo."""
    largura, altura = base.size
    brilho = Image.new("L", (largura, altura), 0)
    faixa = max(4, largura // 6)
    centro = int((posicao * (largura + 2 * faixa)) - faixa)
    for x in range(max(0, centro - faixa), min(largura, centro + faixa)):
        forca_x = int(255 * forca * (1 - abs(x - centro) / float(faixa)))
        for y in range(altura):
            brilho.putpixel((x, y), max(0, forca_x))
    luz = Image.merge("RGBA", (brilho, brilho, brilho,
                               Image.new("L", (largura, altura), 0)))
    return ImageChops.add(base, luz)


def montar_sequencia(T, nome_do_pacote, nome_base, quadros, trabalho,
                     aolog=None):
    """
    Poe os quadros num .utx, numerados como o cliente espera.

    O nome de cada objeto e `<base>_00`, `<base>_01`... -- a numeracao com
    zero a esquerda mantem a ordem certa em qualquer lugar que ordene por
    texto, que e como o cliente e o umodel listam.
    """
    import l2icone

    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    imagens = {}
    for i, quadro in enumerate(quadros):
        alvo = trabalho / ("%s_%02d.png" % (nome_base, i))
        quadro.save(alvo)
        imagens["%s_%02d" % (nome_base, i)] = alvo
    if aolog:
        aolog("Montando %d quadros no pacote %s…" % (len(imagens),
                                                     nome_do_pacote))
    return l2icone.montar_pacote(T, nome_do_pacote, imagens, trabalho,
                                 aolog=aolog)
