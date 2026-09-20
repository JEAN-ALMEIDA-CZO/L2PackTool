#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multisell: a lista de trocas que um NPC oferece.

Uma multisell e um arquivo XML no servidor com uma serie de trocas. Cada troca
diz o que o jogador **paga** (`ingredient`) e o que ele **recebe**
(`production`), com quantidade e, se for o caso, encantamento:

    <?xml version='1.0' encoding='utf-8'?>
    <list>
        <npcs>
            <npc>30006</npc>
        </npcs>
        <item>
            <ingredient id="57" count="1000000"/>
            <production id="7575" count="1" enchant="0"/>
        </item>
    </list>

## O nome do arquivo e a chave

Isto e do core deste servidor, e nao e obvio:

    final int id = file.getName().replaceAll(".xml", "").hashCode();

O identificador da multisell e o **hashCode do nome do arquivo**, sem a
extensao. Nao ha campo de id dentro do XML. Quem abre a lista chama

    multisell <nome do arquivo>          no bypass do NPC
    exc_multisell <nome do arquivo>      so o que estiver no inventario

Entao renomear o arquivo troca a multisell de identidade, e dois arquivos com o
mesmo nome em pastas diferentes sao a MESMA multisell -- o segundo a carregar
apaga o primeiro.

## Os NPCs

    public boolean isNpcAllowed(int npcId) {
        return _npcsAllowed == null || _npcsAllowed.contains(npcId);
    }

Sem nenhum `<npc>`, **qualquer** NPC pode abrir. Com pelo menos um, so aqueles
-- e `isNpcOnly()` passa a ser verdadeiro, o que impede abrir a lista sem NPC
(de um painel da comunidade, por exemplo).

## Do lado do cliente nao ha arquivo

Multisell e inteiramente do servidor: o cliente so desenha o que o pacote
manda. O que o cliente precisa e conhecer os ITENS usados -- se um id nao
estiver nas tabelas dele, a linha aparece sem nome e sem icone. Por isso existe
`conferir`, que cruza a lista com as tabelas do cliente antes de instalar.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ASSUNTO = "multisell"

# Os atributos de `<list>`, com o que cada um significa.
OPCOES = (
    ("applyTaxes", "cobrar a taxa do castelo"),
    ("maintainEnchantment", "manter o encantamento do item dado"),
)

# Os atributos de `<ingredient>` e `<production>` que o core le.
CAMPOS = ("id", "count", "enchant")

_SO_NOME = re.compile(r"^[A-Za-z0-9_\-]+$")


class ErroDeMultisell(Exception):
    pass


# ---------------------------------------------------------------------------
# Ler
# ---------------------------------------------------------------------------
def listar(pasta):
    """
    As multisells que existem naquela pasta, com um resumo de cada uma.

    Le o arquivo inteiro para contar as trocas: um resumo que mente e pior do
    que resumo nenhum, e sao arquivos de alguns kilobytes.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []

    achadas = []
    for arquivo in sorted(pasta.glob("*.xml")):
        try:
            lista = ler(arquivo)
            achadas.append({
                "nome": arquivo.stem,
                "caminho": arquivo,
                "trocas": len(lista["trocas"]),
                "npcs": len(lista["npcs"]),
                "erro": "",
            })
        except Exception as erro:                   # noqa: BLE001
            # Arquivo que nao abre continua aparecendo na lista, com o motivo.
            # Some-lo seria esconder justamente o que precisa de atencao.
            achadas.append({"nome": arquivo.stem, "caminho": arquivo,
                            "trocas": 0, "npcs": 0, "erro": str(erro)[:120]})
    return achadas


def ler(caminho):
    """
    Uma multisell lida do arquivo.

    Devolve {"nome", "npcs", "opcoes", "trocas"}, onde cada troca e
    {"paga": [...], "recebe": [...], "comentario"} e cada lado e uma lista de
    {"id", "count", "enchant"}.
    """
    caminho = Path(caminho)
    try:
        arvore = ET.parse(str(caminho))
    except ET.ParseError as erro:
        raise ErroDeMultisell("o XML nao esta bem formado: %s" % erro)

    raiz = arvore.getroot()
    if raiz.tag.lower() != "list":
        raise ErroDeMultisell("a raiz e <%s>, e deveria ser <list>." % raiz.tag)

    opcoes = {}
    for chave, _rotulo in OPCOES:
        valor = raiz.get(chave)
        if valor is not None:
            opcoes[chave] = str(valor).strip().lower() in ("1", "true", "yes")

    npcs = []
    for bloco in raiz.findall("npcs"):
        for no in bloco.findall("npc"):
            texto = (no.text or "").strip()
            if texto.isdigit():
                npcs.append(texto)

    trocas = []
    for item in raiz.findall("item"):
        troca = {"paga": [], "recebe": [], "comentario": ""}
        for no in item:
            nome = (no.tag or "").lower()
            if nome == "ingredient":
                troca["paga"].append(_lado(no))
            elif nome == "production":
                troca["recebe"].append(_lado(no))
        if troca["paga"] or troca["recebe"]:
            trocas.append(troca)

    return {"nome": caminho.stem, "npcs": npcs, "opcoes": opcoes,
            "trocas": trocas}


def _lado(no):
    """Um `<ingredient>` ou `<production>` como dicionario."""
    saida = {}
    for campo in CAMPOS:
        valor = no.get(campo)
        if valor is not None and str(valor).strip() != "":
            saida[campo] = str(valor).strip()
    saida.setdefault("count", "1")
    return saida


def vazia(nome=""):
    """Uma multisell nova, sem troca nenhuma."""
    return {"nome": nome, "npcs": [], "opcoes": {}, "trocas": []}


# ---------------------------------------------------------------------------
# Escrever
# ---------------------------------------------------------------------------
def xml(lista, nomes=None):
    """
    A multisell em XML, no formato deste servidor.

    `nomes` e {id: nome do item}, so para escrever o comentario ao lado de cada
    linha. Sem ele o arquivo continua valido -- o comentario e para quem for
    abrir depois, e um XML de trocas so com numeros e ilegivel.
    """
    nomes = nomes or {}
    linhas = ["<?xml version='1.0' encoding='utf-8'?>"]

    atributos = []
    for chave, _rotulo in OPCOES:
        if lista.get("opcoes", {}).get(chave):
            atributos.append('%s="true"' % chave)
    linhas.append("<list%s>" % ("".join(" " + a for a in atributos)))

    if lista.get("npcs"):
        linhas.append("\t<npcs>")
        for npc in lista["npcs"]:
            linhas.append("\t\t<npc>%s</npc>" % npc)
        linhas.append("\t</npcs>")
    else:
        # Sem `<npcs>` qualquer NPC abre. Dizer isso no arquivo evita que
        # alguem olhe depois e ache que a secao se perdeu.
        linhas.append("\t<!-- sem <npcs>: qualquer NPC pode abrir esta "
                      "lista -->")

    for troca in lista.get("trocas") or []:
        comentario = troca.get("comentario") or _resumo(troca, nomes)
        if comentario:
            linhas.append("\t<!-- %s -->" % _comentario(comentario))
        linhas.append("\t<item>")
        for lado, etiqueta in (("paga", "ingredient"), ("recebe", "production")):
            for parte in troca.get(lado) or []:
                linhas.append("\t\t<%s %s/>" % (etiqueta, _atributos(parte)))
        linhas.append("\t</item>")

    linhas.append("</list>")
    return "\n".join(linhas) + "\n"


def _atributos(parte):
    """`id="57" count="100"`, na ordem que o arquivo usa. Sem enchant zero."""
    saida = []
    for campo in CAMPOS:
        valor = str(parte.get(campo, "")).strip()
        if not valor:
            continue
        if campo == "enchant" and valor in ("0", "0.0"):
            continue        # o padrao do core; escrever zero e ruido
        saida.append('%s="%s"' % (campo, _escapar(valor)))
    return " ".join(saida)


def _resumo(troca, nomes):
    """`1000 Adena -> 1 Scroll of Escape`, para o comentario."""
    def lado(qual):
        partes = []
        for p in troca.get(qual) or []:
            nome = nomes.get(str(p.get("id"))) or ("item %s" % p.get("id"))
            partes.append("%s %s" % (p.get("count", "1"), nome))
        return " + ".join(partes)

    paga, recebe = lado("paga"), lado("recebe")
    if paga and recebe:
        return "%s -> %s" % (paga, recebe)
    return paga or recebe


def _comentario(texto):
    """
    Um comentario XML seguro.

    Nao leva escape de entidade -- `&` e `>` sao literais dentro de comentario,
    e escapa-los so deixa `-&gt;` no lugar de `->`. O que ele nao aceita e `--`
    no meio: aquilo fecha o comentario antes da hora e quebra o arquivo.
    """
    limpo = str(texto)
    while "--" in limpo:                # tres tracos ou mais, numa passada so
        limpo = limpo.replace("--", "-")
    return limpo.strip().rstrip("-").strip()


def _escapar(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# Conferir
# ---------------------------------------------------------------------------
def nome_valido(nome):
    """O nome do arquivo serve como chave? Devolve o motivo, ou ''."""
    nome = (nome or "").strip()
    if not nome:
        return "o nome nao pode ficar vazio."
    if not _SO_NOME.match(nome):
        return ("use so letras, numeros, `-` e `_`: o nome vira o "
                "identificador da lista, e o bypass do NPC nao aceita "
                "espaco.")
    return ""


def conferir(lista, itens=None, nomes_existentes=()):
    """
    O que esta errado nesta multisell, em portugues. Lista vazia = nada.

    `itens` e um `l2item.Itens` aberto: com ele da para dizer que um id nao
    existe no cliente, que e o defeito que mais aparece -- a linha sai sem nome
    e sem icone, e ninguem sabe por que.
    """
    problemas = []

    motivo = nome_valido(lista.get("nome"))
    if motivo:
        problemas.append(motivo)
    elif lista["nome"] in nomes_existentes:
        problemas.append("ja existe uma multisell chamada %r. O nome e a "
                         "chave: duas com o mesmo nome sao a mesma lista, e "
                         "a segunda a carregar apaga a primeira."
                         % lista["nome"])

    if not lista.get("trocas"):
        problemas.append("a lista nao tem troca nenhuma.")

    conhecidos = None
    if itens is not None:
        try:
            conhecidos = set(str(i["id"]) for i in itens.listar())
        except Exception:                           # noqa: BLE001
            conhecidos = None

    for numero, troca in enumerate(lista.get("trocas") or [], 1):
        if not troca.get("paga"):
            problemas.append("troca %d: nao diz o que o jogador paga." % numero)
        if not troca.get("recebe"):
            problemas.append("troca %d: nao diz o que o jogador recebe."
                             % numero)
        for qual, rotulo in (("paga", "paga"), ("recebe", "recebe")):
            for parte in troca.get(qual) or []:
                ident = str(parte.get("id", "")).strip()
                if not ident.isdigit() or int(ident) <= 0:
                    problemas.append("troca %d (%s): id %r nao e um numero."
                                     % (numero, rotulo, ident))
                    continue
                conta = str(parte.get("count", "")).strip()
                if not conta.isdigit() or int(conta) <= 0:
                    problemas.append("troca %d (%s): a quantidade do item %s "
                                     "tem de ser maior que zero."
                                     % (numero, rotulo, ident))
                if conhecidos is not None and ident not in conhecidos:
                    problemas.append("troca %d (%s): o item %s nao existe nas "
                                     "tabelas do cliente -- a linha apareceria "
                                     "sem nome e sem icone."
                                     % (numero, rotulo, ident))
    return problemas


# ---------------------------------------------------------------------------
# Instalar
# ---------------------------------------------------------------------------
def gravar(texto, pasta, nome):
    """Escreve a multisell em `pasta/nome.xml`. Devolve o caminho."""
    motivo = nome_valido(nome)
    if motivo:
        raise ErroDeMultisell(motivo)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / ("%s.xml" % nome)
    alvo.write_text(texto, encoding="utf-8")
    return alvo


def bypass(nome, so_inventario=False):
    """O comando que abre esta lista, para pôr no HTML do NPC."""
    return "%s %s" % ("exc_multisell" if so_inventario else "multisell", nome)
