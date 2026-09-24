#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
As tabelas de C1 e C2, que sao TEXTO e nao binario.

Ate o C2 o cliente guardava as tabelas em texto, uma linha por registro, com
os campos escritos por nome:

    item_begin  object_id=1  object_name=[small_sword]  body_part={rhand} ...
    npc_begin   npc_id=1     npc_name=[gremlin]  mesh_name=[...]  ...
    item_name_begin  id=1  name=[Short Sword]  description=[]  item_name_end

Sao arquivos `.txt`, criptografados como qualquer outro (Ver211), e por isso
parecem binario a quem so olha o cabecalho. Aberto, e texto UTF-16 separado
por tabulacao.

## Por que isto nao usa .ddf

Nao precisa. A definicao existe para dizer onde cada campo comeca num binario
sem cabecalho; aqui cada campo diz o proprio nome. Nao ha coluna a contar, nao
ha campo a deslocar, e nao ha o que provar sobre a estrutura -- o que vale
provar e a ida e volta, que continua sendo feita.

## A linha crua e a fonte da verdade

Cada linha e guardada como veio. Ler monta um dicionario a partir dela;
gravar reescreve a MESMA linha, trocando so o pedaco do campo alterado.

Nao e economia de trabalho: e o que garante que um arquivo em que nada mudou
volte identico, com os mesmos espacos, a mesma ordem e as mesmas
tabulacoes -- inclusive as do fim da linha, que existem e nao significam
nada, mas fazem diferenca na comparacao.
"""

import re
import shutil
from pathlib import Path

import motor

# `chave=valor`, com ou sem espaco em volta do igual -- o C1 escreve
# `object_id=1` no weapongrp e `skill_id = 3` no skillgrp, no mesmo cliente.
# O valor vai ate a proxima tabulacao; os colchetes e as chaves dos valores
# compostos ficam nele, como estao no arquivo.
CAMPO = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)[ ]*=[ ]*([^\t]*)")

CODIFICACAO = "utf-16-le"


class ErroDeTexto(Exception):
    pass


def parece_texto(caminho):
    """Este arquivo e uma tabela de texto? Vale pela extensao e pelo nome."""
    return Path(caminho).suffix.lower() == ".txt"


class TabelaTexto:
    """
    Uma tabela de C1/C2, com a mesma cara das outras para quem usa.

    Expoe `cabecalho` e `linhas` como a Tabela binaria, para que as telas nao
    precisem saber de que geracao e o cliente. A diferenca e que aqui o
    cabecalho nasce dos nomes encontrados, e nao de uma definicao.
    """

    def __init__(self, origem, T, trabalho):
        self.origem = Path(origem)
        self.T = T
        self.trabalho = Path(trabalho)
        self.trabalho.mkdir(parents=True, exist_ok=True)
        self.metodo = None
        self.marca_de_ordem = ""
        self.fim_de_linha = "\r\n"

        self.brutas = []        # a linha como veio, uma por registro
        self.mapas = []         # {campo: valor} de cada linha
        self.lugares = []       # {campo: (inicio, fim)} na linha crua
        self.cabecalho = []     # os campos, na ordem em que aparecem
        self._ler()

    # -- ida ---------------------------------------------------------------
    def _ler(self):
        import l2npc                     # so para o cabecalho do arquivo

        self.metodo = l2npc.metodo_do_arquivo(self.origem)
        puro = self.trabalho / (self.origem.stem + ".txt.dec")
        if self.metodo:
            try:
                motor.abrir_dat(self.T, self.origem, puro, limite=600)
            except OSError as erro:
                raise ErroDeTexto(str(erro))
        else:
            shutil.copy2(self.origem, puro)

        bruto = puro.read_bytes()
        self._puro = puro
        texto = bruto.decode(CODIFICACAO, errors="replace")
        if texto.startswith("﻿"):
            self.marca_de_ordem = "﻿"
            texto = texto[1:]
        if "\r\n" not in texto:
            self.fim_de_linha = "\n"

        vistos = {}
        for linha in texto.split(self.fim_de_linha):
            if not linha.strip():
                continue
            self.brutas.append(linha)
            # Guarda onde cada campo comeca e termina na linha crua: assim
            # gravar recorta e cola no lugar exato, sem depender de como o
            # arquivo escreveu o igual nem de espaco a mais.
            campos, lugares = {}, {}
            for achado in CAMPO.finditer(linha):
                nome, valor = achado.group(1), achado.group(2)
                campos[nome] = valor
                lugares[nome] = achado.span()
            self.mapas.append(campos)
            self.lugares.append(lugares)
            for nome in campos:
                if nome not in vistos:
                    vistos[nome] = True
                    self.cabecalho.append(nome)

        # o fim do arquivo: quantas quebras havia depois da ultima linha
        self.rabo = texto[len(self.fim_de_linha.join(self.brutas)):]

    # -- acesso, com a mesma cara da Tabela binaria ------------------------
    @property
    def linhas(self):
        """As linhas em forma de lista, na ordem do cabecalho."""
        return [[m.get(c, "") for c in self.cabecalho] for m in self.mapas]

    def coluna(self, nome):
        return self.cabecalho.index(nome)

    def campo(self, linha, nome):
        """
        O valor daquele campo. `linha` pode ser o indice ou a lista.

        Os valores vem como estao no arquivo, com os colchetes: quem escreveu
        `[Short Sword]` quis dizer texto, e `{rhand}` quis dizer lista. Tirar
        isso aqui obrigaria a adivinhar na hora de gravar.
        """
        indice = self._indice(linha)
        if indice is None:
            return ""
        return self.mapas[indice].get(nome, "")

    def definir(self, linha, nome, valor):
        """Muda um campo, na linha crua e no mapa."""
        indice = self._indice(linha)
        if indice is None:
            raise ErroDeTexto("não achei essa linha")
        if nome not in self.mapas[indice]:
            raise ErroDeTexto("a linha não tem o campo %s" % nome)

        antiga = self.brutas[indice]
        inicio, fim = self.lugares[indice][nome]
        # O pedaco trocado mantem a escrita do arquivo -- se ele poe espaco
        # em volta do igual, o valor novo entra no mesmo formato.
        pedaco = antiga[inicio:fim]
        antes_do_valor = pedaco[:len(pedaco) - len(self.mapas[indice][nome])]
        self.brutas[indice] = (antiga[:inicio] + antes_do_valor + valor
                               + antiga[fim:])
        desloca = len(valor) - len(self.mapas[indice][nome])
        if desloca:
            for outro, (a, b) in self.lugares[indice].items():
                if a > inicio:
                    self.lugares[indice][outro] = (a + desloca, b + desloca)
        self.lugares[indice][nome] = (inicio, fim + desloca)
        self.mapas[indice][nome] = valor

    def _indice(self, linha):
        if isinstance(linha, int):
            return linha if 0 <= linha < len(self.brutas) else None
        try:
            return self.linhas.index(linha)
        except ValueError:
            return None

    def por_campo(self, nome, valor):
        """O indice da primeira linha em que aquele campo tem aquele valor."""
        for i, mapa in enumerate(self.mapas):
            if mapa.get(nome) == valor:
                return i
        return None

    # -- volta -------------------------------------------------------------
    def _texto_montado(self):
        corpo = self.fim_de_linha.join(self.brutas)
        return self.marca_de_ordem + corpo + self.rabo

    def gravar(self, destino):
        """Monta e criptografa de volta, com o metodo do arquivo de origem."""
        destino = Path(destino)
        puro = self.trabalho / (self.origem.stem + "_novo.dec")
        puro.write_bytes(self._texto_montado().encode(CODIFICACAO))

        if not self.metodo:
            shutil.copy2(puro, destino)
            return destino

        provisorio = self.trabalho / (self.origem.stem + "_novo.txt")
        provisorio.unlink(missing_ok=True)
        _codigo, saida = motor.executar(
            [self.T["l2encdec"], "-h", self.metodo, puro, provisorio],
            limite=600)
        if not provisorio.exists():
            raise ErroDeTexto("o l2encdec não fechou %s: %s"
                              % (self.origem.name, (saida or "").strip()[:200]))
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(provisorio), str(destino))
        return destino

    def conferir_ciclo(self):
        """
        Remonta sem mudar nada e compara com o que foi lido.

        Aqui a prova diz menos do que na tabela binaria -- nao ha definicao
        que possa estar errada --, mas continua valendo a pena: ela pega
        codificacao trocada, quebra de linha trocada e campo comido por uma
        expressao regular malfeita.
        """
        montado = self._texto_montado().encode(CODIFICACAO)
        original = self._puro.read_bytes()
        if montado == original:
            return True, "identico ao original"
        return False, ("a volta nao reproduz o original (%d contra %d bytes)"
                       % (len(montado), len(original)))
