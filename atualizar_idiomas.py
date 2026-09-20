#!/usr/bin/env python3
"""
Poe os arquivos de idioma em dia com o codigo.

Rode depois de mexer em qualquer frase da interface:

    python atualizar_idiomas.py

O que ele faz:

  - varre gui.py e gui_npc.py atras de t("...") e N_("..."), que sao as duas
    unicas portas por onde texto chega a tela;
  - reescreve idiomas/en.ini e idiomas/es.ini com a lista completa, mantendo
    intacta toda traducao ja escrita -- frase nova entra com `t =` vazio, e
    frase que sumiu do codigo sai do arquivo;
  - confere se cada traducao tem os mesmos %s e %d do original, na mesma
    ordem. Essa e a unica diferenca entre os dois textos capaz de derrubar o
    programa: o resto, no pior caso, fica feio.

Nada aqui e chamado pelo programa em si -- e ferramenta de manutencao.
"""

import ast
import io
from pathlib import Path
import os
import re
import sys

import idioma

# Todo modulo de tela entra sozinho. A lista escrita a mao deixou o
# gui_arma.py de fora no dia em que ele nasceu, e uma tela em
# portugues dentro de um programa traduzido so aparece para quem usa
# outro idioma -- ou seja, tarde.
ARQUIVOS = tuple(sorted(
    p.name for p in Path(__file__).parent.glob("gui*.py")) ) + ("manual.py",)
RAIZ = os.path.dirname(os.path.abspath(__file__))

# %s, %d, %.2f, %-30s... A ordem importa: "%s de %d" traduzido como "%d of %s"
# troca os valores de lugar e estoura na hora de formatar.
MARCA = re.compile(r"%[-#0 +]*[\d.*]*[hlL]?[diouxXeEfFgGcrs%]")


def frases_de(caminho):
    arvore = ast.parse(io.open(caminho, encoding="utf-8").read())
    achadas = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                and no.func.id in ("t", "N_") and len(no.args) == 1):
            continue
        arg = no.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            achadas.append(arg.value)
    return achadas


def frases_das_tabelas():
    """
    As frases que a tela traduz com `t(variavel)`, e o AST nao enxerga.

    Sao tabelas de dominio, nao de interface: vivem no modulo do assunto e a
    tela as traduz ao montar a caixa de escolha. Sem esta ponte elas ficariam
    em portugues para quem usa o programa noutro idioma.
    """
    import l2env
    import l2item
    import l2multisell
    achadas = []
    for tabela in (l2item.O_QUE_A_OPERACAO_FAZ, l2item.O_QUE_A_ORDEM_FAZ,
                   l2env.MOSTRAR, l2multisell.OPCOES):
        achadas.extend(texto for _chave, texto in tabela)
    return achadas


def main():
    todas = []
    for nome in ARQUIVOS:
        achadas = frases_de(os.path.join(RAIZ, nome))
        print("%-12s %d chamadas" % (nome, len(achadas)))
        todas.extend(achadas)

    das_tabelas = frases_das_tabelas()
    print("%-12s %d frases" % ("(tabelas)", len(das_tabelas)))
    todas.extend(das_tabelas)

    # Ordenadas para o numero da secao nao dancar a cada execucao.
    unicas = sorted(set(todas))
    print("\n%d ocorrencias, %d frases distintas" % (len(todas), len(unicas)))

    idioma.carregar()
    problemas = 0
    for codigo, nome in idioma.IDIOMAS:
        if codigo == "pt":
            continue

        existentes = idioma.TEXTOS.get(codigo, {})
        caminho = os.path.join(RAIZ, idioma.PASTA, codigo + ".ini")
        idioma.gravar_catalogo(unicas, codigo, caminho, existentes)

        traduzidas = [f for f in unicas if existentes.get(f)]
        print("\n%-22s %d/%d traduzidas" % (nome, len(traduzidas), len(unicas)))

        faltando = [f for f in unicas if not existentes.get(f)]
        for f in faltando[:10]:
            print("   falta: %r" % f[:70])
        if len(faltando) > 10:
            print("   ... e mais %d." % (len(faltando) - 10))

        for f in traduzidas:
            if MARCA.findall(existentes[f]) != MARCA.findall(f):
                problemas += 1
                print("   ATENCAO, %%s fora de lugar em %r" % f[:60])
                print("      original: %s" % MARCA.findall(f))
                print("      traducao: %s" % MARCA.findall(existentes[f]))

    print("\n%s" % ("tudo certo." if not problemas
                    else "%d traducao(oes) com %%s trocado -- corrija antes de "
                         "empacotar." % problemas))
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
