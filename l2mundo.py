#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O que o servidor precisa saber sobre um NPC: atributos, drop, spawn e loja.

O cliente sabe DESENHAR o NPC -- malha, textura, som -- e isso ja e trabalho da
aba de NPC. O que falta e o outro lado: quanto de vida ele tem, o que larga ao
morrer, onde nasce e o que vende. Nada disso existe no cliente.

Cada core guarda isso do seu jeito, e o modulo `l2servidor` cuida da traducao.
Aqui ficam so as formas que nao sao um campo simples:

    drop      no aCis mora DENTRO do <npc>, em <drops><category>; no banco e
              uma linha por item na tabela droplist
    spawn     no aCis e um <npcmaker> com <npc pos="x;y;z;h">; no banco e uma
              linha em spawnlist
    loja      o multisell, que nos dois casos e um XML proprio, com a lista de
              NPCs que o vendem e os pares ingrediente/produto

## As categorias de drop

O aCis separa em SPOIL (o que sai no roubo), CURRENCY (adena) e DROP (o resto).
O banco do L2J usa numero: 0 e drop normal e 1 e spoil, com as categorias
maiores servindo de sorteio por grupo. A conversao esta no perfil.

## Chance

No aCis a chance e percentual com casa decimal: `chance="23.2459"` e 23,2%. No
banco do L2J a mesma coisa costuma ser em centesimos de milesimo -- 1.000.000 e
100%. O perfil diz qual usar, porque errar isso faz o dragao largar tudo ou
nada.
"""

from pathlib import Path

import l2servidor

# O que o aCis chama cada gaveta de drop, e o numero equivalente no banco.
# As quatro sao as que o datapack usa de fato: HERB aparece 7.362 vezes, DROP
# 4.561, CURRENCY 1.905 e SPOIL 1.645. No banco so ha dois numeros, e tudo o
# que nao e roubo cai no zero.
CATEGORIAS = (("DROP", "0"), ("CURRENCY", "0"), ("HERB", "0"), ("SPOIL", "1"))
CATEGORIAS_ROTULO = tuple(nome for nome, _n in CATEGORIAS)

# Os campos de NPC que a tela oferece. Nome neutro (o mesmo que o aCis usa no
# <set name=>), rotulo, e valor de partida.
CAMPOS_DE_NPC = (
    ("type", "tipo", "Monster"),
    ("level", "nível", "70"),
    ("hp", "vida", "3000"),
    ("mp", "mana", "1500"),
    ("hpRegen", "regeneração de vida", "7.5"),
    ("mpRegen", "regeneração de mana", "2.7"),
    ("pAtk", "ataque físico", "700"),
    ("pDef", "defesa física", "300"),
    ("mAtk", "ataque mágico", "470"),
    ("mDef", "defesa mágica", "220"),
    ("crit", "crítico", "4"),
    ("atkSpd", "velocidade de ataque", "253"),
    ("mAtkSpd", "velocidade de magia", "333"),
    ("runSpd", "velocidade de corrida", "120"),
    ("walkSpd", "velocidade de caminhada", "50"),
    ("exp", "experiência", "0"),
    ("sp", "SP", "0"),
    ("aggroRange", "raio de agressão", "0"),
    ("attackRange", "alcance de ataque", "40"),
    ("radius", "raio de colisão", "8"),
    ("height", "altura de colisão", "24"),
    ("str", "STR", "40"),
    ("con", "CON", "43"),
    ("dex", "DEX", "30"),
    ("int", "INT", "21"),
    ("wit", "WIT", "20"),
    ("men", "MEN", "20"),
    ("sex", "sexo", "male"),
    ("corpseTime", "tempo do corpo (s)", "7"),
    ("rHand", "arma na mão direita", "0"),
    ("lHand", "arma na mão esquerda", "0"),
    ("targetable", "pode ser alvo", "true"),
    ("undying", "não morre", "false"),
)

# Os tipos de NPC que o aCis conhece e que se usam na pratica. A lista inteira
# tem dezenas; estas sao as que aparecem quando se cria conteudo.
TIPOS_DE_NPC = ("Monster", "Folk", "Merchant", "Warehouse", "Teleporter",
                "Guard", "RaidBoss", "GrandBoss", "Chest", "Trainer",
                "Npc", "ClanHallManager", "CastleBlacksmith", "Fisherman",
                "Auctioneer", "SymbolMaker", "VillageMaster")

SEXOS = ("male", "female", "etc")
SIM_NAO = ("", "true", "false")


class ErroDeMundo(Exception):
    pass


def _inteiro(texto, padrao=0):
    try:
        return int(float(str(texto).strip()))
    except (TypeError, ValueError):
        return padrao


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------
def xml_do_npc(perfil, ident, nome, titulo, campos, drops=(), id_base="",
               nome_pelo_servidor=True):
    """
    O NPC pronto para o servidor escolhido.

    No aCis o drop vai DENTRO do <npc>; por isso ele entra aqui, e nao numa
    chamada separada. No banco o drop e outra tabela, e sai a parte -- quem
    chama recebe os dois textos.

    `nome_pelo_servidor` escreve `usingServerSideName` e `usingServerSideTitle`.
    Com eles o servidor manda o nome junto com o NPC e o cliente so desenha o
    que recebeu -- que e a saida quando o cliente nao consegue resolver o nome
    sozinho, o caso do "NoNameNPC" num NPC de classe propria. Os perfis de
    banco ja traduzem esses dois campos para as colunas deles.
    """
    comentario = ("Gerado pelo L2PackTool. NPC base copiado no cliente: %s"
                  % id_base if id_base else "Gerado pelo L2PackTool.")

    campos = dict(campos)
    if nome_pelo_servidor:
        if nome:
            campos["usingServerSideName"] = "true"
        if titulo:
            campos["usingServerSideTitle"] = "true"

    if e_h5(perfil) and (perfil.get("formato") or "xml").lower() != "sql":
        return _npc_h5(perfil, ident, nome, titulo, campos, drops,
                       comentario), ".xml"

    if (perfil.get("formato") or "xml").lower() == "sql":
        juntos = {"id": ident, "idTemplate": ident, "nome": nome,
                  "title": titulo or ""}
        juntos.update(campos)
        texto = l2servidor.insert(perfil, "npcs",
                                  _traduzido(perfil, "npcs", juntos),
                                  comentario)
        if drops:
            texto += "\n" + sql_do_drop(perfil, ident, drops)
        return texto, ".sql"

    numerada = (perfil.get("categoria_de_drop") or "nome") == "numero"
    escala = float(perfil.get("escala_de_chance") or 1)
    dentro = (_drops_em_xml(drops, numerada=numerada, escala=escala)
              if drops else "")
    corpo = l2servidor.bloco_xml(
        "npc",
        {"id": str(ident), "idTemplate": str(ident),
         "name": nome or ("NPC %s" % ident), "title": titulo or ""},
        _traduzido(perfil, "npcs", campos), dentro, comentario)
    return l2servidor.documento_xml(corpo), ".xml"


def _traduzido(perfil, assunto, campos):
    traduzidos, _sobraram = l2servidor.traduzir_campos(perfil, assunto, campos)
    return dict((k, l2servidor.converter_valor(perfil, k, v))
                for k, v in traduzidos.items())


# ---------------------------------------------------------------------------
# Drop
# ---------------------------------------------------------------------------
def _na_escala(chance, escala):
    """A chance da tela (por cento) na unidade do core."""
    if escala == 1:
        return chance
    try:
        return "%g" % (float(chance) * escala)
    except (TypeError, ValueError):
        return chance


def _drops_em_xml(drops, nivel=2, numerada=False, escala=1.0):
    """
    <drops> com uma <category> por gaveta.

    Duas escritas para a mesma ideia: o aCis nomeia a gaveta
    (`type="DROP"`) e o L2J a numera (`id="0"`, com `-1` para o espolio). O
    perfil diz qual usar; escrever a errada da um NPC que carrega sem drop
    nenhum, e sem erro nenhum para avisar.

    A chance da categoria e a do sorteio do grupo; a do item, a dele dentro do
    grupo. Pondo a categoria em 100 e a chance no item, o numero que o usuario
    digitou e o que vale -- que e o que ele espera.

    Na forma numerada cada item ganha a sua gaveta: uma gaveta sorteia UM item
    entre os seus, entao juntar tudo numa so transformaria cinco drops
    independentes num drop unico. O espolio e a excecao -- ele e sempre a
    gaveta -1, e vai inteiro nela.
    """
    recuo = "\t" * nivel
    por_categoria = {}
    for entrada in drops:
        por_categoria.setdefault(entrada.get("categoria", "DROP"),
                                 []).append(entrada)

    linhas = ["%s<drops>" % recuo]
    gaveta = 0
    for categoria, lista in sorted(por_categoria.items()):
        if not numerada:
            grupos = [('type="%s"' % categoria, lista)]
        elif categoria == "SPOIL":
            grupos = [('id="-1"', lista)]
        else:
            grupos = []
            for entrada in lista:
                grupos.append(('id="%d"' % gaveta, [entrada]))
                gaveta += 1

        for marca, dentro in grupos:
            linhas.append('%s\t<category %s chance="100.0">' % (recuo, marca))
            for entrada in dentro:
                linhas.append(
                    '%s\t\t<drop itemid="%s" min="%s" max="%s" chance="%s"/>'
                    % (recuo, entrada["item"], entrada.get("minimo", 1),
                       entrada.get("maximo", 1),
                       _na_escala(entrada.get("chance", "1.0"), escala)))
            linhas.append("%s\t</category>" % recuo)
    linhas.append("%s</drops>" % recuo)
    return "\n".join(linhas)


def sql_do_drop(perfil, ident, drops):
    """Uma linha por item na tabela droplist."""
    escala = float(perfil.get("escala_de_chance") or 1.0)
    numero = dict(CATEGORIAS)
    linhas = []
    for entrada in drops:
        campos = {
            "npc": str(ident),
            "item": str(entrada["item"]),
            "minimo": str(entrada.get("minimo", 1)),
            "maximo": str(entrada.get("maximo", 1)),
            "categoria": numero.get(entrada.get("categoria", "DROP"), "0"),
            "chance": str(int(round(float(entrada.get("chance", 1.0))
                                    * escala))),
        }
        linhas.append(l2servidor.insert(perfil, "droplist",
                                        _traduzido(perfil, "droplist", campos)))
    return "".join(linhas)


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------
def spawn(perfil, ident, x, y, z, direcao=0, quantos=1, intervalo=60,
          nome_do_grupo=""):
    """
    Onde o NPC nasce.

    No aCis um spawn simples e um <npcmaker> com um <npc pos="x;y;z;h">. No
    banco e uma linha em spawnlist. As coordenadas se pegam em jogo, com o
    comando que mostra a posicao.
    """
    nome_do_grupo = nome_do_grupo or ("custom_%s" % ident)
    if e_h5(perfil):
        return _spawn_h5(perfil, ident, x, y, z, direcao, quantos, intervalo,
                         nome_do_grupo)
    if (perfil.get("formato") or "xml").lower() == "sql":
        campos = {"npc": str(ident), "x": str(x), "y": str(y), "z": str(z),
                  "direcao": str(direcao), "quantos": str(quantos),
                  "intervalo": str(intervalo), "local": nome_do_grupo}
        return l2servidor.insert(perfil, "spawn",
                                 _traduzido(perfil, "spawn", campos),
                                 "Gerado pelo L2PackTool"), ".sql"

    corpo = ('\t<npcmaker name="%s">\n'
             '\t\t<npc id="%s" pos="%s;%s;%s;%s" total="%s" respawn="%ssec"/>\n'
             '\t</npcmaker>'
             % (nome_do_grupo, ident, x, y, z, direcao, quantos, intervalo))
    return l2servidor.documento_xml(corpo), ".xml"


# ---------------------------------------------------------------------------
# Loja (multisell)
# ---------------------------------------------------------------------------
def multisell(ident, npcs, linhas, comentario=""):
    """
    A loja: quem vende, e o que se troca por o que.

    Multisell e XML nos dois mundos -- ate os cores de banco guardam a loja em
    arquivo. Por isso ela nao passa pelo perfil.

    Cada linha e {"paga": [(id, quantidade)], "recebe": [(id, quantidade)]}.
    Uma venda comum e pagar adena (id 57) e receber o item.
    """
    saida = ['<?xml version="1.0" encoding="UTF-8"?>']
    if comentario:
        saida.append("<!-- %s -->" % comentario)
    saida.append("<list>")

    if npcs:
        saida.append("\t<npcs>")
        for npc in npcs:
            saida.append("\t\t<npc>%s</npc>" % npc)
        saida.append("\t</npcs>")

    for linha in linhas:
        saida.append("\t<item>")
        for item, quantos in linha.get("paga", ()):
            saida.append('\t\t<ingredient id="%s" count="%s"/>' % (item, quantos))
        for item, quantos in linha.get("recebe", ()):
            saida.append('\t\t<production id="%s" count="%s"/>' % (item, quantos))
        saida.append("\t</item>")

    saida.append("</list>")
    return "\n".join(saida) + "\n"


def nome_do_multisell(ident):
    """O arquivo de multisell e o proprio id, com zeros a esquerda."""
    return "%s.xml" % str(ident).zfill(3)


# ---------------------------------------------------------------------------
# Gravar
# ---------------------------------------------------------------------------
def gravar(destino, nome, texto):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    alvo = destino / nome
    alvo.write_text(texto, encoding="utf-8", newline="")
    return alvo


# ---------------------------------------------------------------------------
# High Five (L2J e Mobius, do Gracia em diante)
# ---------------------------------------------------------------------------
# O <npc> ali nao e lista de <set>: cada numero mora num atributo de um
# elemento proprio, na forma que o datapack de fabrica usa:
#
#     <npc id="..." level="..." type="..." name="...">
#         <sex>MALE</sex>
#         <acquire exp="..." sp="..." />
#         <stats str="..." ...> <vitals .../> <attack .../> ... </stats>
#         <dropLists> <drop> <item id min max chance /> </drop> </dropLists>
#         <collision> <radius normal="..." /> <height normal="..." /> </collision>
#     </npc>
#
# A chance e em porcento, igual a da tela -- nao ha conversao. O Mobius chama
# as gavetas de <drop>/<spoil> e o L2J de <death>/<corpse>; o perfil detectado
# diz qual. E so o que o xsd do Mobius conhece entra: `mAtkSpd`, por exemplo,
# nao tem lugar no <npc> dele, e um atributo estranho derruba o ARQUIVO todo.
def e_h5(perfil):
    return (perfil or {}).get("npc_xml") == "h5"


def _atrs(pares):
    """' a="1" b="2"' so com os pares que tem valor."""
    return "".join(' %s="%s"' % (k, _esc(v)) for k, v in pares
                   if str(v).strip() != "")


def _esc(valor):
    return (str(valor).strip().replace("&", "&amp;").replace("<", "&lt;")
            .replace('"', "&quot;"))


def _npc_h5(perfil, ident, nome, titulo, campos, drops, comentario):
    c = dict((k, str(v).strip()) for k, v in dict(campos).items())
    r = "\t\t"
    linhas = ["\t<!-- %s -->" % comentario] if comentario else []
    linhas.append("\t<npc%s>" % _atrs((
        ("id", ident), ("level", c.get("level", "")),
        ("type", c.get("type", "")), ("name", nome or "NPC %s" % ident),
        ("usingServerSideName", c.get("usingServerSideName", "")),
        ("title", titulo or ""),
        ("usingServerSideTitle", c.get("usingServerSideTitle", "")))))
    if c.get("sex"):
        linhas.append("%s<sex>%s</sex>" % (r, c["sex"].upper()))
    equipamento = _atrs((("rhand", c.get("rHand", "") if c.get("rHand") != "0"
                          else ""),
                         ("lhand", c.get("lHand", "") if c.get("lHand") != "0"
                          else "")))
    if equipamento:
        linhas.append("%s<equipment%s />" % (r, equipamento))
    # O Mobius da a experiencia em pontos (`exp`); o L2J, como multiplicador
    # da tabela por nivel (`expRate`), e o xsd dele recusa `exp`.
    if (perfil.get("gavetas_de_drop") or ["drop"])[0] == "death":
        adquire = _atrs((("expRate", c.get("expRate", "")),
                         ("sp", c.get("sp", ""))))
    else:
        adquire = _atrs((("exp", c.get("exp", "")), ("sp", c.get("sp", ""))))
    if adquire:
        linhas.append("%s<acquire%s />" % (r, adquire))

    linhas.append("%s<stats%s>" % (r, _atrs(
        [(k, c.get(k, "")) for k in ("str", "int", "dex", "wit", "con", "men")])))
    vitais = _atrs((("hp", c.get("hp", "")), ("hpRegen", c.get("hpRegen", "")),
                    ("mp", c.get("mp", "")), ("mpRegen", c.get("mpRegen", ""))))
    if vitais:
        linhas.append("%s\t<vitals%s />" % (r, vitais))
    ataque = _atrs((("physical", c.get("pAtk", "")),
                    ("magical", c.get("mAtk", "")),
                    ("critical", c.get("crit", "")),
                    ("attackSpeed", c.get("atkSpd", "")),
                    ("range", c.get("attackRange", ""))))
    if ataque:
        linhas.append("%s\t<attack%s />" % (r, ataque))
    defesa = _atrs((("physical", c.get("pDef", "")),
                    ("magical", c.get("mDef", ""))))
    if defesa:
        linhas.append("%s\t<defence%s />" % (r, defesa))
    if c.get("walkSpd") or c.get("runSpd"):
        linhas.append("%s\t<speed>" % r)
        if c.get("walkSpd"):
            linhas.append('%s\t\t<walk ground="%s" />' % (r, _esc(c["walkSpd"])))
        if c.get("runSpd"):
            linhas.append('%s\t\t<run ground="%s" />' % (r, _esc(c["runSpd"])))
        linhas.append("%s\t</speed>" % r)
    linhas.append("%s</stats>" % r)

    estado = _atrs((("targetable", c.get("targetable", "")),
                    ("undying", c.get("undying", ""))))
    if estado:
        linhas.append("%s<status%s />" % (r, estado))
    if c.get("corpseTime"):
        linhas.append("%s<corpseTime>%s</corpseTime>" % (r, _esc(c["corpseTime"])))
    if c.get("aggroRange") and c["aggroRange"] != "0":
        linhas.append('%s<ai aggroRange="%s" isAggressive="true" />'
                      % (r, _esc(c["aggroRange"])))

    if drops:
        normal, espolio = (perfil.get("gavetas_de_drop")
                           or ["drop", "spoil"])[:2]
        comuns = [d for d in drops if d.get("categoria", "DROP") != "SPOIL"]
        roubo = [d for d in drops if d.get("categoria", "DROP") == "SPOIL"]
        linhas.append("%s<dropLists>" % r)
        for gaveta, lista in ((normal, comuns), (espolio, roubo)):
            if not lista:
                continue
            linhas.append("%s\t<%s>" % (r, gaveta))
            for d in lista:
                linhas.append('%s\t\t<item id="%s" min="%s" max="%s" '
                              'chance="%s" />'
                              % (r, _esc(d["item"]), d.get("minimo", 1),
                                 d.get("maximo", 1), d.get("chance", "1.0")))
            linhas.append("%s\t</%s>" % (r, gaveta))
        linhas.append("%s</dropLists>" % r)

    colisao = []
    if c.get("radius"):
        colisao.append('%s\t<radius normal="%s" />' % (r, _esc(c["radius"])))
    if c.get("height"):
        colisao.append('%s\t<height normal="%s" />' % (r, _esc(c["height"])))
    if colisao:
        linhas += ["%s<collision>" % r] + colisao + ["%s</collision>" % r]
    linhas.append("\t</npc>")

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<list xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="../../../xsd/npcs.xsd">\n'
            + "\n".join(linhas) + "\n</list>\n")


def _spawn_h5(perfil, ident, x, y, z, direcao, quantos, intervalo,
              nome_do_grupo):
    """
    Mobius: um XML em `data/spawns`; L2J: um XML em `data/spawnlist`, com o
    mesmo `<spawn><npc x= y= z=/>`. Sem nenhuma das duas pastas, o spawn vai
    para o banco, na `custom_spawnlist`, que o core le com
    `CustomSpawnlistTable = True`.
    """
    pasta_de_spawn = (perfil.get("pastas") or {}).get("spawn") or ""
    if pasta_de_spawn:
        # Mesmo formato nos dois; so o nome do xsd muda com a pasta.
        xsd = ("spawnlist.xsd" if pasta_de_spawn.endswith("spawnlist")
               else "spawns.xsd")
        corpo = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<list enabled="true" '
                 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                 'xsi:noNamespaceSchemaLocation="../xsd/%s">\n'
                 '\t<!-- Gerado pelo L2PackTool -->\n'
                 '\t<spawn name="%s">\n'
                 '\t\t<npc id="%s" x="%s" y="%s" z="%s" heading="%s" '
                 'count="%s" respawnDelay="%s" />\n'
                 '\t</spawn>\n'
                 '</list>\n'
                 % (xsd, _esc(nome_do_grupo), _esc(ident), _esc(x), _esc(y),
                    _esc(z), _esc(direcao), _esc(quantos), _esc(intervalo)))
        return corpo, ".xml"
    texto = ("-- Gerado pelo L2PackTool. No L2J High Five o spawn mora no "
             "banco;\n-- custom_spawnlist precisa de CustomSpawnlistTable = "
             "True no General.properties.\n"
             "INSERT INTO `custom_spawnlist` (`location`, `count`, "
             "`npc_templateid`, `locx`, `locy`, `locz`, `randomx`, `randomy`, "
             "`heading`, `respawn_delay`, `respawn_random`, `loc_id`, "
             "`periodOfDay`) VALUES\n"
             "('%s', %d, %d, %d, %d, %d, 0, 0, %d, %d, 0, 0, 0);\n"
             % (str(nome_do_grupo).replace("'", "''")[:40], _inteiro(quantos, 1),
                _inteiro(ident), _inteiro(x), _inteiro(y), _inteiro(z),
                _inteiro(direcao), _inteiro(intervalo, 60)))
    return texto, ".sql"
