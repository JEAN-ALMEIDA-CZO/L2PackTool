#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Itens do cliente: ler, copiar para um id novo, e devolver para as tabelas.

Um item existe em dois lugares ao mesmo tempo, e os dois tem de concordar:

    weapongrp.dat / armorgrp.dat / etcitemgrp.dat   a aparencia
    itemname-e.dat                                   o nome e a descricao

O cliente casa as duas pelo id. Escrever so numa delas produz item sem nome,
ou nome sem item -- e nenhum dos dois casos da erro: da confusao.

Por isso o item novo e sempre uma COPIA de um que ja funciona. Uma linha do
armorgrp tem 332 colunas, e as que nao tem a ver com aparencia -- peso, som ao
equipar, tipo de cristal, malha de cada uma das doze combinacoes de raca e
sexo -- precisam de valores plausiveis. Herda-las de um item que o cliente ja
desenha e mais seguro do que inventa-las.

## A definicao da tabela

Um .dat e um binario sem cabecalho de formato: quem diz onde cada campo comeca
e uma definicao .ddf. Uma definicao errada nao da erro -- ela le campos
deslocados e grava lixo por cima da tabela, e o sintoma aparece no jogo.

As definicoes base ficam em recursos/definicoes/<cronica>/. Elas descrevem os
campos, mas nao quantas colunas cada tabela dinamica tem -- e isso varia de
cliente para cliente. O proprio l2disasm conta isso na primeira passada e
devolve a definicao completa com a opcao -e; e o que `completar()` faz, no
cliente do usuario, antes de qualquer leitura valer.

Depois disso ainda vem a prova: `conferir_ciclo()` remonta o que foi lido sem
mudar nada e compara com o binario original. Se a volta nao reproduz a ida byte
a byte, nada e gravado.
"""

import json
import re
import shutil
from pathlib import Path

import l2npc
import motor

PASTA_DE_DEFINICOES = "recursos/definicoes"
CRONICA_PADRAO = "interlude"

# Que tabela guarda que tipo de item, e como isso aparece na tela.
GRUPOS = (
    ("weapon", "weapongrp.dat", "Armas"),
    ("armor", "armorgrp.dat", "Armaduras"),
    ("etc", "etcitemgrp.dat", "Outros"),
)

NOMES = "itemname-e.dat"

# A coluna do id em cada tabela. Nas tres de aparencia o id e a SEGUNDA coluna;
# a primeira e o tipo de registro. No itemname-e o id e a primeira.
COLUNA_ID = {"weapon": 1, "armor": 1, "etc": 1, "nome": 0}

# As colunas que a tela mostra e deixa editar, por grupo. Nome da coluna no
# .ddf -> como aparece para o usuario.
CAMPOS_VISIVEIS = {
    "weapon": (("icon[0]", "ícone"), ("wpn_mesh[0]", "malha"),
               ("wpn_tex[0]", "textura"), ("weight", "peso"),
               ("crystal_type", "grau")),
    "armor": (("icon[0]", "ícone"), ("drop_mesh1", "malha ao cair"),
              ("drop_tex1", "textura ao cair"), ("weight", "peso"),
              ("crystal_type", "grau")),
    "etc": (("icon[0]", "ícone"), ("drop_mesh1", "malha ao cair"),
            ("drop_tex1", "textura ao cair"), ("weight", "peso"),
            ("grade", "grau")),
}

# O primeiro id que vale a pena sugerir para item novo. Abaixo disso e area do
# jogo original, e sobrescrever um item de verdade e o erro mais caro aqui.
PRIMEIRO_ID_LIVRE = 30000


class ErroDeItem(Exception):
    pass


# ---------------------------------------------------------------------------
# As definicoes
# ---------------------------------------------------------------------------
def pasta_de_definicoes(cronica=None):
    """A pasta daquela cronica. Sem cronica dita, a do projeto."""
    return motor.definicoes(cronica or cronica_em_uso())


def cronica_em_uso():
    """
    A cronica do projeto, com Interlude de reserva.

    Quem chama passando cronica explicita manda; quem nao passa segue o
    projeto, que e onde o cliente esta apontado.
    """
    try:
        import projeto
        return projeto.cronica() or CRONICA_PADRAO
    except Exception:                               # noqa: BLE001
        return CRONICA_PADRAO


# O nome da pasta e chave: esta na configuracao guardada e dentro do
# executavel. O que o usuario le e outra coisa, e nao precisa ser igual -- e
# quem diz e o `nucleo.json` de dentro da pasta, para que acrescentar cronica
# seja largar uma pasta, sem tocar em codigo.
NOME_DO_NUCLEO = "nucleo.json"
ROTULOS_DE_CRONICA = {"interlude": "C6 - Interlude"}


def nucleo(cronica):
    """O cartao de identidade daquela cronica: rotulo, o que foi provado."""
    caminho = motor.definicoes(cronica) / NOME_DO_NUCLEO
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def provadas(cronica):
    """As tabelas que a prova de ida e volta ja confirmou nesta cronica."""
    return list(nucleo(cronica).get("provadas") or [])


# O atributo -- a pedra de elemento que se poe na arma ou na armadura -- chegou
# no Kamael. Medido no proprio cliente: o `systemmsg-e` do C3, do C4 e do C5 nao
# tem uma unica mensagem que fale de atributo; o do Kamael tem onze, o do High
# Five, vinte e seis. Oferecer o campo antes disso seria oferecer nada.
ORDEM_DO_ATRIBUTO = 70


def tem_atributo(cronica=None):
    """Esta cronica tem o sistema de atributo (elemento)?"""
    dados = nucleo(cronica or cronica_em_uso())
    try:
        return int(dados.get("ordem") or 0) >= ORDEM_DO_ATRIBUTO
    except (TypeError, ValueError):
        return False


def cronicas():
    """As cronicas que tem definicao embutida, em ordem de lançamento."""
    raiz = Path(motor.AQUI) / PASTA_DE_DEFINICOES
    if not raiz.is_dir():
        return []
    # Pasta com manifesto e sem .ddf tambem vale: as cronicas de tabela em
    # texto (C1, C2) nao tem definicao porque nao ha coluna a definir.
    return motor.em_ordem(p.name for p in raiz.iterdir()
                          if p.is_dir() and (any(p.glob("*.ddf"))
                                             or (p / NOME_DO_NUCLEO).is_file()))


def rotulo_da_cronica(chave):
    """Como a cronica aparece na tela: o que o nucleo disser, ou a pasta."""
    return (nucleo(chave).get("rotulo")
            or ROTULOS_DE_CRONICA.get(chave, chave))


def cronica_do_rotulo(rotulo, entre=()):
    """O caminho de volta, do que esta na tela para o nome da pasta."""
    for chave in (entre or cronicas()):
        if rotulo_da_cronica(chave) == rotulo:
            return chave
    return rotulo


def completar(T, base, binario, trabalho):
    """
    A definicao com os limites que o l2asm exige, medidos NESTE cliente.

    A definicao base descreve os campos; quantas colunas cada tabela dinamica
    tem depende do arquivo. O l2disasm conta na primeira passada e devolve a
    definicao completa com -e. Sem isso o l2asm recusa a definicao, e usar
    numeros de outro cliente truncaria colunas em silencio.
    """
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    completa = trabalho / (Path(base).stem + "_completa.ddf")
    rascunho = trabalho / (Path(base).stem + "_medida.txt")
    completa.unlink(missing_ok=True)

    try:
        completa = motor.completar_definicao(T, base, binario, trabalho)
    except OSError as erro:
        raise ErroDeItem(str(erro))
    return completa.read_text(encoding="latin-1")


def erro_de_cronica(cronica, arquivo):
    """A frase de quando a definicao nao serve para o cliente apontado."""
    return ("%s não abre como %s: as colunas não batem.\n\n"
            "Isso quase sempre é a crônica do projeto errada. Abra "
            "Projetos… e use Detectar — o programa mede o cliente e diz de "
            "qual crônica ele é."
            % (Path(arquivo).name, rotulo_da_cronica(cronica)))


def _decifrar(T, origem, trabalho):
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    puro = trabalho / (Path(origem).stem + "_base.dec")
    metodo = l2npc.metodo_do_arquivo(origem)
    if not metodo:
        shutil.copy2(origem, puro)
        return puro
    puro.unlink(missing_ok=True)
    try:
        # Tenta as duas familias de chave: cliente de servidor privado usa as
        # do l2encdec, cliente oficial limpo usa as da NCSoft.
        aberto, _chave = motor.abrir_dat(T, origem, puro)
    except OSError as erro:
        raise ErroDeItem(str(erro))
    return aberto



def coluna_do_id(tabela, chave):
    """
    Onde esta o id nesta tabela.

    No binario e uma posicao fixa por tabela, escrita em COLUNA_ID. No texto
    a coluna tem nome e pode estar em qualquer lugar -- entao se pergunta a
    ela. Perguntar primeiro e o que faz o mesmo codigo servir aos dois.
    """
    try:
        return tabela.coluna("id")
    except Exception:                               # noqa: BLE001
        return COLUNA_ID.get(chave, 0)


def abrir_tabela(T, system, arquivo, trabalho, cronica=None):
    """Uma tabela do cliente, com a definicao ja medida nele."""
    cronica = cronica or cronica_em_uso()
    if motor.formato_da_cronica(cronica) == "texto":
        # C1 e C2 guardam as tabelas em texto. O adaptador as entrega com a
        # mesma cara da binaria, e o resto do codigo nao precisa saber.
        import l2compat
        alvo = l2compat.caminho_de_texto(system, arquivo)
        if not alvo.is_file():
            raise ErroDeItem("nao achei %s em %s" % (alvo.name, system))
        return l2compat.TabelaCompativel(alvo, T, trabalho)
    origem = Path(system) / arquivo
    if not origem.is_file():
        raise ErroDeItem("nao achei %s em %s" % (arquivo, system))

    base = pasta_de_definicoes(cronica) / (origem.stem + ".ddf")
    if not base.is_file():
        raise ErroDeItem("nao tenho a definicao de %s para %s"
                         % (origem.stem, cronica))

    puro = _decifrar(T, origem, trabalho)
    try:
        definicao = completar(T, base, puro, trabalho)
    except ErroDeItem as erro:
        raise ErroDeItem(com_a_cronica_certa(T, system, cronica, origem,
                                             trabalho, erro))
    return l2npc.Tabela(origem, definicao, T, trabalho)


def com_a_cronica_certa(T, system, cronica, arquivo, trabalho, erro):
    """
    A mensagem de cronica errada, com a cronica certa medida na hora.

    Se a medicao tambem nao achar nada, fica o recado original -- dizer "nao
    sei" e melhor do que apontar uma cronica ao acaso.
    """
    recado = "%s: %s" % (Path(arquivo).name, erro)
    try:
        import l2cronica
        achado = l2cronica.detectar(T, system, Path(trabalho) / "cronica",
                                    preferida=cronica)
    except Exception:                               # noqa: BLE001
        return recado
    if not achado.get("cronica") or achado["cronica"] == cronica:
        return recado
    return ("Este cliente não é %s.\n\nMedi as tabelas dele: é %s (%s).\n\n"
            "Troque a crônica em Projetos… — o botão Detectar faz essa mesma "
            "medição e já deixa escolhido."
            % (rotulo_da_cronica(cronica),
               rotulo_da_cronica(achado["cronica"]), achado["detalhe"]))


# ---------------------------------------------------------------------------
# O conjunto de tabelas
# ---------------------------------------------------------------------------
class Itens:
    """
    As quatro tabelas de item abertas juntas, porque um item vive nas duas
    metades e nenhuma operacao aqui toca so numa.
    """

    def __init__(self, T, system, trabalho, cronica=None,
                 aoprogresso=None):
        self.T = T
        self.system = Path(system)
        self.trabalho = Path(trabalho)
        self.cronica = cronica
        self.tabelas = {}
        self.alteradas = set()
        self.provas = {}

        alvos = [(chave, arquivo) for chave, arquivo, _r in GRUPOS]
        alvos.append(("nome", NOMES))
        for i, (chave, arquivo) in enumerate(alvos):
            if aoprogresso:
                aoprogresso(i / float(len(alvos) + 1), "abrindo %s" % arquivo)
            self.tabelas[chave] = abrir_tabela(T, system, arquivo,
                                               self.trabalho, cronica)

        # A prova tem de ser feita AGORA, com as tabelas do jeito que vieram.
        # Depois de acrescentar um item a volta nao reproduz mais o original --
        # nem deveria -- e a conferencia perderia o sentido.
        for i, (chave, arquivo) in enumerate(alvos):
            if aoprogresso:
                aoprogresso((i + 1) / float(len(alvos) + 1),
                            "conferindo %s" % arquivo)
            self.provas[chave] = self.tabelas[chave].conferir_ciclo()

        if aoprogresso:
            aoprogresso(1.0, "pronto")

    # -- leitura -----------------------------------------------------------
    def nomes(self):
        """
        {id: (nome, descricao, destaque)} do itemname-e.

        O destaque e a coluna `add_name`: a palavra que o jogo desenha em
        dourado ao lado do nome -- `Legendary`, `Light`, o grau do conjunto.
        Nem toda definicao de tabela traz essa coluna, entao a leitura dela
        nao pode derrubar a lista de itens inteira.
        """
        tabela = self.tabelas["nome"]

        def coluna(linha, nome, padrao=""):
            try:
                return _limpar(tabela.campo(linha, nome))
            except Exception:                       # noqa: BLE001
                return padrao

        saida = {}
        onde = coluna_do_id(tabela, "nome")
        for linha in tabela.linhas:
            saida[linha[onde]] = (coluna(linha, "name"),
                               coluna(linha, "description"),
                               coluna(linha, "add_name"))
        return saida

    def listar(self, aoprogresso=None):
        """Um registro por item, com o que a tela precisa mostrar."""
        nomes = self.nomes()
        saida = []
        for chave, _arquivo, rotulo in GRUPOS:
            tabela = self.tabelas[chave]
            coluna = coluna_do_id(tabela, chave)
            for linha in tabela.linhas:
                ident = linha[coluna]
                nome, descricao, destaque = nomes.get(ident, ("", "", ""))
                saida.append({
                    "id": ident,
                    "grupo": chave,
                    "rotulo": rotulo,
                    "nome": nome,
                    "descricao": descricao,
                    "destaque": destaque,
                    "icone": self.icone_de(chave, linha),
                    "linha": linha,
                })
        saida.sort(key=lambda item: int(item["id"] or 0))
        return saida

    def tem_destaque(self):
        """
        Esta cronica tem a palavra dourada ao lado do nome?

        Ela mora na coluna `add_name` do itemname, que e de cronicas
        posteriores: C1 e C2 nao a tem. Quem for oferecer o campo na tela
        pergunta aqui antes.
        """
        try:
            self.tabelas["nome"].coluna("add_name")
            return True
        except Exception:                           # noqa: BLE001
            return False

    def icone_de(self, grupo, linha):
        """
        O icone deste item, em qualquer das colunas em que ele possa estar.

        Nao e sempre a primeira. O Interlude poe em `icon[0]`; o C3 poe em
        `icon[4]` e deixa as quatro primeiras vazias -- olhando so a primeira,
        6.218 dos 6.391 itens do C3 pareciam nao ter icone.
        """
        tabela = self.tabelas[grupo]
        candidatas = ["icon[%d]" % i for i in range(5)]
        candidatas += ["icon", "icons[0]", "icon_name"]
        for nome in candidatas:
            try:
                valor = tabela.campo(linha, nome)
            except Exception:                       # noqa: BLE001
                continue
            if valor:
                return valor
        return ""

    def por_id(self, grupo, ident):
        tabela = self.tabelas[grupo]
        return tabela.por_chave(str(ident), COLUNA_ID[grupo])

    def onde_esta(self, ident):
        """Em que grupo o id existe. None se nao existe em nenhum."""
        for chave, _arquivo, _rotulo in GRUPOS:
            if self.por_id(chave, ident) is not None:
                return chave
        return None

    def proximo_id_livre(self, a_partir_de=PRIMEIRO_ID_LIVRE):
        usados = set()
        for chave, _arquivo, _rotulo in GRUPOS:
            tabela = self.tabelas[chave]
            coluna = coluna_do_id(tabela, chave)
            for linha in tabela.linhas:
                try:
                    usados.add(int(linha[coluna]))
                except (ValueError, IndexError):
                    pass
        for linha in self.tabelas["nome"].linhas:
            try:
                usados.add(int(linha[0]))
            except (ValueError, IndexError):
                pass
        ident = int(a_partir_de)
        while ident in usados:
            ident += 1
        return ident

    # -- escrita -----------------------------------------------------------
    def clonar(self, grupo, id_base, id_novo, nome="", descricao="",
               trocas=None, substituir=False, destaque=None):
        """
        Copia a linha inteira do item base sob outro id, nas duas metades.

        `trocas` e {coluna: valor} para o que a tela deixou o usuario mudar --
        icone, malha, textura. O resto vem do item base sem ser tocado.
        """
        base = self.por_id(grupo, id_base)
        if base is None:
            raise ErroDeItem("o item %s nao existe em %s."
                             % (id_base, dict((c, a) for c, a, _r in GRUPOS)[grupo]))

        ja_em = self.onde_esta(id_novo)
        if ja_em is not None:
            if not substituir:
                raise ErroDeItem("o id %s ja existe (%s). Escolha outro, ou "
                                 "mande substituir." % (id_novo, ja_em))
            self.tabelas[ja_em].remover_linha(
                str(id_novo), coluna_do_id(self.tabelas[ja_em], ja_em))
            self.alteradas.add(ja_em)

        tabela = self.tabelas[grupo]
        novo = list(base)
        novo[coluna_do_id(tabela, grupo)] = str(id_novo)
        for coluna, valor in (trocas or {}).items():
            try:
                tabela.definir(novo, coluna, valor)
            except ValueError:
                raise ErroDeItem("a coluna %s nao existe em %s"
                                 % (coluna, grupo))
        tabela.linhas.append(novo)
        self.alteradas.add(grupo)

        self.definir_nome(id_novo, nome or ("Item %s" % id_novo), descricao,
                          id_base, destaque)
        return novo

    def definir_nome(self, ident, nome, descricao="", id_base=None,
                     destaque=None):
        """
        Cria ou atualiza a entrada do itemname-e.

        A entrada nova e copia da do item base -- ou da primeira da tabela --
        porque as colunas de conjunto e de encantamento precisam de valores
        plausiveis, e copiar quem ja funciona e mais seguro do que inventa-los.
        """
        tabela = self.tabelas["nome"]
        linha = tabela.por_chave(str(ident))
        if linha is None:
            modelo = (tabela.por_chave(str(id_base)) if id_base is not None
                      else None)
            if modelo is None:
                if not tabela.linhas:
                    raise ErroDeItem("o itemname-e.dat esta vazio; nao tenho "
                                     "de onde copiar o formato de uma entrada.")
                modelo = tabela.linhas[0]
            linha = list(modelo)
            linha[coluna_do_id(tabela, "nome")] = str(ident)
            tabela.linhas.append(linha)

        # O NOME vai cru. Contadas as 9.432 linhas do itemname-e deste
        # cliente, 9.431 nao tem prefixo nenhum na coluna `name` -- a unica que
        # tinha era a que este programa escreveu, e o cliente mostrava o `a,`
        # no inventario. Ja a DESCRICAO tem `a,` em todas as 9.432, e nenhuma
        # termina em `\0`.
        tabela.definir(linha, "name", nome)
        if getattr(tabela, "e_texto", False):
            # No texto a descricao e o texto, e os colchetes sao do adaptador.
            tabela.definir(linha, "description", descricao)
        else:
            tabela.definir(linha, "description",
                           "a,%s" % descricao if descricao else "a,")
        # `None` quer dizer "deixa como esta" -- numa copia, o destaque do
        # item base continua valendo. Texto vazio apaga de proposito.
        if destaque is not None:
            try:
                tabela.definir(linha, "add_name", destaque)
            except Exception:                       # noqa: BLE001
                pass                # tabela sem essa coluna: nao ha destaque
        self.alteradas.add("nome")
        return linha

    def remover(self, ident):
        """Tira o item das quatro tabelas. Devolve de onde ele saiu."""
        saiu = []
        for chave, _arquivo, _rotulo in GRUPOS:
            if self.tabelas[chave].remover_linha(
                    str(ident), coluna_do_id(self.tabelas[chave], chave)):
                saiu.append(chave)
                self.alteradas.add(chave)
        if self.tabelas["nome"].remover_linha(str(ident)):
            saiu.append("nome")
            self.alteradas.add("nome")
        return saiu

    # -- gravacao ----------------------------------------------------------
    def conferir(self, so_alteradas=True):
        """
        O que a prova de ida e volta disse de cada tabela, quando foi aberta.

        Uma definicao que nao reproduz o original gravaria campos deslocados, e
        o sintoma disso nao e um erro: e o cliente lendo itens errados. Por isso
        a resposta e olhada antes de gravar, e nao depois.
        """
        chaves = sorted(self.alteradas) if so_alteradas else sorted(self.provas)
        problemas = []
        for chave in chaves:
            deu, motivo = self.provas.get(chave, (False, "nao foi conferida"))
            if not deu:
                problemas.append((self.tabelas[chave].origem.name, motivo))
        return problemas

    def gravar(self, destino, aolog=None):
        """
        Grava as tabelas alteradas em `destino`, sem tocar no cliente.

        Gerar e instalar sao separados de proposito: quem gera pode olhar o
        resultado antes de deixar o cliente depender dele.
        """
        problemas = self.conferir()
        if problemas:
            raise ErroDeItem(
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


def _limpar(texto):
    """
    Tira o 'a,'/'u,' do comeco e o \\0 do fim.

    Continua tirando os dois mesmo agora que o programa nao os escreve: a
    descricao REAL tem `a,` em todas as linhas, e os itens que este programa
    criou antes da correcao tem o prefixo no nome e o `\\0` na descricao. Ler
    limpo e o que permite regravar certo.
    """
    if texto.startswith(("a,", "u,")):
        texto = texto[2:]
    return texto.replace("\\0", "")


# ---------------------------------------------------------------------------
# Instalacao no cliente
# ---------------------------------------------------------------------------
PASTA_GUARDA = "backup_itens"



def _garantir_chave(system, aolog=None):
    """
    Converte o cliente para a chave em que o programa grava, se precisar.

    Importado aqui dentro e nao no topo porque o l2chaves importa o l2npc,
    que importa este modulo -- e um ciclo que so existe na hora de instalar.
    """
    try:
        import l2chaves
        T = motor.carregar_config()
        l2chaves.garantir_para_gravar(T, system,
                                      Path(motor.BASE) / "trabalho" / "chaves",
                                      aolog=aolog)
    except Exception as erro:                       # noqa: BLE001
        if aolog:
            aolog("  não deu para conferir a chave do cliente: %s" % erro)


def instalar(gravados, system, aolog=None):
    """
    Poe as tabelas geradas no cliente, guardando as originais na primeira vez.

    A copia de guarda so e feita uma vez por arquivo: na segunda instalacao o
    "original" ja seria o arquivo gerado antes, e guardar por cima apagaria a
    unica copia do que o cliente tinha de fabrica.
    """
    system = Path(system)
    # Antes de por qualquer coisa: o cliente esta na chave em que gravamos?
    # Se nao estiver, converte -- senao o cliente fica com duas chaves e o
    # jogo nao le nenhuma das duas metades.
    _garantir_chave(system, aolog)
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
    """Devolve as tabelas guardadas. Devolve a lista do que voltou."""
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


# ---------------------------------------------------------------------------
# O lado do servidor
# ---------------------------------------------------------------------------
# Os catalogos abaixo foram lidos do codigo do aCis, e nao da internet: sao os
# nomes que AQUELE servidor aceita.
#
#   Stats.java          os nomes de status
#   DocumentBase.java   as operacoes que envolvem um status
#   Item.java           as chaves <set name="...">, e a tabela SLOTS
#   MaterialType, CrystalType, WeaponType, ArmorType, EtcItemType, ActionType
#
# Um nome fora dessas listas nao e ignorado pelo servidor: ele derruba o
# carregamento da tabela de itens inteira, com NoSuchElementException. Por isso
# a tela oferece escolha em lista e nao campo livre.
TIPO_DO_GRUPO = {"weapon": "Weapon", "armor": "Armor", "etc": "EtcItem"}
TIPOS_DE_ITEM = ("Weapon", "Armor", "EtcItem")

# Como o status entra na conta. `add` soma ao valor ja calculado; `baseadd`
# soma a base antes dos multiplicadores; `set` fixa; `enchant` e a parcela que
# cresce a cada encantamento.
OPERACOES = ("add", "baseadd", "sub", "mul", "basemul", "div", "set",
             "enchant", "addMul", "subDiv")

# O `order` diz em que momento da conta o valor entra, e o servidor NAO tem
# padrao para ele: `DocumentBase.java` le o atributo sem checar se existe, e a
# carga da tabela de itens para inteira se ele faltar.
#
# Os numeros saem da contagem do datapack, e nao de palpite: `set` aparece
# 4.736 vezes com 0x08, `enchant` com 0x0C, `add` e `sub` com 0x10, `mul` com
# 0x30. Quem sabe o que esta fazendo pode trocar na tela; quem nao sabe recebe
# o que o jogo usa.
ORDEM_DA_OPERACAO = {
    "set": "0x08",        # fixa a base
    "enchant": "0x0C",    # o que cresce a cada +1, logo depois da base
    "add": "0x10",        # soma antes dos multiplicadores
    "baseadd": "0x10",
    "sub": "0x10",
    "mul": "0x30",        # multiplica
    "basemul": "0x30",
    "div": "0x30",
    "addMul": "0x30",
    "subDiv": "0x30",
}

# Soma DEPOIS dos multiplicadores. O datapack usa em 120 maxMp e alguns pDef.
# Nao e padrao de operacao nenhuma -- fica aqui para quem escolher a mao.
ORDEM_TARDIA = "0x40"

ORDENS = ("0x08", "0x0C", "0x10", "0x30", "0x40", "0x50")

# O que cada ordem significa, para a tela nao mostrar seis numeros hexa sem uma
# palavra ao lado. A descricao sai do que o datapack faz com cada uma.
O_QUE_A_ORDEM_FAZ = (
    ("0x08", "fixa o valor da base"),
    ("0x0C", "o que cresce a cada +1"),
    ("0x10", "soma antes dos multiplicadores"),
    ("0x30", "multiplica"),
    ("0x40", "soma depois dos multiplicadores"),
    ("0x50", "soma no fim de tudo (raro)"),
)

# O que cada operacao faz, na mesma ideia.
O_QUE_A_OPERACAO_FAZ = (
    ("set", "fixa o valor, ignorando o que havia"),
    ("add", "soma ao total"),
    ("sub", "subtrai do total"),
    ("baseadd", "soma à base, antes dos multiplicadores"),
    ("mul", "multiplica (1.1 = mais 10%)"),
    ("basemul", "multiplica a base"),
    ("div", "divide"),
    ("enchant", "a parcela que cresce a cada encantamento"),
    ("addMul", "soma e multiplica"),
    ("subDiv", "subtrai e divide"),
)


def com_explicacao(pares):
    """['set — fixa o valor…', …] para a caixa de escolha da tela."""
    from idioma import t
    return ["%s — %s" % (chave, t(texto)) for chave, texto in pares]


def so_a_chave(texto):
    """
    De 'set — fixa o valor…' tira 'set'. Aceita o valor cru tambem.

    Nao confia no separador: se a traducao trocar o ` — ` por outra coisa, a
    chave ainda e achada procurando na propria tabela. Uma operacao lida errada
    escreveria `<0x08 stat=...>` no XML, que nao e tag nenhuma.
    """
    bruto = str(texto or "").strip()
    if not bruto:
        return ""
    primeiro = bruto.split(" — ")[0].strip()
    conhecidas = ([c for c, _d in O_QUE_A_OPERACAO_FAZ]
                  + [c for c, _d in O_QUE_A_ORDEM_FAZ])
    if primeiro in conhecidas:
        return primeiro
    for chave in conhecidas:
        if bruto == chave or bruto.startswith(chave + " "):
            return chave
    return primeiro

# Os status, agrupados para dar para achar. O nome da esquerda e o que vai no
# XML; ele tem de sair exatamente assim.
ESTADOS = (
    ("Vida, mana e regeneração", (
        ("maxHp", "vida máxima"),
        ("maxMp", "mana máxima"),
        ("maxCp", "CP máximo"),
        ("regHp", "regeneração de vida"),
        ("regMp", "regeneração de mana"),
        ("regCp", "regeneração de CP"),
        ("gainMp", "recarga de mana"),
        ("gainHp", "cura recebida"),
        ("giveHp", "cura aplicada"),
    )),
    ("Ataque e defesa", (
        ("pAtk", "ataque físico"),
        ("mAtk", "ataque mágico"),
        ("pDef", "defesa física"),
        ("mDef", "defesa mágica"),
        ("sDef", "defesa do escudo"),
        ("pAtkSpd", "velocidade de ataque"),
        ("mAtkSpd", "velocidade de magia"),
        ("mReuse", "recarga de magia"),
        ("pReuse", "recarga física"),
        ("cAtk", "dano crítico"),
        ("cAtkAdd", "dano crítico somado"),
        ("cAtkPos", "dano crítico pelas costas"),
    )),
    ("Taxas e esquiva", (
        ("rCrit", "taxa de crítico"),
        ("mCritRate", "taxa de crítico mágico"),
        ("rEvas", "esquiva"),
        ("pSkillEvas", "esquiva de habilidade física"),
        ("accCombat", "precisão"),
        ("rShld", "taxa de bloqueio"),
        ("shieldDefAngle", "ângulo do escudo"),
        ("blowRate", "taxa de golpe furtivo"),
        ("lethalRate", "taxa de golpe letal"),
        ("cancel", "chance de cancelar"),
    )),
    ("Alcance e movimento", (
        ("pAtkRange", "alcance de ataque"),
        ("pAtkAngle", "ângulo de ataque"),
        ("atkCountMax", "alvos por golpe"),
        ("runSpd", "velocidade de corrida"),
    )),
    ("Atributos", (
        ("STR", "força"),
        ("CON", "constituição"),
        ("DEX", "destreza"),
        ("INT", "inteligência"),
        ("WIT", "sabedoria"),
        ("MEN", "mentalidade"),
        ("breath", "fôlego"),
        ("fall", "queda"),
    )),
    ("PvP", (
        ("pvpPhysDmg", "dano físico em PvP"),
        ("pvpMagicalDmg", "dano mágico em PvP"),
        ("pvpPhysSkillsDmg", "dano de habilidade em PvP"),
        ("pvpPhysSkillsDef", "defesa de habilidade em PvP"),
    )),
    ("Resistência a elementos", (
        ("fireRes", "resistência a fogo"),
        ("waterRes", "resistência a água"),
        ("windRes", "resistência a vento"),
        ("earthRes", "resistência a terra"),
        ("holyRes", "resistência sagrada"),
        ("darkRes", "resistência sombria"),
        ("valakasRes", "resistência a Valakas"),
    )),
    ("Poder de elementos", (
        ("firePower", "poder de fogo"),
        ("waterPower", "poder de água"),
        ("windPower", "poder de vento"),
        ("earthPower", "poder de terra"),
        ("holyPower", "poder sagrado"),
        ("darkPower", "poder sombrio"),
        ("valakasPower", "poder de Valakas"),
    )),
    ("Chance de efeito", (
        ("aggression", "provocação"),
        ("bleed", "sangramento"),
        ("poison", "veneno"),
        ("stun", "atordoamento"),
        ("root", "enraizamento"),
        ("movement", "lentidão"),
        ("confusion", "confusão"),
        ("sleep", "sono"),
    )),
    ("Vulnerabilidade a efeito", (
        ("bleedVuln", "a sangramento"),
        ("poisonVuln", "a veneno"),
        ("stunVuln", "a atordoamento"),
        ("paralyzeVuln", "a paralisia"),
        ("rootVuln", "a enraizamento"),
        ("sleepVuln", "a sono"),
        ("damageZoneVuln", "a zona de dano"),
        ("critVuln", "a dano crítico"),
        ("cancelVuln", "a cancelamento"),
        ("derangementVuln", "a transtorno"),
        ("debuffVuln", "a maldição"),
    )),
    ("Vulnerabilidade a arma", (
        ("swordWpnVuln", "a espada"),
        ("bluntWpnVuln", "a maça"),
        ("daggerWpnVuln", "a adaga"),
        ("bowWpnVuln", "a arco"),
        ("poleWpnVuln", "a lança"),
        ("dualWpnVuln", "a espadas duplas"),
        ("dualFistWpnVuln", "a punhos duplos"),
        ("bigSwordWpnVuln", "a espadão"),
        ("bigBluntWpnVuln", "a marreta"),
    )),
    ("Reflexo e absorção", (
        ("reflectDam", "refletir dano"),
        ("reflectSkillMagic", "refletir magia"),
        ("reflectSkillPhysic", "refletir habilidade física"),
        ("counterSkill", "contra-ataque"),
        ("absorbDam", "absorver dano"),
        ("transDam", "transferir dano"),
    )),
    ("Contra tipo de criatura", (
        ("pAtk-plants", "ataque contra plantas"),
        ("pAtk-insects", "ataque contra insetos"),
        ("pAtk-animals", "ataque contra animais"),
        ("pAtk-beasts", "ataque contra feras"),
        ("pAtk-dragons", "ataque contra dragões"),
        ("pAtk-giants", "ataque contra gigantes"),
        ("pAtk-magicCreature", "ataque contra criaturas mágicas"),
        ("pDef-plants", "defesa contra plantas"),
        ("pDef-insects", "defesa contra insetos"),
        ("pDef-animals", "defesa contra animais"),
        ("pDef-beasts", "defesa contra feras"),
        ("pDef-dragons", "defesa contra dragões"),
        ("pDef-giants", "defesa contra gigantes"),
        ("pDef-magicCreature", "defesa contra criaturas mágicas"),
    )),
    ("Limites e consumo", (
        ("weightLimit", "limite de peso"),
        ("weightPenalty", "penalidade de peso"),
        ("inventoryLimit", "espaços no inventário"),
        ("whLimit", "espaços no armazém"),
        ("FreightLimit", "espaços na entrega"),
        ("PrivateSellLimit", "espaços na loja de venda"),
        ("PrivateBuyLimit", "espaços na loja de compra"),
        ("DwarfRecipeLimit", "receitas anãs"),
        ("CommonRecipeLimit", "receitas comuns"),
        ("PhysicalMpConsumeRate", "consumo de mana físico"),
        ("MagicalMpConsumeRate", "consumo de mana mágico"),
        ("DanceMpConsumeRate", "consumo de mana em dança"),
        ("skillMastery", "maestria de habilidade"),
    )),
)

# {nome no XML: rotulo}, achatado, para a tela procurar.
ESTADOS_POR_NOME = dict((nome, rotulo)
                        for _grupo, pares in ESTADOS
                        for nome, rotulo in pares)

MATERIAIS = ("STEEL", "FINE_STEEL", "COTTON", "BLOOD_STEEL", "BRONZE",
             "SILVER", "GOLD", "MITHRIL", "ORIHARUKON", "PAPER", "WOOD",
             "CLOTH", "LEATHER", "BONE", "HORN", "DAMASCUS", "ADAMANTAITE",
             "CHRYSOLITE", "CRYSTAL", "LIQUID", "SCALE_OF_DRAGON", "DYESTUFF",
             "COBWEB")

GRAUS = ("", "D", "C", "B", "A", "S")

PARTES_DO_CORPO = ("none", "rhand", "lhand", "lrhand", "chest", "legs",
                   "chest,legs", "fullarmor", "alldress", "head", "hair",
                   "hairall", "face", "underwear", "back", "neck", "feet",
                   "gloves", "rear;lear", "rfinger;lfinger", "wolf",
                   "hatchling", "strider", "babypet")

TIPOS_DE_ARMA = ("NONE", "SWORD", "BLUNT", "DAGGER", "BOW", "POLE", "ETC",
                 "FIST", "DUAL", "DUALFIST", "BIGSWORD", "FISHINGROD",
                 "BIGBLUNT", "PET")

TIPOS_DE_ARMADURA = ("NONE", "LIGHT", "HEAVY", "MAGIC", "PET")

TIPOS_DE_ETC = ("NONE", "ARROW", "POTION", "SCRL_ENCHANT_WP",
                "SCRL_ENCHANT_AM", "SCROLL", "RECIPE", "MATERIAL",
                "PET_COLLAR", "CASTLE_GUARD", "LOTTO", "RACE_TICKET", "DYE",
                "SEED", "CROP", "MATURECROP", "HARVEST", "SEED2",
                "TICKET_OF_LORD", "LURE", "BLESS_SCRL_ENCHANT_WP",
                "BLESS_SCRL_ENCHANT_AM", "COUPON", "ELIXIR", "SHOT", "HERB",
                "QUEST")

ACOES = ("none", "equip", "calc", "call_skill", "capsule", "create_mpcc",
         "dice", "fishingshot", "harvest", "hide_name", "keep_exp",
         "nick_color", "peel", "recipe", "seed",
         "show_adventurer_guide_book", "show_html", "show_ssq_status",
         "skill_maintain", "skill_reduce", "soulshot", "spiritshot",
         "start_quest", "summon_soulshot", "summon_spiritshot", "xmas_open")


# ---------------------------------------------------------------------------
# Do numero do cliente para o nome do servidor
# ---------------------------------------------------------------------------
# O cliente guarda material, grau e parte do corpo como numeros; o servidor os
# escreve por nome. A correspondencia nao esta documentada em lugar nenhum --
# foi deduzida cruzando os 9.208 itens que existem nos dois lados: para cada id
# presente no cliente e no datapack, anotou-se o par (numero, nome). Cada
# numero abaixo caiu sempre no mesmo nome.
#
# Serve para PREENCHER a tela, nao para decidir: tudo aparece em lista e pode
# ser trocado antes de gerar.
MATERIAL_DO_CLIENTE = {
    0: "PAPER", 1: "ORIHARUKON", 2: "MITHRIL", 3: "GOLD", 4: "SILVER",
    6: "BRONZE", 8: "STEEL", 13: "WOOD", 14: "BONE", 17: "CLOTH",
    18: "PAPER", 19: "LEATHER", 23: "CRYSTAL", 33: "COTTON", 37: "COBWEB",
    38: "DYESTUFF", 46: "SCALE_OF_DRAGON", 47: "ADAMANTAITE",
    48: "BLOOD_STEEL", 49: "CHRYSOLITE", 50: "DAMASCUS", 51: "FINE_STEEL",
    52: "HORN", 53: "LIQUID",
}

# Os dois graus de cima chegaram depois: o S80 no Kamael e o S84 no Gracia
# Final. Sao chave nova, e nao significado novo -- de 1 a 5 nada mudou, o que se
# conferiu cruzando os itens do High Five com o datapack dele (289 D, 242 C,
# 455 B, 521 A, 411 S, 116 S80, 224 S84, todos sem uma unica discordancia).
GRAU_DO_CLIENTE = {0: "", 1: "D", 2: "C", 3: "B", 4: "A", 5: "S",
                   6: "S80", 7: "S84"}

PARTE_DA_ARMA = {0: "none", 7: "rhand", 8: "lhand", 14: "lrhand"}

PARTE_DA_ARMADURA = {
    0: "underwear", 1: "rear;lear", 3: "neck", 4: "rfinger;lfinger",
    6: "head", 9: "gloves", 10: "chest", 11: "legs", 12: "feet",
    13: "underwear", 15: "fullarmor", 16: "alldress", 17: "face",
    18: "hair", 19: "hairall",
}

# A partir do Gracia Final os numeros MUDARAM de significado. Nao e um campo
# novo: e o mesmo campo com outra tabela por tras, e a mudanca e silenciosa --
# o 10, que era peitoral, passou a ser o cabelo inteiro. Gerar o XML com o mapa
# antigo num cliente novo poe a peca no lugar errado, e o item simplesmente nao
# equipa.
#
# Medido cruzando o cliente do High Five com o datapack dele, item por item:
# para cada id presente nos dois, anotou-se (numero do cliente, nome do
# servidor). Entre parenteses, quantos itens sustentam cada linha.
#
#   1 rear;lear (143)   3 neck (141)    4 rfinger;lfinger (155)  6 head (254)
#   8 onepiece (172)    9 alldress (4)  10 hairall (563 de 567)  19 waist (86)
#   20 gloves (362)     21 chest (419 de 463)   22 legs (246)    23 feet (384)
#   24 back (41)        25 hair (88 de 97)      26 hair2 (43)    28 lhand (24)
#
# O 0 ficou de fora de proposito: os 463 itens que o tem se espalham por
# lbracelet (308), deco1 (100), underwear (38) e rbracelet (12). Numero que nao
# responde nada nao entra no mapa -- a tela mostra vazio e quem sabe escolhe.
PARTE_DA_ARMADURA_NOVA = {
    1: "rear;lear", 3: "neck", 4: "rfinger;lfinger", 6: "head",
    8: "onepiece", 9: "alldress", 10: "hairall", 19: "waist",
    20: "gloves", 21: "chest", 22: "legs", 23: "feet", 24: "back",
    25: "hair", 26: "hair2", 28: "lhand",
}

# A arma mudou junto, e de um jeito traicoeiro: o 7, que era a mao direita,
# passou a ser as duas maos. Medido no mesmo cruzamento:
#   0 rhand (38)   7 lrhand (2087 de 2186)   27 rhand (1590 de 1663)
#   28 lhand (171 de 172)
PARTE_DA_ARMA_NOVA = {0: "rhand", 7: "lrhand", 27: "rhand", 28: "lhand"}

# Onde a escala nova comeca. E este numero que separa as duas, porque na antiga
# ele nunca aparece: contados os onze clientes daqui, de C3 a Gracia Part 2
# nenhuma linha tem body_part entre 20 e 40, e de Gracia Final em diante sao
# mais de mil por cliente.
PRIMEIRO_CODIGO_NOVO = 20
_ULTIMO_CODIGO_NOVO = 40


def escala_da_parte(tabela):
    """
    Qual mapa de `body_part` esta tabela usa -- decidido OLHANDO a tabela.

    Nao se pergunta a cronica. Amarrar no nome dela obrigaria a lembrar deste
    arquivo a cada nucleo novo, e o esquecimento nao daria erro: daria parte do
    corpo errada, que passa despercebida ate alguem tentar equipar.

    A conta e feita uma vez por tabela e fica guardada nela.
    """
    guardado = getattr(tabela, "_escala_da_parte", None)
    if guardado is not None:
        return guardado

    nova = False
    try:
        for linha in tabela.linhas:
            numero = _inteiro(tabela.campo(linha, "body_part"), 0)
            if PRIMEIRO_CODIGO_NOVO <= numero <= _ULTIMO_CODIGO_NOVO:
                nova = True
                break
    except Exception:                               # noqa: BLE001
        nova = False
    try:
        tabela._escala_da_parte = nova
    except Exception:                               # noqa: BLE001
        pass
    return nova


def parte_do_corpo(tabela, linha, grupo):
    """
    A parte do corpo daquela linha, na lingua do servidor.

    Devolve "" quando o numero nao esta no mapa -- e melhor do que chutar, que
    foi o que poe peitoral em pulseira.
    """
    try:
        numero = _inteiro(tabela.campo(linha, "body_part"), -1)
    except Exception:                               # noqa: BLE001
        return ""
    nova = escala_da_parte(tabela)
    if grupo == "weapon":
        mapa = PARTE_DA_ARMA_NOVA if nova else PARTE_DA_ARMA
    else:
        mapa = PARTE_DA_ARMADURA_NOVA if nova else PARTE_DA_ARMADURA
    parte = mapa.get(numero, "")
    return "" if parte == "none" else parte

# A coluna weapon_type do cliente nao separa espada de espadao: as duas valem
# 1. Quem separa e o campo `handness` -- uma mao ou duas. O mesmo vale para
# maca e marreta.
#
# De 0 a 10 nada mudou de cronica para cronica. O que houve foi arma nova
# ganhando numero novo: rapieira, besta e espada ancestral no Kamael (11, 12,
# 13) e adaga dupla no Gracia Final (15). Conferido no cruzamento com o datapack
# do High Five: 239 rapieiras, 204 bestas, 192 espadas ancestrais e 22 adagas
# duplas, todas de acordo.
ARMA_DO_CLIENTE = {
    0: "NONE", 1: "SWORD", 2: "BLUNT", 3: "DAGGER", 4: "POLE", 5: "DUALFIST",
    6: "BOW", 7: "ETC", 8: "DUAL", 10: "FISHINGROD", 11: "RAPIER",
    12: "CROSSBOW", 13: "ANCIENTSWORD", 15: "DUALDAGGER",
}
ARMA_DE_DUAS_MAOS = {"SWORD": "BIGSWORD", "BLUNT": "BIGBLUNT"}

# O `SIGIL` -- o "escudo" do mago -- chegou no Gracia Final, como numero novo.
ARMADURA_DO_CLIENTE = {0: "NONE", 1: "LIGHT", 2: "HEAVY", 3: "MAGIC",
                       4: "SIGIL"}


def _inteiro(texto, padrao=0):
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao


def campos_do_servidor(itens, grupo, linha):
    """
    O que da para aproveitar da linha do cliente para o XML do servidor.

    Peso, material, grau e parte do corpo estao na tabela do cliente, e sao os
    mesmos do servidor -- so mudam de escrita. Preencher isso poupa o trabalho
    de copiar a mao e, principalmente, evita o erro silencioso de escrever o
    numero onde o servidor espera o nome.

    O que NAO sai do cliente -- dano, defesa, preco -- fica em branco. Um item
    que existe e esta errado e pior do que um item que precisa ser completado.
    """
    tabela = itens.tabelas[grupo]

    def campo(nome, padrao=""):
        try:
            return tabela.campo(linha, nome)
        except Exception:
            return padrao

    # Valor que é o padrão do servidor sai em branco, e não escrito: o item
    # se comporta igual e o XML fica legível. Peso zero, parte "none" e tipo
    # "NONE" são exatamente isso.
    peso = campo("weight", "") or ""
    dados = {
        "tipo": TIPO_DO_GRUPO.get(grupo, "EtcItem"),
        "default_action": "equip" if grupo != "etc" else "",
        "weight": "" if _inteiro(peso, 0) == 0 else peso,
        "material": MATERIAL_DO_CLIENTE.get(_inteiro(campo("material"), -1), ""),
        "price": "",
        "crystal_type": GRAU_DO_CLIENTE.get(
            _inteiro(campo("crystal_type" if grupo != "etc" else "grade"), 0), ""),
        "bodypart": "",
    }

    if grupo == "weapon":
        # A escala do `body_part` mudou no Gracia Final, e quem decide qual
        # vale e a propria tabela. Ver `escala_da_parte`.
        parte = parte_do_corpo(tabela, linha, grupo) or "rhand"
        dados["bodypart"] = "" if parte == "none" else parte
        # O escudo mora no weapongrp do cliente, mas para o servidor ele e
        # Armor -- sem excecao: os 95 escudos deste cliente sao todos Armor no
        # datapack, e todos tem body_part 8 (mao esquerda). Gerar um escudo
        # como Weapon faria o personagem empunha-lo como arma.
        if parte == "lhand":
            dados["tipo"] = "Armor"
            dados["armor_type"] = ""
        tipo = ARMA_DO_CLIENTE.get(_inteiro(campo("weapon_type"), -1), "NONE")
        # O BIGSWORD/BIGBLUNT so existe na geracao antiga. Do Gracia Final em
        # diante quem diz que a arma e de duas maos e a parte do corpo
        # (`lrhand`), e o tipo continua SWORD: cruzando o High Five com o
        # datapack dele, as 857 armas de weapon_type 1 sao SWORD sem excecao, e
        # subir 401 macas para BIGBLUNT era inventar um tipo que aquele servidor
        # nao conhece.
        if not escala_da_parte(tabela) and _inteiro(campo("handness"), 1) >= 2:
            tipo = ARMA_DE_DUAS_MAOS.get(tipo, tipo)
        dados["weapon_type"] = "" if tipo == "NONE" else tipo
        for chave, coluna in (("random_damage", "random_damage"),
                              ("soulshots", "SS_count"),
                              ("spiritshots", "SPS_count"),
                              ("mp_consume", "mp_consume")):
            valor = campo(coluna, "") or ""
            dados[chave] = "" if _inteiro(valor, 0) == 0 else valor
    elif grupo == "armor":
        dados["bodypart"] = parte_do_corpo(tabela, linha, grupo)
        tipo = ARMADURA_DO_CLIENTE.get(_inteiro(campo("armor_type"), -1), "NONE")
        dados["armor_type"] = "" if tipo == "NONE" else tipo
    else:
        dados["etcitem_type"] = ""
        if campo("stackable") == "2":
            dados["is_stackable"] = "true"

    return dados


# A ordem em que os campos saem no XML. Fora desta lista nada e escrito -- e o
# que impede um campo inventado de derrubar a tabela de itens do servidor.
ORDEM_DOS_CAMPOS = ("default_action", "weapon_type", "armor_type",
                    "etcitem_type", "bodypart", "random_damage",
                    "material", "weight", "price", "crystal_type",
                    "crystal_count", "soulshots", "spiritshots",
                    "mp_consume", "mp_consume_reduce", "reduced_soulshot",
                    "reuse_delay", "is_magical",
                    "item_skill", "enchant4_skill",
                    "oncrit_skill", "oncrit_chance",
                    "oncast_skill", "oncast_chance",
                    "is_stackable", "is_tradable", "is_dropable",
                    "is_sellable", "is_destroyable", "is_depositable",
                    "is_oly_restricted", "handler", "duration",
                    # Do Kamael em diante: diz que o item aceita pedra de
                    # atributo. Sao 1.110 itens no datapack do High Five.
                    "element_enabled")

# As skills que um item carrega. Nao ha `<skill>` dentro de `<item>` neste
# core -- sao `<set>`, com o valor escrito "id-nivel".
SKILLS_DO_ITEM = (
    ("item_skill", "enquanto equipado", None),
    ("enchant4_skill", "a partir do +4", None),
    ("oncrit_skill", "ao dar crítico", "oncrit_chance"),
    ("oncast_skill", "ao castar", "oncast_chance"),
)

# A que exige chance junto: sem ela o core descarta em silencio.
CHANCE_DA_SKILL = dict((campo, chance) for campo, _r, chance in SKILLS_DO_ITEM
                       if chance)

# Campo que so existe num tipo de item. O escudo sai do weapongrp do cliente
# levando junto soulshots e dano aleatorio; escritos num <item type="Armor">
# eles nao dao erro -- o servidor so nunca os le, e ficam no arquivo dando a
# entender que fazem alguma coisa.
CAMPOS_DO_TIPO = {
    "Weapon": ("weapon_type", "random_damage", "soulshots", "spiritshots",
               "mp_consume", "mp_consume_reduce", "reduced_soulshot",
               "is_magical", "enchant4_skill", "oncrit_skill",
               "oncrit_chance", "oncast_skill", "oncast_chance"),
    "Armor": ("armor_type",),
    "EtcItem": ("etcitem_type", "handler"),
}
_EXCLUSIVOS = set(c for campos in CAMPOS_DO_TIPO.values() for c in campos)


def xml_servidor(ident, nome, grupo, id_base, campos=None, estados=(),
                 tipo=None, extras="", sets_de_fora=None, do_servidor=()):
    """
    O item em XML, no formato do aCis.

    O cliente sozinho nao faz item nenhum existir: ele so sabe desenhar o que o
    servidor mandar. O id amarra os dois -- e o mesmo que o cliente procura no
    weapongrp/armorgrp/etcitemgrp.

    `campos` sao os <set name="..."> e `estados` a lista de
    {operacao, estado, valor}, que vira o bloco <for>. Campo vazio nao e
    escrito: o servidor tem padrao para todos, e escrever "" onde ele espera um
    numero derruba o carregamento.

    `extras` e o que o item tinha no servidor e esta tela nao edita -- a
    condicao de uso, o bonus de conjunto, o que o core daquele pack inventou.
    Vem de `l2servidor.extras_do_corpo` e sai aqui igual ao que entrou: um item
    regravado sem isso perde a condicao de raca ou de classe e passa a servir a
    qualquer um, sem nada avisando.

    `sets_de_fora` sao os `<set>` do servidor que esta tela nao mostra. Cada
    cronica trouxe campo novo -- o `element_enabled` do atributo, o
    `is_premium`, o `attack_range` -- e a tela conhece os de sempre. Escrever so
    os conhecidos fazia o item voltar ao servidor sem icone e sem alcance.

    `do_servidor` sao os nomes que vieram lidos de la. O filtro de
    `CAMPOS_DO_TIPO` existe para o item NOVO, que herda colunas do grupo do
    cliente e nao deveria sair com tiro dentro de uma armadura; para o item que
    ja estava no servidor ele estava atrapalhando -- no High Five ha armadura
    com `enchant4_skill` e ha EtcItem com `weapon_type`, e regravar apagava
    justamente isso.
    """
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<list>']
    linhas.append('\t<!-- Gerado pelo L2PackTool. Item base copiado no '
                  'cliente: %s -->' % id_base)
    campos = campos or {}
    # O tipo nao sai so do grupo: o escudo mora no weapongrp do cliente e e
    # Armor para o servidor. Quem escolhe e a tela, que ja sabe disso.
    tipo = tipo or campos.get("tipo") or TIPO_DO_GRUPO.get(grupo, "EtcItem")
    linhas.append('\t<item id="%s" type="%s" name="%s">'
                  % (ident, tipo, _escapar(nome or ("Item %s" % ident))))

    do_tipo = CAMPOS_DO_TIPO.get(tipo, ())
    escritos = set()
    for chave in ORDEM_DOS_CAMPOS:
        if (chave in _EXCLUSIVOS and chave not in do_tipo
                and chave not in do_servidor):
            continue
        valor = str(campos.get(chave, "")).strip()
        if valor:
            escritos.add(chave)
            linhas.append('\t\t<set name="%s" val="%s" />'
                          % (chave, _escapar(valor)))

    for chave, valor in (sets_de_fora or {}).items():
        valor = str(valor).strip()
        if valor and chave not in escritos and chave != "tipo":
            linhas.append('\t\t<set name="%s" val="%s" />'
                          % (chave, _escapar(valor)))

    validos = [e for e in estados if str(e.get("valor", "")).strip()]
    if validos:
        linhas.append('\t\t<for>')
        for entrada in validos:
            operacao = entrada.get("operacao", "add")
            # O `order` e obrigatorio: o servidor le o atributo sem checar se
            # existe. Escrever sempre, com o padrao da operacao quando a tela
            # nao mandou outro, e o que impede o item de derrubar a carga.
            ordem = (str(entrada.get("ordem", "")).strip()
                     or ORDEM_DA_OPERACAO.get(operacao, "0x10"))
            linhas.append('\t\t\t<%s order="%s" stat="%s" val="%s" />'
                          % (operacao, ordem, entrada.get("estado", ""),
                             str(entrada.get("valor", "")).strip()))
        linhas.append('\t\t</for>')

    if extras:
        import l2servidor

        linhas.append(l2servidor.recuar(extras, "\t\t"))

    linhas.append('\t</item>')
    linhas.append('</list>')
    return "\n".join(linhas) + "\n"


# (coluna do cliente, rotulo, status do servidor, operacao)
#
# `operacao` None quer dizer que o par do servidor nao e status do `<for>` e sim
# um `<set name=...>` do corpo do item -- peso, tiro, mana. "sinal" quer dizer
# que o proprio numero decide: negativo e `sub`, positivo e `add`.
NUMEROS_DA_ARMA = (
    ("patt", "dano físico", "pAtk", "set"),
    ("matt", "dano mágico", "mAtk", "set"),
    ("critical", "crítico", "rCrit", "set"),
    ("speed", "velocidade de ataque", "pAtkSpd", "set"),
    ("hit_mod", "precisão", "accCombat", "sinal"),
    ("avoid_mod", "evasão", "rEvas", "sinal"),
    ("shield_pdef", "defesa do escudo", "sDef", "set"),
    ("shield_rate", "chance de bloquear", "rShld", "set"),
    ("random_damage", "dano aleatório", "random_damage", None),
    ("mp_consume", "mana por golpe", "mp_consume", None),
    ("SS_count", "soulshots", "soulshots", None),
    ("SPS_count", "spiritshots", "spiritshots", None),
    ("weight", "peso", "weight", None),
)

COLUNAS_DA_ARMA = tuple(c for c, _r, _s, _o in NUMEROS_DA_ARMA)


def numeros_da_arma(itens, ident):
    """
    O que o `weapongrp.dat` diz desta arma. {coluna: texto}.

    E o que a tooltip do inventario mostra -- nao o que o golpe faz.
    """
    tabela = itens.tabelas.get("weapon")
    if tabela is None:
        raise ErroDeItem("este cliente nao tem weapongrp aberto.")
    linha = tabela.por_chave(str(ident), COLUNA_ID["weapon"])
    if linha is None:
        raise ErroDeItem("a arma %s nao esta no weapongrp." % ident)
    return dict((coluna, tabela.campo(linha, coluna).strip())
                for coluna in COLUNAS_DA_ARMA
                if coluna in tabela.cabecalho)


def aplicar_numeros_da_arma(itens, ident, valores):
    """
    Escreve os numeros da tooltip na linha do cliente, na memoria.

    Quem grava e `Itens.gravar`, com a mesma prova de ciclo das outras telas.
    Campo que nao veio nao e tocado: nao escrever e diferente de escrever zero.
    """
    tabela = itens.tabelas.get("weapon")
    if tabela is None:
        raise ErroDeItem("este cliente nao tem weapongrp aberto.")
    linha = tabela.por_chave(str(ident), COLUNA_ID["weapon"])
    if linha is None:
        raise ErroDeItem("a arma %s nao esta no weapongrp." % ident)

    postos = []
    for coluna in COLUNAS_DA_ARMA:
        if coluna not in valores or coluna not in tabela.cabecalho:
            continue
        texto = str(valores[coluna]).strip()
        if texto == "":
            continue
        try:
            int(texto)
        except ValueError:
            raise ErroDeItem("o valor de %s (%r) nao e um numero inteiro."
                             % (coluna, texto))
        tabela.definir(linha, coluna, texto)
        postos.append(coluna)

    if postos:
        itens.alteradas.add("weapon")
    return postos


def comparar_lados(do_cliente, campos, estados):
    """
    Onde a tooltip e o golpe discordam, em portugues. Lista vazia = batem.

    Nao e erro -- os dois arquivos podem divergir de proposito. E o tipo de
    coisa que ninguem percebe sozinho, porque nenhum dos dois lados reclama.
    """
    campos = campos or {}
    por_status = {}
    for entrada in estados or ():
        nome = str(entrada.get("estado", "")).strip()
        valor = str(entrada.get("valor", "")).strip()
        if nome and valor:
            por_status[nome] = (str(entrada.get("operacao", "add")), valor)

    avisos = []
    for coluna, rotulo, alvo, operacao in NUMEROS_DA_ARMA:
        if coluna not in do_cliente:
            continue
        aqui = (do_cliente.get(coluna) or "").strip()
        if aqui == "":
            continue

        if operacao is None:
            la = str(campos.get(alvo, "")).strip()
            # Campo em branco no XML e o padrao do servidor, e nao discordancia:
            # o gerador deixa em branco de proposito o que vale zero.
            if la == "" or _inteiro(la, 0) == _inteiro(aqui, 0):
                continue
            avisos.append("%s: o cliente mostra %s e o servidor usa %s."
                          % (rotulo, aqui, la))
            continue

        if alvo not in por_status:
            continue
        op, la = por_status[alvo]
        if operacao == "sinal":
            # O cliente guarda o sinal no numero; o servidor, na operacao.
            esperado = -_inteiro(la, 0) if op == "sub" else _inteiro(la, 0)
            if _inteiro(aqui, 0) == esperado:
                continue
            avisos.append("%s: o cliente mostra %s e o servidor faz %s de %s."
                          % (rotulo, aqui, op, la))
            continue

        if _inteiro(la, 0) == _inteiro(aqui, 0):
            continue
        avisos.append("%s: o cliente mostra %s e o servidor usa %s."
                      % (rotulo, aqui, la))
    return avisos


def estados_dos_numeros(do_cliente):
    """
    Os numeros da tooltip escritos como status do servidor.

    Serve para o caminho contrario: quem ajustou a arma pelo cliente ganha o
    `<for>` correspondente sem digitar duas vezes.
    """
    saida = []
    for coluna, _rotulo, alvo, operacao in NUMEROS_DA_ARMA:
        if operacao is None or coluna not in do_cliente:
            continue
        numero = _inteiro(do_cliente.get(coluna), 0)
        if numero == 0:
            continue
        if operacao == "sinal":
            saida.append({"operacao": "sub" if numero < 0 else "add",
                          "estado": alvo, "valor": str(abs(numero))})
        else:
            saida.append({"operacao": "set", "estado": alvo,
                          "valor": str(numero)})
    return saida


def conferir_skills(campos):
    """
    O que esta errado nas skills do item, em portugues. Lista vazia = nada.

    Conferir importa aqui mais do que nos outros campos porque o core NAO
    reclama: `oncrit_skill` sem `oncrit_chance` passa pela carga sem uma linha
    de log e a arma simplesmente nao faz nada. Quem for testar vai culpar a
    skill, e nao o campo que faltou.
    """
    problemas = []
    for campo, rotulo, chance in SKILLS_DO_ITEM:
        valor = str((campos or {}).get(campo, "")).strip()
        if not valor:
            continue
        for pedaco in valor.split(";"):
            pedaco = pedaco.strip()
            if not pedaco:
                continue
            partes = pedaco.split("-")
            numeros = [p.strip().isdigit() for p in partes]
            if len(partes) != 2 or not all(numeros):
                problemas.append("%s: %r nao esta no formato id-nivel."
                                 % (campo, pedaco))
                continue
            if int(partes[0]) == 0 or int(partes[1]) == 0:
                problemas.append("%s: id e nivel tem de ser maiores que zero; "
                                 "o servidor descarta %r." % (campo, pedaco))
        if campo != "item_skill" and ";" in valor:
            problemas.append("%s so aceita UMA skill; o servidor le apenas a "
                             "primeira." % campo)
        if chance:
            quanto = str((campos or {}).get(chance, "")).strip()
            if not quanto or not quanto.isdigit() or int(quanto) <= 0:
                problemas.append(
                    "%s precisa de %s maior que zero -- sem ela o servidor "
                    "descarta a skill sem avisar." % (campo, chance))
    return problemas


def _escapar(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# O icone
# ---------------------------------------------------------------------------
_PACOTE_DE_ICONE = re.compile(r"^([A-Za-z0-9_\-]+)\.(.+)$")


def caminho_do_icone(cliente, referencia):
    """
    (pacote em disco, nome do objeto) de uma referencia "icon.xxx_i00".

    Os icones de um cliente costumam estar repartidos entre system/Icon.u e
    systextures/Icon.utx, e o cliente resolve os dois pelo mesmo nome de
    pacote. Por isso a busca devolve TODOS os candidatos: quem procura o objeto
    tem de olhar em cada um.
    """
    achado = _PACOTE_DE_ICONE.match(referencia or "")
    if not achado:
        return []

    import l2conferir
    raiz = l2conferir.raiz_do_cliente(cliente)
    nome_pacote, objeto = achado.group(1), achado.group(2).split(".")[-1]

    candidatos = []
    for pasta in ("systextures", "system", "textures"):
        diretorio = raiz / pasta
        if not diretorio.is_dir():
            continue
        for item in diretorio.iterdir():
            if (item.is_file() and item.suffix.lower() in l2conferir.EXTENSOES
                    and item.stem.lower() == nome_pacote.lower()):
                candidatos.append((item, objeto))
    return candidatos


# Os pacotes que nao abriram e ja foram anunciados. Uma lista de quarenta itens
# do mesmo pacote daria quarenta linhas iguais no registro.
_JA_AVISADOS = set()


def extrair_icone(T, cliente, referencia, destino, dizer=None):
    """
    Tira o icone do pacote para um arquivo de imagem. Devolve o caminho ou None.

    Procura em todos os pacotes com aquele nome, porque um so deles tem o
    objeto -- e qual deles varia de cliente para cliente.

    Nenhum abrindo, devolve None e pronto: nao sai procurando o mesmo nome de
    objeto em outro pacote. Ha pack cujo pacote de icone vem protegido, e o
    objeto costuma existir no `Icon.u` com o mesmo nome -- mas nao ha nada que
    garanta ser a mesma arte. Mostrar a de outro pacote apagaria o unico sinal
    de que aquele pacote precisa ser resolvido.

    Quando ha `dizer`, o pacote que nao abriu e anunciado uma vez -- nao uma
    vez por icone, que numa lista de quarenta daria quarenta linhas iguais.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    candidatos = caminho_do_icone(cliente, referencia)
    for pacote, objeto in candidatos:
        try:
            gravados = motor.exportar(T, pacote, [objeto], destino)
        except Exception:
            continue
        if gravados:
            return gravados[0]

    de_onde = referencia.split(".")[0]
    if dizer and candidatos and de_onde not in _JA_AVISADOS:
        _JA_AVISADOS.add(de_onde)
        dizer("o pacote %s nao abriu; os icones dele nao vao aparecer"
              % de_onde)
    return None


def icones_do_cliente(cliente, usados=()):
    """
    Todas as referencias de icone que da para escolher neste cliente.

    Duas fontes, somadas: as que os itens ja usam -- garantidamente validas --
    e o conteudo dos pacotes chamados "icon", que traz tambem os icones
    instalados e ainda nao usados por item nenhum.

    Este cliente tem os icones repartidos entre system/Icon.u e
    systextures/Icon.utx; a soma dos dois e o que o jogo enxerga.
    """
    import l2conferir

    # A chave e a referencia em MINUSCULA, e nao a referencia como veio.
    #
    # As duas fontes escrevem o nome do pacote de jeitos diferentes: a tabela
    # guarda `icon.skill0002`, o arquivo no disco se chama `Icon.utx`. Num
    # conjunto de texto as duas grafias sao entradas distintas, e a grade
    # mostrava o MESMO desenho duas vezes, lado a lado -- porque a ordenacao e
    # por minuscula e as punha vizinhas.
    #
    # Quem chega depois ganha, e o pacote e varrido depois de proposito: a
    # grafia do arquivo e a verdadeira, a da tabela e so como alguem a
    # escreveu.
    achadas = {}
    for usado in usados:
        if usado:
            achadas[usado.lower()] = usado

    raiz = l2conferir.raiz_do_cliente(cliente)
    for pasta in ("systextures", "system", "textures"):
        diretorio = raiz / pasta
        if not diretorio.is_dir():
            continue
        for item in diretorio.iterdir():
            if (not item.is_file()
                    or item.suffix.lower() not in l2conferir.EXTENSOES
                    or not item.stem.lower().startswith("icon")):
                continue
            try:
                objetos = l2conferir.objetos_do_pacote(item)
            except Exception:
                continue
            for objeto in objetos:
                if objeto:
                    referencia = "%s.%s" % (item.stem, objeto)
                    achadas[referencia.lower()] = referencia
    return sorted(achadas.values(), key=lambda r: r.lower())


# ---------------------------------------------------------------------------
# Trocar a aparencia de um item que ja existe
# ---------------------------------------------------------------------------
def referencias_da_linha(itens, grupo, linha):
    """
    Toda coluna daquela linha que aponta para um objeto de pacote.

    Serve para trocar a aparencia sem criar item novo. Nao ha lista fixa de
    colunas porque ela muda com a tabela: a arma tem duas malhas e tres
    texturas, a armadura tem um par por combinacao de raca e sexo -- sao 96
    colunas so de aparencia no armorgrp. Procurar pelo FORMATO do valor pega
    todas sem depender de eu ter listado cada uma.
    """
    tabela = itens.tabelas[grupo]
    achadas = []
    for i, nome in enumerate(tabela.cabecalho):
        if i >= len(linha):
            break
        valor = linha[i]
        if valor and _PACOTE_DE_ICONE.match(valor) and "." in valor:
            achadas.append({"coluna": nome, "valor": valor})
    return achadas


def trocar_aparencia(itens, grupo, ident, trocas):
    """
    Grava outras referencias na linha do item, sem mexer no id.

    `trocas` e {coluna: valor novo}. Devolve quantas colunas mudaram.
    """
    linha = itens.por_id(grupo, ident)
    if linha is None:
        raise ErroDeItem("o item %s nao existe em %s." % (ident, grupo))

    tabela = itens.tabelas[grupo]
    mudou = 0
    for coluna, valor in trocas.items():
        try:
            antes = tabela.campo(linha, coluna)
        except Exception:
            raise ErroDeItem("a coluna %s nao existe em %s" % (coluna, grupo))
        if str(valor) != antes:
            tabela.definir(linha, coluna, valor)
            mudou += 1
    if mudou:
        itens.alteradas.add(grupo)
    return mudou


def trocar_pacote(referencias, de, para):
    """
    Troca o nome do pacote em todas as referencias de uma vez.

    E o que resolve um pack de retextura inteiro: o pack novo tem os mesmos
    nomes de objeto noutro pacote, e a troca e sempre o prefixo.
    """
    de, para = (de or "").strip(), (para or "").strip()
    saida = {}
    for entrada in referencias:
        valor = entrada["valor"]
        cabeca, resto = valor.split(".", 1)
        if de and cabeca.lower() != de.lower():
            continue
        saida[entrada["coluna"]] = "%s.%s" % (para or cabeca, resto)
    return saida
