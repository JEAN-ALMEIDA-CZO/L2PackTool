#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O brilho da arma -- o "glow" -- e onde ele mora no weapongrp.

Uma arma com glow tem um efeito de particula preso a ela: o risco de luz que
acompanha a lamina, o halo do Infinity Bow, a aura das armas de boss. Quem
monta servidor privado poe isso em armas custom, e ate hoje so a mao, num
editor de tabela, contando colunas.

## Onde isso esta

No `weapongrp.dat`, em dois pares de colunas. A definicao embutida chama cinco
delas de `junk`, porque quem a escreveu nao sabia o que eram; o tutorial da
comunidade nomeia, e os dados deste cliente confirmam -- 282 das 1.346 armas
tem glow, em 48 combinacoes distintas desses cinco numeros, ou seja, eles sao
mesmo ajustados arma a arma:

    effA        LineageEffect.c_u006      o efeito
    junk1A[0]   longitudinal              ao longo da lamina, do cabo a ponta
    junk1A[1]   vertical                  sobe e desce
    junk1A[2]   lateral                   para os lados
    junk1A[3]   tamanho                   0,80 a 1,55 nas armas do jogo
    junk1A[4]   intensidade               0,20 a 1,00

O par B -- `effB` e `junk1B[*]` -- e um segundo efeito na mesma arma, com os
mesmos cinco ajustes.

## O que este modulo NAO faz

Nao desenha o glow. Particula do Unreal Engine 2 so o motor do jogo desenha:
nem o umodel abre, nem ha visualizador que o faca. A regua da tela mostra ONDE
o efeito vai ficar em relacao a lamina, medido da malha; como ele parece, so em
jogo.

Nao mexe no `env.int`. La ficam as cores do brilho de ENCANTAMENTO, que sao
globais: mudar uma muda todas as armas do servidor. E outro assunto, com outro
risco, e merece tela propria.
"""

from idioma import N_

# ---------------------------------------------------------------------------
# As colunas
# ---------------------------------------------------------------------------
# Os nomes a esquerda sao os da definicao embutida; os da direita, o que eles
# significam. Manter os dois lados aqui e o que permite trocar de definicao sem
# cacar numero de coluna pelo programa inteiro.
EFEITO = {"a": "effA", "b": "effB"}
AJUSTES = {"a": ["junk1A[%d]" % i for i in range(5)],
           "b": ["junk1B[%d]" % i for i in range(5)]}

# A coluna que o tutorial descreve como "1 sem mesh, -1 com mesh". Neste
# cliente ela so tem esses dois valores, o que bate -- mas a definicao a chama
# de `is_hero`, que diz outra coisa. Fica aqui nomeada pelo que a definicao diz,
# e a tela avisa que o efeito dela e para conferir em jogo.
MESH = "is_hero"

# Os cinco ajustes, na ordem em que aparecem na coluna, com o rotulo da tela e
# a faixa vista nas armas do proprio jogo. A faixa nao e limite: e referencia,
# para quem digita saber se esta perto ou longe do que o jogo usa.
CAMPOS = (
    ("longitudinal", N_("ao longo da lâmina"), -25.0, 30.0),
    ("vertical", N_("altura"), -12.0, 12.0),
    ("lateral", N_("lado"), -6.0, 6.0),
    ("tamanho", N_("tamanho"), 0.1, 3.0),
    ("intensidade", N_("intensidade"), 0.0, 2.0),
)

NOMES = [c[0] for c in CAMPOS]


class ErroDeGlow(Exception):
    pass


# ---------------------------------------------------------------------------
# Ler e escrever
# ---------------------------------------------------------------------------
def _tabela(itens):
    tabela = itens.tabelas.get("weapon")
    if tabela is None:
        raise ErroDeGlow("este cliente nao tem weapongrp aberto.")
    # A definicao pode nao ter estas colunas -- outra cronica, outro .ddf. Vale
    # descobrir aqui, com o nome da coluna que falta, e nao la dentro do
    # `definir`, que so diria que um `index` nao achou nada.
    faltando = [c for c in (list(EFEITO.values()) + AJUSTES["a"] + AJUSTES["b"])
                if c not in tabela.cabecalho]
    if faltando:
        raise ErroDeGlow("o weapongrp desta cronica nao tem as colunas de "
                         "glow: %s." % ", ".join(faltando))
    return tabela


def _linha(itens, ident):
    tabela = _tabela(itens)
    coluna = tabela.cabecalho.index("id")
    alvo = str(ident)
    for linha in tabela.linhas:
        if linha[coluna] == alvo:
            return tabela, linha
    raise ErroDeGlow("a arma %s nao esta no weapongrp." % ident)


def ler(itens, ident):
    """
    O glow daquela arma: os dois efeitos e os cinco ajustes de cada um.

    Devolve {"a": {...}, "b": {...}, "mesh": "..."}. Campo vazio volta vazio --
    nao invento zero onde o arquivo nao tem nada, porque zero e um valor e
    "nada" e outro.
    """
    tabela, linha = _linha(itens, ident)

    def um(lado):
        dados = {"efeito": tabela.campo(linha, EFEITO[lado]).strip()}
        for nome, coluna in zip(NOMES, AJUSTES[lado]):
            dados[nome] = tabela.campo(linha, coluna).strip()
        return dados

    return {"a": um("a"), "b": um("b"),
            "mesh": tabela.campo(linha, MESH).strip()}


def aplicar(itens, ident, glow):
    """
    Escreve o glow na linha da arma, na memoria.

    Quem grava e `Itens.gravar`, como na aba de Itens: a mesma prova de ciclo,
    o mesmo caminho de instalacao. Aqui so se mexe nas colunas do brilho.

    Um efeito vazio limpa o par inteiro -- efeito e ajustes. Deixar cinco
    numeros apontando para efeito nenhum e lixo que confunde quem for ler
    depois.
    """
    tabela, linha = _linha(itens, ident)

    for lado in ("a", "b"):
        dados = glow.get(lado) or {}
        efeito = str(dados.get("efeito", "")).strip()
        tabela.definir(linha, EFEITO[lado], efeito)
        for nome, coluna in zip(NOMES, AJUSTES[lado]):
            if not efeito:
                tabela.definir(linha, coluna, "")
                continue
            tabela.definir(linha, coluna, _numero(dados.get(nome), nome))

    if glow.get("mesh") not in (None, "") and MESH in tabela.cabecalho:
        tabela.definir(linha, MESH, str(glow["mesh"]).strip())

    # Sem isto, `Itens.gravar` nao escreve nada: ele so grava as tabelas que
    # alguem declarou ter mexido, e mexer na linha direto nao declara.
    itens.alteradas.add("weapon")
    return linha


def _numero(valor, nome):
    """
    O numero como a tabela o guarda: oito casas, como o resto do arquivo.

    O arquivo escreve `0.80000001` -- float de 32 bits escrito por extenso.
    Gravar `0.8` tambem funciona, mas deixa a linha visivelmente diferente das
    outras 1.345, e quem abrir o arquivo depois vai se perguntar por que.
    """
    texto = str(valor if valor not in (None, "") else 0).replace(",", ".")
    try:
        return "%.8f" % float(texto)
    except ValueError:
        raise ErroDeGlow("o valor de %s (%r) nao e um numero." % (nome, valor))


def descrever(glow):
    """Uma linha legivel do que esta posto, para o registro e a tela."""
    partes = []
    for lado in ("a", "b"):
        dados = glow.get(lado) or {}
        if not dados.get("efeito"):
            continue
        partes.append("%s [%s]" % (
            dados["efeito"],
            " ".join("%s=%s" % (n, dados.get(n) or "0") for n in NOMES)))
    return "; ".join(partes) or "sem glow"


# ---------------------------------------------------------------------------
# Sugestao de efeito
# ---------------------------------------------------------------------------
# O que cada familia de efeito e, em palavras. O prefixo e o comeco do nome do
# objeto, depois do ponto. Serve so para a lista se ler como frase em vez de
# como codigo -- quem decide o que aparece e a contagem do cliente.
FAMILIAS = (
    ("e_u092_", "hero glow"),
    ("c_u", "brilho comum do jogo"),
    ("SHEV_weapon_shadow", "shadow weapon"),
    ("w_vari_", "encantamento"),
)


def _familia(caminho):
    objeto = (caminho or "").split(".")[-1]
    for prefixo, rotulo in FAMILIAS:
        if objeto.startswith(prefixo):
            return rotulo
    return ""


def tipo_da_arma(itens, linha):
    """
    O tipo da arma como o servidor o escreve: SWORD, BIGSWORD, BOW...

    Duas colunas, e nao uma: `weapon_type` nao separa espada de espadao -- as
    duas valem 1 --, quem separa e `handness`. O mesmo vale para maca e
    marreta.
    """
    import l2item
    tabela = itens.tabelas["weapon"]
    bruto = l2item._inteiro(tabela.campo(linha, "weapon_type"), -1)
    tipo = l2item.ARMA_DO_CLIENTE.get(bruto, "")
    if l2item._inteiro(tabela.campo(linha, "handness"), 1) >= 2:
        tipo = l2item.ARMA_DE_DUAS_MAOS.get(tipo, tipo)
    return tipo


def _contar(itens):
    """
    {efeito: {tipo de arma: quantas}} e {(efeito, tipo): ajustes mais comuns}.

    Uma passada so pela tabela. E o levantamento inteiro: quem usa o que, em
    que arma, e com que numeros.
    """
    tabela = itens.tabelas["weapon"]
    if EFEITO["a"] not in tabela.cabecalho:
        return {}, {}
    coluna_fx = tabela.coluna(EFEITO["a"])
    quantas = {}
    numeros = {}
    for linha in tabela.linhas:
        caminho = linha[coluna_fx].strip()
        if not caminho:
            continue
        tipo = tipo_da_arma(itens, linha)
        quantas.setdefault(caminho, {})
        quantas[caminho][tipo] = quantas[caminho].get(tipo, 0) + 1
        chave = (caminho, tipo)
        valores = tuple(tabela.campo(linha, c).strip() for c in AJUSTES["a"])
        numeros.setdefault(chave, {})
        numeros[chave][valores] = numeros[chave].get(valores, 0) + 1
    return quantas, numeros


def sugerir(itens, tipo=None):
    """
    Os efeitos que o proprio jogo usa, na frente os deste tipo de arma.

    Cada sugestao e {caminho, familia, quantas, neste_tipo, ajustes}, onde
    `ajustes` sao os cinco numeros mais comuns naquele efeito para aquele tipo
    -- os do jogo, e nao um palpite de 0 e 1.

    Nao e lista de compatibilidade: e lista do que ESTE cliente ja desenha. Um
    efeito fora dela pode funcionar; um efeito dela funciona, porque o jogo o
    usa todo dia.
    """
    quantas, numeros = _contar(itens)
    saida = []
    for caminho, por_tipo in quantas.items():
        neste = por_tipo.get(tipo, 0) if tipo else 0
        ajustes = numeros.get((caminho, tipo)) or {}
        if not ajustes:
            # Sem exemplo neste tipo, pega o mais comum em qualquer arma: o
            # efeito ainda vale, o enquadramento e que pode nao ser o ideal.
            for (esse, _t), conta in numeros.items():
                if esse == caminho:
                    ajustes = conta
                    break
        melhores = (max(ajustes.items(), key=lambda p: p[1])[0]
                    if ajustes else ("", "", "", "", ""))
        saida.append({
            "caminho": caminho,
            "familia": _familia(caminho),
            "quantas": sum(por_tipo.values()),
            "neste_tipo": neste,
            "tipos": sorted(por_tipo, key=lambda k: -por_tipo[k]),
            "ajustes": dict(zip(NOMES, melhores)),
        })

    # Os deste tipo primeiro, e dentro de cada grupo os mais usados. Um efeito
    # que o jogo repete trinta vezes e mais seguro do que um que ele usa uma.
    saida.sort(key=lambda s: (-s["neste_tipo"], -s["quantas"],
                              s["caminho"].lower()))
    return saida


# ---------------------------------------------------------------------------
# A regua
# ---------------------------------------------------------------------------
def eixo_da_arma(medida):
    """
    Qual eixo da malha e o COMPRIMENTO da arma, e onde ele comeca e acaba.

    A arma deita: no Dragon Slayer o X vai de -17,83 (cabo) a 40,76 (ponta),
    enquanto Y e Z nao passam de 7. O eixo do comprimento e o de maior alcance
    -- e e nele que o ajuste longitudinal anda.

    Devolve (nome do eixo, minimo, maximo), ou None se a malha nao foi medida.
    """
    if not medida:
        return None
    melhor = None
    for eixo in ("x", "y", "z"):
        menor = medida.get(eixo + "_min")
        maior = medida.get(eixo + "_max")
        if menor is None or maior is None:
            continue
        alcance = maior - menor
        if melhor is None or alcance > melhor[3]:
            melhor = (eixo, menor, maior, alcance)
    if melhor is None:
        return None
    return melhor[0], melhor[1], melhor[2]
