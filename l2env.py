#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O `env.int`: a partir de que +N o brilho de encantamento aparece.

Isto e OUTRA coisa do glow da arma. O glow do `weapongrp.dat` e da arma: uma
Dragon Slayer com `c_u000` brilha sempre, em +0. O brilho de ENCANTAMENTO e o
halo que a arma ganha ao ser refinada -- o azul do +4, o dourado do +7 -- e ele
mora aqui, no `env.int`.

    EnchantMeshShow=4        do +4 em diante a arma ganha cor
    EnchantEffectShow=7      do +7 em diante aparece a chama
    Enchant0..Enchant20      a cor de cada nivel
    [Variation] Enchant0..   o mesmo, para augmentation

## As duas cores de cada nivel

`R1,G1,B1` e `R2,G2,B2`. O que o jogo faz com elas -- alterna, mistura, usa uma
para o nucleo e outra para a borda -- **este modulo nao afirma**, porque nao da
para provar daqui.

O que se sabe, e como:

- Nos 21 niveis de fabrica a cor 2 e **sempre a mesma cor da 1, um pouco mais
  escura**: (40,87,126) e (30,70,110) no +7, (220,0,0) e (195,0,0) no +20. Vale
  para os 21, sem excecao.
- O `env.int` aponta para o material
  `LineageEffectsTextures.Etc.Enchant_Aura001_Shader01`, e a cadeia dele passa
  por um `FadeColor` -- a classe do Unreal que vai e volta entre duas cores.
  **Mas as cores gravadas nesse FadeColor sao outras**: (7,20,69)/(5,15,48),
  (24,41,46)/(34,45,47), (90,122,128)/(80,109,115). Nenhuma e a cor de nivel
  nenhum. Entao o material tem a pulsacao dele, com cores proprias, e as duas
  do arquivo entram por outro caminho.
- `EnchantEffectShow`, `EnchantMeshShow` e as linhas `Enchant*` nao estao na
  tabela de nomes de nenhum `.u` do cliente: quem as le e o codigo nativo do
  executavel, e nao UnrealScript. Nao ha o que ler.

Quem quiser saber, poe duas cores bem diferentes num nivel que o cliente
certamente le e olha em jogo. E a unica resposta que vale.

## Isto e GLOBAL

Nao ha um `env.int` por arma. Mudar `EnchantEffectShow` de 7 para 4 faz TODA
arma do servidor brilhar a partir do +4 -- a do jogador e a do mob. E um ajuste
de regra do cliente, e nao de item, e por isso ele vive numa caixa separada,
com aviso e com copia de seguranca.

## O formato

`Lineage2Ver111` -- Blowfish, o mesmo dos pacotes. Decifra com `l2encdec -d`,
volta com `-e 111`. O texto e UTF-16 com BOM, e as quebras sao CRLF: reescrever
com outra codificacao daria um arquivo que o cliente le como lixo.

A gravacao confere a volta: o arquivo cifrado e decifrado de novo e comparado
com o que se queria gravar. Nao batendo, nada e instalado -- um `env.int`
quebrado deixa o cliente sem iluminacao nenhuma.
"""

import re
import shutil
from pathlib import Path

import l2npc
import l2upscale as motor

ARQUIVO = "env.int"
PASTA_GUARDA = "backup_env"

# Os dois numeros que respondem "a partir de que +N".
MOSTRAR = (
    ("EnchantMeshShow", "a arma ganha cor a partir do +"),
    ("EnchantEffectShow", "a chama aparece a partir do +"),
)

# Os campos de cada linha de cor, na ordem em que o arquivo os escreve.
CORES = ("R1", "G1", "B1", "R2", "G2", "B2", "Opacity", "Num")

# O cliente de fabrica traz 21 niveis, `Enchant0` a `Enchant20`. Servidor com
# encantamento alto precisa de mais, e a serie e regular: o programa aceita ate
# `Enchant60`.
NIVEIS_DE_FABRICA = 21
NIVEIS = 61                     # Enchant0 .. Enchant60

# A linha `Enchant=` sem numero, logo abaixo da serie. E o que vale acima do
# ultimo nivel numerado -- sem ela, um +40 num cliente com 21 niveis ficaria
# sem cor nenhuma.
ACIMA = "acima"

# A secao onde tudo isto vive. Ler ou escrever fora dela e escrever no vazio: o
# `[Variation]` repete os mesmos nomes de chave para augmentation, e o que cair
# antes do primeiro cabecalho nao pertence a secao nenhuma.
SECAO = "[enchanteffect]"

_CHAVE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_CAMPO = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,()]+)")


class ErroDeEnv(Exception):
    pass


# ---------------------------------------------------------------------------
# Ler e escrever o arquivo
# ---------------------------------------------------------------------------
def _decifrar(T, origem, trabalho):
    """
    Devolve (texto, versao). `versao` e None quando o arquivo ja era texto.

    O cliente escolhe como decifrar pelo cabecalho, e nao pela extensao. Quem
    grava de volta tem de usar a MESMA versao: um arquivo que saiu como 111 e
    voltou como 121 e outro arquivo para o resto do jogo.
    """
    origem = Path(origem)
    if not origem.is_file():
        raise ErroDeEnv("nao achei o %s em %s" % (ARQUIVO, origem.parent))

    versao = l2npc.metodo_do_arquivo(origem)
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)

    if versao is None:
        texto, codificacao = _texto_de(origem.read_bytes())
        return texto, None, codificacao

    copia = trabalho / origem.name
    shutil.copy2(origem, copia)
    puro = trabalho / "env.txt"
    puro.unlink(missing_ok=True)
    motor.executar([T["l2encdec"], "-d", str(copia), str(puro)], limite=60)
    if not puro.is_file():
        raise ErroDeEnv("o l2encdec nao decifrou o %s." % ARQUIVO)
    texto, codificacao = _texto_de(puro.read_bytes())
    return texto, str(versao), codificacao


def _texto_de(dados):
    """
    (texto, codificacao) do arquivo -- e a codificacao importa tanto quanto.

    Ha cliente que guarda o `env.int` em UTF-16 com BOM e ha cliente que o
    guarda em texto simples. Neste ele sai do l2encdec em texto simples: 5.906
    bytes para 5.906 caracteres. Gravar de volta em UTF-16 dobraria o arquivo e
    o cliente o leria como lixo -- por isso a codificacao lida volta junto, e e
    ela que a gravacao usa.
    """
    if dados[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return dados.decode("utf-16"), "utf-16"
    try:
        return dados.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return dados.decode("latin-1"), "latin-1"


def ler(T, system, trabalho):
    """
    O que o `env.int` diz do encantamento.

    Devolve {"mostrar": {chave: numero}, "cores": {nivel: {campo: valor}},
    "texto": ..., "versao": ...}. O texto inteiro vai junto porque a gravacao
    troca linha por linha: reescrever o arquivo a partir do que foi lido
    perderia tudo o que este modulo nao entende -- e ele entende uma fracao.
    """
    texto, versao, codificacao = _decifrar(T, Path(system) / ARQUIVO,
                                           trabalho)

    mostrar = {}
    cores = {}
    acima = {}
    # So o que estiver DENTRO de `[EnchantEffect]`. Ler solto daria por bom o
    # que estivesse fora de secao nenhuma, e a tela mostraria como certo um
    # arquivo que o jogo ignora.
    na_secao = False
    for linha in texto.split("\n"):
        limpa = linha.strip()
        if limpa.startswith("["):
            na_secao = limpa.lower().startswith(SECAO)
            continue
        if not na_secao:
            continue
        achado = _CHAVE.match(linha)
        if not achado:
            continue
        chave, valor = achado.group(2), achado.group(3).strip()
        if chave in dict(MOSTRAR):
            mostrar[chave] = valor
            continue
        if chave.startswith("Enchant") and valor.startswith("("):
            resto = chave[len("Enchant"):]
            if resto.isdigit():
                cores[int(resto)] = dict(_CAMPO.findall(valor))
            elif resto == "":
                # `Enchant=` sem numero: o que vale acima do ultimo numerado.
                acima = dict(_CAMPO.findall(valor))

    return {"mostrar": mostrar, "cores": cores, "texto": texto,
            "versao": versao, "codificacao": codificacao,
            ACIMA: acima}


def aplicar(env, mostrar=None, cores=None, acima=None):
    """
    Devolve o texto com as linhas trocadas, e as que faltam acrescentadas.

    Troca LINHA POR LINHA, e nao reescreve o arquivo: o `env.int` tem cerca de
    duzentas chaves -- neblina, sombra, agua, shaders -- e este modulo entende
    duas dezenas. Remontar o arquivo a partir do que ele entende apagaria o
    resto.

    Nivel que ainda nao existe no arquivo -- `Enchant21` em diante, num cliente
    de fabrica -- e INSERIDO, logo antes da linha `Enchant=` sem numero, que e
    onde a serie acaba. So na secao `[EnchantEffect]`: o `[Variation]` repete os
    mesmos nomes de chave e nao e assunto desta tela.
    """
    mostrar = mostrar or {}
    cores = cores or {}
    validos = dict(MOSTRAR)

    for chave, valor in mostrar.items():
        if chave not in validos:
            raise ErroDeEnv("nao conheco a chave %r." % chave)
        if not str(valor).strip().isdigit():
            raise ErroDeEnv("%s tem de ser um numero inteiro." % chave)

    # Os niveis que o TEXTO ja tem, anotados enquanto se caminha. Comparar com
    # `env["cores"]` nao serviria: a tela mexe naquele dicionario direto, entao
    # o nivel recem-acrescentado ja estaria la e nunca seria escrito.
    vistos = set()

    def faltando():
        return sorted(n for n in cores if n not in vistos)

    saida = []
    na_secao = False
    for linha in env["texto"].split("\n"):
        fim = "\r" if linha.endswith("\r") else ""
        corpo = linha[:-1] if fim else linha
        limpa = corpo.strip()

        if limpa.startswith("["):
            # SAIR do `[EnchantEffect]` e o gatilho para escrever os niveis
            # novos -- e nao "achar um cabecalho". O primeiro cabecalho do
            # arquivo e o `[EnvSetup]`, e os niveis iam parar la, fora de toda
            # secao, onde o jogo nunca os le.
            if na_secao:
                saida.extend(_novas_linhas(faltando(), cores, fim))
                vistos.update(cores)
            na_secao = limpa.lower().startswith(SECAO)
            saida.append(linha)
            continue
        if not na_secao:
            saida.append(linha)
            continue

        achado = _CHAVE.match(corpo)
        if not achado:
            saida.append(linha)
            continue

        espaco, chave = achado.group(1), achado.group(2)
        if chave in mostrar:
            saida.append("%s%s=%s%s" % (espaco, chave, mostrar[chave], fim))
            continue

        if chave.startswith("Enchant") and achado.group(3).strip().startswith("("):
            resto = chave[len("Enchant"):]
            if resto.isdigit():
                vistos.add(int(resto))
                if int(resto) in cores:
                    saida.append("%s%s=%s%s"
                                 % (espaco, chave,
                                    _linha_de_cor(cores[int(resto)]), fim))
                    continue
            if resto == "":
                # A linha sem numero: os niveis novos entram ANTES dela, para a
                # serie continuar em ordem e o catch-all seguir sendo o ultimo.
                saida.extend(_novas_linhas(faltando(), cores, fim))
                vistos.update(cores)
                if acima:
                    saida.append("%s%s=%s%s" % (espaco, chave,
                                                _linha_de_cor(acima), fim))
                    continue

        saida.append(linha)

    if na_secao:                # a secao ia ate o fim do arquivo
        saida.extend(_novas_linhas(faltando(), cores, ""))

    return "\n".join(saida)


def linhas_fora_da_secao(env):
    """
    Linhas `Enchant*` que estao FORA do `[EnchantEffect]` -- e nao deviam.

    Uma versao anterior deste programa escrevia os niveis novos antes do
    primeiro cabecalho do arquivo. Elas nao fazem o jogo funcionar nem quebrar,
    mas confundem quem abrir o arquivo, e a tela avisa para serem tiradas.

    Devolve a lista dos numeros de linha (a partir de 1).
    """
    fora = []
    # `None` ate o primeiro cabecalho: linha antes de qualquer secao nao
    # pertence a nenhuma, e e justamente onde o defeito as punha.
    secao = None
    for numero, linha in enumerate(env["texto"].split("\n"), 1):
        limpa = linha.strip()
        if limpa.startswith("["):
            secao = limpa.lower()
            continue
        # O `[Variation]` tem `Enchant*` proprios, e eles estao no lugar deles.
        if secao is not None and (secao.startswith(SECAO)
                                  or secao.startswith("[variation")):
            continue
        achado = _CHAVE.match(linha.rstrip("\r"))
        if achado and achado.group(2).startswith("Enchant"):
            fora.append(numero)
    return fora


def limpar_fora_da_secao(env):
    """Tira do texto as linhas `Enchant*` que estao fora da secao."""
    fora = set(linhas_fora_da_secao(env))
    if not fora:
        return env["texto"]
    return "\n".join(linha for numero, linha
                      in enumerate(env["texto"].split("\n"), 1)
                      if numero not in fora)


def _novas_linhas(niveis, cores, fim):
    """As linhas dos niveis que ainda nao existiam, em ordem."""
    return ["Enchant%d=%s%s" % (n, _linha_de_cor(cores[n]), fim)
            for n in niveis]


def _linha_de_cor(campos):
    """`(R1=30,G1=30,...)` na ordem e na grafia que o arquivo usa."""
    partes = []
    for nome in CORES:
        if nome in campos and str(campos[nome]).strip() != "":
            partes.append("%s=%s" % (nome, str(campos[nome]).strip()))
    return "(%s)" % ",".join(partes)


def gravar(T, env, texto, destino, nome=ARQUIVO):
    """
    Grava o `env.int` novo em `destino`. Devolve (caminho, a volta bateu).

    A volta e conferida sempre: o arquivo cifrado e decifrado de novo e
    comparado com o que se queria gravar. Nao batendo, quem chama nao deve
    instalar -- um `env.int` quebrado deixa o cliente sem iluminacao nenhuma, e
    o sintoma nao parece com a causa.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    # A MESMA codificacao que veio. Neste cliente o arquivo decifrado e
    # texto simples; grava-lo em UTF-16 dobraria o tamanho, e o sintoma --
    # "o jogo ficou sem iluminacao" -- nao pareceria com a causa.
    codificacao = env.get("codificacao") or "utf-8"
    if codificacao == "utf-16":
        dados = ("﻿" + texto.lstrip("﻿")).encode("utf-16")
    else:
        dados = texto.lstrip("﻿").encode(codificacao)

    if env["versao"] is None:
        alvo = destino / nome
        alvo.write_bytes(dados)
        return alvo, True

    puro = destino / "_env_plano.bin"
    puro.write_bytes(dados)
    alvo, bateu = motor.criptografar(T, puro, nome, destino,
                                     cifrar=True, versao=env["versao"])
    puro.unlink(missing_ok=True)
    return alvo, bateu


# ---------------------------------------------------------------------------
# Instalar e restaurar
# ---------------------------------------------------------------------------
def instalar(arquivo, system, aolog=None):
    """Copia o env.int gerado para o cliente, guardando o original antes."""
    system = Path(system)
    guarda = system / PASTA_GUARDA
    guarda.mkdir(exist_ok=True)

    original = system / ARQUIVO
    copia = guarda / ARQUIVO
    if original.is_file() and not copia.is_file():
        shutil.copy2(original, copia)
        if aolog:
            aolog("original guardado em %s" % copia)

    shutil.copy2(arquivo, original)
    if aolog:
        aolog("instalado %s" % original)
    return original


def restaurar(system, aolog=None):
    """Devolve o env.int guardado. Devolve o caminho, ou None."""
    system = Path(system)
    copia = system / PASTA_GUARDA / ARQUIVO
    if not copia.is_file():
        return None
    alvo = system / ARQUIVO
    shutil.copy2(copia, alvo)
    if aolog:
        aolog("restaurado %s" % alvo)
    return alvo


def tem_guardado(system):
    return (Path(system) / PASTA_GUARDA / ARQUIVO).is_file()
