#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fechar o cliente com a chave de quem é dono dele.

## O que este módulo faz, em uma frase

Troca a chave dos arquivos escolhidos do `system` pela chave derivada de uma
frase que só o dono sabe, e escreve essa chave dentro do executável do cliente
-- para que o jogo continue abrindo os arquivos e mais ninguém consiga
produzir arquivos que ele aceite.

## A ordem importa, e é esta

    1. copiar o original para `backup_protecao` (uma vez por arquivo);
    2. abrir com a chave atual -- a do cliente, ou a do l2encdec;
    3. fechar com a chave nova;
    4. ABRIR DE NOVO e comparar byte a byte com o passo 2;
    5. só então trocar o arquivo, e por último a chave do executável.

O passo 4 é o que separa esta função de uma que estraga cliente. Arquivo que
não volta igual não é instalado, e o `system` fica como estava.

O executável é o ÚLTIMO a mudar: enquanto ele tem a chave velha, um arquivo
novo já gravado só deixaria o jogo sem abrir aquele arquivo. Na ordem
contrária -- exe primeiro --, um erro no meio deixaria o cliente inteiro sem
abrir nada.

## Onde funciona, e onde não

Do C3 ao Interlude o módulo RSA mora como texto hexa dentro do `l2.exe` e do
`engine.dll`, e é trocável. Do Kamael em diante o executável vem empacotado: a
chave só existe em memória, entregue pelo loader, e trocá-la exigiria um
loader próprio -- que este programa não escreve. Nesses clientes a página
oferece o que dá: fechar com a chave do l2encdec, que já tira o cliente da
lista dos que se abrem com as chaves originais.

## O que isso protege

A ESCRITA. Sem a frase, ninguém gera um `itemname-e.dat` que o seu cliente
aceite.

A LEITURA não, e nenhum esquema do lado do cliente protege: para jogar, o
cliente precisa abrir, e por isso carrega a chave de leitura dentro de si.
Quem tem o seu cliente pode achá-la -- este mesmo programa acha em
milissegundos. O que a chave própria faz é tirar o seu servidor do "qualquer
um abre com um clique" e pôr no "quem souber procurar".
"""

import shutil
import time
from pathlib import Path

import l2cripto
import motor

PASTA_GUARDA = "backup_protecao"

# Os grupos que a tela oferece. Nome do arquivo em minusculas, porque o disco
# do Windows nao liga e o do usuario pode ter qualquer caixa.
GRUPOS = (
    ("itens", "Itens e armas",
     ("weapongrp.dat", "armorgrp.dat", "etcitemgrp.dat", "itemname-e.dat")),
    ("skills", "Habilidades",
     ("skillgrp.dat", "skillname-e.dat", "skillsoundgrp.dat")),
    ("npcs", "NPCs e monstros",
     ("npcgrp.dat", "npcname-e.dat", "mobskillanimgrp.dat")),
    ("mundo", "Mundo e textos",
     ("zonename-e.dat", "questname-e.dat", "systemmsg-e.dat",
      "sysstring-e.dat", "huntingzone-e.dat")),
)


class ErroDeProtecao(Exception):
    pass


def arquivos_do_grupo(system, chaves):
    """Os arquivos que existem, para os grupos escolhidos."""
    system = Path(system)
    quero = set()
    for chave, _rotulo, nomes in GRUPOS:
        if chave in chaves:
            quero.update(n.lower() for n in nomes)
    achados = []
    for arquivo in sorted(system.iterdir()):
        if arquivo.is_file() and arquivo.name.lower() in quero:
            achados.append(arquivo)
    return achados


def estado_do_cliente(system):
    """
    O que dá para fazer neste cliente. Devolve um dicionário para a tela.

    `trocavel` é o que decide tudo: sem ele, chave própria não é possível, e
    a tela precisa dizer isso antes de a pessoa escolher arquivos.
    """
    system = Path(system)
    onde = l2cripto.onde_trocar_a_chave(system) if system.is_dir() else []
    return {
        "system": system,
        "existe": system.is_dir(),
        "trocavel": bool(onde),
        "executaveis": [p for p, _o, _m in onde],
        "modulo_atual": onde[0][2] if onde else None,
    }


def marca_da_chave(modulo):
    """Oito dígitos do começo e do fim -- para conferir sem mostrar a chave."""
    texto = "%064x" % modulo if modulo else ""
    return "%s…%s" % (texto[:8], texto[-8:]) if texto else "—"


def _abrir_como_der(T, caminho, modulo=None):
    """
    O conteúdo aberto, tentando a chave do cliente e depois o l2encdec.

    Devolve (conteúdo, método, rabo, de_onde). A ordem não é gosto: a chave do
    cliente é a que vale para os arquivos dele, e o l2encdec entra quando o
    arquivo veio de outro lugar -- ou quando o método não é dos que este
    programa faz sozinho.
    """
    dados = Path(caminho).read_bytes()
    met = l2cripto.metodo(dados)
    if met is None:
        return dados, None, b"", "não estava cifrado"

    if met in l2cripto.SO_XOR:
        conteudo, rabo = l2cripto.abrir_xor(dados, met, Path(caminho).name)
        return conteudo, met, rabo, "chave do formato"

    if modulo is not None:
        expoente = l2cripto.expoente_que_abre(dados, modulo)
        if expoente is not None:
            conteudo, rabo = l2cripto.abrir_41x(dados, modulo, expoente)
            return conteudo, met, rabo, "chave do cliente"

    # Sobrou o l2encdec, que tem as chaves originais e a dele.
    trabalho = Path(motor.BASE) / "trabalho" / "protecao"
    trabalho.mkdir(parents=True, exist_ok=True)
    aberto, _obs = motor.descriptografar(T, Path(caminho), trabalho)
    if aberto is None or not Path(aberto).is_file():
        raise ErroDeProtecao(
            "não consegui abrir %s: nem a chave do cliente nem o l2encdec "
            "serviram." % Path(caminho).name)
    return Path(aberto).read_bytes(), met, dados[-l2cripto.RABO:], "l2encdec"


def proteger(T, system, escolhidos, frase, aolog=None, trocar_exe=True):
    """
    Fecha os arquivos escolhidos com a chave da frase. Devolve o relatório.

    Nada é instalado sem passar pela conferência: cada arquivo é reaberto com
    a chave nova e comparado com o que saiu da leitura. O executável só muda
    depois de todos os arquivos, e só se todos passarem.
    """
    def diga(texto):
        if aolog:
            aolog(texto)

    estado = estado_do_cliente(system)
    if not estado["existe"]:
        raise ErroDeProtecao("não achei a pasta system em %s" % system)
    if not estado["trocavel"] and trocar_exe:
        raise ErroDeProtecao(
            "este cliente guarda a chave empacotada (Kamael em diante): não dá "
            "para escrever a sua nela. Use a opção sem troca de chave.")

    alvos = [Path(p) for p in escolhidos]
    if not alvos:
        raise ErroDeProtecao("nenhum arquivo escolhido.")

    modulo_atual = estado["modulo_atual"]
    expoente = l2cripto.EXPOENTE_413
    for alvo in alvos:
        if l2cripto.metodo(alvo.read_bytes()[:28]) in ("411", "412", "413",
                                                       "414"):
            achado = (l2cripto.expoente_que_abre(alvo.read_bytes(),
                                                 modulo_atual)
                      if modulo_atual else None)
            if achado:
                expoente = achado
                break

    par = l2cripto.par_da_frase(frase, expoente=expoente)
    diga("chave da frase: %d bits, expoente 0x%x, marca %s"
         % (par["bits"], par["publico"], marca_da_chave(par["modulo"])))

    guarda = Path(system) / PASTA_GUARDA
    guarda.mkdir(parents=True, exist_ok=True)
    prontos, recusados = [], []

    for alvo in alvos:
        try:
            conteudo, met, rabo, de_onde = _abrir_como_der(T, alvo,
                                                           modulo_atual)
            if met is None:
                recusados.append((alvo.name, "não está cifrado"))
                diga("  %-22s pulado: não está cifrado" % alvo.name)
                continue
            if met in l2cripto.SO_XOR:
                recusados.append((alvo.name, "formato %s não usa chave" % met))
                diga("  %-22s pulado: %s é XOR, não tem chave a trocar"
                     % (alvo.name, met))
                continue

            novo = l2cripto.fechar_41x(conteudo, par["modulo"],
                                       par["privado"], met, rabo_modelo=rabo)
            # A conferencia: reabrir com a chave nova e comparar com o que
            # saiu da leitura. Sem isto, um erro so apareceria no jogo.
            volta, _rabo = l2cripto.abrir_41x(novo, par["modulo"],
                                              par["publico"])
            if volta != conteudo:
                recusados.append((alvo.name, "a ida e volta não bateu"))
                diga("  %-22s RECUSADO: a ida e volta não bateu" % alvo.name)
                continue

            copia = guarda / alvo.name
            if not copia.exists():
                shutil.copy2(alvo, copia)
            alvo.write_bytes(novo)
            prontos.append(alvo.name)
            diga("  %-22s %s, lido pela %s, %d bytes -> %d"
                 % (alvo.name, met, de_onde, copia.stat().st_size, len(novo)))
        except Exception as erro:                   # noqa: BLE001
            recusados.append((alvo.name, str(erro)[:80]))
            diga("  %-22s RECUSADO: %s" % (alvo.name, str(erro)[:60]))

    trocados = []
    if trocar_exe and prontos:
        for caminho in estado["executaveis"]:
            copia = guarda / (caminho.name + ".antes-da-chave")
            if not copia.exists():
                shutil.copy2(caminho, copia)
            antigo, _novo = l2cripto.trocar_chave_do_cliente(caminho,
                                                             par["modulo"])
            conferido, _pos = l2cripto.chave_do_cliente(caminho)
            if conferido != par["modulo"]:
                shutil.copy2(copia, caminho)
                raise ErroDeProtecao(
                    "a chave não ficou gravada em %s; o arquivo foi "
                    "restaurado." % caminho.name)
            trocados.append(caminho.name)
            diga("  %-22s chave %s -> %s"
                 % (caminho.name, marca_da_chave(antigo),
                    marca_da_chave(par["modulo"])))

    return {"prontos": prontos, "recusados": recusados,
            "executaveis": trocados, "marca": marca_da_chave(par["modulo"]),
            "guarda": guarda}


def desfazer(system, aolog=None):
    """Põe de volta tudo o que está em `backup_protecao`."""
    def diga(texto):
        if aolog:
            aolog(texto)

    system = Path(system)
    guarda = system / PASTA_GUARDA
    if not guarda.is_dir():
        raise ErroDeProtecao("não há %s neste cliente: nada foi protegido por "
                             "aqui." % PASTA_GUARDA)
    voltaram = []
    for copia in sorted(guarda.iterdir()):
        if not copia.is_file():
            continue
        nome = copia.name
        if nome.endswith(".antes-da-chave"):
            nome = nome[:-len(".antes-da-chave")]
        destino = system / nome
        shutil.copy2(copia, destino)
        voltaram.append(nome)
        diga("  %s voltou" % nome)
    return voltaram


def relatorio(system):
    """O que a tela mostra ao abrir: o que já está protegido, e por qual chave."""
    estado = estado_do_cliente(system)
    guarda = Path(system) / PASTA_GUARDA
    estado["protegidos"] = sorted(p.name for p in guarda.iterdir()
                                  if p.is_file()) if guarda.is_dir() else []
    estado["marca"] = marca_da_chave(estado["modulo_atual"])
    estado["quando"] = (time.strftime("%d/%m/%Y %H:%M",
                                      time.localtime(guarda.stat().st_mtime))
                        if guarda.is_dir() else "")
    return estado
