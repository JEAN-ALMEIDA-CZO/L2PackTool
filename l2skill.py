#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Habilidades do cliente: ler, copiar para um id novo, e devolver para as tabelas.

Mesmo desenho da aba de itens, com uma diferenca que muda tudo: habilidade tem
NIVEL. Uma habilidade nao e uma linha, e um bloco de linhas -- uma por nivel --
nas duas tabelas:

    skillgrp.dat      aparencia e custo: icone, mana, alcance, tempo de uso
    skillname-e.dat   nome e descricao, tambem por nivel

Neste cliente sao 3.067 habilidades em 42.019 linhas de skillgrp e 29.856 de
skillname. Copiar uma habilidade e copiar todos os niveis dela, nas duas
tabelas, de uma vez -- meia copia produz a habilidade que existe ate o nivel 12
e some no 13.

O servidor casa pelo id, como no item, e o XML declara `levels="N"`. Esse N tem
de bater com quantos niveis o cliente tem, ou o jogador ganha um nivel que o
cliente nao sabe desenhar.
"""

import re
import shutil
from pathlib import Path

import l2item
import l2npc
import motor

ARQUIVO = "skillgrp.dat"
NOMES = "skillname-e.dat"

# Onde ficam o id e o nivel em cada tabela.
COLUNA_ID = {"skill": 0, "nome": 0}
COLUNA_NIVEL = {"skill": 1, "nome": 1}

# Acima disto a copia deixa de fazer sentido: as habilidades com milhares de
# niveis sao as rotas de encantamento (50000 e vizinhas), e clonar 6.410 linhas
# por engano dobra o tamanho da tabela sem servir para nada.
NIVEIS_DE_AVISO = 100

# O primeiro id que vale sugerir. A faixa do jogo vai bem acima de 10.000, e as
# rotas de encantamento ocupam os 50.000 -- 90.000 fica livre nos clientes que
# vi, e e o que a comunidade costuma usar para habilidade propria.
PRIMEIRO_ID_LIVRE = 90000

# A rota de encantamento nao e uma habilidade a parte: sao NIVEIS altos da mesma
# habilidade. A primeira rota ocupa 101, 102, 103...; a segunda, 201; e assim por
# diante -- no High Five ha oito rotas, ate a casa dos 800.
#
# Isso importa porque o `levels` do XML tem de ser o numero de niveis DE VERDADE.
# Conferido contra os datapacks: contando todas as linhas, a contagem bate em
# 93% das 8.136 habilidades do High Five; contando so os niveis abaixo de 100,
# bate em 99,6%. A habilidade 1, que o servidor declara com 37 niveis, tem 247
# linhas no cliente -- as outras 210 sao rotas.
PRIMEIRO_NIVEL_DE_ROTA = 101


class ErroDeSkill(Exception):
    pass


class Skills:
    """As duas tabelas de habilidade abertas juntas."""

    def __init__(self, T, system, trabalho, cronica=None,
                 aoprogresso=None):
        self.T = T
        self.system = Path(system)
        self.trabalho = Path(trabalho)
        self.cronica = cronica
        self.tabelas = {}
        self.alteradas = set()
        self.provas = {}

        alvos = (("skill", ARQUIVO), ("nome", NOMES))
        for i, (chave, arquivo) in enumerate(alvos):
            if aoprogresso:
                aoprogresso(i / float(len(alvos) + 1), "abrindo %s" % arquivo)
            self.tabelas[chave] = l2item.abrir_tabela(T, system, arquivo,
                                                      self.trabalho, cronica)
        for i, (chave, arquivo) in enumerate(alvos):
            if aoprogresso:
                aoprogresso((i + 1) / float(len(alvos) + 1),
                            "conferindo %s" % arquivo)
            self.provas[chave] = self.tabelas[chave].conferir_ciclo()
        if aoprogresso:
            aoprogresso(1.0, "pronto")

    # -- leitura -----------------------------------------------------------
    def linhas_de(self, chave, ident):
        """Todas as linhas daquele id, em ordem de nivel."""
        alvo = str(ident)
        coluna = COLUNA_ID[chave]
        achadas = [l for l in self.tabelas[chave].linhas if l[coluna] == alvo]
        achadas.sort(key=lambda l: _inteiro(l[COLUNA_NIVEL[chave]]))
        return achadas

    def nomes(self):
        """{id: (nome, descricao)} do primeiro nivel de cada habilidade."""
        tabela = self.tabelas["nome"]
        saida = {}
        for linha in tabela.linhas:
            ident = linha[0]
            if ident in saida:
                continue
            saida[ident] = (l2item._limpar(tabela.campo(linha, "name")),
                            l2item._limpar(tabela.campo(linha, "description")))
        return saida

    def listar(self):
        """
        Uma entrada por HABILIDADE, e nao por nivel.

        A lista por nivel teria 42.019 linhas e a mesma habilidade repetida
        quarenta vezes; ninguem procura assim.

        `niveis` conta so os niveis de verdade. As rotas de encantamento moram
        na mesma habilidade, em niveis a partir de 101, e somar tudo dava uma
        habilidade de 37 niveis com "247" escrito ao lado -- numero que ia
        direto para o `levels` do XML e fazia o servidor prometer nivel que o
        cliente nao desenha. Elas vao em `rotas`, contadas a parte.
        """
        nomes = self.nomes()
        tabela = self.tabelas["skill"]
        por_id = {}
        for linha in tabela.linhas:
            ident = linha[0]
            nivel = _inteiro(linha[COLUNA_NIVEL["skill"]], 0)
            e_rota = nivel >= PRIMEIRO_NIVEL_DE_ROTA
            entrada = por_id.get(ident)
            if entrada is None:
                nome, descricao = nomes.get(ident, ("", ""))
                entrada = por_id[ident] = {
                    "id": ident,
                    "nome": nome,
                    "descricao": descricao,
                    "icone": tabela.campo(linha, "icon_name"),
                    "niveis": 0,
                    "rotas": 0,
                    "linha": linha,
                    "tipo": _tipo_legivel(tabela, linha),
                    "_linha_de_rota": e_rota,
                }
            if e_rota:
                entrada["rotas"] += 1
            else:
                entrada["niveis"] += 1
                # A linha de referencia tem de ser de um nivel de verdade: e
                # dela que saem o icone e o modo. Se a primeira linha vista foi
                # de rota, esta a substitui.
                if entrada["_linha_de_rota"]:
                    entrada["linha"] = linha
                    entrada["_linha_de_rota"] = False
                    entrada["icone"] = tabela.campo(linha, "icon_name")
                    entrada["tipo"] = _tipo_legivel(tabela, linha)
        for entrada in por_id.values():
            # Habilidade que so tem rota -- existe, nas faixas de 50.000 -- nao
            # pode aparecer com zero nivel: o XML sairia com `levels="0"`.
            entrada["niveis"] = max(1, entrada["niveis"])
            entrada.pop("_linha_de_rota", None)
        return sorted(por_id.values(), key=lambda s: _inteiro(s["id"]))

    def por_id(self, ident):
        for linha in self.tabelas["skill"].linhas:
            if linha[0] == str(ident):
                return linha
        return None

    def existe(self, ident):
        return self.por_id(ident) is not None

    def proximo_id_livre(self, a_partir_de=PRIMEIRO_ID_LIVRE):
        usados = set()
        for chave in ("skill", "nome"):
            coluna = COLUNA_ID[chave]
            for linha in self.tabelas[chave].linhas:
                usados.add(_inteiro(linha[coluna]))
        ident = int(a_partir_de)
        while ident in usados:
            ident += 1
        return ident

    # -- escrita -----------------------------------------------------------
    def clonar(self, id_base, id_novo, nome="", descricao="", icone="",
               ate_o_nivel=None, substituir=False, com_rotas=False):
        """
        Copia a habilidade inteira -- todos os niveis, nas duas tabelas.

        `ate_o_nivel` corta a copia: uma habilidade de quarenta niveis clonada
        so ate o quinto fica com cinco.

        `com_rotas` decide as rotas de encantamento, e o padrao e NAO leva-las.
        Elas sao niveis a partir de 101 da mesma habilidade e apontam, no
        `ench_skill_id`, para a habilidade parceira do ORIGINAL -- copiadas, o
        cliente passa a oferecer encantamento de uma habilidade que o servidor
        nao tem, apontando para outra. Sem elas, o `is_ench` tambem e zerado:
        deixar a marca sem as rotas abriria a janela de encantamento vazia.
        """
        base = self.linhas_de("skill", id_base)
        if not base:
            raise ErroDeSkill("a habilidade %s nao existe no skillgrp."
                              % id_base)

        if self.existe(id_novo):
            if not substituir:
                raise ErroDeSkill("o id %s ja existe. Escolha outro, ou mande "
                                  "substituir." % id_novo)
            self.remover(id_novo)

        if not com_rotas:
            base = [l for l in base
                    if _inteiro(l[COLUNA_NIVEL["skill"]], 0)
                    < PRIMEIRO_NIVEL_DE_ROTA]
            if not base:
                raise ErroDeSkill(
                    "a habilidade %s so tem rotas de encantamento (nivel %d "
                    "para cima). Marque copiar as rotas para leva-las."
                    % (id_base, PRIMEIRO_NIVEL_DE_ROTA))

        if ate_o_nivel:
            base = [l for l in base
                    if _inteiro(l[COLUNA_NIVEL["skill"]]) <= int(ate_o_nivel)]
            if not base:
                raise ErroDeSkill("nenhum nivel ate %s." % ate_o_nivel)

        tabela = self.tabelas["skill"]
        novos = []
        for linha in base:
            novo = list(linha)
            novo[0] = str(id_novo)
            if icone:
                tabela.definir(novo, "icon_name", icone)
            if not com_rotas:
                for coluna in ("is_ench", "ench_skill_id"):
                    try:
                        tabela.definir(novo, coluna, "0")
                    except Exception:               # noqa: BLE001
                        pass        # C3 nao tem encantamento de habilidade
            tabela.linhas.append(novo)
            novos.append(novo)
        self.alteradas.add("skill")

        self._clonar_nomes(id_base, id_novo, nome, descricao,
                           [l[COLUNA_NIVEL["skill"]] for l in novos])
        return novos

    def _clonar_nomes(self, id_base, id_novo, nome, descricao, niveis):
        """
        Refaz o skillname-e para os niveis copiados.

        O nome vai igual em todos os niveis, que e como o jogo faz. A descricao
        do jogo muda de nivel para nivel (o "Power 25" que vira "Power 27"); a
        copia mantem a do nivel de origem quando o usuario nao escreve outra --
        e melhor uma descricao herdada do que nenhuma.
        """
        tabela = self.tabelas["nome"]
        do_base = dict((l[COLUNA_NIVEL["nome"]], l)
                       for l in self.linhas_de("nome", id_base))
        modelo = None
        if do_base:
            modelo = do_base[sorted(do_base, key=_inteiro)[0]]
        elif tabela.linhas:
            modelo = tabela.linhas[0]
        if modelo is None:
            raise ErroDeSkill("o skillname-e.dat esta vazio; nao tenho de onde "
                              "copiar o formato de uma entrada.")

        for nivel in niveis:
            origem = do_base.get(nivel, modelo)
            linha = list(origem)
            linha[0] = str(id_novo)
            linha[COLUNA_NIVEL["nome"]] = str(nivel)
            if nome:
                tabela.definir(linha, "name", "a,%s" % nome)
            if descricao:
                tabela.definir(linha, "description", "a,%s\\0" % descricao)
            tabela.linhas.append(linha)
        self.alteradas.add("nome")

    def remover(self, ident):
        """Tira a habilidade inteira das duas tabelas."""
        alvo = str(ident)
        saiu = []
        for chave in ("skill", "nome"):
            tabela = self.tabelas[chave]
            coluna = COLUNA_ID[chave]
            antes = len(tabela.linhas)
            tabela.linhas = [l for l in tabela.linhas if l[coluna] != alvo]
            if len(tabela.linhas) != antes:
                saiu.append(chave)
                self.alteradas.add(chave)
        return saiu

    # -- gravacao ----------------------------------------------------------
    def conferir(self, so_alteradas=True):
        chaves = sorted(self.alteradas) if so_alteradas else sorted(self.provas)
        problemas = []
        for chave in chaves:
            deu, motivo = self.provas.get(chave, (False, "nao foi conferida"))
            if not deu:
                problemas.append((self.tabelas[chave].origem.name, motivo))
        return problemas

    def gravar(self, destino, aolog=None):
        problemas = self.conferir()
        if problemas:
            raise ErroDeSkill(
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


def _inteiro(texto, padrao=0):
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao


def _tipo_legivel(tabela, linha):
    """
    Ativa, passiva ou alternavel -- e o numero nao quer dizer o mesmo em todas.

    A coluna tem dois nomes (`oper_type` de C3 em diante, `operate_type` em
    C1 e C2) e, pior, DUAS ESCALAS. Ver `ESCALA_ANTIGA` e `ESCALA_NOVA`, que
    trazem o que foi medido.
    """
    for coluna in ("oper_type", "operate_type"):
        cru = (tabela.campo(linha, coluna) or "").strip()
        if not cru:
            continue
        if cru.upper() in ("ACTIVE", "PASSIVE", "TOGGLE"):
            return cru.upper()
        numero = _inteiro(cru, -1)
        escala = _escala_da_tabela(tabela, coluna)
        if escala is ESCALA_NOVA:
            if numero in ESCALA_NOVA:
                return ESCALA_NOVA[numero]
            # Valor de escala nova que ainda nao foi visto: 10 ou mais e
            # passiva, porque e la que a faixa das passivas comeca. Abaixo
            # disso e ativa. Chutar "" seria esconder a habilidade da lista.
            return "PASSIVE" if numero >= 10 else "ACTIVE"
        return escala.get(numero, "")
    return ""


# A escala ANTIGA -- C1, C2, C3, C4, C5 e Kamael. Medida por habilidade
# conhecida nos clientes:
#   0  golpe        Power Strike, Mortal Blow, Divine Heal
#   1  aura/buff    Dash, War Cry, Majesty, Shield Stun   -- ativa tambem
#   2  passiva      Weapon Mastery, Armor Mastery, Critical Chance, Trade
#   3  alternavel   Relax
ESCALA_ANTIGA = {0: "ACTIVE", 1: "ACTIVE", 2: "PASSIVE", 3: "TOGGLE"}

# A escala NOVA -- Hellbound em diante. O mesmo campo passa a separar a ativa
# por natureza, e joga as passivas para a casa dos dez:
#   0  fisica       Power Strike
#   1  magica       Divine Heal, Poison Recovery
#   2  aura/buff    Dash, War Cry, Majesty
#   3  fisica especial  Shield Stun
#   4  especial     Seal of Ruler, Build Headquarters, Noblesse Blessing
#   5  pesca        Fishing, Pumping
#   6  ALTERNAVEL   Relax
#   7  transformacao    Transform Grail Apostle
#   11 mastery      Weapon Mastery, Armor Mastery, Long Shot
#   12 critico      Critical Chance, Magician's Movement
#   13 peso/sentido Weight Limit, Shadow Sense
#   14 oficio       Cubic Mastery, Trade
#   15 cla          Clan Vitality, Clan Spirituality
#   16 bonus        int_1, str_2, maxmp_5 (as dos itens)
ESCALA_NOVA = {0: "ACTIVE", 1: "ACTIVE", 2: "ACTIVE", 3: "ACTIVE",
               4: "ACTIVE", 5: "ACTIVE", 6: "TOGGLE", 7: "ACTIVE",
               11: "PASSIVE", 12: "PASSIVE", 13: "PASSIVE", 14: "PASSIVE",
               15: "PASSIVE", 16: "PASSIVE"}

# Onde a escala nova comeca a contar passiva. E este numero que separa as
# duas escalas, porque na antiga ele nunca aparece.
PRIMEIRA_PASSIVA_NOVA = 10


def _escala_da_tabela(tabela, coluna):
    """
    Qual das duas escalas esta tabela usa -- decidido OLHANDO a tabela.

    Nao se pergunta a cronica: valor de 10 para cima so existe na escala
    nova, entao a propria coluna responde. Amarrar no nome da cronica
    obrigaria a lembrar deste arquivo a cada nucleo novo, e um esquecimento
    aqui nao daria erro -- daria tipo errado, que e pior.

    A conta e feita uma vez por tabela e fica guardada nela.
    """
    guardado = getattr(tabela, "_escala_do_oper", None)
    if guardado is not None:
        return guardado

    escala = ESCALA_ANTIGA
    try:
        for linha in tabela.linhas:
            if _inteiro(tabela.campo(linha, coluna), 0) >= PRIMEIRA_PASSIVA_NOVA:
                escala = ESCALA_NOVA
                break
    except Exception:                               # noqa: BLE001
        escala = ESCALA_ANTIGA
    try:
        tabela._escala_do_oper = escala
    except Exception:                               # noqa: BLE001
        pass
    return escala


# Os nomes antigos, que outros modulos ainda importam.
OPER_DO_CLIENTE = ESCALA_ANTIGA
OPER_DO_CLIENTE_ANTIGO = ESCALA_ANTIGA


# ---------------------------------------------------------------------------
# Instalacao
# ---------------------------------------------------------------------------
PASTA_GUARDA = "backup_skills"


def instalar(gravados, system, aolog=None):
    """
    Poe as tabelas geradas no cliente, guardando as originais na primeira vez.

    Como nos itens: a copia de guarda so e feita uma vez por arquivo, senao a
    segunda instalacao guardaria por cima o arquivo gerado na primeira.
    """
    system = Path(system)
    # Como nos itens: se o cliente ainda esta nas chaves da NCSoft, converte
    # antes -- gravar numa chave e deixar o resto noutra nao da erro, da
    # cliente quebrado em silencio.
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


# ---------------------------------------------------------------------------
# O lado do servidor
# ---------------------------------------------------------------------------
# Lidos do codigo do aCis: SkillType.java, SkillTargetType.java,
# SkillOpType.java, ElementType.java. Como nos itens, um nome fora destas
# listas nao e ignorado -- ele derruba o carregamento da tabela de habilidades.
TIPOS = (
    "PDAM", "MDAM", "FATAL", "BLOW", "DRAIN", "DRAIN_SOUL", "DEATHLINK",
    "CPDAMPERCENT", "MANADAM", "DOT", "MDOT", "REAL_DAMAGE", "CHARGEDAM",
    "SIGNET", "SIGNET_CASTTIME", "SEED",
    "HEAL", "HEAL_STATIC", "HEAL_PERCENT", "HOT", "COMBATPOINTHEAL",
    "MANAHEAL", "MANAHEAL_PERCENT", "MANARECHARGE", "MPHOT", "BALANCE_LIFE",
    "RESURRECT", "GIVE_SP",
    "BUFF", "DEBUFF", "CONT", "PASSIVE", "LUCK",
    "BLEED", "POISON", "STUN", "ROOT", "CONFUSION", "FEAR", "SLEEP", "MUTE",
    "PARALYZE", "WEAKNESS", "BETRAY", "ERASE", "CANCEL", "CANCEL_DEBUFF",
    "NEGATE", "MAGE_BANE", "WARRIOR_BANE",
    "AGGDAMAGE", "AGGREDUCE", "AGGREMOVE", "AGGREDUCE_CHAR", "AGGDEBUFF",
    "REFLECT", "SPOIL", "SWEEP", "FAKE_DEATH", "FUSION",
    "SUMMON", "SUMMON_FRIEND", "SUMMON_PARTY", "SUMMON_CREATURE", "SPAWN",
    "FEED_PET", "BEAST_FEED", "CHANGE_APPEARANCE", "INSTANT_JUMP",
    "RECALL", "TELEPORT", "GET_PLAYER",
    "ENCHANT_ARMOR", "ENCHANT_WEAPON", "SOULSHOT", "SPIRITSHOT",
    "CREATE_ITEM", "EXTRACTABLE", "EXTRACTABLE_FISH", "COMMON_CRAFT",
    "DWARVEN_CRAFT", "SOW", "HARVEST", "UNLOCK", "UNLOCK_SPECIAL",
    "DELUXE_KEY_UNLOCK", "FISHING", "PUMPING", "REELING",
    "SIEGE_FLAG", "TAKE_CASTLE", "STRIDER_SIEGE_ASSAULT",
    "DUMMY", "NOTDONE", "COREDONE",
)

ALVOS = ("SELF", "ONE", "PARTY", "ALLY", "CLAN", "AREA", "FRONT_AREA", "AURA",
         "FRONT_AURA", "BEHIND_AURA", "CORPSE", "UNDEAD", "AURA_UNDEAD",
         "CORPSE_ALLY", "CORPSE_PLAYER", "CORPSE_PET", "CORPSE_MOB",
         "AREA_CORPSE_MOB", "UNLOCKABLE", "HOLY", "PARTY_MEMBER",
         "PARTY_OTHER", "SUMMON", "AREA_SUMMON", "ENEMY_SUMMON", "OWNER_PET",
         "GROUND", "NONE")

OPERACOES = ("ACTIVE", "PASSIVE", "TOGGLE")

ELEMENTOS = ("", "FIRE", "WATER", "WIND", "EARTH", "HOLY", "DARK", "VALAKAS")

ARMAS_PERMITIDAS = ("", "SWORD", "BLUNT", "DAGGER", "BOW", "POLE", "FIST",
                    "DUAL", "DUALFIST", "BIGSWORD", "BIGBLUNT", "ETC",
                    "FISHINGROD")

SIM_NAO = ("", "true", "false")

# A ordem em que os campos saem no XML. Fora desta lista nada e escrito.
ORDEM_DOS_CAMPOS = (
    "skillType", "operateType", "target", "magicLvl", "power", "mpConsume",
    "mpInitialConsume", "hpConsume", "castRange", "effectRange",
    "skillRadius", "hitTime", "coolTime", "reuseDelay", "isMagic",
    "isDebuff", "isPotion", "lvlDepend", "element", "weaponsAllowed",
    "aggroPoints", "activateRate", "baseCritRate", "overHit",
    "nextActionAttack", "ignoreShld", "staticReuse", "staticHitTime",
    "SSBoost", "itemConsumeId", "itemConsumeCount", "abnormalLvl",
    "abnormalTime", "negateStats",
)


def campos_do_servidor(skills, linha):
    """
    O que da para aproveitar da linha do cliente para o XML do servidor.

    Custo de mana, alcance, tempo de uso e o tipo (ativa/passiva) estao no
    skillgrp e sao os mesmos numeros que o servidor usa. O resto -- poder,
    recarga, tipo de efeito -- nao sai do cliente e fica em branco.
    """
    tabela = skills.tabelas["skill"]

    def campo(nome, padrao=""):
        try:
            return tabela.campo(linha, nome)
        except Exception:
            return padrao

    dados = {
        "operateType": OPER_DO_CLIENTE.get(_inteiro(campo("oper_type"), 0),
                                           "ACTIVE"),
        "target": "ONE",
        "skillType": "",
        "isMagic": "true" if _inteiro(campo("is_magic"), 0) else "",
    }

    for chave, coluna in (("mpConsume", "mp_consume"),
                          ("hpConsume", "hp_consume"),
                          ("castRange", "cast_range")):
        valor = campo(coluna, "")
        if _inteiro(valor, 0) > 0:
            dados[chave] = valor

    # hit_time vem em segundos com casa decimal; o servidor conta em
    # milissegundos.
    try:
        segundos = float(campo("hit_time", "0") or 0)
    except ValueError:
        segundos = 0.0
    if segundos > 0:
        dados["hitTime"] = str(int(round(segundos * 1000)))

    if dados["operateType"] == "PASSIVE":
        dados["skillType"] = "PASSIVE"
        dados["target"] = "SELF"
    return dados


SEPARADORES = ",;"


def por_nivel(valor):
    """
    Os numeros de um valor por nivel, ou None quando e valor unico.

    "431 458 486" e uma progressao; "431" e um numero; "#power" e uma
    referencia que ja existe e passa direto. Virgula e ponto-e-virgula valem
    como espaco, porque quem digita quarenta numeros usa o que tiver a mao.

    Um texto que nao seja todo numerico volta None de proposito: nome de
    elemento e tipo de efeito tem espaco nenhum, mas `SWORD,BLUNT` tem virgula
    -- e aquilo e uma lista de armas, nao uma progressao.
    """
    texto = str(valor or "").strip()
    if not texto or texto.startswith("#"):
        return None
    for separador in SEPARADORES:
        texto = texto.replace(separador, " ")
    partes = texto.split()
    if len(partes) < 2:
        return None
    for parte in partes:
        try:
            float(parte)
        except ValueError:
            return None             # lista de nomes, e nao progressao
    return partes


def _apelido(base, usados):
    """Um nome de tabela que ainda nao esteja em uso neste XML."""
    nome = "#%s" % base
    conta = 2
    while nome in usados:
        nome = "#%s%d" % (base, conta)
        conta += 1
    usados.add(nome)
    return nome


def xml_servidor(ident, nome, id_base, niveis=1, campos=None, estados=(),
                 avisos=None, extras="", sets_de_fora=None):
    """
    A habilidade em XML, no formato do aCis/L2J.

    `levels` tem de bater com quantos niveis a habilidade tem no cliente: o
    servidor so entrega os niveis que declarar aqui, e um nivel a mais seria
    uma habilidade que o cliente nao sabe desenhar.

    **Valor por nivel.** O "Power 25" que vira "Power 27" se escreve com
    `<table>`, e agora sai daqui: um campo com varios numeros separados por
    espaco vira uma tabela, e o `<set>` passa a apontar para ela.

        <table name="#power"> 431 458 486 </table>
        <set name="power" val="#power" />

    As tabelas vao antes dos `<set>`, como o datapack escreve, e a referencia
    vale tambem dentro do `<for>`.

    A tabela precisa ter exatamente `levels` numeros -- uma a menos derruba a
    habilidade ou entrega o nivel errado, e nada avisa. O que nao bater e
    contado em `avisos`, se quem chamou passar uma lista; o XML sai assim
    mesmo, para a previa mostrar o que esta sendo montado.

    **O que esta tela nao edita.** Numa habilidade do L2J, o `<effects>` e os
    `<enchantN>` sao a maior parte do arquivo -- 77% das habilidades do datapack
    do High Five tem algo assim. Isso chega em `extras`, vindo do servidor pelo
    `l2servidor.extras_do_corpo`, e sai igual ao que entrou: regravar sem isso
    deixaria a habilidade com nome e custo de mana, e sem efeito nenhum.
    """
    quantos = max(1, int(niveis))
    campos = campos or {}
    avisos = avisos if avisos is not None else []

    # Primeiro as tabelas: e preciso saber os apelidos antes de escrever os
    # <set> que apontam para eles. Os apelidos que vem nos extras entram como
    # usados: dar o mesmo nome a duas tabelas faria uma calar a outra, e a
    # habilidade passaria a usar numeros de outro campo.
    usados = set(re.findall(r'<table\s+name\s*=\s*"([^"]+)"', extras or "",
                            re.I))
    tabelas = []
    refs_de_campo = {}
    for chave in ORDEM_DOS_CAMPOS:
        serie = por_nivel(campos.get(chave, ""))
        if serie is None:
            continue
        apelido = _apelido(chave, usados)
        refs_de_campo[chave] = apelido
        tabelas.append((apelido, serie))
        if len(serie) != quantos:
            avisos.append("%s tem %d valores, e a habilidade tem %d niveis "
                          "no cliente" % (chave, len(serie), quantos))

    # Os campos que esta tela nao mostra passam pelo mesmo moinho: um
    # `mpConsume2` lido do servidor vem com um numero por nivel, e escreve-lo
    # como valor unico poria 37 numeros dentro de um `val=` -- a habilidade
    # deixaria de carregar.
    de_fora = dict((chave, str(valor).strip())
                   for chave, valor in (sets_de_fora or {}).items()
                   if str(valor).strip() and chave not in ORDEM_DOS_CAMPOS)
    for chave in sorted(de_fora):
        # So o espaco vale como progressao aqui. Quem digita quarenta numeros a
        # mao usa virgula, e por isso `por_nivel` a aceita -- mas um valor que
        # voltou do servidor com virgula e uma tupla, nao uma progressao: o
        # `fanRange="0,0,200,180"` de um leque sao quatro medidas, e virar uma
        # tabela de quatro numeros numa habilidade de 34 niveis a quebraria.
        if any(s in de_fora[chave] for s in SEPARADORES):
            continue
        serie = por_nivel(de_fora[chave])
        if serie is None:
            continue
        apelido = _apelido(chave, usados)
        refs_de_campo[chave] = apelido
        tabelas.append((apelido, serie))
        if len(serie) != quantos:
            avisos.append("%s tem %d valores, e a habilidade tem %d niveis "
                          "no cliente" % (chave, len(serie), quantos))

    validos = [e for e in estados if str(e.get("valor", "")).strip()]
    refs_de_estado = {}
    for i, entrada in enumerate(validos):
        serie = por_nivel(entrada.get("valor", ""))
        if serie is None:
            continue
        apelido = _apelido(entrada.get("estado", "val") or "val", usados)
        refs_de_estado[i] = apelido
        tabelas.append((apelido, serie))
        if len(serie) != quantos:
            avisos.append("%s tem %d valores, e a habilidade tem %d niveis "
                          "no cliente"
                          % (entrada.get("estado", "?"), len(serie), quantos))

    linhas = ['<?xml version="1.0" encoding="UTF-8"?>', '<list>']
    linhas.append('\t<!-- Gerado pelo L2PackTool. Habilidade base copiada no '
                  'cliente: %s -->' % id_base)
    linhas.append('\t<skill id="%s" levels="%d" name="%s">'
                  % (ident, quantos,
                     l2item._escapar(nome or ("Skill %s" % ident))))

    for apelido, serie in tabelas:
        linhas.append('\t\t<table name="%s"> %s </table>'
                      % (apelido, " ".join(serie)))

    for chave in ORDEM_DOS_CAMPOS:
        valor = str(campos.get(chave, "")).strip()
        if not valor:
            continue
        linhas.append('\t\t<set name="%s" val="%s" />'
                      % (chave, refs_de_campo.get(chave)
                         or l2item._escapar(valor)))

    for chave in sorted(de_fora):
        linhas.append('\t\t<set name="%s" val="%s" />'
                      % (chave, refs_de_campo.get(chave)
                         or l2item._escapar(de_fora[chave])))

    if validos:
        linhas.append('\t\t<for>')
        for i, entrada in enumerate(validos):
            linhas.append('\t\t\t<%s stat="%s" val="%s" />'
                          % (entrada.get("operacao", "add"),
                             entrada.get("estado", ""),
                             refs_de_estado.get(i)
                             or str(entrada.get("valor", "")).strip()))
        linhas.append('\t\t</for>')

    if extras:
        import l2servidor

        linhas.append(l2servidor.recuar(extras, "\t\t"))

    linhas.append('\t</skill>')
    linhas.append('</list>')
    return "\n".join(linhas) + "\n"
