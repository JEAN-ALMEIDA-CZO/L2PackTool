#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conjunto de armadura: as duas metades do mesmo assunto.

O jogador le "P. Def. +2% e HP maximo +41" no fim da descricao do peitoral e
ganha a habilidade quando veste as pecas todas. Sao duas coisas diferentes, em
lugares diferentes:

  * o CLIENTE guarda a lista de pecas e o TEXTO do bonus no `itemname-e`, e e
    so isso -- ele desenha a frase, nao aplica nada;
  * o SERVIDOR e quem aplica: ele tem a propria lista de conjuntos, com a
    habilidade que cada um concede.

Mexer so num dos dois da o erro classico: a frase aparece e o bonus nao vem, ou
o bonus vem e ninguem entende de onde. Por isso este modulo faz os dois lados.

## Onde fica, no cliente

Contado nos dez clientes que estao aqui, ha duas formas e um vazio:

    C3, C4            a coluna nao existe -- esta cronica nao tem conjunto
                      escrito no itemname
    C5 .. Gracia 2    UMA coluna `set_ids`, em texto: "a,23,2386,43\\0"
    Gracia Final ..   uma coluna POR PECA (`set_ids[0]`, `set_ids[1]`...) com
    High Five         um contador ao lado (`cnt0`, `supercnt0`)

E a lista vai numa peca so. Das 207 linhas com conjunto do High Five, 195 tem o
proprio id como primeiro da lista, e apenas 8 das 691 pecas apontadas por
alguma lista levam lista propria. Quem carrega o conjunto e o peitoral; as
outras pecas nao repetem nada. Escrever em todas seria inventar um dado que o
jogo original nao tem.

## Onde fica, no servidor

Tambem duas formas, medidas em dois datapacks de verdade:

    L2J (High Five)   data/stats/armorsets/*.xml, com `<set id="N">` e um filho
                      por parte -- e mais de um id na mesma parte, quando a
                      peca tem versao alternativa
    aCis (Interlude)  data/xml/armorSets.xml, uma linha por conjunto:
                      `<armorset name= chest= legs= head= ... skillId= />`

A forma nao se escolhe em menu: le-se a pasta do servidor e se ve qual esta
ali. Servidor que nao tem nem uma nem outra recebe a forma do perfil.
"""

import re
from pathlib import Path

import l2item

# A ordem e a que o datapack escreve, nao a alfabetica: e a ordem em que a
# pessoa veste.
PARTES = ("chest", "legs", "head", "gloves", "feet", "shield")

# O `body_part` do cliente, traduzido para a parte do conjunto. A armadura
# inteira conta como peitoral -- e o que o servidor faz com ela -- e o escudo
# chega pela mao esquerda, porque no cliente ele mora no weapongrp.
PARTE_DO_CONJUNTO = {
    "chest": "chest", "fullarmor": "chest", "alldress": "chest",
    "legs": "legs", "head": "head", "gloves": "gloves", "feet": "feet",
    "lhand": "shield",
}

# Quantas pecas o formato em coluna aguenta vem medido do arquivo. Este numero
# so serve para a mensagem de erro dizer algo util quando nem isso existe.
PECAS_MINIMAS = 2

ARQUIVO_ACIS = "armorSets.xml"
PASTA_L2J = "armorsets"

_SET_L2J = re.compile(r"<set\b[^>]*\bid\s*=\s*[\"'](\d+)[\"']", re.I)
_ARMORSET_ACIS = re.compile(r"<armorset\b", re.I)


class ErroDeConjunto(Exception):
    pass


# ---------------------------------------------------------------------------
# O lado do cliente
# ---------------------------------------------------------------------------
def colunas(tabela):
    """
    Onde este `itemname-e` guarda o conjunto.

    Devolve {"ids": [nomes de coluna], "contadores": [...], "descricao": nome,
    "extras": [...], "contadores_extras": [...], "descricao_extra": nome}.
    Lista de ids vazia quer dizer que a cronica nao tem conjunto no itemname --
    e o caso do C3 e do C4.
    """
    cabecalho = list(getattr(tabela, "cabecalho", []))
    achado = {"ids": [], "contadores": [], "descricao": "",
              "extras": [], "contadores_extras": [], "descricao_extra": ""}
    for nome in cabecalho:
        cru = nome.split("[")[0]
        if cru == "set_ids":
            achado["ids"].append(nome)
        elif cru in ("set_extra_ids", "set_extra_id"):
            achado["extras"].append(nome)
        elif cru == "set_bonus_desc":
            achado["descricao"] = nome
        elif cru == "set_extra_desc":
            achado["descricao_extra"] = nome
        elif cru in ("cnt0", "supercnt0"):
            achado["contadores"].append(nome)
        elif cru in ("cnt1", "supercnt1"):
            achado["contadores_extras"].append(nome)
    return achado


def tem_conjunto(itens):
    """Esta cronica escreve conjunto no itemname?"""
    return bool(colunas(itens.tabelas["nome"])["ids"])


def _em_coluna(onde):
    """
    Uma coluna por peca (Gracia Final em diante) ou uma so, com virgulas?

    Quem decide e o CONTADOR ao lado, nao quantas colunas apareceram. Um
    cliente pode ter medido uma coluna so porque nenhum conjunto dele passa de
    uma peca, e ali a lista continua sendo uma lista -- com o contador dizendo
    quantas valem.
    """
    return bool(onde["contadores"]) or len(onde["ids"]) > 1


def _vazio_de_coluna():
    """
    O que fica na coluna de peca que sobrou.

    Medido: nos clientes de Gracia Final em diante, a peca que nao existe fica
    com a coluna VAZIA -- nao com zero. Escrever "0" ali faz o montador recusar
    a tabela inteira, e a queixa dele nao diz qual campo.
    """
    return ""


def _texto_guardado(texto):
    """
    O texto como o arquivo o guarda: pagina de codigo na frente, zero no fim.

    Contadas as linhas com conjunto dos dez clientes, TODAS tem o `a,` e todas
    -- fora as do C5 mais antigo -- terminam em `\\0`. Escrever sem isso poe o
    proprio prefixo na tela do jogador, ou deixa o texto emendado no seguinte.
    """
    limpo = l2item._limpar(str(texto or "")).strip()
    return "a,%s\\0" % limpo if limpo else "a,"


def _ler_lista(tabela, linha, onde):
    """Os ids da lista de pecas daquela linha, em ordem."""
    if _em_coluna(onde):
        saida = []
        for nome in onde["ids"]:
            try:
                valor = str(tabela.campo(linha, nome)).strip()
            except Exception:                       # noqa: BLE001
                continue
            if valor and valor != "0":
                saida.append(valor)
        return saida
    try:
        cru = l2item._limpar(str(tabela.campo(linha, onde["ids"][0])))
    except Exception:                               # noqa: BLE001
        return []
    return [p.strip() for p in cru.replace(";", ",").split(",") if p.strip()]


def _extra_em_coluna(onde):
    """O mesmo, para a peca extra: `cnt1` ao lado quer dizer lista."""
    return bool(onde["contadores_extras"]) or len(onde["extras"]) > 1


def _ler_extras(tabela, linha, onde):
    if not onde["extras"]:
        return []
    if _extra_em_coluna(onde):
        saida = []
        for nome in onde["extras"]:
            try:
                valor = str(tabela.campo(linha, nome)).strip()
            except Exception:                       # noqa: BLE001
                continue
            if valor and valor != "0":
                saida.append(valor)
        return saida
    try:
        cru = l2item._limpar(str(tabela.campo(linha, onde["extras"][0])))
    except Exception:                               # noqa: BLE001
        return []
    return [p.strip() for p in cru.replace(";", ",").split(",") if p.strip()]


def _ler_texto(tabela, linha, nome):
    if not nome:
        return ""
    try:
        return l2item._limpar(str(tabela.campo(linha, nome))).strip()
    except Exception:                               # noqa: BLE001
        return ""


def do_item(itens, ident):
    """
    O conjunto escrito NAQUELE item, ou None.

    `None` nao quer dizer que o item nao pertence a conjunto nenhum: quer dizer
    que nao e ele que carrega a lista. Quem procura pelo outro lado usa
    `onde_aparece`.
    """
    tabela = itens.tabelas["nome"]
    onde = colunas(tabela)
    if not onde["ids"]:
        return None
    linha = tabela.por_chave(str(ident))
    if linha is None:
        return None
    pecas = _ler_lista(tabela, linha, onde)
    if not pecas:
        return None
    return {"dono": str(ident), "pecas": pecas,
            "descricao": _ler_texto(tabela, linha, onde["descricao"]),
            "extras": _ler_extras(tabela, linha, onde),
            "descricao_extra": _ler_texto(tabela, linha,
                                          onde["descricao_extra"])}


def listar(itens):
    """Todos os conjuntos escritos neste cliente, na ordem do id."""
    tabela = itens.tabelas["nome"]
    onde = colunas(tabela)
    if not onde["ids"]:
        return []
    coluna_id = l2item.coluna_do_id(tabela, "nome")
    saida = []
    for linha in tabela.linhas:
        pecas = _ler_lista(tabela, linha, onde)
        if not pecas:
            continue
        saida.append({"dono": linha[coluna_id], "pecas": pecas,
                      "descricao": _ler_texto(tabela, linha,
                                              onde["descricao"]),
                      "extras": _ler_extras(tabela, linha, onde),
                      "descricao_extra": _ler_texto(
                          tabela, linha, onde["descricao_extra"])})
    saida.sort(key=lambda c: int(c["dono"] or 0))
    return saida


def onde_aparece(itens, ident):
    """Os conjuntos que citam este item, mesmo que ele nao carregue a lista."""
    procurado = str(ident)
    return [c for c in listar(itens)
            if procurado in c["pecas"] or procurado in c["extras"]]


def cabem(itens):
    """Quantas pecas a lista deste cliente aguenta."""
    onde = colunas(itens.tabelas["nome"])
    if not onde["ids"]:
        return 0
    # Uma coluna de texto nao tem limite de contagem; a de colunas tem o que o
    # arquivo mediu.
    return len(onde["ids"]) if _em_coluna(onde) else 0


def escrever(itens, dono, pecas, descricao="", extras=(), descricao_extra=""):
    """
    Grava o conjunto na linha do `dono`, no itemname que esta na memoria.

    Nao toca no cliente: quem grava em disco e o `Itens.gravar`, e quem instala
    e o `l2item.instalar` -- os mesmos de sempre, para o conjunto seguir o
    caminho que o resto do programa ja usa.
    """
    tabela = itens.tabelas["nome"]
    onde = colunas(tabela)
    if not onde["ids"]:
        raise ErroDeConjunto(
            "esta cronica nao guarda conjunto no itemname-e: a coluna "
            "`set_ids` nao existe nesta tabela.")

    linha = tabela.por_chave(str(dono))
    if linha is None:
        raise ErroDeConjunto("o item %s nao esta no itemname-e." % dono)

    limpas = [str(p).strip() for p in pecas if str(p).strip()]
    if len(limpas) < PECAS_MINIMAS:
        raise ErroDeConjunto("um conjunto precisa de pelo menos %d pecas."
                             % PECAS_MINIMAS)
    if len(set(limpas)) != len(limpas):
        raise ErroDeConjunto("ha peca repetida na lista.")

    limite = cabem(itens)
    if limite and len(limpas) > limite:
        raise ErroDeConjunto(
            "este cliente guarda no maximo %d pecas por conjunto -- a tabela "
            "dele tem %d colunas de peca. Tire %d."
            % (limite, limite, len(limpas) - limite))

    extras_limpos = [str(p).strip() for p in extras if str(p).strip()]
    limite_extra = len(onde["extras"]) if _extra_em_coluna(onde) else 0
    if limite_extra and len(extras_limpos) > limite_extra:
        raise ErroDeConjunto(
            "este cliente guarda no maximo %d peca(s) extra por conjunto."
            % limite_extra)

    if _em_coluna(onde):
        for i, nome in enumerate(onde["ids"]):
            tabela.definir(linha, nome, limpas[i] if i < len(limpas)
                           else _vazio_de_coluna())
        # O contador e que diz ao cliente quantas colunas ler. Deixa-lo no
        # numero antigo mostraria peca a menos, ou leria coluna que ficou para
        # tras da lista anterior.
        for nome in onde["contadores"]:
            tabela.definir(linha, nome, str(len(limpas)))
    else:
        tabela.definir(linha, onde["ids"][0],
                       _texto_guardado(",".join(limpas)))

    if onde["descricao"]:
        tabela.definir(linha, onde["descricao"], _texto_guardado(descricao))

    if onde["extras"]:
        if _extra_em_coluna(onde):
            for i, nome in enumerate(onde["extras"]):
                tabela.definir(linha, nome,
                               extras_limpos[i] if i < len(extras_limpos)
                               else _vazio_de_coluna())
            for nome in onde["contadores_extras"]:
                tabela.definir(linha, nome, str(len(extras_limpos)))
        else:
            tabela.definir(linha, onde["extras"][0],
                           _texto_guardado(",".join(extras_limpos))
                           if extras_limpos else "a,")
    if onde["descricao_extra"]:
        tabela.definir(linha, onde["descricao_extra"],
                       _texto_guardado(descricao_extra))

    itens.alteradas.add("nome")
    return len(limpas)


def limpar(itens, dono):
    """Apaga o conjunto da linha daquele item."""
    tabela = itens.tabelas["nome"]
    onde = colunas(tabela)
    if not onde["ids"]:
        return False
    linha = tabela.por_chave(str(dono))
    if linha is None:
        return False
    if _em_coluna(onde):
        for nome in onde["ids"]:
            tabela.definir(linha, nome, _vazio_de_coluna())
        for nome in onde["contadores"]:
            tabela.definir(linha, nome, "0")
    else:
        tabela.definir(linha, onde["ids"][0], "a,")
    for nome in [onde["descricao"], onde["descricao_extra"]]:
        if nome:
            tabela.definir(linha, nome, "a,")
    for nome in onde["extras"]:
        tabela.definir(linha, nome,
                       _vazio_de_coluna() if _extra_em_coluna(onde) else "a,")
    for nome in onde["contadores_extras"]:
        tabela.definir(linha, nome, "0")
    itens.alteradas.add("nome")
    return True


# ---------------------------------------------------------------------------
# De que parte do corpo e cada peca
# ---------------------------------------------------------------------------
def parte_de(itens, ident):
    """
    Em que parte do corpo esta peca entra, na lingua do servidor.

    Devolve "" quando o item nao existe ou nao e peca de conjunto -- um frasco
    de vida nao tem parte, e dizer "chest" nele poria lixo no XML.
    """
    grupo = itens.onde_esta(str(ident))
    if grupo is None:
        return ""
    linha = itens.por_id(grupo, str(ident))
    if linha is None:
        return ""
    # Quem sabe ler o `body_part` e o l2item: sao duas escalas de numero, e a
    # certa se decide olhando a tabela.
    return PARTE_DO_CONJUNTO.get(
        l2item.parte_do_corpo(itens.tabelas[grupo], linha, grupo), "")


def por_parte(itens, pecas, extras=()):
    """
    {parte: [ids]}, com as pecas que nao se souberam sob a chave "".

    Mais de um id na mesma parte e normal: no High Five a mesma armadura tem
    versao antiga e versao nova, e as duas valem para o conjunto.
    """
    saida = {}
    for ident in list(pecas) + list(extras):
        parte = parte_de(itens, ident)
        # O escudo vem pela mao esquerda, e e o que o servidor chama de shield.
        # Peca que a lista de extras traz e escudo por definicao, quando nao se
        # soube dizer de outra forma.
        if not parte and ident in list(extras):
            parte = "shield"
        saida.setdefault(parte, []).append(str(ident))
    return saida


# ---------------------------------------------------------------------------
# O lado do servidor
# ---------------------------------------------------------------------------
def forma_do_servidor(pasta):
    """
    Que forma de conjunto este servidor usa, medida na pasta dele.

    Devolve ("l2j"|"acis"|"", arquivo ou pasta onde foi visto). Nao se pergunta
    ao usuario o que da para ver: as duas formas sao distinguiveis a olho, uma
    tem `<set id=` dentro de uma pasta `armorsets`, a outra tem `<armorset` num
    arquivo so.
    """
    if not pasta:
        return "", None
    raiz = Path(pasta)
    if not raiz.is_dir():
        return "", None

    for alvo in sorted(raiz.rglob(PASTA_L2J)):
        if not alvo.is_dir():
            continue
        for arquivo in sorted(alvo.glob("*.xml")):
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _SET_L2J.search(texto):
                return "l2j", alvo
    for arquivo in sorted(raiz.rglob("*.xml")):
        if arquivo.name.lower() != ARQUIVO_ACIS.lower():
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _ARMORSET_ACIS.search(texto):
            return "acis", arquivo
    return "", None


def maior_id(pasta_ou_arquivo):
    """O maior `id` de conjunto que ja existe la, para o proximo nao bater."""
    maior = 0
    if not pasta_ou_arquivo:
        return maior
    alvo = Path(pasta_ou_arquivo)
    arquivos = (sorted(alvo.glob("*.xml")) if alvo.is_dir()
                else ([alvo] if alvo.is_file() else []))
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for bruto in _SET_L2J.findall(texto):
            try:
                maior = max(maior, int(bruto))
            except ValueError:
                pass
    return maior


def xml_servidor(forma, nome, partes, skill="", nivel="1", skill_do_escudo="",
                 nivel_do_escudo="1", encantado="", nivel_encantado="1",
                 ident=None, estados=()):
    """
    O conjunto no formato daquele servidor.

    `partes` e {parte: [ids]} -- o que o `por_parte` devolve. `estados` sao os
    pares (status, valor) que o L2J escreve como filho (`<str val="-2" />`),
    que o aCis nao tem: la eles sairiam num campo que nao existe, e por isso
    aparecem so numa das formas.
    """
    nome = (nome or "Conjunto").strip()
    if forma == "acis":
        return _xml_acis(nome, partes, skill, skill_do_escudo, encantado)
    return _xml_l2j(nome, partes, skill, nivel, skill_do_escudo,
                    nivel_do_escudo, encantado, nivel_encantado, ident,
                    estados)


def _primeiro(partes, parte):
    lista = partes.get(parte) or []
    return lista[0] if lista else "0"


def _xml_acis(nome, partes, skill, skill_do_escudo, encantado):
    """
    A linha do aCis: uma peca por atributo, e zero onde nao ha peca.

    O `0` nao e enfeite -- o core le o atributo sem conferir se existe, e a
    linha sem ele nao carrega. Por isso todos os nove sao escritos sempre.
    """
    campos = [("name", nome)]
    for parte in ("chest", "legs", "head", "gloves", "feet"):
        campos.append((parte, _primeiro(partes, parte)))
    campos.append(("skillId", str(skill or "0").strip() or "0"))
    campos.append(("shield", _primeiro(partes, "shield")))
    campos.append(("shieldSkillId", str(skill_do_escudo or "0").strip() or "0"))
    campos.append(("enchant6Skill", str(encantado or "0").strip() or "0"))
    linha = " ".join('%s="%s"' % (chave, l2item._escapar(str(valor)))
                     for chave, valor in campos)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<list>\n'
            '\t<!-- Gerado pelo L2PackTool -->\n'
            '\t<armorset %s/>\n</list>\n' % linha)


def _xml_l2j(nome, partes, skill, nivel, skill_do_escudo, nivel_do_escudo,
             encantado, nivel_encantado, ident, estados):
    """
    O bloco do L2J: um filho por peca, e mais de um por parte quando ha.

    O `id` do conjunto e do servidor, nao do item: e a chave do conjunto na
    lista dele. Quando quem chama nao sabe qual usar, fica um comentario no
    lugar em vez de um numero inventado -- id repetido faz o core descartar um
    dos dois conjuntos em silencio.
    """
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<list>',
              '\t<!-- %s. Gerado pelo L2PackTool -->' % l2item._escapar(nome)]
    linhas.append('\t<set id="%s">' % (ident if ident is not None
                                       else "PONHA_UM_ID_LIVRE"))
    for parte in PARTES:
        if parte == "shield":
            continue
        for peca in partes.get(parte) or []:
            linhas.append('\t\t<%s id="%s" />' % (parte, peca))
    for peca in partes.get("shield") or []:
        linhas.append('\t\t<shield id="%s" />' % peca)
    if str(skill or "").strip():
        linhas.append('\t\t<skill id="%s" level="%s" />'
                      % (str(skill).strip(), str(nivel or "1").strip()))
    if str(skill_do_escudo or "").strip():
        linhas.append('\t\t<shield_skill id="%s" level="%s" />'
                      % (str(skill_do_escudo).strip(),
                         str(nivel_do_escudo or "1").strip()))
    if str(encantado or "").strip():
        linhas.append('\t\t<enchant6skill id="%s" level="%s" />'
                      % (str(encantado).strip(),
                         str(nivel_encantado or "1").strip()))
    for estado, valor in estados or ():
        if str(valor).strip():
            linhas.append('\t\t<%s val="%s" />' % (estado, str(valor).strip()))
    # A parte que nao se soube identificar sai em comentario: some-la num
    # `<chest>` poria a peca errada no lugar certo, e apaga-la esconderia que
    # ela existe.
    soltas = partes.get("") or []
    if soltas:
        linhas.append('\t\t<!-- sem parte identificada no cliente: %s -->'
                      % ", ".join(soltas))
    linhas.append('\t</set>')
    linhas.append('</list>')
    return "\n".join(linhas) + "\n"
