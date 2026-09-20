#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O lado do servidor, em mais de um sabor.

O cliente do Lineage 2 e um so; o servidor nao. Cada emulador guarda a mesma
informacao do seu jeito, e as duas familias que importam aqui sao:

    XML    aCis, L2jServer, Mobius, Lisvus. Arquivos em data/xml/items,
           data/xml/npcs, data/xml/skills. Campo vira <set name="x" val="y"/>.

    BANCO  L2jFrozen e os cores de datapack antigo. Linhas nas tabelas
           `weapon`, `armor`, `etcitem`, `npc`, `droplist`, `spawnlist`. Campo
           vira COLUNA, e nem todo campo do XML tem coluna correspondente.

Nao e so o formato que muda: o XML do aCis escreve `crystal_type="D"` e o banco
escreve `crystal_type='d'`; o XML poe o ataque num bloco <for> e o banco tem uma
coluna `p_dam`. Por isso o programa trabalha com um conjunto de campos PROPRIO,
neutro, e cada perfil diz como traduzi-lo.

## Os perfis sao arquivos

Um servidor novo e um .json em recursos/servidores/, sem mexer em codigo. O
arquivo diz o formato, onde ficam as coisas, e o de-para dos campos. E o mesmo
arranjo dos moldes de lobby e das definicoes de tabela: quem tem um core que
nao esta aqui acrescenta um arquivo.

## O INSERT sai com os nomes das colunas

Schema de emulador nao e fixo: o mesmo `weapon` tem 36 colunas num core e
outras tantas noutro, e ha quem acrescente as suas. INSERT posicional casa
pela ordem, entao uma coluna a mais no meio poe preco no lugar de peso -- sem
erro, sem aviso.

Nomeando as colunas, o que o core nao tiver fica no padrao dele e o que ele
tiver a mais nao atrapalha. Na leitura, quando o INSERT NAO nomeia -- e quase
todo .sql que circula e assim -- vale a ordem declarada no perfil, e a
contagem e conferida antes de casar.
"""

import json
import re
from pathlib import Path

import l2upscale as motor

PASTA_DE_PERFIS = "recursos/servidores"
PERFIL_PADRAO = "acis"


class ErroDeServidor(Exception):
    pass


# ---------------------------------------------------------------------------
# Os perfis
# ---------------------------------------------------------------------------
def pasta_de_perfis():
    for raiz in (motor.AQUI, motor.BASE):
        caminho = Path(raiz) / PASTA_DE_PERFIS
        if caminho.is_dir():
            return caminho
    return Path(motor.AQUI) / PASTA_DE_PERFIS


def perfis():
    """Todos os perfis que acompanham o programa, em ordem de nome."""
    pasta = pasta_de_perfis()
    if not pasta.is_dir():
        return []
    achados = []
    for arquivo in sorted(pasta.glob("*.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception:
            continue
        dados["chave"] = arquivo.stem
        achados.append(dados)
    achados.sort(key=lambda p: (p.get("ordem", 50), p.get("nome", "")))
    return achados


def perfil(chave=None):
    """O perfil pedido, ou o primeiro da lista."""
    todos = perfis()
    if not todos:
        raise ErroDeServidor("nao achei nenhum perfil de servidor em %s"
                             % pasta_de_perfis())
    if chave:
        for p in todos:
            if p["chave"] == chave or p.get("nome") == chave:
                return p
    for p in todos:
        if p["chave"] == PERFIL_PADRAO:
            return p
    return todos[0]


def nomes_dos_perfis():
    return [p.get("nome", p["chave"]) for p in perfis()]


# A escolha que nao e um perfil: le o servidor e monta um na hora.
DETECTAR = "detectar"


def _tem_perfil(escolha):
    return any(p["chave"] == escolha or p.get("nome") == escolha
               for p in perfis())


def perfil_escolhido(escolha, pasta=None, aoprogresso=None):
    """
    O perfil a usar, dada a escolha da tela.

    `DETECTAR` le a pasta do servidor. Sem pasta apontada ainda -- a tela abre
    antes de o usuario escolher onde fica -- cai no perfil padrao, que serve
    para desenhar a previa e nada mais.

    Os perfis continuam valendo quando escolhidos: detectar e o padrao, nao uma
    imposicao. Um core com arrumacao estranha o bastante para enganar a
    leitura ainda pode ser dito na mao.
    """
    # Um nome que nao existe mais -- um perfil apagado, uma configuracao velha
    # -- nao pode virar aCis em silencio: isso e responder outra coisa sem
    # dizer. Detectar e a resposta honesta para "nao conheco esse".
    if escolha and escolha != DETECTAR and _tem_perfil(escolha):
        return perfil(escolha)
    if pasta and Path(pasta).is_dir():
        try:
            return farejar(pasta, aoprogresso)
        except ErroDeServidor:
            pass
    return perfil(None)


# ---------------------------------------------------------------------------
# Farejar: o perfil tirado do proprio servidor
# ---------------------------------------------------------------------------
# Um perfil por servidor nao se sustenta. Quem monta um servidor pega um core,
# troca o nome e mexe no que quer: um pack com nome proprio costuma ser aCis
# por baixo, com tres ou quatro diferencas. Pedir um arquivo novo para cada um desses seria
# transferir para ele um trabalho que o proprio servidor responde -- as
# diferencas estao escritas nos arquivos dele.
#
# Entao o programa le e decide. Nao adivinha: cada resposta sai de contagem, e
# o que foi visto aparece na tela, para o usuario conferir em vez de confiar.
_ALVO_DE_SKILL = re.compile(r'<set\s+name="target"\s+val="([^"]+)"', re.I)
_MODO_DE_SKILL = re.compile(r'<set\s+name="operateType"\s+val="([^"]+)"', re.I)
_CATEGORIA_NOMEADA = re.compile(r"<category\b[^>]*\btype\s*=", re.I)
_CATEGORIA_NUMERADA = re.compile(r"<category\b[^>]*\bid\s*=", re.I)
_CHANCE_DE_DROP = re.compile(r'<drop\b[^>]*\bchance="([0-9.]+)"', re.I)
_INSERT_NA_TABELA = re.compile(r"INSERT\s+INTO\s+[`\"']?(\w+)", re.I)

_FAREJADOS = {}


# `stat="pAtk"` nos arquivos do servidor. Aceita hifen: `pAtk-animals` e um
# nome so.
_STATUS_USADO = re.compile(r'stat\s*=\s*"([A-Za-z0-9_\-]+)"')

# A linha do enum no fonte: `POWER_ATTACK("pAtk"),`. O nome entre aspas e o que
# o XML escreve.
_STATUS_DO_ENUM = re.compile(r'\(\s*"([A-Za-z0-9_\-]+)"\s*\)')


def _status_do_core(pasta):
    """
    Todos os status que o core aceita, lidos do `Stats.java` dele.

    Sobe ate seis niveis a partir da pasta de dados: o datapack mora em
    `build/dist/game/data` e o fonte em `java/`, os dois pendurados no mesmo
    tronco. Devolve (conjunto, caminho) ou (None, None) se nao achar.
    """
    de_onde = Path(pasta).resolve()
    for _ in range(6):
        for achado in de_onde.glob("java/**/skills/Stats.java"):
            try:
                texto = achado.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            nomes = set(_STATUS_DO_ENUM.findall(texto))
            if len(nomes) > 20:      # e o enum mesmo, e nao outro arquivo
                return nomes, achado
        if de_onde.parent == de_onde:
            break
        de_onde = de_onde.parent
    return None, None


def farejar(pasta, aoprogresso=None, de_novo=False):
    """
    O perfil deste servidor, lido dos arquivos dele.

    Parte do aCis (ou do L2jFrozen, se o que houver for banco) e corrige o que
    a leitura mostrar diferente: onde ficam as coisas, se o alvo da habilidade
    leva prefixo, como a gaveta de drop e escrita e em que unidade vai a
    chance.

    Devolve o perfil com uma chave `achados` -- as frases do que foi visto,
    para a tela mostrar. Detectar em silencio seria trocar um palpite do
    usuario por um palpite meu.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroDeServidor("nao achei a pasta %s" % pasta)

    marca = str(pasta.resolve()).lower()
    if not de_novo and marca in _FAREJADOS:
        return _FAREJADOS[marca]

    onde = {"itens": {}, "skills": {}, "npcs": {}}
    alvos, modos = [], []
    status_usados = set()
    nomeadas = numeradas = 0
    maior_chance = 0.0
    tem_chance = False
    elementos = 0
    inserts = {}

    arquivos = [q for q in pasta.rglob("*")
                if q.is_file() and q.suffix.lower() in (".xml", ".sql")]
    for i, arquivo in enumerate(arquivos):
        if aoprogresso and i % 40 == 0:
            aoprogresso(i / float(max(1, len(arquivos))),
                        "lendo %s" % arquivo.name)
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if arquivo.suffix.lower() == ".sql":
            for tabela in _INSERT_NA_TABELA.findall(texto):
                gaveta = _onde_cai(tabela)
                if gaveta:
                    inserts[gaveta] = inserts.get(gaveta, 0) + 1
            continue

        try:
            dentro = arquivo.parent.relative_to(pasta).as_posix()
        except ValueError:
            continue

        quantos = dict(
            (assunto, len(_so_definicoes(assunto, padrao.findall(texto))))
            for assunto, padrao in (("itens", _ITEM_XML),
                                    ("skills", _SKILL_XML),
                                    ("npcs", _NPC_XML)))
        for assunto, n in quantos.items():
            if n:
                onde[assunto][dentro] = onde[assunto].get(dentro, 0) + n
                elementos += n

        # Fora do `if` de assunto de proposito: status aparece em item, em
        # habilidade e em armadura, e o que interessa e a uniao dos tres.
        status_usados.update(_STATUS_USADO.findall(texto))

        if quantos["skills"]:
            alvos.extend(_ALVO_DE_SKILL.findall(texto))
            modos.extend(_MODO_DE_SKILL.findall(texto))
        if quantos["npcs"]:
            nomeadas += len(_CATEGORIA_NOMEADA.findall(texto))
            numeradas += len(_CATEGORIA_NUMERADA.findall(texto))
            for bruto in _CHANCE_DE_DROP.findall(texto):
                tem_chance = True
                try:
                    maior_chance = max(maior_chance, float(bruto))
                except ValueError:
                    pass

    achado = _partir_de("frozen" if not elementos and inserts
                        else PERFIL_PADRAO)
    achado["chave"] = "detectado"
    achado["nome"] = "detectado"
    frases = []

    if not elementos and not inserts:
        frases.append("nao achei item, habilidade nem NPC nesta pasta")
        achado["achados"] = frases
        _FAREJADOS[marca] = achado
        return achado

    if elementos:
        achado["formato"] = "xml"
        pastas = {}
        vistas = []
        for assunto in ("itens", "skills", "npcs"):
            if not onde[assunto]:
                continue
            # A pasta com MAIS elementos daquele tipo, e nao a primeira que
            # aparecer: `recipes.xml` tambem tem <item id="1">, so que ali item
            # e ingrediente de receita. Com dez mil itens de um lado e algumas
            # centenas do outro, a contagem nao tem duvida.
            melhor = max(onde[assunto].items(), key=lambda par: par[1])
            pastas[assunto] = melhor[0]
            vistas.append("%s em %s (%d)" % (assunto, melhor[0] or ".",
                                             melhor[1]))
        # No XML o drop mora dentro do <npc>, e multisell e spawn ficam ao
        # lado. Herdar esses caminhos do perfil base misturaria caminho medido
        # com caminho suposto, cada um a partir de uma raiz diferente.
        pastas["droplist"] = pastas.get("npcs", "")
        vizinha = (pastas.get("npcs") or "").rsplit("/", 1)[0]
        for assunto, nome in (("multisell", "multisell"), ("spawn", "spawnlist")):
            candidata = "%s/%s" % (vizinha, nome) if vizinha else nome
            if (pasta / candidata).is_dir():
                pastas[assunto] = candidata
        achado["pastas"] = pastas
        frases.append("XML: " + ", ".join(vistas))
    else:
        achado["formato"] = "sql"
        frases.append("banco: INSERT em " + ", ".join(
            "%s (%d)" % (k, v) for k, v in sorted(inserts.items())))

    prefixos = {}
    for campo, vistos, candidato in (("target", alvos, "TARGET_"),
                                     ("operateType", modos, "OP_")):
        if _a_maioria_comeca_com(vistos, candidato):
            prefixos[campo] = candidato
            frases.append("%s das habilidades com %s" % (campo, candidato))
    if prefixos:
        achado["prefixos"] = prefixos

    if numeradas or nomeadas:
        numerada = numeradas > nomeadas
        achado["categoria_de_drop"] = "numero" if numerada else "nome"
        frases.append("gaveta de drop %s"
                      % ("numerada (id=)" if numerada else "nomeada (type=)"))

    if tem_chance:
        milionesimos = maior_chance > 100
        achado["escala_de_chance"] = 10000 if milionesimos else 1
        frases.append("chance de drop %s (a maior vista foi %g)"
                      % ("em milionesimos" if milionesimos else "por cento",
                         maior_chance))

    # Os status: primeiro o fonte do core, que e a lista inteira; senao, o que
    # o datapack usa, que e menor mas e prova de que aquilo sobe.
    do_core, onde_esta = _status_do_core(pasta)
    if do_core:
        achado["estados_aceitos"] = sorted(do_core)
        achado["estados_de_onde"] = "core"
        frases.append("%d status lidos de %s"
                      % (len(do_core), onde_esta.name))
    elif status_usados:
        achado["estados_aceitos"] = sorted(status_usados)
        achado["estados_de_onde"] = "datapack"
        frases.append("%d status em uso nos arquivos do servidor"
                      % len(status_usados))
    achado["estados_usados"] = sorted(status_usados)

    achado["achados"] = frases
    _FAREJADOS[marca] = achado
    return achado


# Onde cada tipo de item costuma morar, quando a pasta e repartida por tipo.
# A ordem e de preferencia: a primeira que existir ganha.
SUBPASTA_DO_GRUPO = {
    "weapon": ("weapons", "weapon", "custom"),
    "armor": ("armors", "armor", "custom"),
    "etc": ("etcitems", "etcitem", "custom"),
    "accessory": ("accessories", "jewels", "custom"),
}


def raiz_de(raiz, perfil_do_servidor, assunto):
    """
    A pasta do assunto, sem subpasta nenhuma. None se nao der para saber.

    O perfil escreve o caminho a partir da RAIZ do servidor, e o usuario
    costuma apontar ja de dentro do `data`. Por isso o caminho e experimentado
    cortando pela cauda -- `game/data/xml/items`, depois `data/xml/items`,
    depois `xml/items`, ate um existir.
    """
    if not raiz:
        return None
    raiz = Path(raiz)
    if not raiz.is_dir():
        return None
    declarada = ((perfil_do_servidor or {}).get("pastas") or {}).get(assunto) or ""
    if not declarada:
        return None
    partes = [p for p in declarada.replace("\\", "/").split("/") if p]
    for corte in range(len(partes)):
        alvo = raiz.joinpath(*partes[corte:])
        if alvo.is_dir():
            return alvo
    return None


def subpastas_de(raiz, perfil_do_servidor, assunto):
    """As subpastas que existem sob a pasta do assunto, em ordem de nome."""
    onde = raiz_de(raiz, perfil_do_servidor, assunto)
    if onde is None:
        return []
    try:
        return sorted(p.name for p in onde.iterdir() if p.is_dir())
    except OSError:
        return []


def subpasta_preferida(raiz, perfil_do_servidor, assunto, grupo):
    """
    A subpasta que casa com o tipo do item, entre as que existem.

    Devolve "" quando nenhuma casa -- e ai o lugar e a propria pasta do
    assunto, que e onde os arquivos de fabrica estao.
    """
    existentes = set(n.lower() for n in subpastas_de(raiz, perfil_do_servidor,
                                                     assunto))
    if not existentes:
        return ""
    for candidata in SUBPASTA_DO_GRUPO.get(grupo, ("custom",)):
        if candidata.lower() in existentes:
            return candidata
    return ""


def pasta_de(raiz, perfil_do_servidor, assunto, sub="custom"):
    """
    Onde a XML daquele assunto deve cair, dentro da pasta do servidor.

    `assunto` e "itens", "skills" ou "npcs". Devolve um Path ou None -- e None
    quer dizer "nao da para saber", que e melhor do que gravar no lugar errado:
    pasta nao apontada, ou um perfil que nao diz onde aquilo mora.

    Duas sutilezas:

    1. O perfil escreve o caminho a partir da RAIZ do servidor, e o usuario
       costuma apontar ja de dentro do `data`. Por isso o caminho e
       experimentado cortando pela cauda -- `game/data/xml/items`, depois
       `data/xml/items`, depois `xml/items`, ate um existir.
    2. A subpasta `custom` e a convencao dos datapacks L2J. Misturar o que foi
       acrescentado com os arquivos de fabrica torna impossivel saber depois o
       que veio de onde.
    """
    onde = raiz_de(raiz, perfil_do_servidor, assunto)
    if onde is None:
        return None
    return onde / sub if sub else onde


def _partir_de(chave):
    """Uma copia funda do perfil base, para mexer sem estragar o original."""
    return json.loads(json.dumps(perfil(chave)))


def _a_maioria_comeca_com(valores, prefixo):
    """
    Verdadeiro quando o prefixo manda na amostra.

    Metade nao bastaria numa amostra de dois; por isso exige tambem um minimo
    de casos. Um servidor com tres habilidades nao decide o formato de nada.
    """
    if len(valores) < 4:
        return False
    com = sum(1 for v in valores if v.upper().startswith(prefixo))
    return com * 2 > len(valores)



# ---------------------------------------------------------------------------
# Escrever
# ---------------------------------------------------------------------------
def _escapar_xml(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _escapar_sql(texto):
    """Aspas simples dobradas, que e o escape do MySQL para string."""
    return str(texto).replace("\\", "\\\\").replace("'", "''")


def _valor_sql(valor):
    texto = str(valor).strip()
    if texto == "":
        return "''"
    if re.match(r"^-?\d+(\.\d+)?$", texto):
        return texto
    return "'%s'" % _escapar_sql(texto)


def traduzir_campos(perfil_do_servidor, assunto, campos):
    """
    Passa os campos neutros para os nomes daquele servidor.

    Devolve (campos traduzidos, o que ficou de fora). O que fica de fora nao e
    erro: o banco do L2J nao tem coluna para material, e dizer isso e melhor do
    que inventar uma.
    """
    mapa = (perfil_do_servidor.get("campos") or {}).get(assunto)
    if mapa is None and "_" in assunto:
        mapa = (perfil_do_servidor.get("campos") or {}).get(
            assunto.split("_", 1)[0])
    mapa = mapa or {}
    traduzidos, sobraram = {}, []
    for chave, valor in campos.items():
        if valor is None or str(valor).strip() == "":
            continue
        destino = mapa.get(chave, chave if not mapa else None)
        if destino is None:
            sobraram.append(chave)
            continue
        traduzidos[destino] = valor
    return traduzidos, sobraram


def converter_valor(perfil_do_servidor, chave, valor):
    """
    Ajusta a escrita do valor: 'D' vira 'd' no banco, e por aí.

    Alguns cores nao mudam o nome, so acrescentam um prefixo: `ONE` vira
    `TARGET_ONE`, `ACTIVE` vira `OP_ACTIVE`. Escrever as 28 linhas do de-para a
    mao daria no mesmo e envelheceria pior -- um alvo que o programa nao
    conhecesse sairia sem prefixo, e sem erro nenhum. O prefixo cobre todos.
    """
    valor = str(valor)
    regras = (perfil_do_servidor.get("valores") or {}).get(chave)
    if regras and valor in regras:
        return regras[valor]
    prefixo = (perfil_do_servidor.get("prefixos") or {}).get(chave)
    if prefixo and valor and not valor.upper().startswith(prefixo):
        return prefixo + valor
    return regras.get(valor, valor) if regras else valor


def _formato(perfil_do_servidor):
    return (perfil_do_servidor.get("formato") or "xml").lower()


def _tabela(perfil_do_servidor, assunto):
    """
    A tabela daquele assunto. `assunto` pode vir com subtipo -- "itens_weapon"
    -- porque no banco arma, armadura e o resto sao tabelas diferentes, embora
    no XML sejam o mesmo elemento com outro type.
    """
    tabelas = perfil_do_servidor.get("tabelas") or {}
    alvo = tabelas.get(assunto)
    if not alvo and "_" in assunto:
        alvo = tabelas.get(assunto.split("_", 1)[0])
    if not alvo:
        raise ErroDeServidor("o perfil %s nao diz em que tabela grava %s"
                             % (perfil_do_servidor.get("nome"), assunto))
    return alvo


def insert(perfil_do_servidor, assunto, campos, comentario=""):
    """Um INSERT com as colunas nomeadas."""
    tabela = _tabela(perfil_do_servidor, assunto)
    colunas, valores = [], []
    for chave, valor in campos.items():
        colunas.append("`%s`" % chave)
        valores.append(_valor_sql(valor))
    linha = "INSERT INTO `%s` (%s) VALUES (%s);" % (
        tabela, ", ".join(colunas), ", ".join(valores))
    return ("-- %s\n%s\n" % (comentario, linha)) if comentario else linha + "\n"


def bloco_xml(raiz, atributos, campos, dentro="", comentario="", nivel=1):
    """
    Um elemento com <set name=... val=.../> dentro, que e a forma do aCis.

    `dentro` ja vem pronto -- e onde entram o <for> e o que mais o assunto
    precisar.
    """
    recuo = "\t" * nivel
    atrib = " ".join('%s="%s"' % (n, _escapar_xml(v))
                     for n, v in atributos.items())
    linhas = []
    if comentario:
        linhas.append("%s<!-- %s -->" % (recuo, comentario))
    linhas.append("%s<%s %s>" % (recuo, raiz, atrib))
    for chave, valor in campos.items():
        linhas.append('%s\t<set name="%s" val="%s" />'
                      % (recuo, chave, _escapar_xml(valor)))
    if dentro:
        linhas.append(dentro.rstrip("\n"))
    linhas.append("%s</%s>" % (recuo, raiz))
    return "\n".join(linhas)


def documento_xml(corpo):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<list>\n%s\n</list>\n'
            % corpo.rstrip("\n"))


def gerar(perfil_do_servidor, assunto, campos, atributos=None, dentro="",
          comentario=""):
    """
    O trecho pronto para aquele servidor, no formato dele.

    Devolve (texto, extensao sugerida, campos que o perfil nao soube traduzir).
    """
    traduzidos, sobraram = traduzir_campos(perfil_do_servidor, assunto, campos)
    traduzidos = dict((k, converter_valor(perfil_do_servidor, k, v))
                      for k, v in traduzidos.items())

    if _formato(perfil_do_servidor) == "sql":
        juntos = dict(atributos or {})
        juntos.update(traduzidos)
        return insert(perfil_do_servidor, assunto, juntos, comentario), ".sql", sobraram

    raiz = ((perfil_do_servidor.get("raiz_xml") or {}).get(assunto)
            or assunto.rstrip("s"))
    corpo = bloco_xml(raiz, atributos or {}, traduzidos, dentro, comentario)
    return documento_xml(corpo), ".xml", sobraram


# ---------------------------------------------------------------------------
# Ler o servidor, para conferir contra o cliente
# ---------------------------------------------------------------------------
_ITEM_XML = re.compile(r'<item\s+([^>]*?)>', re.I)
_SKILL_XML = re.compile(r'<skill\s+([^>]*?)>', re.I)
_NPC_XML = re.compile(r'<npc\s+([^>]*?)>', re.I)

# O mesmo nome de elemento serve para DEFINIR e para REFERENCIAR. O NPC diz
# `<skill id="4416" level="6"/>` para contar que sabe aquela habilidade, e a
# receita diz `<item id="57" count="10"/>` para contar do que e feita. Nenhum
# dos dois define coisa alguma, e somados davam 27 mil "habilidades" dentro da
# pasta de NPCs.
#
# A definicao se reconhece pelo que so ela tem: um nome, ou a contagem de
# niveis. Quem so tem `level` no singular e referencia.
_MARCAS_DE_DEFINICAO = {"itens": ("name", "type"),
                        "skills": ("name", "levels"),
                        "npcs": ("name", "title", "idtemplate")}


def _so_definicoes(assunto, brutos):
    """Descarta as referencias, ficando com os elementos que definem algo."""
    marcas = _MARCAS_DE_DEFINICAO[assunto]
    ficam = []
    for bruto in brutos:
        campos = set(k.lower() for k, _v in _ATRIBUTO.findall(bruto))
        if campos.intersection(marcas):
            ficam.append(bruto)
    return ficam
_ATRIBUTO = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_INSERT = re.compile(
    r"INSERT\s+INTO\s+[`\"]?(\w+)[`\"]?\s*(?:\(([^)]*)\))?\s*VALUES\s*(.+?);",
    re.I | re.S)


def _atributos(texto):
    return dict(_ATRIBUTO.findall(texto))


def _primeiro_valor(bruto):
    """O primeiro campo de um VALUES(...), que nos .dat do L2J e sempre o id."""
    texto = bruto.strip().lstrip("(")
    achado = re.match(r"\s*'?(-?\d+)'?", texto)
    return achado.group(1) if achado else None


def _cabe_em(raiz, arquivo, so_em):
    """
    Diz, por assunto, se este arquivo conta.

    Sem pastas declaradas tudo conta -- e como era antes, e continua servindo
    para um core cuja arrumacao ninguem conhece.
    """
    if not so_em:
        return lambda _assunto: True
    try:
        dentro = arquivo.parent.relative_to(raiz).as_posix()
    except ValueError:
        return lambda _assunto: False

    def cabe(assunto):
        alvo = so_em.get(assunto)
        if not alvo:
            return True
        return dentro == alvo or dentro.startswith(alvo + "/")
    return cabe


def ler_servidor(pasta, aoprogresso=None, pastas=None):
    """
    O que o servidor tem, em qualquer dos dois formatos.

    Devolve {"itens": {id: nome}, "skills": {id: niveis}, "npcs": {id: nome},
             "arquivos": n, "formato": "xml"/"sql"/"os dois"}.

    A leitura e por varredura de texto, e nao por analise estrita: serve para
    responder "este id existe aqui?", que e a pergunta da conferencia. Um core
    que escreva o XML de outro jeito continua sendo lido, desde que o elemento
    se chame item, skill ou npc.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroDeServidor("nao achei a pasta %s" % pasta)

    itens, skills, npcs = {}, {}, {}
    arquivos = 0
    formatos = set()

    todos = [q for q in pasta.rglob("*")
             if q.is_file() and q.suffix.lower() in (".xml", ".sql")]
    # Sem isto, o `<item id="1">` de `recipes.xml` -- que ali e ingrediente de
    # receita -- entrava na conta como item do jogo, e a conferencia acusava
    # diferencas que nao existem. As pastas vem de quem farejou o servidor.
    so_em = dict((k, v) for k, v in (pastas or {}).items()
                 if k in ("itens", "skills", "npcs") and v)
    for i, arquivo in enumerate(todos):
        if aoprogresso and i % 40 == 0:
            aoprogresso(i / float(max(1, len(todos))),
                        "lendo %s" % arquivo.name)
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        arquivos += 1

        if arquivo.suffix.lower() == ".xml":
            achou = False
            cabe = _cabe_em(pasta, arquivo, so_em)
            for bruto in (_so_definicoes("itens", _ITEM_XML.findall(texto))
                          if cabe("itens") else ()):
                a = _atributos(bruto)
                if a.get("id"):
                    itens[a["id"]] = a.get("name", "")
                    achou = True
            for bruto in (_so_definicoes("skills",
                                         _SKILL_XML.findall(texto))
                          if cabe("skills") else ()):
                a = _atributos(bruto)
                if a.get("id"):
                    skills[a["id"]] = _inteiro(a.get("levels", "1"), 1)
                    achou = True
            for bruto in (_so_definicoes("npcs", _NPC_XML.findall(texto))
                          if cabe("npcs") else ()):
                a = _atributos(bruto)
                if a.get("id"):
                    npcs[a["id"]] = a.get("name", "")
                    achou = True
            if achou:
                formatos.add("xml")
        else:
            for tabela, colunas, valores in _INSERT.findall(texto):
                alvo = _onde_cai(tabela)
                if alvo is None:
                    continue
                formatos.add("sql")
                for bloco in re.findall(r"\(([^()]*)\)", valores):
                    ident = _primeiro_valor(bloco)
                    if not ident:
                        continue
                    if alvo == "itens":
                        itens.setdefault(ident, _nome_no_insert(bloco))
                    elif alvo == "skills":
                        skills.setdefault(ident, 1)
                    else:
                        npcs.setdefault(ident, _nome_no_insert(bloco))

    if aoprogresso:
        aoprogresso(1.0, "pronto")
    return {"itens": itens, "skills": skills, "npcs": npcs,
            "arquivos": arquivos,
            "formato": "+".join(sorted(formatos)) or "nenhum",
            "pasta": pasta}


# Que tabela do banco guarda o que. O prefixo `custom_` e a convencao do L2J
# para conteudo que nao veio do jogo, e vale o mesmo.
_TABELAS = {
    "itens": ("weapon", "armor", "etcitem", "custom_weapon", "custom_armor",
              "custom_etcitem"),
    "npcs": ("npc", "custom_npc"),
    "skills": ("skill", "custom_skill"),
}


def _onde_cai(tabela):
    nome = tabela.lower()
    for alvo, nomes in _TABELAS.items():
        if nome in nomes:
            return alvo
    return None


def _nome_no_insert(bloco):
    """O segundo campo, que nas tabelas de item e de npc do L2J e o nome."""
    achado = re.findall(r"'([^']*)'|(-?\d+(?:\.\d+)?)", bloco)
    valores = [a or b for a, b in achado]
    return valores[1] if len(valores) > 1 else ""


def _inteiro(texto, padrao=0):
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao


# ---------------------------------------------------------------------------
# Conferir os dois lados
# ---------------------------------------------------------------------------
def conferir(cliente_itens, cliente_skills, cliente_npcs, servidor):
    """
    O que existe num lado e nao no outro.

    `cliente_itens` e {id: nome}; `cliente_skills` e {id: niveis};
    `cliente_npcs` e {id: nome}. Todos com id em texto, como as tabelas dao.

    Um id so no cliente e um item que o jogador nunca recebe. Um id so no
    servidor e um item que cai no chao sem nome nem desenho. Os dois casos sao
    silenciosos em jogo -- nenhum deles gera erro em lugar nenhum.
    """
    def comparar(do_cliente, do_servidor):
        so_cliente = sorted(set(do_cliente) - set(do_servidor), key=_inteiro)
        so_servidor = sorted(set(do_servidor) - set(do_cliente), key=_inteiro)
        return so_cliente, so_servidor

    itens_c, itens_s = comparar(cliente_itens, servidor["itens"])
    skills_c, skills_s = comparar(cliente_skills, servidor["skills"])
    npcs_c, npcs_s = comparar(cliente_npcs, servidor["npcs"])

    # Nivel a mais no servidor e um caso proprio: a habilidade existe nos dois,
    # mas o servidor entrega um nivel que o cliente nao sabe desenhar.
    niveis = []
    for ident, no_servidor in servidor["skills"].items():
        no_cliente = cliente_skills.get(ident)
        if no_cliente is None:
            continue
        if _inteiro(no_servidor, 1) > _inteiro(no_cliente, 1):
            niveis.append((ident, no_cliente, _inteiro(no_servidor, 1)))
    niveis.sort(key=lambda t: _inteiro(t[0]))

    return {
        "itens_so_no_cliente": itens_c,
        "itens_so_no_servidor": itens_s,
        "skills_so_no_cliente": skills_c,
        "skills_so_no_servidor": skills_s,
        "npcs_so_no_cliente": npcs_c,
        "npcs_so_no_servidor": npcs_s,
        "niveis_a_mais": niveis,
        "servidor": servidor,
        "totais": {
            "cliente": (len(cliente_itens), len(cliente_skills),
                        len(cliente_npcs)),
            "servidor": (len(servidor["itens"]), len(servidor["skills"]),
                         len(servidor["npcs"])),
        },
    }


def texto_da_conferencia(resultado, nomes_do_cliente=None):
    """O relatorio em texto."""
    nomes_do_cliente = nomes_do_cliente or {}
    servidor = resultado["servidor"]
    linhas = ["CONFERENCIA ENTRE CLIENTE E SERVIDOR",
              "=" * 66,
              "servidor: %s  (%d arquivos, formato %s)"
              % (servidor["pasta"], servidor["arquivos"], servidor["formato"]),
              ""]

    c_itens, c_skills, c_npcs = resultado["totais"]["cliente"]
    s_itens, s_skills, s_npcs = resultado["totais"]["servidor"]
    linhas.append("%-12s %10s %10s" % ("", "cliente", "servidor"))
    linhas.append("%-12s %10d %10d" % ("itens", c_itens, s_itens))
    linhas.append("%-12s %10d %10d" % ("habilidades", c_skills, s_skills))
    linhas.append("%-12s %10d %10d" % ("npcs", c_npcs, s_npcs))
    linhas.append("")

    def secao(titulo, explicacao, ids, nomes):
        if not ids:
            return
        linhas.append(titulo.upper())
        linhas.append(explicacao)
        linhas.append("-" * 66)
        # Sem corte, pelo mesmo motivo das referencias: a lista e para
        # conferir, e meia lista nao confere nada.
        for ident in ids:
            linhas.append("  %-8s %s" % (ident, nomes.get(ident, "")))
        linhas.append("")

    secao("Itens so no cliente",
          "O cliente desenha, o servidor nao entrega. O jogador nunca ve.",
          resultado["itens_so_no_cliente"], nomes_do_cliente.get("itens", {}))
    secao("Itens so no servidor",
          "O servidor entrega, o cliente nao desenha: cai sem nome nem icone.",
          resultado["itens_so_no_servidor"], servidor["itens"])
    secao("Habilidades so no cliente",
          "Aparecem na lista de habilidades e nao existem para o servidor.",
          resultado["skills_so_no_cliente"],
          nomes_do_cliente.get("skills", {}))
    secao("Habilidades so no servidor",
          "O servidor entrega e o cliente nao sabe desenhar.",
          resultado["skills_so_no_servidor"], {})
    secao("NPCs so no cliente",
          "Estao no npcgrp e o servidor nunca faz nascer.",
          resultado["npcs_so_no_cliente"], nomes_do_cliente.get("npcs", {}))
    secao("NPCs so no servidor",
          "O servidor faz nascer e o cliente nao sabe desenhar.",
          resultado["npcs_so_no_servidor"], servidor["npcs"])

    if resultado["niveis_a_mais"]:
        linhas.append("HABILIDADES COM NIVEL A MAIS NO SERVIDOR")
        linhas.append("O servidor entrega um nivel que o cliente nao desenha.")
        linhas.append("-" * 66)
        for ident, no_cliente, no_servidor in resultado["niveis_a_mais"][:200]:
            linhas.append("  %-8s cliente %3s, servidor %3d"
                          % (ident, no_cliente, no_servidor))
        linhas.append("")

    return "\n".join(linhas) + "\n"

# ---------------------------------------------------------------------------
# Ler um NPC de volta, do servidor para o formulario
# ---------------------------------------------------------------------------
# O caminho de ida -- formulario para arquivo -- ja existia. Este e o de volta,
# e custa uma coisa a mais: a traducao inversa. No XML do aCis o nome do campo
# no arquivo e o mesmo que o programa usa, entao nao ha o que inverter; no
# banco, `patk` tem de virar `pAtk` outra vez e `L2Monster` tem de virar
# `Monster`.
#
# Ha um caso que o de-para sozinho nao resolve: o INSERT sem nomes de coluna.
# Os .sql que circulam sao quase todos assim -- posicionais -- e ai a unica
# saida e saber a ordem das colunas daquela tabela. Ela vai no perfil, em
# "colunas", e so e usada quando o INSERT nao se identifica. Sem ela, o
# programa diz que nao soube ler, em vez de adivinhar campo por posicao.
_NPC_INTEIRO = re.compile(
    r"<npc\b[^>]*\bid\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</npc>", re.I | re.S)
_SET_XML = re.compile(r'<set\s+name\s*=\s*"([^"]+)"\s+val\s*=\s*"([^"]*)"', re.I)
_TABELA_XML = re.compile(r'<table\s+name\s*=\s*"([^"]+)"\s*>(.*?)</table>',
                         re.I | re.S)
# Ha duas escritas para a mesma ideia: o aCis nomeia a gaveta
# (`type="SPOIL"`) e o L2J a numera (`id="-1"`). Aceitar so uma fazia todo NPC
# do outro core voltar com zero drops -- e monstro sem drop parece um dado
# plausivel, entao nada denunciava a falha.
_CATEGORIA = re.compile(r"<category\s+([^>]*?)>(.*?)</category>", re.I | re.S)
_DROP = re.compile(r"<drop\s+([^>]*?)/?>", re.I)
_NPCMAKER = re.compile(r"<npcmaker\b[^>]*>(.*?)</npcmaker>", re.I | re.S)
_NPC_SOLTO = re.compile(r"<npc\s+([^>]*?)/?>", re.I)
_MULTISELL_NPC = re.compile(r"<npcs>(.*?)</npcs>", re.I | re.S)
_INGREDIENTE = re.compile(r'<ingredient\s+id="(\d+)"\s+count="(\d+)"', re.I)
_PRODUCAO = re.compile(r'<production\s+id="(\d+)"\s+count="(\d+)"', re.I)
_ITEM_LOJA = re.compile(r"<item>(.*?)</item>", re.I | re.S)


_ABERTURA = {}


def _corpo_do_elemento(texto, tag, ident):
    """
    Acha <tag id="ident"> ... </tag> sem regex atravessando o arquivo.

    Devolve (atributos da abertura, corpo) ou None.

    A versao anterior usava `<tag ...>(.*?)</tag>`, que num arquivo cheio de
    `<tag .../>` fechados em si mesmos varre ate o fim a cada ocorrencia --
    procurar uma habilidade na pasta inteira do datapack passava de sete
    minutos por causa disso.
    """
    padrao = _ABERTURA.get(tag)
    if padrao is None:
        padrao = re.compile(r"<%s\b([^>]*)>" % tag, re.I)
        _ABERTURA[tag] = padrao

    fechamento = "</%s>" % tag
    for achado in padrao.finditer(texto):
        atributos = achado.group(1)
        if atributos.rstrip().endswith("/"):
            continue                    # fecha em si mesmo: nao tem corpo
        campos = dict(_ATRIBUTO.findall(atributos))
        if campos.get("id") != ident:
            continue
        fim = texto.find(fechamento, achado.end())
        if fim < 0:
            continue
        return campos, texto[achado.end():fim]
    return None


def _inverter(mapa):
    return dict((v, k) for k, v in (mapa or {}).items())


def _inverso_de_valor(perfil_do_servidor, campo_no_core):
    """{valor do core: valor neutro} daquele campo, se houver conversao."""
    regras = (perfil_do_servidor.get("valores") or {}).get(campo_no_core)
    return _inverter(regras) if regras else {}


def _tirar_prefixo(perfil_do_servidor, campo_no_core, valor):
    """O valor sem o prefixo do core, quando o perfil declara um."""
    prefixo = (perfil_do_servidor.get("prefixos") or {}).get(campo_no_core)
    if prefixo and str(valor).upper().startswith(prefixo):
        return str(valor)[len(prefixo):]
    return valor


def _dividir_valores(bruto):
    """
    Parte um VALUES(...) em campos, respeitando aspas.

    Nao da para usar split(",") e pronto: nome de NPC com virgula existe, e um
    'Guarda, o Velho' viraria dois campos.
    """
    campos, atual, dentro, escape = [], [], False, False
    for c in bruto:
        if escape:
            atual.append(c)
            escape = False
        elif c == "\\":
            escape = True
        elif c == "'":
            dentro = not dentro
        elif c == "," and not dentro:
            campos.append("".join(atual).strip())
            atual = []
        else:
            atual.append(c)
    campos.append("".join(atual).strip())
    return campos


def _colunas_do_perfil(perfil_do_servidor, assunto, declaradas):
    if declaradas.strip():
        return [c.strip().strip("`\"[] ") for c in declaradas.split(",")]
    return (perfil_do_servidor.get("colunas") or {}).get(assunto, [])


def achar_npc(pasta, ident, perfil_do_servidor, aoprogresso=None):
    """
    Procura aquele NPC no servidor e devolve o que ele tem, em campos neutros.

    Devolve None quando o id nao esta la -- que e a resposta util para "este
    NPC ainda nao existe no servidor; quer criar?".

    O que volta: {"campos", "nome", "titulo", "drops", "spawn", "loja",
    "arquivo", "formato"}.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroDeServidor("nao achei a pasta %s" % pasta)

    ident = str(ident).strip()
    campos_do_perfil = perfil_do_servidor.get("campos") or {}
    de_volta = _inverter(campos_do_perfil.get("npcs"))
    de_volta_drop = _inverter(campos_do_perfil.get("droplist"))
    de_volta_spawn = _inverter(campos_do_perfil.get("spawn"))

    achado = None
    drops, spawn, loja = [], {}, {}

    arquivos = _arquivos_para(pasta, perfil_do_servidor, "npcs")
    for i, arquivo in enumerate(arquivos):
        if aoprogresso and i % 40 == 0:
            aoprogresso(i / float(max(1, len(arquivos))),
                        "procurando em %s" % arquivo.name)
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ident not in texto:
            continue

        if arquivo.suffix.lower() == ".xml":
            if achado is None:
                achado = _npc_do_xml(texto, ident, arquivo, drops,
                                     perfil_do_servidor)
            _spawn_do_xml(texto, ident, spawn)
            _loja_do_xml(texto, ident, arquivo, loja)
        else:
            if achado is None:
                achado = _npc_do_sql(texto, ident, arquivo,
                                     perfil_do_servidor, de_volta)
            _drops_do_sql(texto, ident, perfil_do_servidor, de_volta_drop,
                          drops)
            _spawn_do_sql(texto, ident, perfil_do_servidor, de_volta_spawn,
                          spawn)

    if aoprogresso:
        aoprogresso(1.0, "pronto")
    if achado is None:
        return None
    achado["drops"] = drops
    achado["spawn"] = spawn
    achado["loja"] = loja
    return achado


def _em_por_cento(chance, escala):
    """A chance do core na unidade da tela. Texto estranho volta como veio."""
    if escala == 1:
        return chance
    try:
        return "%g" % (float(chance) / escala)
    except (TypeError, ValueError):
        return chance


def _nome_da_categoria(atributos):
    """
    O nome neutro da gaveta de drop, venha ela nomeada ou numerada.

    `type="SPOIL"` no aCis; `id="-1"` no L2J, onde o -1 e o espolio e os
    numeros a partir de zero sao gavetas de drop.
    """
    if atributos.get("type"):
        return atributos["type"].upper()
    numero = (atributos.get("id") or "").strip()
    return "SPOIL" if numero.startswith("-") else "DROP"


def _npc_do_xml(texto, ident, arquivo, drops, perfil_do_servidor=None):
    lido = _corpo_do_elemento(texto, "npc", ident)
    if lido is not None:
        cabeca, corpo = lido
        # A tela pede a chance em por cento. O aCis escreve por cento e os dois
        # batiam; ha packs que escrevem em milionesimos, e sem a escala o
        # 700000 deles (70% de adena) chegava cru na coluna "chance %".
        escala = float((perfil_do_servidor or {}).get("escala_de_chance") or 1)
        for atributos, dentro in _CATEGORIA.findall(corpo):
            categoria = _nome_da_categoria(dict(_ATRIBUTO.findall(atributos)))
            for bruto in _DROP.findall(dentro):
                a = dict(_ATRIBUTO.findall(bruto))
                if not a.get("itemid"):
                    continue
                drops.append({"item": a["itemid"],
                              "minimo": a.get("min", "1"),
                              "maximo": a.get("max", "1"),
                              "chance": _em_por_cento(a.get("chance", "1"),
                                                      escala),
                              "categoria": categoria.upper()})
        return {"campos": _desconverter(perfil_do_servidor or {},
                                        dict(_SET_XML.findall(corpo))),
                "nome": cabeca.get("name", ""),
                "titulo": cabeca.get("title", ""),
                "arquivo": arquivo, "formato": "xml", "aviso": ""}
    return None


def _npc_do_sql(texto, ident, arquivo, perfil_do_servidor, de_volta):
    for tabela, colunas, valores in _INSERT.findall(texto):
        if _onde_cai(tabela) != "npcs":
            continue
        nomes = _colunas_do_perfil(perfil_do_servidor, "npcs", colunas)
        for bloco in re.findall(r"\(([^()]*)\)", valores):
            crus = _dividir_valores(bloco)
            if not crus or crus[0].strip().strip("'") != ident:
                continue
            if not nomes:
                # Sem nomes no INSERT e sem a ordem no perfil, adivinhar por
                # posicao poria vida no lugar de mana. Melhor dizer que nao deu.
                return {"campos": {}, "nome": "", "titulo": "",
                        "arquivo": arquivo, "formato": "sql",
                        "aviso": "o INSERT nao nomeia as colunas e o perfil "
                                 "nao traz a ordem delas"}
            campos, nome, titulo = {}, "", ""
            for coluna, valor in zip(nomes, crus):
                neutro = de_volta.get(coluna)
                if neutro is None:
                    continue
                valor = valor.strip().strip("'")
                valor = _inverso_de_valor(perfil_do_servidor,
                                          coluna).get(valor, valor)
                if neutro in ("nome", "name"):
                    nome = valor
                elif neutro == "title":
                    titulo = valor
                elif neutro not in ("id", "idTemplate"):
                    campos[neutro] = valor
            return {"campos": campos, "nome": nome, "titulo": titulo,
                    "arquivo": arquivo, "formato": "sql", "aviso": ""}
    return None


def _drops_do_sql(texto, ident, perfil_do_servidor, de_volta, drops):
    nome_da_gaveta = {"0": "DROP", "1": "SPOIL"}
    escala = float(perfil_do_servidor.get("escala_de_chance") or 1.0)
    for tabela, colunas, valores in _INSERT.findall(texto):
        if tabela.lower() not in ("droplist", "custom_droplist"):
            continue
        nomes = _colunas_do_perfil(perfil_do_servidor, "droplist", colunas)
        if not nomes:
            continue
        for bloco in re.findall(r"\(([^()]*)\)", valores):
            crus = dict(zip(nomes, _dividir_valores(bloco)))
            neutros = dict((de_volta.get(k, k), v.strip().strip("'"))
                           for k, v in crus.items())
            if neutros.get("npc") != ident:
                continue
            chance = neutros.get("chance", "0")
            try:
                chance = "%g" % (float(chance) / escala)
            except ValueError:
                pass
            drops.append({"item": neutros.get("item", ""),
                          "minimo": neutros.get("minimo", "1"),
                          "maximo": neutros.get("maximo", "1"),
                          "chance": chance,
                          "categoria": nome_da_gaveta.get(
                              neutros.get("categoria", "0"), "DROP")})


def _spawn_do_xml(texto, ident, spawn):
    if spawn:
        return
    for dentro in _NPCMAKER.findall(texto):
        for bruto in _NPC_SOLTO.findall(dentro):
            a = dict(_ATRIBUTO.findall(bruto))
            if a.get("id") != ident or not a.get("pos"):
                continue
            partes = a["pos"].split(";")
            if len(partes) < 3:
                continue
            spawn.update({"x": partes[0], "y": partes[1], "z": partes[2],
                          "direcao": partes[3] if len(partes) > 3 else "0",
                          "quantos": a.get("total", "1"),
                          "intervalo": re.sub(r"\D", "",
                                              a.get("respawn", "60")) or "60"})
            return


def _spawn_do_sql(texto, ident, perfil_do_servidor, de_volta, spawn):
    if spawn:
        return
    for tabela, colunas, valores in _INSERT.findall(texto):
        if tabela.lower() not in ("spawnlist", "custom_spawnlist"):
            continue
        nomes = _colunas_do_perfil(perfil_do_servidor, "spawn", colunas)
        if not nomes:
            continue
        for bloco in re.findall(r"\(([^()]*)\)", valores):
            crus = dict(zip(nomes, _dividir_valores(bloco)))
            neutros = dict((de_volta.get(k, k), v.strip().strip("'"))
                           for k, v in crus.items())
            if neutros.get("npc") != ident:
                continue
            spawn.update({"x": neutros.get("x", ""),
                          "y": neutros.get("y", ""),
                          "z": neutros.get("z", ""),
                          "direcao": neutros.get("direcao", "0"),
                          "quantos": neutros.get("quantos", "1"),
                          "intervalo": neutros.get("intervalo", "60")})
            return


def _loja_do_xml(texto, ident, arquivo, loja):
    """A loja e XML nos dois mundos; a dele e a que cita o id na lista de npcs."""
    if loja:
        return
    achado = _MULTISELL_NPC.search(texto)
    if achado is None:
        return
    citados = re.findall(r"<npc>\s*(\d+)\s*</npc>", achado.group(1), re.I)
    if ident not in citados:
        return
    linhas = []
    for bloco in _ITEM_LOJA.findall(texto):
        paga = _INGREDIENTE.findall(bloco)
        recebe = _PRODUCAO.findall(bloco)
        if paga or recebe:
            linhas.append({"paga": paga, "recebe": recebe})
    if linhas:
        loja.update({"id": arquivo.stem, "linhas": linhas, "arquivo": arquivo})

# ---------------------------------------------------------------------------
# Item e habilidade, de volta do servidor
# ---------------------------------------------------------------------------
# O mesmo caminho de volta do NPC, para os outros dois assuntos. A diferenca
# esta em duas coisas:
#
#   * o item e a habilidade guardam os status num bloco <for>, e nao em campos
#     soltos -- entao a volta devolve tambem a lista de (operacao, status,
#     valor), que e o que a tela mostra numa tabela;
#
#   * habilidade e XML ATE nos cores de banco. O L2jFrozen guarda item e NPC em
#     tabelas, mas as habilidades ficam em data/stats/skills, em arquivo. Por
#     isso aqui so ha o caminho do XML, e isso nao e um buraco.
_ITEM_INTEIRO = re.compile(
    r"<item\b[^>]*\bid\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</item>", re.I | re.S)
_SKILL_INTEIRO = re.compile(
    r"<skill\b[^>]*\bid\s*=\s*[\"'](\d+)[\"'][^>]*>(.*?)</skill>", re.I | re.S)
_BLOCO_FOR = re.compile(r"<for>(.*?)</for>", re.I | re.S)
# Os atributos podem vir em qualquer ordem, e ha cores que poem um `order`
# antes do `stat`, assim: `<set order="0x08" stat="pAtk" val="24"/>`. Exigir
# `stat` logo apos o nome da operacao fazia o programa ler zero status nesses
# servidores, sem dizer por que.
_OPERACAO = re.compile(
    r"<(add|baseadd|sub|mul|basemul|div|set|enchant|addMul|subDiv)\s+([^>]*?)/?>",
    re.I)

# As tabelas de item do banco, por tipo. A leitura precisa saber de qual veio
# para dizer se e arma, armadura ou o resto.
_TABELA_DO_TIPO = {
    "weapon": "Weapon", "custom_weapon": "Weapon",
    "armor": "Armor", "custom_armor": "Armor",
    "etcitem": "EtcItem", "custom_etcitem": "EtcItem",
}


def _estados_do_xml(corpo):
    """A lista de (operacao, status, valor) do bloco <for>."""
    estados = []
    for dentro in _BLOCO_FOR.findall(corpo):
        for operacao, atributos in _OPERACAO.findall(dentro):
            campos = dict(_ATRIBUTO.findall(atributos))
            if "stat" not in campos:
                continue
            # A ordem vem junto: regravar o item sem ela trocaria uma escolha
            # feita a mao pelo padrao da operacao, sem avisar.
            estados.append({"operacao": operacao, "estado": campos["stat"],
                            "ordem": campos.get("order", ""),
                            "valor": campos.get("val", "")})
    return estados


def _arquivos_para(pasta, perfil_do_servidor, qual):
    """
    Os arquivos do servidor, com os da pasta declarada na frente.

    A varredura para no primeiro arquivo que casa, entao a ordem decide o
    resultado. Sem isto, em alguns packs o item 1 vinha de `xml/recipes.xml`: ali
    `<item id="1">` e ingrediente de receita, e o que voltava era um item vazio.

    O perfil escreve o caminho a partir da raiz do servidor ("data/xml/items"),
    mas quem aponta a pasta e o usuario, e ele costuma apontar ja de dentro do
    `data`. Por isso o caminho e cortado pela cauda: tenta-se
    `data/xml/items`, depois `xml/items`, depois `items`, e vale o primeiro que
    encontra algo. Assim o mesmo perfil serve para as duas maneiras de apontar.

    O resto da arvore continua na lista, atras: ha cores que guardam as coisas
    fora da pasta de sempre, e deixar de olhar seria trocar um erro por outro.
    """
    todos = [q for q in pasta.rglob("*")
             if q.is_file() and q.suffix.lower() in (".xml", ".sql")]
    declarada = ((perfil_do_servidor.get("pastas") or {}).get(qual) or "")
    partes = [p for p in declarada.replace("\\", "/").split("/") if p]
    if not partes:
        return todos

    for corte in range(len(partes)):
        cauda = tuple(x.lower() for x in partes[corte:])
        dentro, fora = [], []
        for arquivo in todos:
            trecho = tuple(x.lower() for x in arquivo.parent.parts)
            (dentro if trecho[-len(cauda):] == cauda else fora).append(arquivo)
        if dentro:
            return dentro + fora
    return todos


def achar_item(pasta, ident, perfil_do_servidor, aoprogresso=None):
    """
    Procura o item no servidor e devolve o que ele tem, em campos neutros.

    None quando o id nao esta la -- a resposta util para "este item ainda nao
    existe do lado do servidor".
    """
    return _achar(pasta, ident, perfil_do_servidor, aoprogresso,
                  do_xml=_item_do_xml, do_sql=_item_do_sql, qual="itens")


def achar_skill(pasta, ident, perfil_do_servidor, aoprogresso=None):
    """
    Procura a habilidade no servidor.

    So olha XML: habilidade e arquivo ate nos cores que guardam item e NPC em
    tabelas.
    """
    return _achar(pasta, ident, perfil_do_servidor, aoprogresso,
                  do_xml=_skill_do_xml, do_sql=None, qual="skills")


def _achar(pasta, ident, perfil_do_servidor, aoprogresso, do_xml, do_sql,
           qual=""):
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroDeServidor("nao achei a pasta %s" % pasta)

    ident = str(ident).strip()
    arquivos = _arquivos_para(pasta, perfil_do_servidor, qual)
    for i, arquivo in enumerate(arquivos):
        if aoprogresso and i % 40 == 0:
            aoprogresso(i / float(max(1, len(arquivos))),
                        "procurando em %s" % arquivo.name)
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ident not in texto:
            continue

        achado = None
        if arquivo.suffix.lower() == ".xml":
            achado = do_xml(texto, ident, arquivo, perfil_do_servidor)
        elif do_sql is not None:
            achado = do_sql(texto, ident, arquivo, perfil_do_servidor)
        if achado is not None:
            if aoprogresso:
                aoprogresso(1.0, "pronto")
            return achado

    if aoprogresso:
        aoprogresso(1.0, "pronto")
    return None


def _desconverter(perfil_do_servidor, campos):
    """
    Devolve os valores do core aos nomes neutros.

    O aCis escreve `SELF` e `ACTIVE`; outros cores escrevem `TARGET_SELF` e
    `OP_PASSIVE`. Sem desfazer isso na volta, o nome do core apareceria na tela
    como se fosse o do programa, e voltaria assim para outro servidor.
    """
    if not (perfil_do_servidor.get("valores")
            or perfil_do_servidor.get("prefixos")):
        return campos
    saida = {}
    for chave, valor in campos.items():
        inverso = _inverso_de_valor(perfil_do_servidor, chave)
        saida[chave] = inverso.get(
            valor, _tirar_prefixo(perfil_do_servidor, chave, valor))
    return saida


def _item_do_xml(texto, ident, arquivo, perfil_do_servidor=None):
    lido = _corpo_do_elemento(texto, "item", ident)
    if lido is None:
        return None
    cabeca, corpo = lido
    return {"campos": _desconverter(perfil_do_servidor or {},
                                    dict(_SET_XML.findall(corpo))),
            "estados": _estados_do_xml(corpo),
            "tipo": cabeca.get("type", ""),
            "nome": cabeca.get("name", ""),
            "arquivo": arquivo, "formato": "xml", "aviso": ""}


def _tabelas_do_xml(corpo):
    """{apelido: "v1 v2 v3"} das <table> daquela habilidade."""
    return dict((nome.strip(), " ".join(valores.split()))
                for nome, valores in _TABELA_XML.findall(corpo))


def _abrir_tabelas(valor, tabelas):
    """
    Troca `#power` pelos numeros dele.

    Mostrar o apelido era honesto e inutil: nao dava para editar, e regravar
    escreveria `val="#power"` apontando para uma tabela que o XML novo nao
    teria. Um apelido sem tabela -- que acontece quando ela mora noutro
    arquivo -- fica como esta, porque inventar numeros seria pior.
    """
    texto = str(valor)
    return tabelas.get(texto, texto) if texto.startswith("#") else texto


def _skill_do_xml(texto, ident, arquivo, perfil_do_servidor=None):
    lido = _corpo_do_elemento(texto, "skill", ident)
    if lido is not None:
        cabeca, corpo = lido
        tabelas = _tabelas_do_xml(corpo)
        campos = _desconverter(
            perfil_do_servidor or {},
            dict((chave, _abrir_tabelas(valor, tabelas))
                 for chave, valor in _SET_XML.findall(corpo)))
        estados = _estados_do_xml(corpo)
        for entrada in estados:
            entrada["valor"] = _abrir_tabelas(entrada["valor"], tabelas)

        soltos = [v for v in list(campos.values())
                  + [e["valor"] for e in estados]
                  if str(v).startswith("#")]
        return {"campos": campos, "estados": estados,
                "niveis": cabeca.get("levels", "1"),
                "nome": cabeca.get("name", ""),
                "arquivo": arquivo, "formato": "xml",
                "aviso": ("%d apelido(s) sem tabela neste arquivo: %s"
                          % (len(soltos), ", ".join(sorted(set(soltos))[:4]))
                          if soltos else "")}
    return None


def _item_do_sql(texto, ident, arquivo, perfil_do_servidor):
    de_volta = _inverter((perfil_do_servidor.get("campos") or {}).get("itens"))
    for tabela, colunas, valores in _INSERT.findall(texto):
        tipo = _TABELA_DO_TIPO.get(tabela.lower())
        if tipo is None:
            continue
        assunto = "itens_" + tipo.lower().replace("etcitem", "etc")
        nomes = _colunas_do_perfil(perfil_do_servidor, assunto, colunas)
        if not nomes:
            nomes = _colunas_do_perfil(perfil_do_servidor, "itens", colunas)
        for bloco in re.findall(r"\(([^()]*)\)", valores):
            crus = _dividir_valores(bloco)
            if not crus or crus[0].strip().strip("'") != ident:
                continue
            if not nomes:
                return {"campos": {}, "estados": [], "tipo": tipo, "nome": "",
                        "arquivo": arquivo, "formato": "sql",
                        "aviso": "o INSERT nao nomeia as colunas e o perfil "
                                 "nao traz a ordem delas"}
            if len(nomes) != len(crus):
                # Core com uma coluna a mais ou a menos. Casar assim mesmo
                # poria preco no lugar de peso -- e o erro nao apareceria ate
                # alguem reclamar do item em jogo.
                return {"campos": {}, "estados": [], "tipo": tipo, "nome": "",
                        "arquivo": arquivo, "formato": "sql",
                        "aviso": "a tabela %s tem %d valores e o perfil "
                                 "descreve %d colunas"
                                 % (tabela, len(crus), len(nomes))}
            campos, estados, nome = {}, [], ""
            for coluna, valor in zip(nomes, crus):
                neutro = de_volta.get(coluna)
                if neutro is None:
                    continue
                valor = valor.strip().strip("'")
                valor = _inverso_de_valor(perfil_do_servidor,
                                          coluna).get(valor, valor)
                if neutro in ("nome", "name"):
                    nome = valor
                elif neutro in ESTADOS_EM_COLUNA:
                    if valor not in ("", "0", "0.0", "0.00000"):
                        estados.append({"operacao": "set", "estado": neutro,
                                        "valor": valor})
                elif neutro != "id":
                    campos[neutro] = valor
            return {"campos": campos, "estados": estados, "tipo": tipo,
                    "nome": nome, "arquivo": arquivo, "formato": "sql",
                    "aviso": ""}
    return None


# Campos neutros que no banco sao COLUNA e no XML vivem dentro do <for>. Na
# volta eles precisam sair dos campos e entrar na lista de status, senao a tela
# mostraria "pAtk" como se fosse um <set name="pAtk">, que o servidor de XML
# nao le.
ESTADOS_EM_COLUNA = ("pAtk", "mAtk", "pDef", "mDef", "pAtkSpd", "rCrit",
                     "sDef", "rShld", "rEvas", "accCombat", "maxMp")
