#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converter as tabelas de um cliente para as chaves com que o programa grava.

## Por que isto existe

O l2encdec ABRE os arquivos 41x com dois pares de chave: o par proprio dele,
que a comunidade usa ha vinte anos, e o par com que a NCSoft distribuiu os
clientes. Fechar, ele so fecha com o par proprio.

Dai o impasse num cliente recem-baixado: o programa le tudo, e nao consegue
gravar nada -- porque o que ele gravasse sairia com a chave do l2encdec, e o
resto do cliente estaria na outra.

A saida e deixar o cliente inteiro numa chave so, que e o que este modulo
faz: para cada tabela, abrir com a chave que servir e fechar com a do
l2encdec. O conteudo nao muda -- foi medido, byte a byte -- so o envelope.

Depois disso o cliente e igual a qualquer cliente de servidor privado, que e
o caso em que este programa sempre trabalhou.

## O que este modulo NAO faz

Nao mexe no executavel do jogo. Trocar as chaves DENTRO do l2.exe e outra
conversa, com outro risco, e quem faz isso sao as ferramentas da comunidade
-- o patcher e os loaders que acompanham o l2encdec. Aqui so se mexe em
arquivo de dado.

## Cada arquivo e tratado inteiro, ou nao e tratado

Para cada um: abre; fecha com a chave nova num temporario; abre o temporario
de novo; compara com o que saiu da primeira leitura. So se bater byte a byte
o original e substituido -- e o original ja foi para a pasta de copias antes
de qualquer escrita.

Assim, parar no meio deixa metade convertida e metade intacta, e nao um
arquivo pela metade. As duas metades continuam legiveis pelo programa, que
tenta as duas chaves de qualquer jeito.
"""

import shutil
from datetime import datetime
from pathlib import Path

import l2npc
import motor

# O que este modulo sabe converter. Os pacotes (.utx, .u, .usx) ficam de fora:
# eles usam Blowfish ou o XOR do Ver121, que nao tem par de chaves e nao
# precisam de conversao nenhuma.
EXTENSOES = (".dat", ".ini", ".htm")

PASTA_DE_COPIAS = "backup_chaves"


class ErroDeChave(Exception):
    pass


def protegidos(system):
    """Os arquivos do system que este modulo sabe converter."""
    system = Path(system)
    if not system.is_dir():
        return []
    return sorted(p for p in system.iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSOES)


def conferir(T, system, trabalho, quantos=6):
    """
    Este cliente esta na chave em que o programa grava?

    Devolve (precisa_converter, examinados, os que estao na chave antiga).
    Nao abre o cliente inteiro: uma amostra basta, porque a chave e a mesma
    em todos os arquivos de um cliente.
    """
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    antigos, vistos = [], 0
    for arquivo in protegidos(system):
        if not l2npc.metodo_do_arquivo(arquivo):
            continue                    # ja esta aberto: nada a fazer
        destino = trabalho / (arquivo.stem + ".conf.dec")
        try:
            _aberto, chave = motor.abrir_dat(T, arquivo, destino, limite=300)
        except OSError:
            continue                    # nao abriu com nenhuma das duas
        vistos += 1
        if chave == "-l":
            antigos.append(arquivo.name)
        if vistos >= quantos:
            break
    return bool(antigos), vistos, antigos


def _converter_um(T, arquivo, trabalho, guarda):
    """
    Converte um arquivo, com copia e prova.

    Devolve "convertido", "ja estava" ou "sem cabecalho"; levanta
    ErroDeChave quando algo nao fecha -- e ai nada foi escrito.
    """
    metodo = l2npc.metodo_do_arquivo(arquivo)
    if not metodo:
        return "sem cabecalho"

    antes = trabalho / (arquivo.stem + ".antes.dec")
    _aberto, chave = motor.abrir_dat(T, arquivo, antes, limite=600)
    if chave != "-l":
        return "ja estava"

    # A copia vai ANTES de escrever: se faltar energia no meio, o que importa
    # e o original estar guardado.
    guarda.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, guarda / arquivo.name)

    fechado = trabalho / (arquivo.stem + ".novo.dat")
    fechado.unlink(missing_ok=True)
    _codigo, saida = motor.executar([T["l2encdec"], "-h", metodo, antes,
                                     fechado], limite=600)
    if not fechado.exists() or not fechado.stat().st_size:
        raise ErroDeChave("não consegui fechar %s: %s"
                          % (arquivo.name, (saida or "").strip()[-140:]))

    depois = trabalho / (arquivo.stem + ".depois.dec")
    depois.unlink(missing_ok=True)
    try:
        _aberto2, chave2 = motor.abrir_dat(T, fechado, depois, limite=600)
    except OSError as erro:
        raise ErroDeChave("%s: o convertido não abriu (%s)"
                          % (arquivo.name, erro))
    if chave2 != "-d":
        raise ErroDeChave("%s: o convertido continua pedindo a chave antiga"
                          % arquivo.name)
    if depois.read_bytes() != antes.read_bytes():
        raise ErroDeChave("%s: o conteúdo mudou na conversão — nada foi "
                          "gravado" % arquivo.name)

    shutil.move(str(fechado), str(arquivo))
    return "convertido"


def converter(T, system, trabalho, aolog=None, aoprogresso=None, parar=None):
    """
    Converte o system inteiro. Devolve o resumo do que aconteceu.

    `parar` e consultado ENTRE arquivos: parar no meio de um nao existe,
    porque o original so e trocado depois da prova.
    """
    system = Path(system)
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)

    def diga(texto):
        if aolog:
            aolog(texto)

    alvos = [a for a in protegidos(system) if l2npc.metodo_do_arquivo(a)]
    if not alvos:
        raise ErroDeChave("não achei arquivo protegido em %s" % system)

    guarda = system / PASTA_DE_COPIAS / datetime.now().strftime("%Y%m%d_%H%M%S")
    diga("Cópias em %s" % guarda)

    contas = {"convertidos": 0, "ja_estavam": 0, "falhas": [],
              "guarda": guarda, "total": len(alvos)}
    for i, arquivo in enumerate(alvos, 1):
        if parar and parar():
            diga("Interrompido. O que já foi convertido continua valendo; o "
                 "resto ficou como estava.")
            break
        if aoprogresso:
            aoprogresso(i, len(alvos), arquivo.name)
        try:
            saiu = _converter_um(T, arquivo, trabalho, guarda)
        except ErroDeChave as erro:
            contas["falhas"].append(str(erro))
            diga("  %s" % erro)
            continue
        if saiu == "convertido":
            contas["convertidos"] += 1
            diga("  %s convertido" % arquivo.name)
        elif saiu == "ja estava":
            contas["ja_estavam"] += 1
    return contas


def desfazer(system, guarda, aolog=None):
    """Devolve os originais de uma pasta de cópias para o system."""
    guarda = Path(guarda)
    if not guarda.is_dir():
        raise ErroDeChave("não achei a pasta de cópias %s" % guarda)
    voltaram = 0
    for arquivo in sorted(guarda.iterdir()):
        if not arquivo.is_file():
            continue
        shutil.copy2(arquivo, Path(system) / arquivo.name)
        voltaram += 1
        if aolog:
            aolog("  %s devolvido" % arquivo.name)
    return voltaram


def garantir_para_gravar(T, system, trabalho, aolog=None):
    """
    Deixa o cliente pronto para receber gravacao, convertendo se precisar.

    Devolve (fez_alguma_coisa, resumo). Chamada antes de instalar: e o ponto
    em que o programa deixa de escrever numa chave e ler noutra.

    Nao pergunta. Quem mandou gravar ja disse o que queria, e a conversao e
    reversivel -- cada original vai para `backup_chaves` antes, e cada arquivo
    so e trocado depois de a volta bater byte a byte.
    """
    system = Path(system)
    trabalho = Path(trabalho)

    def diga(texto):
        if aolog:
            aolog(texto)

    try:
        precisa, vistos, _antigos = conferir(T, system, trabalho)
    except Exception as erro:                       # noqa: BLE001
        diga("  não consegui conferir a chave do cliente: %s" % erro)
        return False, None
    if not vistos or not precisa:
        return False, None

    diga("Este cliente é oficial: as tabelas estão nas chaves da NCSoft, e o "
         "programa grava nas do l2encdec.")
    diga("Convertendo a pasta system antes de instalar -- os originais vão "
         "para backup_chaves.")
    resumo = converter(T, system, trabalho, aolog=diga)
    diga("Conversão: %d arquivos convertidos, %d já estavam, %d falharam."
         % (resumo["convertidos"], resumo["ja_estavam"],
            len(resumo["falhas"])))
    diga("Falta um passo que não é deste programa: o JOGO ainda não conhece a "
         "chave nova. Use o patcher ou o loader do l2encdec para iniciar o "
         "cliente -- sem isso o jogo não lê nem o que já estava lá.")
    return True, resumo


# Qual loader serve a qual geracao. Ate o Interlude um; do Chaotic Throne em
# diante o outro. Os dois acompanham o l2encdec.
LOADER_ANTIGO = "loader.exe"
LOADER_NOVO = "loaderCT1++.exe"
CRONICAS_ANTIGAS = ("c1", "c2", "c3", "c4", "c5", "interlude")


def loader_da_cronica(cronica):
    """O nome do loader daquela cronica."""
    return (LOADER_ANTIGO if (cronica or "").lower() in CRONICAS_ANTIGAS
            else LOADER_NOVO)


def onde_esta_o_loader(T, cronica=None):
    """O caminho do loader na pasta de ferramentas, ou None."""
    caminho = T.get("l2encdec")
    if not caminho:
        return None
    perto = Path(caminho).parent / loader_da_cronica(cronica)
    return perto if perto.is_file() and perto.stat().st_size else None


def por_o_loader(T, cliente, cronica=None, aolog=None):
    """
    Copia o loader para a pasta do cliente. Nao executa nada.

    Devolve o caminho onde ficou, ou levanta ErroDeChave dizendo o que falta.
    """
    de = onde_esta_o_loader(T, cronica)
    if de is None:
        raise ErroDeChave(
            "nao achei o %s na pasta de ferramentas. Ele acompanha o "
            "l2encdec." % loader_da_cronica(cronica))

    destino = Path(cliente) / de.name
    shutil.copy2(de, destino)
    if aolog:
        aolog("Loader em %s" % destino)
        aolog("Inicie o jogo por ele: e o que faz o cliente entender as "
              "tabelas convertidas.")
    return destino
