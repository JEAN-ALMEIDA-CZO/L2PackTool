#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A tabela de texto de C1/C2 com a cara da tabela binaria.

As telas sabem falar com UMA coisa: uma tabela com `cabecalho`, `linhas`,
`campo()`, `definir()` e `gravar()`, onde as colunas se chamam `icon[0]`,
`wpn_mesh[0]`, `class`, `mesh`. Nas cronicas de texto os mesmos dados existem
com outros nomes -- `icon`, `mesh`, `class_name`, `mesh_name` -- e numa
estrutura diferente.

Reescrever as telas para conhecer os dois formatos espalharia `if` por toda
parte, e cada `if` desses e um lugar onde uma cronica funciona e a outra nao.
Entao a traducao mora aqui, num so lugar: este adaptador recebe a tabela de
texto e devolve a interface que as telas ja usam.

## O que ele traduz

    nome da coluna    `icon[0]` vira `icon`, `class` vira `class_name`. O mapa
                      de cada tabela esta em MAPAS, e foi lido dos clientes
                      C1 e C2 -- nao inventado.

    colchetes         o texto do jogo e escrito `name=[Short Sword]`. Quem le
                      recebe `Short Sword`; quem grava pode mandar com ou sem
                      colchete, que eles voltam como estavam.

    linha nova        a binaria copia uma lista e acrescenta ao fim. Aqui a
                      linha nova nao tem texto de origem, entao ela e
                      DESENHADA a partir de um molde -- a primeira linha da
                      tabela -- com os valores da linha copiada.

## O que ele preserva

Linha que ninguem tocou volta como veio, byte por byte. E o que permite a
prova de ida e volta continuar valendo alguma coisa depois da traducao: se
so um item mudou, so aquela linha muda no arquivo.
"""

import re
from pathlib import Path

import l2texto

# canonico -> nome no arquivo de texto, por tipo de tabela. Lido dos clientes
# C1 e C2; o que nao existe naquela geracao simplesmente nao esta aqui, e o
# programa trata como coluna ausente (que ja e um caso previsto).
MAPAS = {
    "weapon": {"id": "object_id", "icon[0]": "icon", "icon": "icon",
               "wpn_mesh[0]": "mesh", "wpn_tex[0]": "texture",
               "drop_mesh1": "drop_mesh", "drop_tex1": "drop_texture",
               "weight": "weight", "crystal_type": "crystal_type",
               "material_type": "material_type", "nome_do_objeto": "object_name"},
    "armor": {"id": "object_id", "icon[0]": "icon", "icon": "icon",
              "drop_mesh1": "drop_mesh", "drop_tex1": "drop_texture",
              "weight": "weight", "crystal_type": "crystal_type",
              "armor_type": "armor_type", "nome_do_objeto": "object_name"},
    "etc": {"id": "object_id", "icon[0]": "icon", "icon": "icon",
            "drop_mesh1": "drop_mesh", "drop_tex1": "drop_texture",
            "weight": "weight", "grade": "crystal_type",
            "crystal_type": "crystal_type", "nome_do_objeto": "object_name"},
    "nome": {"id": "id", "name": "name", "description": "description"},
    "npcgrp": {"id": "npc_id", "tag": "npc_id", "class": "class_name",
               "mesh": "mesh_name", "texture": "texture_name",
               "collision_radius": "collision_radius",
               "collision_height": "collision_height"},
    "npcname": {"id": "id", "name": "name", "description": "nick",
                "title": "nick"},
    "skill": {"id": "skill_id", "level": "skill_level", "icon_name": "icon",
              "operate_type": "operate_type", "is_magic": "is_magic",
              "mp_consume": "mp_consume", "cast_range": "cast_range"},
    "skillname": {"id": "skill_id", "level": "skill_level", "name": "name",
                  "description": "desc"},
}

# Qual mapa serve para qual arquivo. O nome do arquivo e o que o programa
# pede; a extensao muda de .dat para .txt nestas cronicas.
POR_ARQUIVO = {
    "weapongrp": "weapon", "armorgrp": "armor", "etcitemgrp": "etc",
    "itemname-e": "nome", "npcgrp": "npcgrp", "npcname-e": "npcname",
    "skillgrp": "skill", "skillname-e": "skillname",
}

# Como o arquivo embrulha valor: `[texto]` para texto e `{[a],[b]}` para
# lista. Quem le quer o conteudo; quem grava tem de devolver o embrulho como
# estava, senao o cliente le uma lista onde esperava um texto.
COLCHETE = re.compile(r"^\[(.*)\]$", re.S)
LISTA = re.compile(r"^\{(.*)\}$", re.S)


def desembrulhar(valor):
    """O conteudo, sem os colchetes e sem as chaves de lista."""
    valor = (valor or "").strip()
    achado = LISTA.match(valor)
    if achado:
        valor = achado.group(1).strip()
    achado = COLCHETE.match(valor)
    if achado:
        valor = achado.group(1).strip()
    return valor


def embrulhar(valor, como_estava):
    """O valor novo com o mesmo embrulho do antigo."""
    valor = desembrulhar(valor)
    antigo = (como_estava or "").strip()
    if LISTA.match(antigo):
        dentro = LISTA.match(antigo).group(1).strip()
        return "{[%s]}" % valor if COLCHETE.match(dentro) else "{%s}" % valor
    if COLCHETE.match(antigo):
        return "[%s]" % valor
    return valor


def tipo_do_arquivo(arquivo):
    """Qual mapa usar para este arquivo, pelo nome dele."""
    return POR_ARQUIVO.get(Path(arquivo).stem.lower())


def caminho_de_texto(system, arquivo):
    """O mesmo arquivo com a extensao das cronicas de texto."""
    alvo = Path(system) / (Path(arquivo).stem + ".txt")
    if alvo.is_file():
        return alvo
    # Os clientes antigos nao sao consistentes na caixa alta: `Itemname-e.txt`
    # num, `itemname-e.txt` noutro.
    for achado in Path(system).glob("*.txt"):
        if achado.stem.lower() == Path(arquivo).stem.lower():
            return achado
    return alvo


class TabelaCompativel:
    """
    Uma tabela de texto que responde como a binaria.

    `linhas` e uma lista de verdade, e nao uma vista: as telas acrescentam
    item com `linhas.append(...)`, e isso precisa continuar funcionando.
    """

    def __init__(self, origem, T, trabalho, tipo=None):
        self.crua = l2texto.TabelaTexto(origem, T, trabalho)
        self.origem = self.crua.origem
        self.T = T
        self.trabalho = Path(trabalho)
        self.tipo = tipo or tipo_do_arquivo(origem) or "nome"
        self.mapa = MAPAS.get(self.tipo, {})
        self.inverso = dict((v, k) for k, v in self.mapa.items())

        # O cabecalho sai dos nomes do arquivo, traduzidos quando ha traducao.
        # Os sem traducao entram como estao: coluna a mais nao atrapalha, e
        # perder coluna atrapalharia.
        self.cabecalho = [self.inverso.get(c, c) for c in self.crua.cabecalho]
        self.linhas = [list(l) for l in self.crua.linhas]
        # De onde veio cada linha, para gravar sem reescrever o que ninguem
        # tocou. Linha acrescentada depois nao esta aqui.
        self._indice_por_arquivo = dict((c, i) for i, c
                                        in enumerate(self.crua.cabecalho))
        self._origem_da_linha = dict((id(l), i)
                                     for i, l in enumerate(self.linhas))
        self._mexidas = set()


    # As telas reconhecem a tabela de texto por esta marca, e mudam o pouco
    # que precisa mudar -- como o prefixo da descricao, que so existe no
    # formato binario.
    e_texto = True

    def por_chave(self, valor, coluna=None):
        """A linha cujo id e este, ou None. Como na tabela binaria."""
        indice = self.coluna("id") if coluna is None else coluna
        for linha in self.linhas:
            if (linha[indice] or "") == str(valor):
                return linha
        return None

    # -- leitura -----------------------------------------------------------
    def coluna(self, nome):
        """
        O indice da coluna, aceitando o nome canonico ou o do arquivo.

        Procurar pelo cabecalho traduzido nao bastava: dois nomes canonicos
        podem apontar para o mesmo campo do arquivo (`icon` e `icon[0]` sao o
        mesmo `icon` do C1), e so um deles sobrevive na traducao de volta.
        Aqui se traduz o que foi pedido e se procura pelo nome REAL.
        """
        procurado = self.mapa.get(nome, nome)
        if procurado in self._indice_por_arquivo:
            return self._indice_por_arquivo[procurado]
        if nome in self._indice_por_arquivo:
            return self._indice_por_arquivo[nome]
        raise ValueError("a coluna %s nao existe nesta tabela" % nome)

    def campo(self, linha, nome):
        """O valor, sem os colchetes com que o arquivo embrulha texto."""
        try:
            valor = linha[self.coluna(nome)]
        except (ValueError, IndexError, TypeError):
            return ""
        return desembrulhar(valor)

    def definir(self, linha, nome, valor):
        """
        Muda um campo. Os colchetes voltam como estavam.

        Levanta ValueError quando a coluna nao existe, que e o que as telas
        ja esperam da tabela binaria.
        """
        indice = self.coluna(nome)              # ValueError se nao existe
        antigo = linha[indice] or ""
        linha[indice] = embrulhar(str(valor), antigo)
        self._mexidas.add(id(linha))

    def remover_linha(self, valor, coluna=0):
        """Tira as linhas em que aquela coluna tem aquele valor."""
        sobraram = [l for l in self.linhas if (l[coluna] or "") != str(valor)]
        tirou = len(self.linhas) - len(sobraram)
        self.linhas = sobraram
        return tirou

    # -- gravacao ----------------------------------------------------------
    def _linha_de_texto(self, linha):
        """
        A linha em texto: a original quando nada mudou, desenhada quando nao.

        Desenhar usa a PRIMEIRA linha da tabela como molde -- dela vem a
        ordem dos campos, os separadores e as palavras de abertura e
        fechamento (`item_begin`, `item_end`), que sao o que o cliente
        procura.
        """
        posicao = self._origem_da_linha.get(id(linha))
        if posicao is not None and id(linha) not in self._mexidas:
            return self.crua.brutas[posicao]

        molde = (self.crua.brutas[posicao] if posicao is not None
                 else self.crua.brutas[0])
        texto = molde
        for nome_canonico, valor in zip(self.cabecalho, linha):
            no_arquivo = self.mapa.get(nome_canonico, nome_canonico)
            achado = l2texto.CAMPO.search(texto)
            # troca campo a campo, achando cada um pelo nome
            padrao = re.compile(r"(\b%s[ ]*=[ ]*)([^\t]*)"
                                % re.escape(no_arquivo))
            if padrao.search(texto):
                texto = padrao.sub(lambda m: m.group(1) + (valor or ""),
                                   texto, count=1)
            del achado
        return texto

    def _montar(self):
        corpo = self.crua.fim_de_linha.join(
            self._linha_de_texto(l) for l in self.linhas)
        return self.crua.marca_de_ordem + corpo + self.crua.rabo

    def gravar(self, destino):
        """Escreve a tabela de volta, criptografada como veio."""
        import shutil
        import motor

        destino = Path(destino)
        # O destino tem de ter a extensao do arquivo de origem: quem pediu
        # `weapongrp.dat` numa cronica de texto quer dizer `weapongrp.txt`.
        if destino.suffix.lower() != self.origem.suffix.lower():
            destino = destino.with_suffix(self.origem.suffix)

        puro = self.trabalho / (self.origem.stem + "_novo.dec")
        puro.write_bytes(self._montar().encode(l2texto.CODIFICACAO))

        if not self.crua.metodo:
            shutil.copy2(puro, destino)
            return destino

        provisorio = self.trabalho / (self.origem.stem + "_novo" +
                                      self.origem.suffix)
        provisorio.unlink(missing_ok=True)
        _codigo, saida = motor.executar(
            [self.T["l2encdec"], "-h", self.crua.metodo, puro, provisorio],
            limite=600)
        if not provisorio.exists():
            raise l2texto.ErroDeTexto(motor.explicar_saida(
                saida, "não consegui fechar %s de volta." % self.origem.name))
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(provisorio), str(destino))
        return destino

    def conferir_ciclo(self):
        """
        A ida e volta, contando so o que ninguem mexeu.

        Depois de acrescentar item a volta nao reproduz o original -- nem
        deveria. A prova aqui vale para o estado em que a tabela foi lida, e
        e assim que as telas a usam: conferem ao abrir.
        """
        if self._mexidas or len(self.linhas) != len(self.crua.brutas):
            return True, "tabela já alterada nesta sessão"
        return self.crua.conferir_ciclo()
