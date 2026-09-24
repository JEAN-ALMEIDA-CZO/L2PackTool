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


# O que dizer quando vai imagem junto. Sem isto o modelo trata a referencia
# como "inspiracao" e devolve outro desenho parecido -- e o usuario queria
# AQUELE desenho, com a mudanca que pediu.
COM_REFERENCIA = (
    "IMPORTANTE -- LEIA A IMAGEM ENVIADA ANTES DE DESENHAR.\n"
    "Vai junto %s. Ela não é inspiração: é o PONTO DE PARTIDA.\n"
    "1) Primeiro identifique o que há nela: que objeto é, de que material, "
    "em que ângulo, com que cores e que luz.\n"
    "2) PRESERVE isso. O mesmo objeto, a mesma silhueta, a mesma paleta e o "
    "mesmo ângulo devem continuar reconhecíveis no resultado.\n"
    "3) Aplique SOMENTE as mudanças pedidas abaixo. O que não foi pedido "
    "fica como está.\n"
    "Não troque o objeto por outro, não mude o enquadramento e não redesenhe "
    "do zero."
)

SEM_REFERENCIA = (
    "Não há imagem de referência: desenhe a partir da descrição abaixo."
)


def montar_prompt(tipo, observacoes="", nome_do_item="", referencias=0,
                  lado=0):
    """
    O pedido completo: a parte fixa, a referencia, o objeto e o que se pediu.

    A parte fixa vem primeiro e nao e editavel na tela de proposito -- e ela
    que mantem o resultado utilizavel como icone. O que o usuario escreve
    entra depois, como detalhe, e nao como substituto.

    `referencias` e QUANTAS imagens vao junto, porque o pedido muda de
    natureza com elas: sem imagem se desenha do zero, com imagem se EDITA a
    que veio. `lado` e o tamanho final no jogo, que entra no pedido para o
    modelo nao encher de detalhe que some ao encolher.
    """
    partes = [MOLDES.get(tipo, BASE_DO_PROMPT)]
    if referencias:
        quantas = ("uma imagem de referência" if referencias == 1
                   else "%d imagens de referência" % referencias)
        partes.append(COM_REFERENCIA % quantas)
    else:
        partes.append(SEM_REFERENCIA)
    if nome_do_item.strip():
        partes.append("O objeto é: %s." % nome_do_item.strip())
    if observacoes.strip():
        partes.append("Pedido de quem encomendou: %s" % observacoes.strip())
    if lado:
        partes.append(
            "A arte será reduzida para %dx%d pixels no jogo. Desenhe pensando "
            "nesse tamanho: formas grandes, poucos detalhes finos, contraste "
            "alto -- detalhe pequeno demais vira sujeira ao encolher."
            % (lado, lado))
    return "\n\n".join(partes)



# ---------------------------------------------------------------------------
# O erro da API, dito de um jeito que se possa agir
# ---------------------------------------------------------------------------
# A API responde com JSON. Mostrar esse JSON na tela nao ajuda ninguem: a
# pessoa escolheu `gemini-2.5-flash` -- que existe, aceita a chave e responde
# -- e recebeu de volta chaves, aspas e "INVALID_ARGUMENT". O que faltava era
# a frase seguinte: esse modelo so devolve texto, escolha um de imagem.
#
# Cada entrada aqui e (pedaco da mensagem da API, o que dizer). A ordem
# importa: a primeira que casar vale, entao o mais especifico vem antes.
RECADOS_DA_API = (
    ("only supports text output",
     "o modelo %(modelo)s só devolve texto -- ele não desenha. Para gerar "
     "arte escolha um modelo de IMAGEM em Configurações: no Gemini o nome "
     "costuma trazer `image` (ex.: gemini-2.5-flash-image). O botão \"Ver os "
     "modelos…\" abre a lista do fabricante."),
    ("does not support image generation",
     "o modelo %(modelo)s não gera imagem. Escolha um modelo de imagem em "
     "Configurações -- no Gemini o nome costuma trazer `image`."),
    ("api key not valid",
     "a chave da API não foi aceita. Confira se copiou a chave inteira, sem "
     "espaço no fim, e se ela é do %(provedor)s."),
    ("api_key_invalid",
     "a chave da API não foi aceita. Confira se copiou a chave inteira, sem "
     "espaço no fim, e se ela é do %(provedor)s."),
    ("expired",
     "a chave da API expirou. Crie outra no site do %(provedor)s e cole em "
     "Configurações."),
    ("is not found",
     "o modelo %(modelo)s não existe nessa API. Nome de modelo muda e é "
     "aposentado: confira na lista do fabricante, em Configurações."),
    ("not supported for generatecontent",
     "o modelo %(modelo)s não atende esse tipo de pedido. Veja na lista do "
     "fabricante qual serve para imagem."),
    ("quota",
     "a cota da sua chave acabou (ou o limite por minuto estourou). Espere um "
     "pouco, ou veja o plano da chave no site do %(provedor)s."),
    ("rate limit",
     "pedidos demais em pouco tempo. Espere alguns segundos e tente de novo."),
    ("billing",
     "a conta do %(provedor)s está sem forma de pagamento ativa para esse "
     "modelo."),
    ("overloaded",
     "o servidor do %(provedor)s está sobrecarregado agora. Tente de novo em "
     "alguns instantes."),
    ("safety",
     "o pedido foi recusado pelo filtro de conteúdo do %(provedor)s. Troque "
     "as palavras das observações e tente de novo."),
    ("blocked",
     "o pedido foi bloqueado pelo filtro de conteúdo do %(provedor)s. Troque "
     "as palavras das observações e tente de novo."),
)

# Quando a mensagem nao casa com nada, o codigo HTTP ainda diz alguma coisa.
RECADOS_POR_CODIGO = {
    400: "a API recusou o pedido.",
    401: "a chave da API não foi aceita.",
    403: "a chave não tem permissão para esse modelo.",
    404: "a API não achou esse modelo.",
    429: "pedidos demais, ou cota esgotada.",
    500: "a API teve um erro interno. Tente de novo.",
    503: "a API está indisponível agora. Tente de novo em alguns instantes.",
}


def mensagem_da_api(corpo):
    """A frase que a API mandou, sem o JSON em volta."""
    try:
        dados = json.loads(corpo)
    except (TypeError, ValueError):
        return (corpo or "").strip()
    erro = dados.get("error") if isinstance(dados, dict) else None
    if isinstance(erro, dict):
        return str(erro.get("message") or erro.get("status") or "").strip()
    if isinstance(erro, str):
        return erro.strip()
    return (corpo or "").strip()


def explicar_erro(codigo, corpo, qual=None):
    """
    O erro da API em uma frase, com o que fazer -- e o original no fim.

    O original fica porque mensagem traduzida nao se pesquisa: quem for
    procurar na internet precisa do texto como a API o escreveu.
    """
    qual = qual or provedor()
    ficha = PROVEDORES.get(qual, {})
    dados = {"modelo": modelo(qual) or "escolhido",
             "provedor": ficha.get("nome", qual)}

    dito = mensagem_da_api(corpo)
    procura = dito.lower()
    for pedaco, recado in RECADOS_DA_API:
        if pedaco in procura:
            return "%s\n\n(a API disse: %s)" % (recado % dados, dito[:300])

    geral = RECADOS_POR_CODIGO.get(codigo, "a API respondeu %s." % codigo)
    if dito:
        return "%s\n\n(a API disse: %s)" % (geral, dito[:300])
    return geral


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
            detalhe = erro.read().decode("utf-8", "replace")[:2000]
        except Exception:                           # noqa: BLE001
            pass
        raise ErroDeIA(explicar_erro(erro.code, detalhe))
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
        tipo, dados = _referencia_em_bytes(caminho)
        partes.append({"inline_data": {
            "mime_type": tipo,
            "data": base64.b64encode(dados).decode("ascii")}})

    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "%s:generateContent" % modelo(qual))
    resposta = _pedir(url,
                      {"contents": [{"parts": partes}],
                       "generationConfig": {
                           "responseModalities": ["IMAGE", "TEXT"]}},
                      {"Content-Type": "application/json",
                       "x-goog-api-key": chave(qual)})

    ditos = []
    for candidato in resposta.get("candidates", []):
        for parte in candidato.get("content", {}).get("parts", []):
            dados = (parte.get("inlineData") or parte.get("inline_data") or {})
            if dados.get("data"):
                return base64.b64decode(dados["data"])
            if parte.get("text"):
                ditos.append(parte["text"].strip())

    # O modelo respondeu, mas com texto. E o que um modelo de texto faz quando
    # lhe pedem desenho -- e o que ele escreveu costuma dizer o motivo, entao
    # engolir isso seria esconder a resposta.
    recado = ("o modelo %s respondeu sem imagem. Se ele for de texto, escolha "
              "um modelo de IMAGEM em Configurações -- no Gemini o nome "
              "costuma trazer `image`." % (modelo(qual) or "escolhido"))
    if ditos:
        recado += "\n\n(o modelo escreveu: %s)" % " ".join(ditos)[:300]
    raise ErroDeIA(recado)



def _referencia_em_bytes(caminho):
    """
    (tipo, bytes) de uma imagem de referencia, ja num formato que a API le.

    GIF animado entra pelo PRIMEIRO QUADRO: mandar o arquivo inteiro faria o
    modelo receber um formato que ele nao interpreta, e o que interessa numa
    referencia e o desenho, nao o movimento.
    """
    caminho = Path(caminho)
    animada = None
    if caminho.suffix.lower() in (".gif", ".webp", ".apng"):
        try:
            animada = quadros_de_arquivo(caminho)
        except Exception:                           # noqa: BLE001
            animada = None
    if animada:
        import io

        memoria = io.BytesIO()
        animada[0].save(memoria, "PNG")
        return "image/png", memoria.getvalue()
    return _tipo_da_imagem(caminho), caminho.read_bytes()

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
# GIF: o que a IA nao faz, e o que o programa faz
# ---------------------------------------------------------------------------
# A API de imagem devolve UM quadro, em PNG. Nao existe resposta animada: nem
# o Gemini nem nenhum outro modelo de imagem devolve GIF. Entao animacao
# gerada continua saindo daqui, de um quadro so.
#
# O que existe e o contrario: o usuario JA TER um GIF pronto. Nesse caso os
# quadros dele valem mais do que qualquer movimento sintetico, porque foram
# desenhados. `quadros_de_arquivo` le GIF, WEBP animado e APNG.
def quadros_de_arquivo(caminho):
    """
    Os quadros de uma imagem animada, ou None se ela for parada.

    Cada quadro vem RGBA e ja composto sobre o anterior -- GIF guarda quadro
    parcial, so o pedaco que mudou, e usar o pedaco solto daria buraco.
    """
    if Image is None:
        raise ErroDeIA("falta o Pillow para ler a imagem.")

    from PIL import ImageSequence

    with Image.open(caminho) as arquivo:
        if getattr(arquivo, "n_frames", 1) <= 1:
            return None
        quadros = []
        for quadro in ImageSequence.Iterator(arquivo):
            quadros.append(quadro.convert("RGBA"))
    return quadros or None


def reamostrar(quadros, quantos):
    """
    A mesma animacao com outra contagem de quadros.

    Serve para encaixar um GIF de 40 quadros numa sequencia de 13 do cliente:
    escolhe-se ao longo do tempo, em vez de cortar o fim -- cortar o fim
    deixaria a volta pela metade.
    """
    quadros = list(quadros)
    if not quadros or quantos <= 0 or len(quadros) == quantos:
        return quadros
    passo = len(quadros) / float(quantos)
    return [quadros[min(len(quadros) - 1, int(i * passo))]
            for i in range(quantos)]


def encaixar(imagem, lado):
    """
    A imagem no tamanho do jogo, quadrada, sem esticar.

    A IA devolve 1024x1024 e o icone do cliente tem 32 ou 64: encolher e
    obrigatorio, e LANCZOS e o que preserva o traco. Imagem nao quadrada e
    centralizada num quadrado transparente, porque esticar deforma.
    """
    if Image is None:
        raise ErroDeIA("falta o Pillow para preparar a imagem.")
    imagem = imagem.convert("RGBA")
    if imagem.size == (lado, lado):
        return imagem
    largura, altura = imagem.size
    escala = float(lado) / max(largura, altura)
    novo = (max(1, int(round(largura * escala))),
            max(1, int(round(altura * escala))))
    menor = imagem.resize(novo, Image.LANCZOS)
    if novo == (lado, lado):
        return menor
    fundo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    fundo.paste(menor, ((lado - novo[0]) // 2, (lado - novo[1]) // 2))
    return fundo

# ---------------------------------------------------------------------------
# A animacao, feita aqui e nao pela IA
# ---------------------------------------------------------------------------
# Os modos, e o que cada um serve:
#
#   pulso      brilho sobe e desce. Serve para botao que "respira".
#   giro       a arte gira. Serve para moldura circular e para selo.
#   varredura  um brilho atravessa a imagem. Serve para borda de botao.
# Os modos, na ordem em que aparecem na tela: do mais discreto ao mais
# chamativo. Quem escolhe animacao para um icone de inventario quase sempre
# quer os primeiros; os ultimos sao para pecas de interface.
MODOS = ("pulso", "fade", "giro", "balanco", "flutuar", "zoom", "tremor",
         "varredura", "contorno", "cintilar", "onda", "matiz")

# O que cada um faz, em uma linha, para a tela poder explicar sem manual.
EXPLICACAO = {
    "pulso": "o brilho sobe e desce",
    "fade": "aparece e some, sem mudar de forma",
    "giro": "dá uma volta inteira",
    "balanco": "gira um pouco para cada lado",
    "flutuar": "sobe e desce no lugar",
    "zoom": "aproxima e afasta",
    "tremor": "treme e volta ao lugar",
    "varredura": "um brilho atravessa a arte",
    "contorno": "uma luz corre pela borda",
    "cintilar": "faíscas acendem e apagam",
    "onda": "ondula como água",
    "matiz": "a cor gira pelo espectro",
}


def animar(imagem, modo="pulso", quadros=8, forca=0.6):
    """
    Devolve `quadros` imagens a partir de uma so, em ciclo fechado.

    Ciclo fechado: o quadro depois do ultimo e o primeiro. E o que faz a
    animacao do cliente nao dar um pulo a cada volta -- e num icone que roda
    o tempo todo, o pulo e a unica coisa que se enxerga.

    Por isso nada aqui usa acaso por quadro: ate o que parece faisca tem
    posicao fixa e brilho em seno.
    """
    if Image is None:
        raise ErroDeIA("falta o Pillow para montar a animação.")

    base = imagem.convert("RGBA") if hasattr(imagem, "convert") \
        else Image.open(imagem).convert("RGBA")
    fabrica = _FABRICAS.get(modo, _pulso)
    return [fabrica(base, i / float(quadros), forca) for i in range(quadros)]


def _seno(fase):
    """0 a 1 e de volta a 0, fechando o ciclo."""
    import math
    return (1 - math.cos(2 * math.pi * fase)) / 2.0


def _pulso(base, fase, forca):
    return ImageEnhance.Brightness(base).enhance(1.0 + forca * _seno(fase))


def _fade(base, fase, forca):
    """Mexe so no alfa: a forma fica, a presenca varia."""
    copia = base.copy()
    alfa = copia.getchannel("A").point(
        lambda v: int(v * (1.0 - forca * _seno(fase))))
    copia.putalpha(alfa)
    return copia


def _giro(base, fase, _forca):
    return base.rotate(360.0 * fase, resample=Image.BICUBIC)


def _balanco(base, fase, forca):
    """Gira pouco, para um lado e para o outro. 15 graus na forca cheia."""
    import math
    angulo = 15.0 * forca * math.sin(2 * math.pi * fase)
    return base.rotate(angulo, resample=Image.BICUBIC)


def _flutuar(base, fase, forca):
    """Sobe e desce sem sair do quadro -- o deslocamento e do tamanho."""
    import math
    largura, altura = base.size
    desloca = int(round(altura * 0.08 * forca * math.sin(2 * math.pi * fase)))
    quadro = Image.new("RGBA", base.size, (0, 0, 0, 0))
    quadro.paste(base, (0, desloca), base)
    return quadro


def _zoom(base, fase, forca):
    """
    Aproxima e afasta mantendo o tamanho do quadro.

    A imagem cresce e e RECORTADA no centro, em vez de o quadro crescer: um
    icone que muda de tamanho de quadro para quadro nao entra num pacote.
    """
    largura, altura = base.size
    escala = 1.0 + 0.18 * forca * _seno(fase)
    nova = base.resize((max(1, int(largura * escala)),
                        max(1, int(altura * escala))), Image.LANCZOS)
    esquerda = (nova.size[0] - largura) // 2
    topo = (nova.size[1] - altura) // 2
    return nova.crop((esquerda, topo, esquerda + largura, topo + altura))


def _tremor(base, fase, forca):
    """
    Treme e volta. O desenho do tremor e fixo: seno em x, dobro em y.

    Acaso por quadro daria um tremor diferente a cada volta, e ai a animacao
    nunca fecharia.
    """
    import math
    largura, altura = base.size
    amplitude = max(1, int(min(largura, altura) * 0.04 * forca))
    dx = int(round(amplitude * math.sin(2 * math.pi * fase)))
    dy = int(round(amplitude * math.sin(4 * math.pi * fase)))
    quadro = Image.new("RGBA", base.size, (0, 0, 0, 0))
    quadro.paste(base, (dx, dy), base)
    return quadro


def _varredura(base, fase, forca):
    """Um brilho diagonal atravessando a imagem, em ciclo."""
    largura, altura = base.size
    faixa = max(4, largura // 6)
    centro = int((fase * (largura + 2 * faixa)) - faixa)
    brilho = Image.new("L", (largura, altura), 0)
    pixels = brilho.load()
    for x in range(max(0, centro - faixa), min(largura, centro + faixa)):
        valor = int(255 * forca * (1 - abs(x - centro) / float(faixa)))
        for y in range(altura):
            pixels[x, y] = max(0, valor)
    luz = Image.merge("RGBA", (brilho, brilho, brilho,
                               Image.new("L", (largura, altura), 0)))
    return ImageChops.add(base, luz)


def _contorno(base, fase, forca):
    """
    Uma luz correndo pela borda, dando a volta.

    Serve para moldura: o centro fica intacto e so a moldura acende. A
    posicao anda pelo PERIMETRO, entao a volta fecha sozinha.
    """
    largura, altura = base.size
    perimetro = 2 * (largura + altura)
    andado = fase * perimetro
    comprimento = max(6, perimetro // 8)

    brilho = Image.new("L", (largura, altura), 0)
    pixels = brilho.load()
    for passo in range(int(comprimento)):
        posicao = (andado + passo) % perimetro
        forca_luz = int(255 * forca * (1 - passo / float(comprimento)))
        x, y = _ponto_do_perimetro(posicao, largura, altura)
        for ex in range(max(0, x - 1), min(largura, x + 2)):
            for ey in range(max(0, y - 1), min(altura, y + 2)):
                pixels[ex, ey] = max(pixels[ex, ey], forca_luz)
    luz = Image.merge("RGBA", (brilho, brilho, brilho, brilho))
    return Image.alpha_composite(base, luz)


def _ponto_do_perimetro(posicao, largura, altura):
    """Onde cai esta distancia, andando pela borda no sentido horario."""
    if posicao < largura:
        return int(posicao), 0
    posicao -= largura
    if posicao < altura:
        return largura - 1, int(posicao)
    posicao -= altura
    if posicao < largura:
        return largura - 1 - int(posicao), altura - 1
    posicao -= largura
    return 0, altura - 1 - int(posicao)


def _cintilar(base, fase, forca):
    """
    Faiscas acendendo e apagando sobre a arte.

    As posicoes sao fixas -- tiradas de uma semente constante -- e o que
    varia e o brilho de cada uma, cada qual com a sua fase. Assim a faisca
    pisca, mas sempre no mesmo lugar, e a volta fecha.
    """
    import math
    import random

    largura, altura = base.size
    sorteio = random.Random(20260924)
    brilho = Image.new("L", (largura, altura), 0)
    pixels = brilho.load()
    quantas = max(3, (largura * altura) // 600)
    for i in range(quantas):
        x = sorteio.randrange(largura)
        y = sorteio.randrange(altura)
        propria = sorteio.random()
        valor = math.sin(2 * math.pi * (fase + propria))
        if valor <= 0:
            continue
        luz = int(255 * forca * valor)
        for ex in range(max(0, x - 1), min(largura, x + 2)):
            for ey in range(max(0, y - 1), min(altura, y + 2)):
                perto = 255 if (ex == x and ey == y) else 120
                pixels[ex, ey] = max(pixels[ex, ey], luz * perto // 255)
    luz_rgba = Image.merge("RGBA", (brilho, brilho, brilho, brilho))
    return Image.alpha_composite(base, luz_rgba)


def _onda(base, fase, forca):
    """
    Ondula: cada linha anda um pouco para o lado, seguindo um seno.

    A onda ANDA com a fase, e o deslocamento de cada linha volta ao inicio no
    fim do ciclo.
    """
    import math
    largura, altura = base.size
    amplitude = max(1, int(largura * 0.05 * forca))
    quadro = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for y in range(altura):
        desloca = int(round(amplitude * math.sin(
            2 * math.pi * (y / float(altura) + fase))))
        linha = base.crop((0, y, largura, y + 1))
        quadro.paste(linha, (desloca, y))
    return quadro


def _matiz(base, fase, _forca):
    """
    A cor gira pelo espectro, e o alfa nao e tocado.

    Uma volta inteira de matiz fecha por definicao: 360 graus e o mesmo que
    zero.
    """
    from PIL import Image as _Image

    alfa = base.getchannel("A")
    hsv = base.convert("RGB").convert("HSV")
    matiz, saturacao, valor = hsv.split()
    # A roda de matiz do Pillow vai de 0 a 255, e a volta inteira sao 256
    # passos -- somar 255 deixa a volta um passo curta, e o ultimo quadro nao
    # fecha no primeiro.
    passo = int(round(256 * fase)) % 256
    matiz = matiz.point(lambda v: (v + passo) % 256)
    girada = _Image.merge("HSV", (matiz, saturacao, valor)).convert("RGBA")
    girada.putalpha(alfa)
    return girada


_FABRICAS = {
    "pulso": _pulso, "fade": _fade, "giro": _giro, "balanco": _balanco,
    "flutuar": _flutuar, "zoom": _zoom, "tremor": _tremor,
    "varredura": _varredura, "contorno": _contorno, "cintilar": _cintilar,
    "onda": _onda, "matiz": _matiz,
}


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
