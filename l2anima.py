#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trocar os quadros de uma animação que o cliente já toca.

## Como o Lineage 2 anima a interface

Não é com material. O `l2_skilltime.utx` de qualquer cliente mostra o
método, e ele é mais simples do que parece:

    cooltime000 .. cooltime359     360 quadros, 32x32, DXT3
    ToggleEffect001 .. ToggleEffect013   13 quadros
    CooltimeEnd1 .. CooltimeEnd9          9 quadros

São só texturas numeradas, sem `Shader` e sem `MaterialSequence` no pacote. O
movimento vem de fora: o código da interface sabe esses nomes e escolhe qual
desenhar a cada instante -- o `cooltime` segue a porcentagem que falta da
recarga, o `ToggleEffect` gira em laço enquanto a habilidade está ligada.

## O que isso permite, e o que não permite

PERMITE trocar o desenho de uma animação que existe: os nomes continuam os
mesmos, a contagem continua a mesma, e o cliente segue tocando -- só que com
a sua arte. É o que este módulo faz.

NÃO PERMITE inventar uma animação nova na interface. Um nome que o código do
cliente não conhece não é desenhado por ninguém: ficaria uma textura parada
dentro do pacote. Animação nova exige mexer na interface, que é outro
assunto.

## Por que respeitar tamanho e formato de cada quadro

Cada quadro é reescrito NO LUGAR, com o mesmo tamanho e o mesmo formato do
que estava lá -- 32x32 DXT3 no caso do skilltime. Mudar isso obrigaria a
mexer nas tabelas do pacote e no que a interface espera encontrar. Como o
tamanho é o mesmo, a troca é cirúrgica: o resto do pacote não se move.
"""

import re
from pathlib import Path

import l2mapa
import l2textura
import motor

# Uma família precisa de pelo menos isto para ser considerada animação. Duas
# texturas com número no fim são coincidência; três já são uma sequência.
MINIMO_DE_QUADROS = 3

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
