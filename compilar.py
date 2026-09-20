#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compila os executaveis e, se houver certificado, assina.

    python compilar.py                 os dois normais
    python compilar.py --completo      os dois com as ferramentas juntas
    python compilar.py --tudo          os quatro
    python compilar.py --so-assinar    nao compila; assina o que esta em dist/

## Sobre "assinar para nao acusar como virus"

Vale ser exato, porque a diferenca custa dinheiro:

**Assinatura nao e um selo de "nao e virus".** Ela diz duas coisas: quem
publicou o arquivo, e que ele nao foi alterado desde entao. O Windows so
acredita nisso se o certificado subir ate uma Autoridade Certificadora que ele
ja confia -- as que vem no Windows de fabrica.

Disso saem tres casos:

1. **Sem assinatura** (hoje). O SmartScreen mostra "O Windows protegeu o seu
   PC" e o arquivo aparece como editor desconhecido. Antivirus de heuristica
   agressiva as vezes barram.

2. **Certificado feito em casa** (`New-SelfSignedCertificate`). O arquivo fica
   assinado, mas por alguem em quem o Windows nao confia. **O aviso continua
   igual** -- na maquina de quem gerou o certificado some, porque ele esta na
   loja de confianca dela; em qualquer outra, nao. Serve para testar o
   processo, nao para resolver o problema.

3. **Certificado de uma CA de verdade** (DigiCert, Sectigo, SSL.com e afins).
   E o unico que tira o aviso. Custa por ano, exige comprovar identidade -- de
   pessoa fisica tambem serve, com documento -- e hoje a chave vem obrigatoria
   em token fisico ou HSM na nuvem. O tipo OV ainda precisa juntar reputacao no
   SmartScreen ao longo de alguns downloads; o EV ja nasce com ela.

Por isso este script **nao inventa certificado**. Sem um configurado, ele
compila, avisa que saiu sem assinatura e para por ai.

## O que da para fazer de graca, e ja esta feito

Assinatura e uma parte. As outras pesam no heuristico e nao custam nada:

- **Sem UPX.** Executavel empacotado e o que empacotador de malware produz, e o
  heuristico sabe disso. Os `.spec` estao com `upx=False`.
- **Com dados de versao.** Nome do produto, descricao, versao e nome original
  do arquivo, escritos por `versao.py`. Binario anonimo e suspeito por si.
- **Icone e nome proprios**, que ja havia.

## Configurar o certificado

Duas maneiras, nenhuma delas com senha escrita em arquivo:

    # a recomendada -- o certificado ja instalado na loja do Windows
    set L2PACKTOOL_CERT_SHA1=a1b2c3...        (a impressao digital, sem espacos)

    # ou um .pfx em disco
    set L2PACKTOOL_CERT_PFX=C:\\caminho\\cert.pfx
    set L2PACKTOOL_CERT_SENHA=...

O carimbo de tempo e sempre posto. Sem ele a assinatura morre junto com o
certificado, e os executaveis ja distribuidos passam a acusar erro.
"""

import os
import subprocess
import sys
from pathlib import Path

import versao

BASE = Path(__file__).parent
DIST = BASE / "dist"

NORMAIS = ("L2PackTool.spec", "l2upscale-cli.spec")
COMPLETOS = ("L2PackTool-Completo.spec", "l2upscale-cli-Completo.spec")

# Servidores de carimbo de tempo, em ordem. Mais de um porque eles caem, e uma
# assinatura sem carimbo vale so ate o certificado expirar.
CARIMBOS = ("http://timestamp.digicert.com",
            "http://timestamp.sectigo.com",
            "http://time.certum.pl")


# ---------------------------------------------------------------------------
# signtool
# ---------------------------------------------------------------------------
def achar_signtool():
    """
    O signtool.exe do Windows SDK, o mais novo que houver.

    Ele nao esta no PATH: vive numa pasta com o numero da versao do SDK no
    caminho, e a maquina pode ter varias.
    """
    for raiz in (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
                 Path(os.environ.get("ProgramFiles", r"C:\Program Files"))):
        kits = raiz / "Windows Kits" / "10" / "bin"
        if not kits.is_dir():
            continue
        achados = sorted(kits.glob("*/x64/signtool.exe"),
                         key=lambda p: p.parent.parent.name, reverse=True)
        if achados:
            return achados[0]
    return None


def certificado():
    """O que foi configurado, ou None. Nao inventa nada."""
    sha1 = (os.environ.get("L2PACKTOOL_CERT_SHA1") or "").replace(" ", "").strip()
    if sha1:
        return ["/sha1", sha1]
    pfx = (os.environ.get("L2PACKTOOL_CERT_PFX") or "").strip()
    if pfx:
        argumentos = ["/f", pfx]
        senha = os.environ.get("L2PACKTOOL_CERT_SENHA")
        if senha:
            argumentos += ["/p", senha]
        return argumentos
    return None


def assinar(alvo, ferramenta, cartao):
    """
    Assina um executavel. Devolve (deu certo, o que dizer).

    Tenta os carimbos de tempo em ordem: o servidor do primeiro pode estar fora
    do ar, e desistir na primeira falha deixaria a assinatura sem carimbo sem
    ninguem perceber.
    """
    ultimo = ""
    for carimbo in CARIMBOS:
        linha = ([str(ferramenta), "sign"] + cartao +
                 ["/fd", "sha256", "/tr", carimbo, "/td", "sha256",
                  "/d", "L2PackTool", str(alvo)])
        saida = subprocess.run(linha, capture_output=True, text=True,
                               errors="replace")
        if saida.returncode == 0:
            return True, "assinado, carimbo de %s" % carimbo
        ultimo = (saida.stdout + saida.stderr).strip().replace("\n", " ")[:200]
    return False, ultimo


def conferir(alvo, ferramenta):
    """
    Pergunta ao proprio Windows se ele aceita a assinatura.

    E a unica resposta que vale: `signtool sign` ter dado certo so quer dizer
    que o arquivo foi assinado, e nao que a cadeia sobe ate alguem confiavel.
    """
    saida = subprocess.run([str(ferramenta), "verify", "/pa", "/v", str(alvo)],
                           capture_output=True, text=True, errors="replace")
    return saida.returncode == 0, (saida.stdout + saida.stderr).strip()


# ---------------------------------------------------------------------------
# compilar
# ---------------------------------------------------------------------------
def compilar(spec):
    print("\n=== %s ===" % spec)
    saida = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm",
                            "--clean", spec], cwd=str(BASE))
    return saida.returncode == 0


def exe_do_spec(spec):
    return DIST / (Path(spec).stem + ".exe")


# O compilador do Inno Setup. O winget instala por usuario; o instalador
# oficial poe em Program Files -- os dois caminhos sao procurados.
ISCC = (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
        / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"))

SEM_INNO = """
Nao achei o compilador do Inno Setup.

    winget install JRSoftware.InnoSetup

ou baixe em https://jrsoftware.org/isinfo.php
"""


def montar_instalador():
    """
    O instalador, a partir do executavel completo que ja esta em dist/.

    Nao compila o programa: quem faz isso e o `--tudo`. Aqui so se empacota
    o que ja existe.
    """
    alvo = DIST / "L2PackTool-Completo.exe"
    if not alvo.exists():
        print("Nao achei %s. Rode antes:  python compilar.py --tudo"
              % alvo.name)
        return False

    for caminho in ISCC:
        if caminho.is_file():
            print("\n=== instalador ===")
            saida = subprocess.run([str(caminho), str(BASE / "instalador.iss")],
                                   cwd=str(BASE))
            return saida.returncode == 0

    print(SEM_INNO)
    return False


def main(argumentos):
    if "--instalador" in argumentos:
        return 0 if montar_instalador() else 1

    so_assinar = "--so-assinar" in argumentos
    if "--tudo" in argumentos:
        specs = NORMAIS + COMPLETOS
    elif "--completo" in argumentos:
        specs = COMPLETOS
    else:
        specs = NORMAIS

    if not so_assinar:
        for alvo in versao.escrever():
            print("versao: %s" % alvo.name)
        for spec in specs:
            if not compilar(spec):
                print("\nA compilacao de %s falhou. Nada foi assinado." % spec)
                alvo = exe_do_spec(spec)
                if alvo.exists():
                    # O PyInstaller apaga o executavel antigo antes de escrever
                    # o novo, e no Windows nao da para apagar arquivo que
                    # alguem esta lendo.
                    print("\nSe o erro foi \"acesso negado\" em %s, alguem "
                          "esta com ele aberto:" % alvo.name)
                    print("  - o antivirus varrendo a pasta dist/")
                    print("  - o proprio programa em execucao")
                    print("  - o Explorer gerando a miniatura")
                    print("Feche e rode de novo.")
                return 1

    feitos = [exe_do_spec(s) for s in specs]
    faltando = [p for p in feitos if not p.exists()]
    if faltando:
        print("\nNao saiu executavel para: %s"
              % ", ".join(p.name for p in faltando))
        return 1

    print("\n=== compilado ===")
    for p in feitos:
        print("  %-32s %s bytes" % (p.name, "{:,}".format(p.stat().st_size)))

    # ---- assinatura -------------------------------------------------------
    cartao = certificado()
    ferramenta = achar_signtool()

    if cartao is None:
        print("""
=== sem assinatura ===

Nenhum certificado configurado, entao os executaveis sairam sem assinatura.

Assinar com um certificado feito em casa nao resolveria: o Windows so tira o
aviso do SmartScreen quando a cadeia sobe ate uma Autoridade Certificadora que
ele ja confia, e um certificado proprio nao sobe. Ficaria assinado e com o
mesmo aviso.

Para assinar de verdade, ponha o certificado na loja do Windows e defina:

    set L2PACKTOOL_CERT_SHA1=<impressao digital>
    python compilar.py --so-assinar

O que ja foi feito e que ajuda sem certificado: sem UPX e com dados de versao
no executavel.""")
        return 0

    if ferramenta is None:
        print("\nHa certificado configurado, mas o signtool.exe nao foi "
              "encontrado.\nEle vem no Windows SDK.")
        return 1

    print("\n=== assinando com %s ===" % ferramenta.parent.parent.name)
    falhou = False
    for p in feitos:
        certo, recado = assinar(p, ferramenta, cartao)
        print("  %-32s %s" % (p.name, recado if certo else "NAO assinou: " + recado))
        falhou = falhou or not certo

    if falhou:
        return 1

    print("\n=== o que o Windows acha ===")
    for p in feitos:
        aceito, detalhe = conferir(p, ferramenta)
        print("  %-32s %s" % (p.name,
                              "cadeia aceita" if aceito else "cadeia RECUSADA"))
        if not aceito:
            print("     %s" % detalhe.replace("\n", "\n     ")[:600])
            print("     Assinado, mas por quem o Windows nao conhece: o aviso\n"
                  "     do SmartScreen continua para quem baixar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
