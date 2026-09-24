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
        """
        nomes = self.nomes()
        tabela = self.tabelas["skill"]
        por_id = {}
        for linha in tabela.linhas:
            ident = linha[0]
            entrada = por_id.get(ident)
            if entrada is None:
                nome, descricao = nomes.get(ident, ("", ""))
                por_id[ident] = {
                    "id": ident,
                    "nome": nome,
                    "descricao": descricao,
                    "icone": tabela.campo(linha, "icon_name"),
                    "niveis": 1,
                    "linha": linha,
                    "tipo": _tipo_legivel(tabela, linha),
                }
            else:
                entrada["niveis"] += 1
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
               ate_o_nivel=None, substituir=False):
        """
        Copia a habilidade inteira -- todos os niveis, nas duas tabelas.

        `ate_o_nivel` corta a copia: uma habilidade de quarenta niveis clonada
        so ate o quinto fica com cinco. Serve para nao arrastar as rotas de
        encantamento, que tem milhares.
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
    Ativa, passiva ou alternavel -- e a coluna nao se chama igual em todas.

    De C3 em diante e `oper_type`, com tres valores. Em C1 e C2 e
    `operate_type`, com QUATRO: la as ativas se dividem em duas (golpe e
    aura), e por isso o numero da passiva e outro. Usar a tabela errada nao
    daria erro, so mostraria toda skill como ativa -- que era o que estava
    acontecendo: 767 ativas e nenhuma passiva no C1.
    """
    for coluna, mapa in (("oper_type", OPER_DO_CLIENTE),
                         ("operate_type", OPER_DO_CLIENTE_ANTIGO)):
        cru = (tabela.campo(linha, coluna) or "").strip()
        if not cru:
            continue
        if cru.upper() in ("ACTIVE", "PASSIVE", "TOGGLE"):
            return cru.upper()
        return mapa.get(_inteiro(cru, -1), "")
    return ""


# oper_type do skillgrp: 0 ativa, 1 passiva, 2 alternavel. Bate com o
# operateType do servidor.
OPER_DO_CLIENTE = {0: "ACTIVE", 1: "PASSIVE", 2: "TOGGLE"}

# operate_type de C1 e C2. Medido nos dois clientes, por skill conhecida:
#   0  golpe        Power Strike, Mortal Blow, Divine Heal
#   1  aura/buff    Dash, War Cry, Majesty          -- ativa tambem
#   2  passiva      Weapon Mastery, Armor Mastery, Critical Chance
#   3  alternavel   Relax, Silent Walk, Hundred Fist
OPER_DO_CLIENTE_ANTIGO = {0: "ACTIVE", 1: "ACTIVE", 2: "PASSIVE",
                          3: "TOGGLE"}


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
                 avisos=None):
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
    """
    quantos = max(1, int(niveis))
    campos = campos or {}
    avisos = avisos if avisos is not None else []

    # Primeiro as tabelas: e preciso saber os apelidos antes de escrever os
    # <set> que apontam para eles.
    usados = set()
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

    if validos:
        linhas.append('\t\t<for>')
        for i, entrada in enumerate(validos):
            linhas.append('\t\t\t<%s stat="%s" val="%s" />'
                          % (entrada.get("operacao", "add"),
                             entrada.get("estado", ""),
                             refs_de_estado.get(i)
                             or str(entrada.get("valor", "")).strip()))
        linhas.append('\t\t</for>')

    linhas.append('\t</skill>')
    linhas.append('</list>')
    return "\n".join(linhas) + "\n"
