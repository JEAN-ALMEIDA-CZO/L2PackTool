#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Os mobs do servidor: status, skills e lista de drop.

Um NPC do servidor mora num `<npc>` dentro de `data/xml/npcs/*.xml`, e cada
arquivo carrega ate mil deles. Tres blocos interessam a quem mexe em pack:

    <npc id="20001" name="Gremlin" title="">
        <set name="level" val="1"/>          <- o status
        <ai type="DEFAULT" .../>
        <skills>
            <skill id="4416" level="13"/>    <- as skills
        </skills>
        <drops>
            <category id="1">                <- a lista de drop
                <drop itemid="112" min="1" max="1" chance="79637"/>
            </category>
        </drops>
    </npc>

## Por que isto nao usa um parser de XML

Reescrever o arquivo com `ElementTree` reformata os OUTROS mil NPCs junto: some
comentario, muda ordem de atributo, troca tabulacao por espaco. Um `git diff`
de mil linhas para editar um mob e um convite a perder alguma coisa sem
perceber.

Entao aqui e cirurgia no texto. De cada filho de `<npc>` guarda-se o **texto
cru** junto com o modelo; na hora de gravar, so o que foi mexido e regerado, e
o resto volta byte a byte. Assim `<petdata>` com as suas cem linhas de `<stat>`,
`<minions>`, e qualquer bloco que este programa nao entenda, atravessam a
edicao intactos.

## O que o core exige, e que este modulo cobra

Lido de `NpcTable.java`, nao do datapack:

- `<ai>` le `type`, `ssCount`, `ssRate`, `spsCount`, `spsRate`, `aggro`,
  `canMove` e `seedable` **sem verificar se existem**. Faltando um, o servidor
  estoura ao carregar. Havendo `clan`, `clanRange` passa a ser obrigatorio pelo
  mesmo motivo.
- `<drop>` de um item que a tabela de itens nao conhece e **descartado com um
  aviso no log** -- em jogo o mob simplesmente nao dropa, e ninguem descobre
  por que sem ler o log.
- `chance` vai de 1 a `DropData.MAX_CHANCE`, que e **1.000.000**. Entao
  `79637` e 7,9637%.
- `category id="-1"` e spoil (sweep); de 0 para cima sao grupos de drop comum.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

# As pastas na ordem em que `NpcTable.hashFiles` as le. A ordem importa: id
# repetido faz valer o ultimo a carregar.
PASTAS = ("", "raidboss", "grandboss", "farmzone", "custom", "events")

# `DropData.MAX_CHANCE`. Uma chance de 1.000.000 e 100%.
CHANCE_CHEIA = 1000000

# Spoil. O core trata esta categoria a parte: ela e sempre visitada.
CATEGORIA_SPOIL = -1

# Os atributos que `NpcTable` le de `<ai>` sem conferir se existem.
AI_OBRIGATORIOS = ("type", "ssCount", "ssRate", "spsCount", "spsRate",
                   "aggro", "canMove", "seedable")

# Os `<set>` que todo NPC do pack tem. Servem de esqueleto para um mob novo e
# de ordem de exibicao na tela -- nao de proibicao: `set` fora desta lista e
# guardado como veio.
STATUS = (
    ("level", "nível"), ("type", "tipo"), ("exp", "exp"),
    ("expRate", "taxa de exp"), ("sp", "sp"),
    ("hp", "HP"), ("mp", "MP"), ("hpRegen", "regen HP"),
    ("mpRegen", "regen MP"), ("pAtk", "atq. físico"),
    ("pDef", "def. física"), ("mAtk", "atq. mágico"),
    ("mDef", "def. mágica"), ("crit", "crítico"), ("atkSpd", "vel. atq."),
    ("walkSpd", "vel. andar"), ("runSpd", "vel. correr"),
    ("str", "STR"), ("int", "INT"), ("dex", "DEX"),
    ("wit", "WIT"), ("con", "CON"), ("men", "MEN"),
    ("attackRange", "alcance"),
    ("radius", "raio"), ("height", "altura"),
    ("rHand", "mão direita"), ("lHand", "mão esquerda"),
    ("corpseTime", "tempo do corpo"), ("dropHerbGroup", "grupo de erva"),
)

# Os tipos que o core distingue para efeito de drop de raid.
TIPOS_DE_RAID = ("L2RaidBoss", "L2GrandBoss")

# Os quatro que o pack usa. Nao ha lista fechada no core -- o valor vira o nome
# de uma classe de AI --, entao o combo aceita escrever outro.
TIPOS_DE_AI = ("DEFAULT", "MAGE", "ARCHER", "CORPSE")

# Os tipos de NPC mais usados no pack, na frente do combo. Tambem nao e lista
# fechada: `type` vira o nome de uma classe do servidor.
TIPOS_DE_NPC = (
    "Monster", "Folk", "Servitor", "RaidBoss", "GrandBoss", "Guard",
    "SiegeGuard", "Merchant", "Trainer", "Gatekeeper", "WarehouseKeeper",
    "Chest", "FriendlyMonster", "PenaltyMonster", "Pet", "BabyPet",
    "TamedBeast", "FeedableBeast", "Walker", "ClassMaster",
)

# `L2Skill.SKILL_NPC_RACE`. Uma linha `<skill id="4416" level="N"/>` NAO e uma
# skill: o core le o `level` como a RACA do mob e sai fora sem registrar nada.
# Mostra-la junto das outras deixaria alguem apagar a raca achando que estava
# tirando um golpe.
SKILL_DA_RACA = 4416

# A raca de um mob, pelo numero que vai no `level` da 4416. Os nomes sao os que
# o cliente usa; o core so guarda o numero.
RACAS = {
    "1": "Undead", "2": "Magic Creature", "3": "Beast", "4": "Animal",
    "5": "Plant", "6": "Humanoid", "7": "Spirit", "8": "Angel",
    "9": "Demon", "10": "Dragon", "11": "Giant", "12": "Bug",
    "13": "Fairy", "14": "Human", "15": "Elf", "16": "Dark Elf",
    "17": "Orc", "18": "Dwarf", "19": "Other", "20": "Non-living Being",
    "21": "Siege Weapon", "22": "Defending Army", "23": "Mercenary",
    "24": "Unknown",
}

# Os blocos que este modulo entende e reescreve. Qualquer outro filho de `<npc>`
# -- `<petdata>` com a tabela de niveis do pet, `<teachTo>` -- atravessa a
# edicao com o texto exato que tinha.
BLOCOS_EDITAVEIS = ("set", "ai", "skills", "drops", "minions")

# No High Five (L2J e Mobius, do Gracia em diante) o status nao e uma lista de
# `<set>`: cada numero mora num atributo de um elemento proprio. A tabela diz
# onde, com o mesmo nome neutro que a tela ja usa para o aCis -- assim a tela
# nao precisa saber qual dos dois esta editando. `None` no atributo quer
# dizer que o valor e o TEXTO do elemento (`<corpseTime>7</corpseTime>`).
CAMPOS_H5 = (
    ("level", "", "level"), ("type", "", "type"),
    ("exp", "acquire", "exp"), ("expRate", "acquire", "expRate"),
    ("sp", "acquire", "sp"),
    ("hp", "stats/vitals", "hp"), ("mp", "stats/vitals", "mp"),
    ("hpRegen", "stats/vitals", "hpRegen"),
    ("mpRegen", "stats/vitals", "mpRegen"),
    ("pAtk", "stats/attack", "physical"), ("pDef", "stats/defence", "physical"),
    ("mAtk", "stats/attack", "magical"), ("mDef", "stats/defence", "magical"),
    ("crit", "stats/attack", "critical"),
    ("atkSpd", "stats/attack", "attackSpeed"),
    ("attackRange", "stats/attack", "range"),
    ("walkSpd", "stats/speed/walk", "ground"),
    ("runSpd", "stats/speed/run", "ground"),
    ("str", "stats", "str"), ("int", "stats", "int"), ("dex", "stats", "dex"),
    ("wit", "stats", "wit"), ("con", "stats", "con"), ("men", "stats", "men"),
    ("radius", "collision/radius", "normal"),
    ("height", "collision/height", "normal"),
    ("rHand", "equipment", "rhand"), ("lHand", "equipment", "lhand"),
    ("corpseTime", "corpseTime", None),
)

# Os filhos de `<npc>` que a tela do High Five edita, inteiros ou em parte.
BLOCOS_EDITAVEIS_H5 = ("ai", "skillList", "dropLists", "stats", "acquire",
                       "collision", "equipment", "corpseTime", "parameters")

# `AIType` do core do High Five.
TIPOS_DE_AI_H5 = ("FIGHTER", "ARCHER", "BALANCED", "MAGE", "HEALER", "CORPSE")

_NPC = re.compile(r"[ \t]*<npc\s[^>]*?>.*?</npc>[ \t]*\r?\n?", re.S)
_ATRIBUTO = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')


def _atributos(texto):
    """Os atributos de uma tag, na ordem em que estao escritos."""
    return dict(_ATRIBUTO.findall(texto))


# =========================================================================
# achar os arquivos
# =========================================================================
def pasta_de_npcs(raiz):
    """
    A pasta `npcs` do datapack, a partir de qualquer ponto do servidor.

    Aceita tanto a raiz do servidor quanto a propria pasta de npcs, porque
    quem usa aponta um ou outro sem pensar.
    """
    caminho = Path(raiz)
    if caminho.name.lower() == "npcs" and caminho.is_dir():
        return caminho
    # `xml/npcs` e o aCis; `stats/npcs` e o L2J e o Mobius do Gracia em
    # diante. A raiz apontada pode ser o servidor, o `game` ou o `data`.
    for meio in (("xml",), ("stats",)):
        for antes in ((), ("data",), ("game", "data"),
                      ("dist", "game", "data"),
                      ("build", "dist", "game", "data")):
            tentativa = caminho.joinpath(*(antes + meio + ("npcs",)))
            if tentativa.is_dir():
                return tentativa
    if (caminho / "npcs").is_dir():
        return caminho / "npcs"
    # Ultimo recurso: a pasta que o farejador do servidor achou -- a que tem
    # mais <npc> --, para datapack com arrumacao propria.
    try:
        import l2servidor
        achada = l2servidor.raiz_de(caminho, l2servidor.farejar(caminho), "npcs")
        if achada is not None:
            return achada
    except Exception:                               # noqa: BLE001
        pass
    return caminho / "npcs"


def arquivos(pasta):
    """Os .xml que o core carrega, na ordem dele."""
    pasta = Path(pasta)
    achados = []
    for sub in PASTAS:
        diretorio = pasta / sub if sub else pasta
        if not diretorio.is_dir():
            continue
        achados.extend(sorted(p for p in diretorio.glob("*.xml")
                              if p.is_file()))
    return achados


def _texto(caminho):
    return Path(caminho).read_text(encoding="utf-8", errors="replace")


# =========================================================================
# ler
# =========================================================================
def _filhos(dentro):
    """
    Os filhos diretos de `<npc>`, cada um com o texto cru que o originou.

    Devolve [(tag, texto cru)]. O que nao for tag -- espaco entre os blocos,
    comentario solto -- vira ("", texto), e assim tambem volta no lugar certo.
    """
    saida = []
    posicao = 0
    while True:
        abre = dentro.find("<", posicao)
        if abre < 0:
            break
        if dentro[abre:abre + 4] == "<!--":
            fim = dentro.find("-->", abre)
            fim = len(dentro) if fim < 0 else fim + 3
            saida.append(("", dentro[posicao:fim]))
            posicao = fim
            continue
        fim_tag = dentro.find(">", abre)
        if fim_tag < 0:
            break
        tag = re.match(r"<\s*([\w:-]+)", dentro[abre:fim_tag + 1])
        if tag is None:
            posicao = fim_tag + 1
            continue
        nome = tag.group(1)
        if dentro[fim_tag - 1] == "/":
            fim = fim_tag + 1
        else:
            fechamento = "</%s>" % nome
            achado = dentro.find(fechamento, fim_tag)
            fim = (fim_tag + 1) if achado < 0 else achado + len(fechamento)
        saida.append((nome, dentro[posicao:fim]))
        posicao = fim
    if posicao < len(dentro):
        saida.append(("", dentro[posicao:]))
    return saida


def _ler_drops(cru):
    """`<drops>` -> [{"id": "1", "itens": [{...}]}], preservando a ordem."""
    categorias = []
    for bloco in re.finditer(r"<category\s[^>]*?>(.*?)</category>", cru, re.S):
        atributos = _atributos(bloco.group(0)[:bloco.group(0).find(">") + 1])
        itens = []
        for drop in re.finditer(r"<drop\s[^>]*?/>", bloco.group(1)):
            itens.append(_atributos(drop.group(0)))
        categorias.append({"id": atributos.get("id", "0"), "itens": itens})
    return categorias


def _ler_skills(cru):
    return [_atributos(m.group(0))
            for m in re.finditer(r"<skill\s[^>]*?/>", cru)]


def _ler_minions(cru):
    return [_atributos(m.group(0))
            for m in re.finditer(r"<minion\s[^>]*?/>", cru)]


def e_a_raca(skill):
    """Esta linha de `<skill>` é a raça do mob, e não um golpe?"""
    return str(skill.get("id", "")).strip() == str(SKILL_DA_RACA)


def raca_de(npc):
    """O número da raça do mob, ou "" se ele não declara uma."""
    for s in npc.get("skills") or []:
        if e_a_raca(s):
            return str(s.get("level", ""))
    return ""


def golpes_de(npc):
    """As skills de verdade -- sem a linha 4416, que é a raça."""
    return [s for s in npc.get("skills") or [] if not e_a_raca(s)]


def _modelo(cru, arquivo, texto_do_arquivo=""):
    """Um `<npc>` cru vira o dicionario que a tela edita."""
    if dialeto(cru) == "h5":
        return _modelo_h5(cru, arquivo, texto_do_arquivo)
    fim_abertura = cru.find(">")
    fecho = cru.rfind("</npc>")
    cabeca = cru[:fim_abertura + 1]
    dentro = cru[fim_abertura + 1:fecho]
    # O fecho vem do texto cru, com o que houver depois dele. Reinventar isso
    # custou uma linha em branco a mais em cada mob na primeira versao.
    rabo = cru[fecho:]
    atributos = _atributos(cabeca)

    npc = {
        "id": atributos.get("id", ""),
        "name": atributos.get("name", ""),
        "title": atributos.get("title", ""),
        "atributos": atributos,
        "arquivo": Path(arquivo),
        "cru": cru,
        "cabeca": cabeca,
        "rabo": rabo,
        "sets": [],
        "ai": {},
        "skills": [],
        "drops": [],
        "minions": [],
        "filhos": _filhos(dentro),
        "mexidos": set(),
        "dialeto": "acis",
    }
    for tag, texto in npc["filhos"]:
        if tag == "set":
            a = _atributos(texto)
            npc["sets"].append((a.get("name", ""), a.get("val", "")))
        elif tag == "ai":
            npc["ai"] = _atributos(texto)
        elif tag == "skills":
            npc["skills"] = _ler_skills(texto)
        elif tag == "drops":
            npc["drops"] = _ler_drops(texto)
        elif tag == "minions":
            npc["minions"] = _ler_minions(texto)
    return npc


def blocos_preservados(npc):
    """
    Os filhos que este programa não edita e devolve como vieram.

    A tela mostra isso: quem abre um pet e vê `petdata` na lista fica sabendo
    que aquelas cem linhas continuam lá, em vez de desconfiar que sumiram.
    """
    editaveis = (BLOCOS_EDITAVEIS_H5 if npc.get("dialeto") == "h5"
                 else BLOCOS_EDITAVEIS)
    vistos = []
    for tag, _texto in npc.get("filhos") or []:
        if tag and tag not in editaveis and tag not in vistos:
            vistos.append(tag)
    return vistos


def listar(pasta, aoprogresso=None):
    """
    Um registro por NPC, leve, para a lista da tela.

    Ler os 6.399 por inteiro para mostrar uma lista seria pagar o preco todo
    de uma vez; aqui sai so o que a lista mostra, e o resto vem quando um for
    marcado.
    """
    todos = arquivos(pasta)
    saida = []
    for numero, arquivo in enumerate(todos):
        if aoprogresso:
            aoprogresso(numero / float(len(todos) or 1), arquivo.name)
        texto = _texto(arquivo)
        for bloco in _NPC.finditer(texto):
            cru = bloco.group(0)
            cabeca = cru[:cru.find(">") + 1]
            a = _atributos(cabeca)
            if dialeto(cru) == "h5":
                nivel, tipo = a.get("level", ""), a.get("type", "")
                drops = _dentro_de(cru, "dropLists").count("<item ")
                skills = _dentro_de(cru, "skillList").count("<skill ")
            else:
                achado = re.search(r'<set name="level" val="([^"]*)"', cru)
                nivel = achado.group(1) if achado else ""
                achado = re.search(r'<set name="type" val="([^"]*)"', cru)
                tipo = achado.group(1) if achado else ""
                drops, skills = cru.count("<drop "), cru.count("<skill ")
            saida.append({
                "id": a.get("id", ""),
                "nome": a.get("name", ""),
                "titulo": a.get("title", ""),
                "tipo": tipo,
                "nivel": nivel,
                "drops": drops,
                "skills": skills,
                "arquivo": arquivo,
            })
    if aoprogresso:
        aoprogresso(1.0, "")
    return saida


def ler(arquivo, ident):
    """O NPC inteiro, ou None se ele não estiver neste arquivo."""
    ident = str(ident)
    texto = _texto(arquivo)
    for bloco in _NPC.finditer(texto):
        cru = bloco.group(0)
        if _atributos(cru[:cru.find(">") + 1]).get("id") == ident:
            return _modelo(cru, arquivo, texto)
    return None


# =========================================================================
# escrever
# =========================================================================
def _recuo(cru):
    """A tabulação do `<npc>`, para os filhos saírem alinhados com o arquivo."""
    linha = cru.split("<npc", 1)[0]
    return linha if linha.strip() == "" else "\t"


def _tag_set(nome, valor):
    return '<set name="%s" val="%s"/>' % (nome, valor)


def _tag_ai(ai):
    ordem = list(AI_OBRIGATORIOS) + [c for c in ai
                                     if c not in AI_OBRIGATORIOS]
    return "<ai %s/>" % " ".join('%s="%s"' % (c, ai[c])
                                 for c in ordem if c in ai)


def xml(npc):
    """
    O bloco `<npc>` pronto para entrar no arquivo.

    Só o que foi mexido é regerado; o resto volta com o texto exato que veio.
    É o que mantém `<petdata>`, `<minions>` e comentários intactos numa edição
    que só mudou o HP.

    Cada pedaço já traz a quebra de linha e o recuo que o precediam no arquivo,
    então o que é regerado também precisa trazer -- e o fecho `</npc>` vem do
    texto cru, não de uma emenda. Reinventar aquele fecho custou uma linha em
    branco a mais em cada um dos 6.532 mobs na primeira versão.
    """
    if npc.get("dialeto") == "h5":
        return _xml_h5(npc)
    recuo = _recuo(npc["cru"])
    dentro = recuo + "\t"
    mexidos = npc.get("mexidos") or set()

    partes = []
    feitos = set()
    for tag, texto in npc["filhos"]:
        if tag == "set" and "sets" in mexidos:
            # Os `<set>` saem todos de uma vez, no lugar do primeiro: eles são
            # uma lista só para quem edita, e espalhá-los pelos lugares
            # antigos embaralharia a ordem ao tirar ou pôr um.
            if "sets" not in feitos:
                feitos.add("sets")
                partes.append("".join("\n" + dentro + _tag_set(n, v)
                                      for n, v in npc["sets"]))
            continue
        if tag == "ai" and "ai" in mexidos:
            partes.append("\n" + dentro + _tag_ai(npc["ai"]))
            feitos.add("ai")
            continue
        if tag == "skills" and "skills" in mexidos:
            bloco = _bloco_skills(npc["skills"], dentro)
            partes.append(("\n" + bloco) if bloco else "")
            feitos.add("skills")
            continue
        if tag == "drops" and "drops" in mexidos:
            bloco = _bloco_drops(npc["drops"], dentro)
            partes.append(("\n" + bloco) if bloco else "")
            feitos.add("drops")
            continue
        if tag == "minions" and "minions" in mexidos:
            bloco = _bloco_minions(npc["minions"], dentro)
            partes.append(("\n" + bloco) if bloco else "")
            feitos.add("minions")
            continue
        partes.append(texto)

    # Bloco que passou a existir agora -- as primeiras skills, o primeiro drop.
    # Ele entra ANTES do espaço final, que é o recuo do `</npc>`.
    novos = []
    if "skills" in mexidos and "skills" not in feitos:
        novos.append(_bloco_skills(npc["skills"], dentro))
    if "drops" in mexidos and "drops" not in feitos:
        novos.append(_bloco_drops(npc["drops"], dentro))
    if "minions" in mexidos and "minions" not in feitos:
        novos.append(_bloco_minions(npc.get("minions") or [], dentro))
    novos = ["\n" + b for b in novos if b]
    if novos:
        onde = len(partes)
        if partes and partes[-1].strip() == "":
            onde -= 1
        partes[onde:onde] = novos

    # A abertura so e regerada se os atributos foram mexidos. Tres mobs do
    # pack tem espaco duplo entre `id=` e `name=`, e normalizar aquilo poria no
    # diff uma linha que ninguem pediu.
    if "atributos" in mexidos or not npc.get("cabeca"):
        cabeca = "%s<npc %s>" % (recuo, " ".join(
            '%s="%s"' % (c, v) for c, v in npc["atributos"].items()))
    else:
        cabeca = npc["cabeca"]
    return cabeca + "".join(partes) + npc.get("rabo", "%s</npc>\n" % recuo)


def _bloco_skills(skills, dentro):
    if not skills:
        return ""
    linhas = [dentro + "<skills>"]
    for s in skills:
        linhas.append('%s\t<skill id="%s" level="%s"/>'
                      % (dentro, s.get("id", ""), s.get("level", "1")))
    linhas.append(dentro + "</skills>")
    return "\n".join(linhas)


def _bloco_drops(drops, dentro):
    cheias = [c for c in drops if c.get("itens")]
    if not cheias:
        return ""
    linhas = [dentro + "<drops>"]
    for categoria in cheias:
        linhas.append('%s\t<category id="%s">' % (dentro, categoria["id"]))
        for item in categoria["itens"]:
            linhas.append('%s\t\t<drop itemid="%s" min="%s" max="%s" '
                          'chance="%s"/>'
                          % (dentro, item.get("itemid", ""),
                             item.get("min", "1"), item.get("max", "1"),
                             item.get("chance", "1")))
        linhas.append("%s\t</category>" % dentro)
    linhas.append(dentro + "</drops>")
    return "\n".join(linhas)


def _bloco_minions(minions, dentro):
    if not minions:
        return ""
    linhas = [dentro + "<minions>"]
    for m in minions:
        linhas.append('%s\t<minion id="%s" min="%s" max="%s"/>'
                      % (dentro, m.get("id", ""), m.get("min", "1"),
                         m.get("max", "1")))
    linhas.append(dentro + "</minions>")
    return "\n".join(linhas)


def gravar(npc, fazer_copia=True):
    """
    Troca só este `<npc>` dentro do arquivo dele. Devolve o caminho da cópia.

    O resto do arquivo -- os outros mil NPCs -- não é tocado em byte nenhum.
    """
    arquivo = Path(npc["arquivo"])
    texto = _texto(arquivo)
    if npc["cru"] not in texto:
        raise ValueError("o npc %s mudou no arquivo desde que foi lido"
                         % npc["id"])
    copia = None
    if fazer_copia:
        copia = arquivo.with_name(
            "%s.%s.bak" % (arquivo.name,
                           datetime.now().strftime("%Y%m%d-%H%M%S")))
        shutil.copy2(arquivo, copia)
    novo = texto.replace(npc["cru"], xml(npc), 1)
    arquivo.write_text(novo, encoding="utf-8", newline="")
    return copia


# =========================================================================
# conferir
# =========================================================================
def porcentagem(chance, npc=None):
    """`79637` -> `7,9637%`. É como o número é escrito e não como ele é lido.

    No High Five a chance já é escrita em porcento: `chance="70"` é 70%.
    """
    try:
        if e_h5(npc):
            return float(chance)
        return 100.0 * float(chance) / CHANCE_CHEIA
    except (TypeError, ValueError):
        return 0.0


def e_h5(npc):
    """O mob é do formato do High Five (L2J/Mobius), e não do aCis?"""
    return bool(npc) and npc.get("dialeto") == "h5"


def chance_padrao(npc):
    """A chance de um drop recém-posto: 1%, na unidade do formato."""
    return "1" if e_h5(npc) else "10000"


def chaves_de_ai(npc):
    """Os campos do <ai> que a tela mostra mesmo vazios."""
    return () if e_h5(npc) else AI_OBRIGATORIOS


def tipos_de_ai(npc):
    return TIPOS_DE_AI_H5 if e_h5(npc) else TIPOS_DE_AI


def da_porcentagem(por_cento):
    """O caminho de volta: `7.9637` -> `79637`."""
    try:
        return max(1, min(CHANCE_CHEIA,
                          int(round(float(por_cento) * CHANCE_CHEIA / 100.0))))
    except (TypeError, ValueError):
        return 1


def conferir(npc, itens=None):
    """
    Cruza o mob com as tabelas do cliente e com o que o core exige.

    `itens` é {id: nome} do cliente; sem ele a conferência roda mesmo assim,
    apenas sem a parte que descobre drop de item inexistente.
    """
    problemas = []

    if not str(npc.get("id") or "").strip().isdigit():
        problemas.append("o id do mob precisa ser um número")
    if not (npc.get("name") or "").strip():
        problemas.append("o mob está sem nome; o core lê o atributo `name` "
                         "sem conferir se ele existe")

    h5 = e_h5(npc)
    ai = npc.get("ai") or {}
    if ai and not h5:
        faltando = [c for c in AI_OBRIGATORIOS if c not in ai]
        if faltando:
            problemas.append("falta em <ai>: %s — o core lê esses atributos "
                             "sem conferir, e o servidor não sobe sem eles"
                             % ", ".join(faltando))
        if "clan" in ai and "clanRange" not in ai:
            problemas.append("tendo `clan`, o <ai> precisa de `clanRange`")

    for chave, valor in npc.get("sets") or []:
        if not chave:
            problemas.append("há um <set> sem nome")
        elif chave in ("level", "exp", "sp") and not _e_numero(valor):
            problemas.append("o status `%s` está com `%s`, que não é número"
                             % (chave, valor))

    if not h5 and (npc.get("ai") or {}).get("type") and \
            npc["ai"]["type"] not in TIPOS_DE_AI:
        problemas.append("o <ai> é do tipo `%s`, que não é um dos quatro que "
                         "o pack usa (%s) — se não existir classe com esse "
                         "nome no core, o mob fica sem IA"
                         % (npc["ai"]["type"], ", ".join(TIPOS_DE_AI)))

    vistas = set()
    racas = 0
    for s in npc.get("skills") or []:
        ident = str(s.get("id", ""))
        nivel = str(s.get("level", ""))
        if e_a_raca(s):
            racas += 1
            if nivel not in RACAS:
                problemas.append("a linha da raça (skill %d) está com `%s`, "
                                 "que não é uma raça conhecida"
                                 % (SKILL_DA_RACA, nivel))
            continue
        if not ident.isdigit():
            problemas.append("skill com id inválido: `%s`" % ident)
        elif ident in vistas:
            problemas.append("a skill %s está repetida" % ident)
        elif not nivel.isdigit():
            problemas.append("a skill %s está com nível `%s`, que não é "
                             "número" % (ident, nivel))
        vistas.add(ident)
    if racas > 1:
        problemas.append("há %d linhas de raça (skill %d); o core guarda só a "
                         "última" % (racas, SKILL_DA_RACA))

    for m in npc.get("minions") or []:
        ident = str(m.get("id", ""))
        if not ident.isdigit():
            problemas.append("minion com id inválido: `%s`" % ident)
            continue
        menor, maior = _inteiro(m.get("min")), _inteiro(m.get("max"))
        if menor is None or maior is None:
            problemas.append("o minion %s está com min/max inválido" % ident)
        elif menor > maior:
            problemas.append("o minion %s tem min %d maior que max %d"
                             % (ident, menor, maior))

    if h5 and (npc.get("gavetas") or ("drop",))[0] == "drop" and any(
            e_grupo(c) and c.get("itens") for c in npc.get("drops") or []
            if str(c.get("id")) != str(CATEGORIA_SPOIL)):
        problemas.append("o Mobius do High Five não tem grupo de drop: os "
                         "itens das categorias além da 0 vão soltos, cada um "
                         "com a própria chance")
    for categoria in npc.get("drops") or []:
        rotulo = ("spoil" if str(categoria.get("id")) == str(CATEGORIA_SPOIL)
                  else "categoria %s" % categoria.get("id"))
        for item in categoria.get("itens") or []:
            ident = str(item.get("itemid", ""))
            if not ident.isdigit():
                problemas.append("%s: drop com itemid inválido `%s`"
                                 % (rotulo, ident))
                continue
            if itens is not None and ident not in itens:
                problemas.append("%s: o item %s não existe no cliente — o core "
                                 "descarta esse drop com um aviso no log, e em "
                                 "jogo o mob simplesmente não o dropa"
                                 % (rotulo, ident))
            minimo = _inteiro(item.get("min"))
            maximo = _inteiro(item.get("max"))
            if minimo is None or maximo is None or minimo < (0 if h5 else 1):
                problemas.append("%s: item %s com min/max inválido" % (rotulo, ident))
            elif minimo > maximo:
                problemas.append("%s: item %s tem min %d maior que max %d"
                                 % (rotulo, ident, minimo, maximo))
            if h5:
                # Porcento com casa decimal; acima de 100 o core do High Five
                # sorteia mais de uma vez, o que quase nunca e o que se quis.
                try:
                    chance = float(item.get("chance"))
                except (TypeError, ValueError):
                    chance = None
                if chance is None or not 0 < chance <= 100:
                    problemas.append("%s: item %s com chance `%s` — no High "
                                     "Five o valor é em porcento, de 0 a 100"
                                     % (rotulo, ident, item.get("chance")))
                continue
            chance = _inteiro(item.get("chance"))
            if chance is None or not 1 <= chance <= CHANCE_CHEIA:
                problemas.append("%s: item %s com chance `%s` — o valor vai de "
                                 "1 a %d, onde %d é 100%%"
                                 % (rotulo, ident, item.get("chance"),
                                    CHANCE_CHEIA, CHANCE_CHEIA))
    return problemas


def _e_numero(valor):
    try:
        float(valor)
        return True
    except (TypeError, ValueError):
        return False


def _inteiro(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


# =========================================================================
# sugerir
# =========================================================================
# {(tipo, inicio da faixa): [(id da skill, quantos mobs)]} -- a varredura le os
# 6.532 mobs, e a segunda pergunta da mesma familia nao pode pagar de novo.
_CONTAGEM = {}

# A largura da faixa de nivel que ainda conta como "parecido". Dez para cada
# lado: no pack deste servidor isso junta a familia sem misturar o mob de
# comeco de jogo com o de fim.
FAIXA_DE_NIVEL = 10


def limpar_cache_de_sugestao():
    """Esquece a contagem. Serve quando a pasta do servidor muda."""
    _CONTAGEM.clear()


def sugerir_skills(pasta, mob, quantas=25, aoprogresso=None):
    """
    As skills que os mobs parecidos com este usam, da mais comum para a menos.

    Devolve [(id, quantos mobs usam)]. Fora ficam a linha da raça, que não é
    skill, e as que este mob já tem -- sugerir o que ele já faz é ruído.
    """
    tipo = dict(mob.get("sets") or []).get("type", "")
    try:
        nivel = int(dict(mob.get("sets") or []).get("level", "0"))
    except (TypeError, ValueError):
        nivel = 0
    chave = (str(pasta), tipo, nivel // FAIXA_DE_NIVEL)

    contagem = _CONTAGEM.get(chave)
    if contagem is None:
        contagem = _contar_skills(pasta, tipo, nivel, aoprogresso)
        _CONTAGEM[chave] = contagem

    ja_tem = set(str(s.get("id")) for s in golpes_de(mob))
    return [(ident, quantos) for ident, quantos in contagem
            if ident not in ja_tem][:quantas]


def _contar_skills(pasta, tipo, nivel, aoprogresso=None):
    """Conta as skills entre os mobs do mesmo tipo e de nível próximo."""
    menor, maior = nivel - FAIXA_DE_NIVEL, nivel + FAIXA_DE_NIVEL
    contagem = {}
    todos = arquivos(pasta)
    for numero, arquivo in enumerate(todos):
        if aoprogresso:
            aoprogresso(numero / float(len(todos) or 1), arquivo.name)
        texto = _texto(arquivo)
        for bloco in _NPC.finditer(texto):
            cru = bloco.group(0)
            if dialeto(cru) == "h5":
                a = _atributos(cru[:cru.find(">") + 1])
                o_tipo, o_nivel = a.get("type"), a.get("level")
                lista = _dentro_de(cru, "skillList")
            else:
                achado = re.search(r'<set name="type" val="([^"]*)"', cru)
                o_tipo = achado.group(1) if achado else None
                achado = re.search(r'<set name="level" val="([^"]*)"', cru)
                o_nivel = achado.group(1) if achado else None
                lista = cru
            if tipo and o_tipo != tipo:
                continue
            try:
                dele = int(o_nivel) if o_nivel else -1
            except ValueError:
                dele = -1
            if not menor <= dele <= maior:
                continue
            # Um mob conta UMA vez por skill, mesmo repetindo a linha.
            for ident in set(re.findall(r'<skill id="([^"]*)"', lista)):
                if ident == str(SKILL_DA_RACA):
                    continue
                contagem[ident] = contagem.get(ident, 0) + 1
    if aoprogresso:
        aoprogresso(1.0, "")
    return sorted(contagem.items(), key=lambda p: (-p[1], int(p[0] or 0)))


# =========================================================================
# o formato do High Five (L2J e Mobius, do Gracia em diante)
# =========================================================================
# O mesmo NPC, escrito de outro jeito:
#
#     <npc id="18038" level="61" type="FestivalMonster" name="...">
#         <acquire exp="5313" sp="468" />
#         <stats str="40" ...>
#             <vitals hp="1985.5" ... />
#             <attack physical="501" ... />
#         </stats>
#         <skillList> <skill id="4416" level="6" /> </skillList>
#         <dropLists>
#             <drop> <item id="57" min="629" max="1257" chance="70" /> </drop>
#             <spoil> ... </spoil>          <- L2J: <death> e <corpse>
#         </dropLists>
#         <parameters>
#             <minions name="Privates"> <npc id="18010" count="2" ... /> </minions>
#         </parameters>
#     </npc>
#
# A chance e em PORCENTO, e nao em milionesimos. E a cirurgia continua a
# mesma: cada numero mexido troca so o atributo dele, e cada bloco mexido
# troca so o bloco -- os comentarios de linha (`<!-- Stun -->`) voltam iguais
# em tudo o que nao mudou.
_MARCAS_H5 = re.compile(
    r"<(stats|skillList|dropLists|acquire|collision|race)(?=[\s/>])")

# Gaveta do High Five -> categoria da tela. O espolio e a -1 nos dois mundos.
_GAVETAS_H5 = {"drop": "0", "death": "0", "spoil": "-1", "corpse": "-1"}

# Um filho com o comentario que vier na mesma linha, para ser devolvido igual.
_LINHA_DE = r"<%s\s[^>]*?/>(?:[^\S\n]*<!--.*?-->)?"


def dialeto(cru):
    """`h5` para o `<npc>` do L2J/Mobius do Gracia em diante; `acis` no resto."""
    cabeca = cru[:cru.find(">") + 1]
    if _MARCAS_H5.search(cru) or re.search(r'\slevel\s*=\s*"', cabeca):
        return "h5"
    return "acis"


def _achar(texto, nome, inicio=0, fim=None):
    """
    (abertura, fim da abertura, fim do elemento) do primeiro `<nome>` no
    trecho, ou None. `<skill` nao casa com `<skillList`.
    """
    fim = len(texto) if fim is None else fim
    achado = re.compile(r"<%s(?=[\s/>])[^>]*>" % re.escape(nome)).search(
        texto, inicio, fim)
    if achado is None:
        return None
    if achado.group(0).endswith("/>"):
        return achado.start(), achado.end(), achado.end()
    fecho = texto.find("</%s>" % nome, achado.end(), fim)
    if fecho < 0:
        return achado.start(), achado.end(), achado.end()
    return achado.start(), achado.end(), fecho + len(nome) + 3


def _caminho(texto, caminho):
    """O elemento em `stats/speed/walk`, a partir do corpo do `<npc>`."""
    inicio = texto.find(">") + 1
    fim = texto.rfind("</npc>")
    fim = len(texto) if fim < 0 else fim
    achado = None
    pai = ""
    for parte in caminho.split("/"):
        if pai == "stats" and parte in ("attack", "defence"):
            # `<stats>` tem um `<attribute>` com `<attack>` e `<defence>` de
            # elemento dentro. O de status e o que esta FORA dele.
            dentro = _achar(texto, "attribute", inicio, fim)
            trechos = (((inicio, dentro[0]), (dentro[2], fim)) if dentro
                       else ((inicio, fim),))
            achado = None
            for de, ate in trechos:
                achado = _achar(texto, parte, de, ate)
                if achado:
                    break
        else:
            achado = _achar(texto, parte, inicio, fim)
        if achado is None:
            return None
        inicio, fim, pai = achado[1], achado[2], parte
    return achado


def _dentro_de(cru, caminho):
    """O texto de dentro do elemento, ou "" se ele nao existe."""
    achado = _caminho(cru, caminho)
    return cru[achado[1]:achado[2]] if achado else ""


def _escapar(valor):
    return (str(valor).replace("&", "&amp;").replace("<", "&lt;")
            .replace('"', "&quot;"))


def _com_atributo(abertura, nome, valor):
    """A tag de abertura com `nome="valor"`, trocado no lugar ou acrescentado."""
    padrao = re.compile(r'(\s%s\s*=\s*")[^"]*(")' % re.escape(nome))
    valor = _escapar(valor)
    if padrao.search(abertura):
        return padrao.sub(lambda m: m.group(1) + valor + m.group(2),
                          abertura, count=1)
    corte = len(abertura) - (2 if abertura.endswith("/>") else 1)
    corpo = abertura[:corte].rstrip()
    return '%s %s="%s"%s' % (corpo, nome, valor, abertura[len(corpo):])


def _trocar(texto, achado, novo):
    """
    Troca o elemento pelo `novo` (que ja traz o proprio recuo). Com `novo`
    vazio, o elemento sai -- e a linha dele junto, se ele estava sozinho nela.
    """
    abre, _f, fim = achado
    linha = texto.rfind("\n", 0, abre) + 1
    sozinho = not texto[linha:abre].strip()
    if novo:
        if sozinho:
            return texto[:linha] + novo + texto[fim:]
        return texto[:abre] + novo.lstrip() + texto[fim:]
    fim_da_linha = texto.find("\n", fim)
    fim_da_linha = len(texto) if fim_da_linha < 0 else fim_da_linha + 1
    if sozinho and not texto[fim:fim_da_linha].strip():
        return texto[:linha] + texto[fim_da_linha:]
    return texto[:abre] + texto[fim:]


def _inserir_antes(texto, nomes, novo, nl):
    """Poe o bloco novo na linha de cima do primeiro destes que existir."""
    pos = None
    for nome in nomes:
        achado = _caminho(texto, nome)
        if achado:
            pos = achado[0]
            break
    if pos is None:
        pos = texto.rfind("</npc>")
    linha = texto.rfind("\n", 0, pos) + 1
    return texto[:linha] + novo + nl + texto[linha:]


def _ler_campo_h5(cru, cabeca, caminho, atributo):
    if not caminho:
        return _atributos(cabeca).get(atributo)
    achado = _caminho(cru, caminho)
    if achado is None:
        return None
    if atributo is None:
        if achado[1] == achado[2]:
            return ""
        fecho = achado[2] - len(caminho.split("/")[-1]) - 3
        return cru[achado[1]:fecho].strip()
    return _atributos(cru[achado[0]:achado[1]]).get(atributo)


def _linhas_de(trecho, tag):
    """[(atributos, linha crua com o comentario)] de cada `<tag .../>`."""
    saida = []
    for achado in re.finditer(_LINHA_DE % tag, trecho):
        linha = achado.group(0)
        saida.append((_atributos(linha.split("/>")[0]), linha))
    return saida


def _minions_h5(texto):
    """O `<minions>` dos lacaios dentro de `<parameters>`, ou None."""
    parametros = _caminho(texto, "parameters")
    if parametros is None:
        return None
    primeiro = None
    inicio = parametros[1]
    while True:
        achado = _achar(texto, "minions", inicio, parametros[2])
        if achado is None:
            return primeiro
        if 'name="Privates"' in texto[achado[0]:achado[1]]:
            return achado
        primeiro = primeiro or achado
        inicio = achado[2]


def _item_h5(a, linha):
    item = {"itemid": a.get("id", ""), "min": a.get("min", "1"),
            "max": a.get("max", "1"), "chance": a.get("chance", "100")}
    item["_orig"] = (item["itemid"], item["min"], item["max"], item["chance"])
    item["_cru"] = linha
    return item


def _recuo_da_linha(texto, achado, padrao):
    """O recuo que a linha do elemento ja tem; o padrao, se ele nao abre linha."""
    if not achado:
        return padrao
    linha = texto.rfind("\n", 0, achado[0]) + 1
    recuo = texto[linha:achado[0]]
    return padrao if recuo.strip() else recuo


def e_grupo(categoria):
    """A categoria vira `<group>` no High Five? A 0 e a -1 sao itens soltos."""
    if "grupo" in categoria:
        return bool(categoria["grupo"])
    return str(categoria.get("id")) not in ("0", "-1")


def _modelo_h5(cru, arquivo, texto_do_arquivo=""):
    fim_abertura = cru.find(">")
    fecho = cru.rfind("</npc>")
    cabeca = cru[:fim_abertura + 1]
    atributos = _atributos(cabeca)

    sets = []
    for chave, caminho, atributo in CAMPOS_H5:
        valor = _ler_campo_h5(cru, cabeca, caminho, atributo)
        if valor is not None:
            sets.append((chave, valor))

    ai = _caminho(cru, "ai")
    ai = _atributos(cru[ai[0]:ai[1]]) if ai else {}

    skills = [a for a, _linha in _linhas_de(_dentro_de(cru, "skillList"),
                                             "skill")]

    drops, usadas = [], []
    lista = _caminho(cru, "dropLists")
    for tag in ("drop", "death", "spoil", "corpse"):
        achado = _achar(cru, tag, lista[1], lista[2]) if lista else None
        if not achado:
            continue
        usadas.append(tag)
        # O L2J agrupa: `<group chance="50">` sorteia UM item entre os seus,
        # e cada grupo vira uma categoria da tela. Item solto, fora de grupo,
        # e sorteado sozinho -- a categoria 0, como no Mobius.
        base = _GAVETAS_H5[tag]
        solta = None
        grupos = 0
        trecho = cru[achado[1]:achado[2]]
        for parte in re.finditer(r"<group\b[^>]*>.*?</group>|" + _LINHA_DE
                                 % "item", trecho, re.S):
            texto_da_parte = parte.group(0)
            if texto_da_parte.startswith("<group"):
                grupos += 1
                abertura = texto_da_parte[:texto_da_parte.find(">") + 1]
                drops.append({
                    "id": base if base == "-1" else str(grupos),
                    "chance": _atributos(abertura).get("chance", "100"),
                    "grupo": True,
                    "itens": [_item_h5(a, linha) for a, linha
                              in _linhas_de(texto_da_parte, "item")]})
                solta = None
                continue
            if solta is None:
                solta = {"id": base, "grupo": False, "itens": []}
                drops.append(solta)
            a = _atributos(texto_da_parte.split("/>")[0])
            solta["itens"].append(_item_h5(a, texto_da_parte))
    # Qual par de nomes o servidor usa: o do proprio mob; senao o dos vizinhos
    # no arquivo; senao o do Mobius. Escrever o par errado e um drop que o core
    # nao le, sem erro nenhum.
    if usadas:
        gavetas = (("death", "corpse") if set(usadas) & {"death", "corpse"}
                   else ("drop", "spoil"))
    elif re.search(r"<(death|corpse)>", texto_do_arquivo or ""):
        gavetas = ("death", "corpse")
    else:
        gavetas = ("drop", "spoil")

    minions = []
    bloco = _minions_h5(cru)
    if bloco:
        for a, linha in _linhas_de(cru[bloco[1]:bloco[2]], "npc"):
            m = {"id": a.get("id", ""), "min": a.get("count", "1"),
                 "max": a.get("count", "1"),
                 "respawnTime": a.get("respawnTime", "120"),
                 "weightPoint": a.get("weightPoint", "0")}
            m["_orig"] = (m["id"], m["max"])
            m["_cru"] = linha
            minions.append(m)

    return {
        "id": atributos.get("id", ""),
        "name": atributos.get("name", ""),
        "title": atributos.get("title", ""),
        "atributos": atributos,
        "arquivo": Path(arquivo),
        "cru": cru,
        "cabeca": cabeca,
        "rabo": cru[fecho:],
        "sets": sets,
        "sets_originais": list(sets),
        "ai": ai,
        "ai_original": dict(ai),
        "skills": skills,
        "drops": drops,
        "gavetas": gavetas,
        "minions": minions,
        "filhos": _filhos(cru[fim_abertura + 1:fecho]),
        "mexidos": set(),
        "dialeto": "h5",
    }


def _xml_h5(npc):
    """O `<npc>` do High Five com so o que foi mexido trocado."""
    texto = npc["cru"]
    mexidos = npc.get("mexidos") or set()
    nl = "\r\n" if "\r\n" in texto else "\n"
    dentro = _recuo(texto) + "\t"

    # ---- os numeros: um atributo por vez -------------------------------
    na_cabeca = {}
    if "atributos" in mexidos:
        # So o que mudou: NPC sem `name` no arquivo nao ganha `name=""`.
        antes = _atributos(npc["cabeca"])
        for chave in ("name", "title"):
            if (npc.get(chave) or "") != (antes.get(chave) or ""):
                na_cabeca[chave] = npc.get(chave) or ""
    if "sets" in mexidos:
        agora = dict(npc.get("sets") or [])
        antes = dict(npc.get("sets_originais") or [])
        for chave, caminho, atributo in CAMPOS_H5:
            if chave not in agora or agora[chave] == antes.get(chave):
                continue
            valor = agora[chave]
            if not caminho:
                na_cabeca[atributo] = valor
                continue
            achado = _caminho(texto, caminho)
            if achado is None:
                continue
            if atributo is None:
                fecho = achado[2] - len(caminho.split("/")[-1]) - 3
                texto = texto[:achado[1]] + _escapar(valor) + texto[fecho:]
            else:
                texto = (texto[:achado[0]]
                         + _com_atributo(texto[achado[0]:achado[1]], atributo,
                                         valor)
                         + texto[achado[1]:])
    if na_cabeca:
        fim = texto.find(">") + 1
        cabeca = texto[:fim]
        for chave, valor in na_cabeca.items():
            cabeca = _com_atributo(cabeca, chave, valor)
        texto = cabeca + texto[fim:]

    # ---- <ai> ------------------------------------------------------------
    if "ai" in mexidos:
        antes = npc.get("ai_original") or {}
        trocar = dict((k, v) for k, v in (npc.get("ai") or {}).items()
                      if str(v) != "" and str(v) != str(antes.get(k, "")))
        if trocar:
            achado = _caminho(texto, "ai")
            if achado:
                abertura = texto[achado[0]:achado[1]]
                for chave, valor in trocar.items():
                    abertura = _com_atributo(abertura, chave, valor)
                texto = texto[:achado[0]] + abertura + texto[achado[1]:]
            else:
                texto = _inserir_antes(
                    texto, ("dropLists", "collision"),
                    "%s<ai %s />" % (dentro, " ".join(
                        '%s="%s"' % (k, _escapar(v))
                        for k, v in trocar.items())),
                    nl)

    # ---- <skillList> -----------------------------------------------------
    if "skills" in mexidos:
        achado = _caminho(texto, "skillList")
        velhas = {}
        if achado:
            for a, linha in _linhas_de(texto[achado[1]:achado[2]], "skill"):
                velhas.setdefault((a.get("id"), a.get("level")), linha)
        skills = npc.get("skills") or []
        if skills:
            base = _recuo_da_linha(texto, achado, dentro)
            linhas = [base + "<skillList>"]
            for s in skills:
                chave = (str(s.get("id", "")), str(s.get("level", "1")))
                linhas.append(base + "\t" + (
                    velhas.get(chave)
                    or '<skill id="%s" level="%s" />' % chave))
            linhas.append(base + "</skillList>")
            novo = nl.join(linhas)
            if achado:
                texto = _trocar(texto, achado, novo)
            else:
                texto = _inserir_antes(texto, ("corpseTime", "exCrtEffect",
                                               "ai", "dropLists", "collision"),
                                       novo, nl)
        elif achado:
            texto = _trocar(texto, achado, "")

    # ---- <dropLists> -----------------------------------------------------
    if "drops" in mexidos:
        normal, espolio = npc.get("gavetas") or ("drop", "spoil")
        comuns, roubo = [], []
        for categoria in npc.get("drops") or []:
            destino = roubo if str(categoria.get("id")) == "-1" else comuns
            destino.append(categoria)

        def linha_do_item(item):
            agora = (str(item.get("itemid", "")), str(item.get("min", "1")),
                     str(item.get("max", "1")), str(item.get("chance", "1")))
            if item.get("_cru") and item.get("_orig") == agora:
                return item["_cru"]
            return '<item id="%s" min="%s" max="%s" chance="%s" />' % agora

        achado = _caminho(texto, "dropLists")
        base = _recuo_da_linha(texto, achado, dentro)
        corpo = []
        for gaveta, categorias in ((normal, comuns), (espolio, roubo)):
            linhas = []
            recuo = base + "\t\t"
            for categoria in categorias:
                itens = categoria.get("itens") or []
                if not itens:
                    continue
                # `<group>` e do L2J (`<death>`); o xsd do Mobius (`<drop>`)
                # recusa o arquivo inteiro se aparecer um.
                if e_grupo(categoria) and gaveta in ("death", "corpse"):
                    linhas.append('%s<group chance="%s">'
                                  % (recuo, categoria.get("chance", "100")))
                    linhas.extend(recuo + "\t" + linha_do_item(i)
                                  for i in itens)
                    linhas.append(recuo + "</group>")
                else:
                    linhas.extend(recuo + linha_do_item(i) for i in itens)
            if linhas:
                corpo += (["%s\t<%s>" % (base, gaveta)] + linhas
                          + ["%s\t</%s>" % (base, gaveta)])
        if corpo:
            novo = nl.join([base + "<dropLists>"] + corpo
                           + [base + "</dropLists>"])
            if achado:
                texto = _trocar(texto, achado, novo)
            else:
                texto = _inserir_antes(texto, ("collision",), novo, nl)
        elif achado:
            # `<dropLists>` vazio nao passa no xsd do Mobius: sai inteiro.
            texto = _trocar(texto, achado, "")

    # ---- <minions> dentro de <parameters> ---------------------------------
    if "minions" in mexidos:
        def linha_do_minion(m):
            agora = (str(m.get("id", "")),
                     str(m.get("max") or m.get("min") or 1))
            if m.get("_cru") and m.get("_orig") == agora:
                return m["_cru"]
            return ('<npc id="%s" count="%s" respawnTime="%s" '
                    'weightPoint="%s" />'
                    % (agora[0], agora[1], m.get("respawnTime", "120"),
                       m.get("weightPoint", "0")))

        lacaios = npc.get("minions") or []
        bloco = _minions_h5(texto)
        if bloco:
            linha = texto.rfind("\n", 0, bloco[0]) + 1
            recuo = texto[linha:bloco[0]]
            if recuo.strip():
                recuo = dentro + "\t"
            if lacaios:
                novo = nl.join([recuo + texto[bloco[0]:bloco[1]]]
                               + [recuo + "\t" + linha_do_minion(m)
                                  for m in lacaios]
                               + [recuo + "</minions>"])
                texto = _trocar(texto, bloco, novo)
            else:
                texto = _trocar(texto, bloco, "")
                # `<parameters>` sem filho nenhum tambem nao passa no xsd.
                parametros = _caminho(texto, "parameters")
                if parametros and not re.search(
                        r"<[A-Za-z]", texto[parametros[1]:parametros[2]
                                            - len("</parameters>")]):
                    texto = _trocar(texto, parametros, "")
        elif lacaios:
            recuo = dentro + "\t"
            minions = nl.join([recuo + '<minions name="Privates">']
                              + [recuo + "\t" + linha_do_minion(m)
                                 for m in lacaios]
                              + [recuo + "</minions>"])
            parametros = _caminho(texto, "parameters")
            if parametros:
                pos = texto.find("\n", parametros[1]) + 1
                texto = texto[:pos] + minions + nl + texto[pos:]
            else:
                novo = nl.join([dentro + "<parameters>", minions,
                                dentro + "</parameters>"])
                pos = texto.find("\n", texto.find(">")) + 1
                texto = texto[:pos] + novo + nl + texto[pos:]
    return texto
