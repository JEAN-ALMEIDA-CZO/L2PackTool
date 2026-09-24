#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Animação no cliente, pelos dois caminhos que o Lineage 2 tem.

## 1. A corrente do motor: `AnimNext`

Uma textura pode apontar para a seguinte. A propriedade chama-se `AnimNext`,
é do próprio Unreal, e o motor percorre a corrente sozinho -- ninguém
programa nada, e a textura anima em qualquer lugar onde apareça.

Está à vista no `anim70.u` de qualquer cliente que tenha esse pacote:

    anim_over   TotalFrameNum = 21   Animator = 50.0   MaxFrameRate = 50.0
    anim_over -> 02 -> 03 -> 04 -> ... -> 21

Vinte quadros mais a cabeça, que é o `TotalFrameNum`. É este o caminho de
`animar_textura_do_cliente`: os quadros viram um `.utx` novo e a textura
escolhida passa a apontar para o primeiro deles. A textura do cliente não
muda de conteúdo, de grupo nem de endereço -- ganha uma propriedade.

A escrita da corrente é do `l2anim`, que já a fazia para o vídeo da tela de
entrada; aqui ela serve a qualquer textura: ícone, botão, moldura, céu.

## 2. A família numerada, que a interface toca

O outro caminho não é do motor, é do código da interface. O
`l2_skilltime.utx` mostra:

    cooltime000 .. cooltime359     360 quadros, 32x32, DXT3
    ToggleEffect001 .. ToggleEffect013   13 quadros
    CooltimeEnd1 .. CooltimeEnd9          9 quadros

São texturas soltas, sem corrente. Quem escolhe qual desenhar a cada instante
é a interface, que conhece esses nomes: o `cooltime` segue a recarga, o
`ToggleEffect` gira em laço enquanto a habilidade está ligada. Aqui não dá
para inventar nome -- um que o cliente não conheça fica parado no pacote --,
mas dá para trocar o DESENHO do que existe, mantendo nome, contagem, tamanho
e formato. É o que faz `trocar_quadros`.

## Qual usar

Para animar alguma coisa que hoje é parada, o caminho é a corrente. Para
mudar a aparência de uma animação que o cliente já toca, é a família. Os dois
guardam o original antes de gravar.
"""
import re
from pathlib import Path

import l2anim
import l2mapa
import l2textura
import motor

# Uma família precisa de pelo menos isto para ser considerada animação. Duas
# texturas com número no fim são coincidência; três já são uma sequência.
MINIMO_DE_QUADROS = 3

# Onde o original espera, nos dois caminhos.
PASTA_DE_COPIAS = "backup_animacao"

# O nome termina em número, e o que vem antes é a família. `cooltime007` ->
# ("cooltime", 7).
NUMERADO = re.compile(r"^(.*?)(\d+)$")


class ErroDeAnimacao(Exception):
    pass


def familias(pacote):
    """
    As sequências animadas de um pacote já lido.

    Devolve [{"prefixo", "quadros": [(numero, indice, nome)], "largura",
    "altura", "formato"}], da maior para a menor. Família com tamanhos
    diferentes entre os quadros é devolvida assim mesmo, e quem for gravar
    respeita o de cada um.
    """
    achadas = {}
    for indice, nome, largura, altura in l2textura.texturas(pacote):
        casou = NUMERADO.match(nome)
        if not casou:
            continue
        prefixo = casou.group(1)
        achadas.setdefault(prefixo, []).append(
            {"numero": int(casou.group(2)), "indice": indice, "nome": nome,
             "largura": largura, "altura": altura})

    saida = []
    for prefixo, quadros in achadas.items():
        if len(quadros) < MINIMO_DE_QUADROS:
            continue
        quadros.sort(key=lambda q: q["numero"])
        saida.append({
            "prefixo": prefixo,
            "quadros": quadros,
            "largura": quadros[0]["largura"],
            "altura": quadros[0]["altura"],
            "formato": l2textura.formato(pacote, quadros[0]["indice"]),
            "quantos": len(quadros),
        })
    saida.sort(key=lambda f: -f["quantos"])
    return saida


def familias_do_arquivo(T, caminho):
    """As famílias de um .utx do disco. Abre, lê e devolve -- sem gravar."""
    pacote = l2mapa.ler(Path(caminho), T)
    return pacote, familias(pacote)


def trocar_quadros(T, caminho, prefixo, imagens, trabalho, aolog=None,
                   destino=None):
    """
    Põe `imagens` nos quadros daquela família, no lugar dos que estão lá.

    `imagens` é uma lista de PIL.Image em ciclo. Se vierem menos do que a
    família tem, elas se repetem em laço -- é o caso comum: oito quadros de
    animação para os 360 do cooltime dariam 45 voltas, o que é rápido demais,
    mas para o ToggleEffect de treze dá certo.

    Cada quadro é redimensionado para o tamanho do que substitui e gravado no
    formato dele. Devolve o caminho do pacote gravado.
    """
    def diga(texto):
        if aolog:
            aolog(texto)

    caminho = Path(caminho)
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)

    pacote = l2mapa.ler(caminho, T)
    alvo = None
    for familia in familias(pacote):
        if familia["prefixo"].lower() == prefixo.lower():
            alvo = familia
            break
    if alvo is None:
        raise ErroDeAnimacao(
            "não achei a sequência %s em %s. As que existem: %s"
            % (prefixo, caminho.name,
               ", ".join(f["prefixo"] for f in familias(pacote)) or "nenhuma"))
    if not imagens:
        raise ErroDeAnimacao("nenhum quadro para gravar.")

    diga("Sequência %s: %d quadros de %dx%d em %s."
         % (alvo["prefixo"], alvo["quantos"], alvo["largura"], alvo["altura"],
            alvo["formato"]))
    if len(imagens) != alvo["quantos"]:
        diga("Você deu %d quadros para %d posições: eles se repetem em laço."
             % (len(imagens), alvo["quantos"]))

    # O `aplicar` recebe {nome da textura: caminho de imagem} -- ele mesmo
    # descobre o formato e a quantidade de mipmaps de cada uma. Entao os
    # quadros sao gravados em disco e passados por nome, que e tambem o que
    # deixa o que foi trocado visivel para quem for conferir.
    trocas = {}
    for posicao, quadro in enumerate(alvo["quadros"]):
        imagem = imagens[posicao % len(imagens)]
        if imagem.size != (quadro["largura"], quadro["altura"]):
            from PIL import Image as _Image
            imagem = imagem.resize((quadro["largura"], quadro["altura"]),
                                   _Image.LANCZOS)
        arquivo = trabalho / ("%s.png" % quadro["nome"])
        imagem.save(arquivo)
        trocas[quadro["nome"]] = arquivo

    l2textura.aplicar(T, pacote, trocas, trabalho, aolog=diga)
    saida = Path(destino) if destino else (trabalho / caminho.name)
    l2textura.gravar(pacote, saida)
    diga("Pacote gravado em %s" % saida)
    return saida



# ---------------------------------------------------------------------------
# A corrente do motor: animar uma textura que hoje e parada
# ---------------------------------------------------------------------------
TAXA_PADRAO = l2anim.TAXA_PADRAO
MAXIMO_DE_QUADROS = l2anim.MAXIMO_DE_QUADROS


def texturas_do_arquivo(T, caminho):
    """(pacote, [(indice, nome, largura, altura)]) de um .utx ou .u do disco."""
    pacote = l2mapa.ler(Path(caminho), T)
    return pacote, l2textura.texturas(pacote)


def _potencia_de_dois(medida):
    """A potencia de dois mais perto, para baixo, com o minimo de 8."""
    medida = max(8, int(medida))
    potencia = 8
    while potencia * 2 <= medida:
        potencia *= 2
    return potencia


def tamanho_da_imagem(arquivo):
    """O tamanho de uma imagem em disco, sem deixar o arquivo aberto."""
    from PIL import Image as _Image

    with _Image.open(arquivo) as imagem:
        return imagem.size


def nome_de_pacote(semente, prefixo="Anim"):
    """
    Um nome que o `ucc make` aceita: letra na frente, so letra, numero e _.

    O nome do pacote vira parte do endereco que a textura do cliente vai
    importar, entao ele nao pode sair do nome de arquivo que o usuario
    escolheu -- que pode ter espaco, acento e ponto.
    """
    limpo = re.sub(r"[^A-Za-z0-9_]", "", str(semente))
    limpo = re.sub(r"^[^A-Za-z]+", "", limpo)
    nome = (prefixo + limpo.title())[:31]
    if len(nome) < 3:
        nome = prefixo + "Quadros"
    return nome


def gravar_quadros(imagens, pasta, prefixo="quadro", tamanho=None):
    """
    Poe as imagens em disco, numeradas, no tamanho que a textura pede.

    O motor Unreal so aceita potencia de dois, e o `texconv` recusa o resto.
    Sem tamanho dado, cada imagem vai para a potencia de dois mais perto para
    baixo -- encolher nao inventa detalhe, aumentar inventaria.
    """
    from PIL import Image as _Image

    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for i, imagem in enumerate(imagens):
        if tamanho is None:
            largura = _potencia_de_dois(imagem.size[0])
            altura = _potencia_de_dois(imagem.size[1])
        else:
            largura, altura = tamanho
        if imagem.size != (largura, altura):
            imagem = imagem.resize((largura, altura), _Image.LANCZOS)
        arquivo = pasta / ("%s%02d.png" % (prefixo, i))
        imagem.save(arquivo)
        escritos.append(arquivo)
    return escritos


def pasta_de_texturas(caminho_no_cliente):
    """
    Onde o pacote de quadros precisa morar para o cliente carregar.

    O cliente procura `.utx` em `SysTextures`. Quando o alvo esta noutra pasta
    -- um `.u` do `system`, por exemplo -- o pacote novo vai para SysTextures
    assim mesmo, que e onde ele sera achado; so na falta dela e que fica ao
    lado do alvo.
    """
    alvo = Path(caminho_no_cliente)
    if alvo.parent.name.lower() == "systextures":
        return alvo.parent
    irma = alvo.parent.parent / "SysTextures"
    return irma if irma.is_dir() else alvo.parent


def animar_textura_do_cliente(T, caminho_no_cliente, textura, imagens,
                              trabalho, aolog=None, taxa=TAXA_PADRAO,
                              nome_pacote=None, tamanho=None, instalar=True):
    """
    Faz uma textura do cliente animar, pela corrente do motor.

    Os quadros viram um `.utx` novo, e a textura escolhida ganha um `AnimNext`
    apontando para o primeiro deles. Ela continua com o conteudo, o grupo e o
    endereco que tinha: quem a usa hoje continua a achando, e agora ela anda.

    O pacote alvo e reescrito, nao remontado -- e o unico jeito para pacote
    que o `ucc` nao devolve, como os de cenario. A escrita e conferida com o
    umodel antes de instalar: se ele nao le a corrente, nada e instalado.

    Devolve {"quadros", "alvo", "endereco", "instalados"}.
    """
    def diga(texto):
        if aolog:
            aolog(texto)

    alvo = Path(caminho_no_cliente)
    trabalho = Path(trabalho)
    imagens = list(imagens)
    if len(imagens) < 2:
        raise ErroDeAnimacao("preciso de pelo menos dois quadros para animar.")
    if len(imagens) > MAXIMO_DE_QUADROS:
        raise ErroDeAnimacao("%d quadros e demais; o maximo e %d."
                             % (len(imagens), MAXIMO_DE_QUADROS))

    quadros = gravar_quadros(imagens, trabalho / "quadros", tamanho=tamanho)
    largura, altura = tamanho_da_imagem(quadros[0])
    diga("%d quadros de %dx%d prontos." % (len(quadros), largura, altura))

    nome = nome_pacote or nome_de_pacote(textura)
    arquivo_quadros, arquivo_alvo, endereco = l2anim.animar_de_fora(
        T, alvo, textura, quadros, trabalho / "montagem",
        trabalho / "pronto", nome_pacote=nome, aolog=diga, taxa=taxa)
    diga("%s -> %s" % (textura, endereco))

    instalados = []
    if instalar:
        instalados.append(l2anim.instalar_pacote(
            arquivo_alvo, alvo.parent, aolog=diga,
            pasta_de_copias=PASTA_DE_COPIAS))
        instalados.append(l2anim.instalar_pacote(
            arquivo_quadros, pasta_de_texturas(alvo), aolog=diga,
            pasta_de_copias=PASTA_DE_COPIAS))
    return {"quadros": arquivo_quadros, "alvo": arquivo_alvo,
            "endereco": endereco, "instalados": instalados}


def instalar(T, pronto, caminho_no_cliente, aolog=None):
    """
    Põe o pacote de volta no cliente, guardando o original antes.

    A cópia leva data e hora no nome e nunca é sobrescrita: é o que permite
    voltar atrás depois da terceira tentativa, quando ninguém mais lembra
    qual era o arquivo bom.
    """
    import shutil
    from datetime import datetime

    alvo = Path(caminho_no_cliente)
    guarda = alvo.parent / "backup_animacao"
    guarda.mkdir(parents=True, exist_ok=True)
    copia = guarda / ("%s_%s" % (datetime.now().strftime("%Y%m%d_%H%M%S"),
                                 alvo.name))
    if alvo.is_file():
        shutil.copy2(alvo, copia)
        if aolog:
            aolog("Original guardado em %s" % copia)

    provisorio = alvo.with_suffix(alvo.suffix + ".novo")
    shutil.copy2(pronto, provisorio)
    provisorio.replace(alvo)
    if aolog:
        aolog("Instalado em %s" % alvo)
    return alvo
