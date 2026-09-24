# -*- coding: utf-8 -*-
"""
Mede, num cliente de verdade, quais definicoes de cronica servem para ele.

A pergunta "da para cobrir a cronica X?" nao se responde lendo documentacao:
responde-se tentando. Para cada conjunto de definicoes .ddf, este programa
desmonta a tabela do cliente e a monta de volta, e compara byte a byte com o
binario original. Se a volta reproduz a ida, a definicao descreve aquele
arquivo. Se nao reproduz, nao descreve -- e nao ha meio termo.

Isso serve para duas coisas:

  1. o levantamento: saber, antes de prometer, quais cronicas o programa
     consegue cobrir com as definicoes que existem;

  2. a deteccao: dado um cliente qualquer, descobrir de que cronica ele e.
     Nao basta uma tabela -- varias atravessam cronicas sem mudar e passam
     em mais de uma. O que identifica e a ASSINATURA: o conjunto de quais
     passam e quais nao.

    python levantar_cronicas.py <pasta system> [--tabelas=a,b] [--cronicas=x,y]
    python levantar_cronicas.py --raiz <pasta com varios clientes>

No modo --raiz, cada subpasta que tiver um `system` com .dat dentro e medida,
e cada uma recebe seu palpite de cronica. Subpasta vazia nao e erro: e
cliente que ainda nao foi copiado para la.
"""

import json
import shutil
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import l2item                                       # noqa: E402
import l2npc                                        # noqa: E402
import motor                                        # noqa: E402

BIBLIOTECA = Path(r"C:\Lineage Programas\L2FileEdit\data\l2asm-disasm\DAT_defs")

# So ate High Five: dali em diante o cliente muda de geracao e a conversa e
# outra. A ordem e cronologica, que e como o resultado se le.
ATE_H5 = ["C3", "C4", "C5", "Interlude", "CT1_0", "CT1_5",
          "CT2_1en", "CT2_2en", "CT2_3en", "CT2_4en", "ct2_5", "ct2_6"]

ROTULO = {"C3": "C3", "C4": "C4", "C5": "C5", "Interlude": "Interlude (C6)",
          "CT1_0": "The Kamael", "CT1_5": "Hellbound",
          "CT2_1en": "Gracia Part 1", "CT2_2en": "Gracia Part 2",
          "CT2_3en": "Gracia Final", "CT2_4en": "Gracia Epilogue",
          "ct2_5": "Freya", "ct2_6": "High Five"}

TABELAS = ["itemname-e", "weapongrp", "armorgrp", "etcitemgrp",
           "skillgrp", "skillname-e", "npcgrp", "npcname-e"]


def provar(T, system, trabalho, cronica, tabela):
    """
    (passou, recado, segundos) para uma definicao contra uma tabela.

    Erro de leitura e resultado tambem: definicao de outra cronica costuma
    estourar no meio do desmonte, e isso ja e a resposta.
    """
    comeco = time.time()
    base = BIBLIOTECA / cronica / (tabela + ".ddf")
    origem = Path(system) / (tabela + ".dat")
    if not base.is_file():
        return None, "sem definicao", 0.0
    if not origem.is_file():
        return None, "sem a tabela no cliente", 0.0
    try:
        puro = l2item._decifrar(T, origem, trabalho)
        definicao = l2item.completar(T, base, puro, trabalho)
        tabela_lida = l2npc.Tabela(origem, definicao, T, trabalho)
        ok, motivo = tabela_lida.conferir_ciclo()
        return bool(ok), (motivo or "")[:60], time.time() - comeco
    except Exception as erro:                       # noqa: BLE001
        return False, str(erro).replace("\n", " ")[:60], time.time() - comeco


def medir(T, system, trabalho, tabelas, cronicas, aolog=print):
    """A matriz de um cliente: {cronica: {tabela: {...}}}."""
    largura = max(len(ROTULO.get(c, c)) for c in cronicas) + 2
    aolog(" " * largura + "".join("%-14s" % t[:13] for t in tabelas))

    resultado = {}
    for cronica in cronicas:
        linha = "%-*s" % (largura, ROTULO.get(cronica, cronica))
        resultado[cronica] = {}
        for tabela in tabelas:
            passou, recado, gasto = provar(T, system, trabalho, cronica, tabela)
            resultado[cronica][tabela] = {"passou": passou, "recado": recado,
                                          "segundos": round(gasto, 1)}
            linha += "%-14s" % {True: "PASSA", False: "-", None: "."}[passou]
        aolog(linha, flush=True) if aolog is print else aolog(linha)
    return resultado


def melhor(resultado):
    """
    A cronica mais provavel, e quantas tabelas fecharam nela.

    Empate nao e falha do metodo: quer dizer que as tabelas medidas nao
    distinguem aquelas duas cronicas. Medir mais tabelas desempata.
    """
    contas = sorted(((sum(1 for c in v.values() if c["passou"]), k)
                     for k, v in resultado.items()), reverse=True)
    if not contas:
        return None, 0, []
    alto = contas[0][0]
    return contas[0][1], alto, [k for n, k in contas if n == alto]


def um_cliente(T, system, trabalho, tabelas, cronicas):
    print("cliente: %s" % system)
    resultado = medir(T, system, trabalho, tabelas, cronicas)
    escolhida, quantas, empatadas = melhor(resultado)
    print()
    if quantas == 0:
        print("nenhuma definicao serviu: ou nao e cliente ate High Five, ou "
              "as tabelas estao noutro formato.")
    elif len(empatadas) > 1:
        print("empate em %d de %d tabelas: %s -- meca mais tabelas para "
              "desempatar." % (quantas, len(tabelas),
                               ", ".join(ROTULO.get(c, c) for c in empatadas)))
    else:
        print("parece %s: passou em %d das %d tabelas."
              % (ROTULO.get(escolhida, escolhida), quantas, len(tabelas)))
    return resultado


def main():
    argumentos = sys.argv[1:]
    if not argumentos:
        print(__doc__)
        return 1

    tabelas, cronicas, raiz, system, esperando = TABELAS, ATE_H5, None, None, False
    for arg in argumentos:
        if arg.startswith("--tabelas="):
            tabelas = arg.split("=", 1)[1].split(",")
        elif arg.startswith("--cronicas="):
            cronicas = arg.split("=", 1)[1].split(",")
        elif arg == "--raiz":
            esperando = True
        elif arg.startswith("--raiz="):
            raiz = Path(arg.split("=", 1)[1])
        elif esperando:
            raiz, esperando = Path(arg), False
        else:
            system = Path(arg)

    T = motor.carregar_config()
    trabalho = Path(motor.BASE) / "trabalho" / "levantamento"
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True, exist_ok=True)

    tudo = {}
    if raiz is not None:
        for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
            dentro = pasta / "system"
            if not dentro.is_dir() or not any(dentro.glob("*.dat")):
                print("%-30s vazia, nada para medir" % pasta.name)
                continue
            print("\n" + "=" * 74)
            tudo[pasta.name] = um_cliente(T, dentro, trabalho, tabelas,
                                          cronicas)
    elif system is not None:
        tudo[system.parent.name or str(system)] = um_cliente(
            T, system, trabalho, tabelas, cronicas)
    else:
        print(__doc__)
        return 1

    fora = trabalho.parent / "levantamento.json"
    fora.write_text(json.dumps(tudo, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    print("\ndetalhe em %s" % fora)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
