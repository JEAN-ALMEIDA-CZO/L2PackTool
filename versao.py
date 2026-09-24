#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A versao do programa, e os arquivos de recurso que o Windows le do .exe.

Um executavel sem nome de produto, sem descricao e sem versao e, para o
heuristico de antivirus, um binario anonimo -- e binario anonimo recem
compilado e exatamente o perfil do que ele foi treinado para barrar. Preencher
isto nao substitui assinatura, mas tira do programa um dos sinais que pesam
contra ele, e de graca.

Sao quatro executaveis, com quatro nomes diferentes. O `OriginalFilename` de
cada um tem de ser o nome dele: um recurso que diz um nome e um arquivo que se
chama outro e, de novo, um sinal a favor da suspeita.

    python versao.py        reescreve os quatro arquivos em recursos/versao/
"""

from pathlib import Path

# O nome do sistema. Serve ao recurso do executavel e tambem ao que o
# programa assina no cliente: o pacote de video de um lobby leva este
# nome, em vez do nome de quem fez o lobby.
NOME = "L2PackTool"

VERSAO = (1, 5, 0, 0)
TEXTO = ".".join(str(n) for n in VERSAO)

BASE = Path(__file__).parent
PASTA = BASE / "recursos" / "versao"

ALVOS = (
    ("L2PackTool", "L2PackTool - ferramentas de cliente Lineage II"),
    ("L2PackTool-Completo",
     "L2PackTool - ferramentas de cliente Lineage II (com as ferramentas)"),
    ("L2PackTool-cli", "L2PackTool - linha de comando"),
    ("L2PackTool-cli-Completo",
     "L2PackTool - linha de comando (com as ferramentas)"),
)

MOLDE = '''# -*- coding: utf-8 -*-
# Gerado por versao.py -- nao edite a mao.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=%(numeros)s,
    prodvers=%(numeros)s,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [StringStruct('CompanyName', 'L2PackTool'),
           StringStruct('FileDescription', %(descricao)r),
           StringStruct('FileVersion', %(texto)r),
           StringStruct('InternalName', %(nome)r),
           StringStruct('LegalCopyright', 'Software livre'),
           StringStruct('OriginalFilename', %(arquivo)r),
           StringStruct('ProductName', 'L2PackTool'),
           StringStruct('ProductVersion', %(texto)r)])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''


def escrever():
    PASTA.mkdir(parents=True, exist_ok=True)
    feitos = []
    for nome, descricao in ALVOS:
        alvo = PASTA / (nome + ".txt")
        alvo.write_text(MOLDE % {"numeros": str(VERSAO), "nome": nome,
                                 "arquivo": nome + ".exe", "texto": TEXTO,
                                 "descricao": descricao}, encoding="utf-8")
        feitos.append(alvo)
    return feitos


if __name__ == "__main__":
    for alvo in escrever():
        print(alvo)
