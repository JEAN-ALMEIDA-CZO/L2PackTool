#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Os textos do cliente: mensagem de sistema, texto de interface e fala de NPC.

Tudo o que o jogo escreve na tela e que nao e nome de item nem de habilidade
mora em tres tabelas:

    systemmsg-e   as mensagens do sistema -- "You have been disconnected",
                  "$s1 does not exist". Cada uma tem id, cor, som e grupo
    sysstring-e   os textos da interface -- "Equipment", "Quest Item"
    npcstring-e   as falas de NPC com variavel dentro, de Freya em diante

Quem monta servidor mexe nisso por dois motivos: traduzir e trocar o que o jogo
diz por algo do proprio servidor. Ate agora era preciso um editor de .dat a
parte para isso, com o risco de sempre -- abrir com a definicao errada estraga
a tabela inteira e o cliente deixa de abrir.

## O que muda e o que nao muda

So o TEXTO. A cor, o som, o grupo e os campos que ninguem decifrou ficam como
estao: uma mensagem com a cor trocada continua funcionando, mas uma mensagem
que perdeu o `$s1` passa a mostrar a frase sem o numero que ela anuncia, e isso
nao da erro em lugar nenhum -- por isso as marcas sao contadas antes de gravar.

## A convencao do texto

O mesmo do itemname: `a,` na frente e `\\0` no fim. Contado nas 3.258 mensagens
do High Five, todas tem o prefixo e todas terminam com o zero. Escrever sem
isso poe o proprio `a,` na tela do jogador, ou emenda a frase na seguinte.

## Prova

As tres tabelas voltam identicas ao original em onze clientes daqui, de C3 a
High Five -- e a mesma prova das outras: abrir, montar de novo e comparar byte
por byte. O Interlude entrou sem prova, porque nao ha cliente dele extraido
aqui; o `nucleo.json` dele diz isso.
"""

import re
import shutil
from pathlib import Path

import l2item
import motor

PASTA_GUARDA = "backup_textos"

# (chave, arquivo, rotulo, coluna do texto)
#
# A coluna muda de tabela para tabela, e nao ha o que deduzir: e o nome que a
# definicao da. `message` na do sistema, `name` na da interface, `string` na de
# NPC.
TABELAS = (
    ("sistema", "systemmsg-e.dat", "mensagem do sistema", "message"),
    ("interface", "sysstring-e.dat", "texto da interface", "name"),
    ("npc", "npcstring-e.dat", "fala de NPC", "string"),
)

# A mensagem do sistema tem uma segunda linha, que o jogo mostra embaixo.
COLUNA_EXTRA = {"sistema": "sub_msg"}

# As marcas que o jogo troca por numero, nome ou item na hora de mostrar.
MARCA = re.compile(r"\$[sc]\d+")


class ErroDeMensagem(Exception):
    pass


class Mensagens:
    """As tabelas de texto que este cliente tiver, abertas juntas."""

    def __init__(self, T, system, trabalho, cronica=None, aoprogresso=None):
        self.T = T
        self.system = Path(system)
        self.trabalho = Path(trabalho)
        self.cronica = cronica
        self.tabelas = {}
        self.provas = {}
        self.alteradas = set()
        self.faltando = []

        quantas = len(TABELAS)
        for i, (chave, arquivo, rotulo, _coluna) in enumerate(TABELAS):
            if aoprogresso:
                aoprogresso(i / float(quantas + 1), "abrindo %s" % arquivo)
            if not self._existe(arquivo):
                # Tabela que a cronica nao tem nao e erro: o `npcstring-e` so
                # aparece na Freya. Some da lista e a tela diz quais abriu.
                self.faltando.append((chave, arquivo, rotulo))
                continue
            self.tabelas[chave] = l2item.abrir_tabela(T, system, arquivo,
                                                      self.trabalho, cronica)
        if not self.tabelas:
            raise ErroDeMensagem(
                "nao achei nenhuma tabela de texto em %s. Esperava %s."
                % (self.system, ", ".join(a for _c, a, _r, _x in TABELAS)))

        for i, (chave, arquivo) in enumerate(
                [(c, a) for c, a, _r, _x in TABELAS if c in self.tabelas]):
            if aoprogresso:
                aoprogresso((i + 1) / float(quantas + 1),
                            "conferindo %s" % arquivo)
            self.provas[chave] = self.tabelas[chave].conferir_ciclo()
        if aoprogresso:
            aoprogresso(1.0, "pronto")

    def _existe(self, arquivo):
        alvo = arquivo.lower()
        for achado in self.system.iterdir():
            if achado.is_file() and achado.name.lower() == alvo:
                return True
        return False

    # -- leitura -----------------------------------------------------------
    def coluna_do_texto(self, chave):
        for c, _arquivo, _rotulo, coluna in TABELAS:
            if c == chave:
                return coluna
        raise ErroDeMensagem("nao conheco a tabela %s." % chave)

    def rotulo(self, chave):
        for c, _arquivo, rotulo, _coluna in TABELAS:
            if c == chave:
                return rotulo
        return chave

    def listar(self, aoprogresso=None):
        """Uma entrada por texto, das tabelas que abriram."""
        saida = []
        for chave, _arquivo, rotulo, coluna in TABELAS:
            tabela = self.tabelas.get(chave)
            if tabela is None:
                continue
            extra = COLUNA_EXTRA.get(chave)
            for linha in tabela.linhas:
                entrada = {
                    "grupo": chave,
                    "rotulo": rotulo,
                    "id": linha[l2item.coluna_do_id(tabela, chave)],
                    "texto": l2item._limpar(str(tabela.campo(linha, coluna))),
                    "linha": linha,
                }
                if extra and extra in tabela.cabecalho:
                    entrada["extra"] = l2item._limpar(
                        str(tabela.campo(linha, extra)))
                saida.append(entrada)
            if aoprogresso:
                aoprogresso(None, "lido %s" % _arquivo)
        return saida

    def por_id(self, chave, ident):
        tabela = self.tabelas.get(chave)
        if tabela is None:
            return None
        coluna = l2item.coluna_do_id(tabela, chave)
        return tabela.por_chave(str(ident), coluna)

    # -- escrita -----------------------------------------------------------
    def trocar(self, chave, ident, texto, extra=None):
        """
        Troca o texto daquele id, e so o texto.

        Devolve as marcas (`$s1`, `$c1`) que estavam no original e nao estao no
        texto novo. Elas nao sao enfeite: o servidor manda o valor e o cliente o
        encaixa na marca. Tirar uma faz a frase chegar sem o numero que ela
        anuncia, e o jogo nao reclama.
        """
        tabela = self.tabelas.get(chave)
        if tabela is None:
            raise ErroDeMensagem("este cliente nao tem a tabela %s."
                                 % self.rotulo(chave))
        linha = self.por_id(chave, ident)
        if linha is None:
            raise ErroDeMensagem("nao achei o id %s em %s."
                                 % (ident, self.rotulo(chave)))
        coluna = self.coluna_do_texto(chave)
        antes = l2item._limpar(str(tabela.campo(linha, coluna)))
        tabela.definir(linha, coluna, _guardado(texto))

        nome_extra = COLUNA_EXTRA.get(chave)
        if extra is not None and nome_extra and nome_extra in tabela.cabecalho:
            tabela.definir(linha, nome_extra, _guardado(extra))

        self.alteradas.add(chave)
        return marcas_perdidas(antes, texto)

    def conferir(self, so_alteradas=True):
        """As tabelas cuja ida e volta nao confere -- gravar nelas e bloqueado."""
        ruins = []
        for chave, (ok, recado) in self.provas.items():
            if so_alteradas and chave not in self.alteradas:
                continue
            if not ok:
                ruins.append((self.tabelas[chave].origem.name, recado))
        return ruins

    def gravar(self, destino, aolog=None):
        """Grava as tabelas mexidas em `destino`, sem tocar no cliente."""
        problemas = self.conferir()
        if problemas:
            raise ErroDeMensagem(
                "a ida e volta nao confere em: %s. Nada foi gravado."
                % ", ".join("%s (%s)" % p for p in problemas))
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        gravados = []
        for chave in sorted(self.alteradas):
            tabela = self.tabelas[chave]
            alvo = destino / tabela.origem.name
            tabela.gravar(alvo)
            gravados.append(alvo)
            if aolog:
                aolog("gravado %s (%s bytes)"
                      % (alvo.name, "{:,}".format(alvo.stat().st_size)))
        return gravados


def _guardado(texto):
    """O texto como a tabela o guarda: `a,` na frente, `\\0` no fim."""
    limpo = l2item._limpar(str(texto or ""))
    return "a,%s\\0" % limpo if limpo else "a,"


def marcas_perdidas(antes, depois):
    """As marcas que existiam e nao existem mais, na ordem em que apareciam."""
    tinha = MARCA.findall(str(antes or ""))
    tem = MARCA.findall(str(depois or ""))
    sobrando = list(tem)
    faltando = []
    for marca in tinha:
        if marca in sobrando:
            sobrando.remove(marca)
        else:
            faltando.append(marca)
    return faltando


# ---------------------------------------------------------------------------
# Instalacao no cliente
# ---------------------------------------------------------------------------
def instalar(gravados, system, aolog=None):
    """
    Poe as tabelas geradas no cliente, guardando as originais na primeira vez.

    Como nos itens e nas habilidades: a copia de guarda e feita uma vez por
    arquivo, senao a segunda instalacao guardaria por cima o arquivo gerado na
    primeira.
    """
    system = Path(system)
    l2item._garantir_chave(system, aolog)
    guarda = system / PASTA_GUARDA
    guarda.mkdir(parents=True, exist_ok=True)
    postos = []
    for arquivo in gravados:
        arquivo = Path(arquivo)
        alvo = system / arquivo.name
        copia = guarda / arquivo.name
        if alvo.exists() and not copia.exists():
            shutil.copy2(alvo, copia)
            if aolog:
                aolog("guardado o original em %s" % copia)
        provisorio = alvo.with_suffix(alvo.suffix + ".novo")
        provisorio.unlink(missing_ok=True)
        shutil.copy2(arquivo, provisorio)
        provisorio.replace(alvo)
        postos.append(alvo)
        if aolog:
            aolog("instalado %s" % alvo.name)
    return postos


def restaurar(system, aolog=None):
    system = Path(system)
    guarda = system / PASTA_GUARDA
    if not guarda.is_dir():
        return []
    voltaram = []
    for copia in sorted(guarda.glob("*.dat")):
        alvo = system / copia.name
        shutil.copy2(copia, alvo)
        voltaram.append(alvo)
        if aolog:
            aolog("restaurado %s" % alvo.name)
    return voltaram


def saida():
    """Onde as tabelas geradas ficam."""
    return Path(motor.BASE) / "textos_gerados"
