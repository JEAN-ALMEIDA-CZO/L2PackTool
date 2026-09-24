#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descobrir de que cronica e um cliente, sem perguntar a ninguem.

Escolher a cronica errada nao da erro claro: da "nao consegui medir
weapongrp.ddf" num caso, e -- pior -- campo deslocado noutro. E e facil de
errar, porque a caixa comeca em alguma coisa e quem acabou de baixar um
cliente nem sempre sabe de que geracao ele e.

## Como se descobre

Pela prova de ida e volta, a mesma que o resto do programa usa: desmontar a
tabela e monta-la de novo, comparando com o binario original. A definicao que
reproduz o arquivo descreve o arquivo -- nao ha meio termo, e nao ha o que
interpretar.

Uma tabela so nao basta. Varias atravessam cronicas sem mudar: o `npcname-e`
e o mesmo de C3 a High Five, e uma definicao dessas passaria em sete. O que
identifica e a ASSINATURA -- quais passam e quais nao, no conjunto. Por isso
se medem tres tabelas das que mais mudam, e ganha quem passar em mais delas.

## As cronicas de texto

Ate o C2 as tabelas sao texto (`weapongrp.txt`), e ai nao ha definicao para
provar. A deteccao troca de criterio: se ha `.txt` e nao ha `.dat`, e uma
delas, e o que separa C1 de C2 sao tabelas que so existem na segunda --
`recipe-c`, `eula-e`, `hennagrp`. Nao e prova byte a byte, e por isso a
resposta vem com a confianca mais baixa.

## Custo

Cada tentativa e uma descriptografia e uma passada do l2disasm num arquivo de
poucos megabytes. A cronica ja escolhida e testada primeiro: quando ela esta
certa -- o caso comum -- a conta acaba na primeira tentativa.
"""

from pathlib import Path

import l2item
import l2npc
import motor

# As tabelas que mais mudam de uma cronica para outra, e por isso as que
# melhor separam. A ordem importa: a primeira decide sozinha na maioria dos
# casos, e as outras entram para desempatar.
#
# O `transformdata` entrou por necessidade, e nao por zelo: Gracia Part 1 e
# Part 2 tem definicao IDENTICA nas tres primeiras, e sem uma quarta um
# cliente de Part 2 sairia como Part 1 com confianca "certa". A definicao do
# Part 2 acrescenta um campo, e ai as duas se separam -- medido nos dois
# clientes, nas duas direcoes. Cliente que nao tem a tabela nao e penalizado:
# ver `detectar`.
TABELAS_DE_PROVA = ("weapongrp", "itemname-e", "npcgrp", "transformdata")

# Tabelas que so existem de C2 em diante. Serve para separar as duas cronicas
# de texto, que o mesmo leitor abre sem reclamar.
SO_NO_C2 = ("recipe-c", "eula-e", "hennagrp", "creditgrp", "servername-e")


class ErroDeDeteccao(Exception):
    pass


def formato_do_cliente(system):
    """"binario", "texto" ou None, olhando o que existe na pasta."""
    system = Path(system)
    if not system.is_dir():
        return None
    nomes = {p.name.lower() for p in system.iterdir() if p.is_file()}
    tem_dat = any(n.endswith(".dat") and "grp" in n for n in nomes)
    tem_txt = any(n.endswith(".txt") and "grp" in n for n in nomes)
    if tem_dat:
        return "binario"
    if tem_txt:
        return "texto"
    return None


def _cronica_de_texto(system):
    """C1 ou C2, pelas tabelas que so a segunda tem."""
    nomes = {p.stem.lower() for p in Path(system).glob("*.txt")}
    achadas = [n for n in SO_NO_C2 if n in nomes]
    if achadas:
        return "c2", "tem %s, que o C1 nao tem" % ", ".join(achadas[:3])
    return "c1", "nao tem nenhuma das tabelas que sao do C2 em diante"


def _provar(T, system, trabalho, cronica, tabela):
    """A definicao daquela cronica reproduz aquela tabela deste cliente?"""
    base = motor.definicoes(cronica) / (tabela + ".ddf")
    origem = Path(system) / (tabela + ".dat")
    if not base.is_file() or not origem.is_file():
        return None
    try:
        puro = l2item._decifrar(T, origem, trabalho)
        definicao = l2item.completar(T, base, puro, trabalho)
        lida = l2npc.Tabela(origem, definicao, T, trabalho)
        deu, _motivo = lida.conferir_ciclo()
        return bool(deu)
    except Exception:                               # noqa: BLE001
        return False


def candidatas(preferida=None):
    """As cronicas instaladas, com a preferida na frente."""
    todas = [c for c in l2item.cronicas()
             if motor.formato_da_cronica(c) != "texto"]
    if preferida in todas:
        todas.remove(preferida)
        todas.insert(0, preferida)
    return todas


def detectar(T, system, trabalho, preferida=None, aoprogresso=None):
    """
    De que cronica e este cliente?

    Devolve {"cronica", "confianca", "detalhe", "placar"}. A confianca e
    "certa" quando a cronica passou em todas as tabelas medidas e nenhuma
    outra passou em tantas; "provavel" quando ganhou mas houve empate ou
    falta; "nenhuma" quando ninguem passou.
    """
    system = Path(system)
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)

    formato = formato_do_cliente(system)
    if formato is None:
        raise ErroDeDeteccao("não achei tabela nenhuma em %s" % system)

    if formato == "texto":
        chave, porque = _cronica_de_texto(system)
        return {"cronica": chave, "confianca": "provavel",
                "detalhe": "as tabelas são texto, e não .dat: %s" % porque,
                "placar": {}}

    placar, medidas = {}, {}
    lista = candidatas(preferida)
    for i, cronica in enumerate(lista):
        acertos, existentes = 0, 0
        for tabela in TABELAS_DE_PROVA:
            if aoprogresso:
                aoprogresso(i, len(lista),
                            "%s / %s" % (l2item.rotulo_da_cronica(cronica),
                                         tabela))
            resultado = _provar(T, system, trabalho, cronica, tabela)
            if resultado is None:
                continue        # tabela que este cliente nao tem: nao conta
            existentes += 1
            if resultado:
                acertos += 1
        placar[cronica] = acertos
        medidas[cronica] = existentes
        # Passou em TODAS as que existem: nao ha o que procurar depois disso.
        # E o caminho comum quando a cronica ja escolhida esta certa.
        if existentes and acertos == existentes:
            return {"cronica": cronica, "confianca": "certa",
                    "detalhe": "passou nas %d tabelas medidas" % existentes,
                    "placar": placar}

    quantas = max(medidas.values() or [len(TABELAS_DE_PROVA)])

    melhor = max(placar, key=lambda c: placar[c]) if placar else None
    if not melhor or not placar[melhor]:
        return {"cronica": None, "confianca": "nenhuma",
                "detalhe": ("nenhuma definição instalada reproduz este "
                            "cliente; ele pode ser de uma crônica que o "
                            "programa ainda não conhece"),
                "placar": placar}

    empatadas = [c for c, n in placar.items() if n == placar[melhor]]
    if len(empatadas) > 1:
        return {"cronica": melhor, "confianca": "provavel",
                "detalhe": ("empate entre %s -- as tabelas medidas não "
                            "separam essas crônicas"
                            % ", ".join(l2item.rotulo_da_cronica(c)
                                        for c in empatadas)),
                "placar": placar}
    return {"cronica": melhor, "confianca": "provavel",
            "detalhe": "passou em %d das %d tabelas medidas"
                       % (placar[melhor], quantas),
            "placar": placar}


def confere(T, system, trabalho, cronica):
    """
    A cronica escolhida serve para este cliente?

    Uma tabela basta para dizer que NAO serve, que e o que interessa antes de
    abrir: se a definicao nao reproduz o weapongrp, ela nao descreve este
    cliente, e o resto seria campo deslocado.
    """
    if motor.formato_da_cronica(cronica) == "texto":
        return formato_do_cliente(system) == "texto"
    for tabela in TABELAS_DE_PROVA:
        resultado = _provar(T, system, trabalho, cronica, tabela)
        if resultado is None:
            continue                    # tabela ausente nao acusa nada
        return resultado
    return True
