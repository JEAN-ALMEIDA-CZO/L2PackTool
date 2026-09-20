# -*- coding: utf-8 -*-
"""
Acrescentar coisas a um mapa `.unr` ja compilado.

Serve a uma necessidade so, mas que nao tinha jeito de contornar: plantar a
tela do video num lobby que nao tem uma. O lobby de cenario e um exemplo -- ele
traz o cenario inteiro e nenhuma tela, entao o filme nao tem onde aparecer.

## A regra que manda no formato

Um pacote Unreal guarda, para cada objeto, a POSICAO ABSOLUTA dos dados dele
no arquivo. Pior: dentro dos dados de textura e de terreno ha TLazyArray, que
tambem guarda posicao absoluta. Mover um byte que seja de lugar deixa o
arquivo com tabelas perfeitas e conteudo mentiroso -- e o cliente so reclama
paginas depois, num objeto que nao foi tocado.

Por isso aqui nada se move. O que existe fica exatamente onde esta, byte por
byte, e tudo o que e novo vai para o FIM do arquivo:

    [cabecalho][tabela de nomes velha][dados dos objetos][tabelas velhas]
    [dados novos][tabela de nomes nova][imports nova][exports nova]

As tres tabelas sao reescritas inteiras no fim, e o cabecalho passa a apontar
para la. As velhas viram bytes mortos no meio do arquivo: ninguem mais as le,
e apaga-las seria justamente mover o que vem depois.

Custa uns oitenta kilobytes num mapa de quatro megabytes. E o preco de nao
mexer no que ja funciona.

## O quadro de estado

Objeto com a marca `TEM_PILHA` grava, antes das propriedades, o quadro de
estado do script: no, no de estado, mascara de sondagem, acao latente e o
deslocamento. Quem le propriedade sem pular isso comeca no lugar errado e nao
acha nada -- foi o que escondeu a posicao das cameras na primeira leitura.
"""

import math
import struct
import tempfile
import shutil
from pathlib import Path

import l2anim
import l2npc

TEM_PILHA = 0x02000000

# O cabecalho tem mais coisa depois dos offsets: o GUID e as geracoes. Elas
# contam nomes e exports de cada versao do pacote, e ficam mentindo quando a
# gente acrescenta -- por isso a ultima e atualizada ao gravar.
TAMANHO_DO_CABECALHO = 36


class ErroDeMapa(Exception):
    pass


# ---------------------------------------------------------------------------
# Ler
# ---------------------------------------------------------------------------
def ler(caminho, ferramentas=None):
    """
    Abre o mapa e devolve as tres tabelas, mais os bytes inteiros.

    `ferramentas` e a configuracao do programa, e so faz falta com mapa
    criptografado -- os das cronicas sao. Sem ela, um mapa desses nao abre.
    """
    caminho = Path(caminho)
    # Mapa criptografado so abre por inteiro, e o l2encdec escreve o aberto
    # em disco. A pasta e temporaria e some aqui mesmo: o que interessa ja
    # esta na memoria.
    rascunho = None
    if ferramentas is not None:
        rascunho = Path(tempfile.mkdtemp(prefix="l2mapa_"))
    try:
        pacote = l2npc.Pacote(caminho, ferramentas, rascunho)
        try:
            dados = bytes(pacote.dados)
        finally:
            pacote.fechar()
    finally:
        if rascunho is not None:
            shutil.rmtree(rascunho, ignore_errors=True)

    (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
     qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(
        l2anim.CABECALHO, dados)

    nomes, _fim = l2anim._ler_nomes_cru(dados, off_nomes, qtd_nomes)

    imports, pos = [], off_imp
    for _ in range(qtd_imp):
        campos, pos = l2anim._ler_import(dados, pos)
        imports.append(campos)

    exports, pos = [], off_exp
    for _ in range(qtd_exp):
        campos, pos = l2anim._ler_export(dados, pos)
        exports.append(campos)

    return {
        "caminho": caminho,
        "dados": dados,
        "versao": versao,
        "licenciado": licenciado,
        "flags": flags,
        "nomes": list(nomes),
        "imports": imports,
        "exports": exports,
        "cifrado": l2npc.metodo_do_arquivo(caminho),
        "novos": [],            # (indice_do_export, bytes) a acrescentar
    }


def nome(mapa, indice):
    """O nome de um indice, ou uma marca quando ele esta fora da tabela."""
    if 0 <= indice < len(mapa["nomes"]):
        return mapa["nomes"][indice][0]
    return "?%d" % indice


def indice_do_nome(mapa, texto, criar=True):
    """
    O indice de um nome na tabela, criando se faltar.

    Acrescentar nome e barato aqui porque a tabela e reescrita inteira no fim
    do arquivo: nada do que ja existe muda de lugar por causa disso.
    """
    for i, (existente, _flags) in enumerate(mapa["nomes"]):
        if existente == texto:
            return i
    if not criar:
        return None
    mapa["nomes"].append((texto, 0x04070010))
    return len(mapa["nomes"]) - 1


def achar_import(mapa, texto, dono=None):
    """O indice (negativo) de um import pelo nome, ou None."""
    for i, campos in enumerate(mapa["imports"]):
        if nome(mapa, campos["nome"]) != texto:
            continue
        if dono is not None and campos["dono"] != dono:
            continue
        return -(i + 1)
    return None


def achar_export(mapa, texto):
    """O indice (positivo) de um export pelo nome, ou None."""
    for i, campos in enumerate(mapa["exports"]):
        if nome(mapa, campos["nome"]) == texto:
            return i + 1
    return None


def classe_do_export(mapa, indice):
    """O nome da classe de um export, resolvido pela tabela de imports."""
    campos = mapa["exports"][indice - 1]
    i = campos["classe"]
    if i < 0 and -i - 1 < len(mapa["imports"]):
        return nome(mapa, mapa["imports"][-i - 1]["nome"])
    if i > 0 and i - 1 < len(mapa["exports"]):
        return nome(mapa, mapa["exports"][i - 1]["nome"])
    return "Class"


def propriedades(mapa, indice):
    """
    As propriedades de um export, pulando o quadro de estado quando houver.

    Devolve [(nome, bytes crus)], do jeito que estao no arquivo.
    """
    campos = mapa["exports"][indice - 1]
    if not campos["tamanho"]:
        return []
    dados, inicio, fim = _onde_esta_o_corpo(mapa, indice)
    if campos["flags"] & TEM_PILHA:
        inicio += _tamanho_do_quadro(dados, inicio)
    lista, _fim = l2anim.ler_propriedades(
        dados, inicio, [n for n, _f in mapa["nomes"]], fim)
    return lista


def _onde_esta_o_corpo(mapa, indice):
    """
    (bytes, inicio, fim) do corpo de um objeto.

    Um objeto ja reescrito nesta sessao ainda nao esta no arquivo: o corpo
    novo espera na fila, e o registro carrega o tamanho novo com a posicao
    velha. Ler do arquivo nesse estado devolve lixo, entao quem esta na fila
    e lido de la.
    """
    for pendente, corpo in mapa["novos"]:
        if pendente == indice:
            return corpo, 0, len(corpo)
    campos = mapa["exports"][indice - 1]
    return (mapa["dados"], campos["inicio"],
            campos["inicio"] + campos["tamanho"])


def _tamanho_do_quadro(dados, pos):
    comeco = pos
    no, pos = l2anim._descompacto(dados, pos)
    _no_estado, pos = l2anim._descompacto(dados, pos)
    pos += 8                                    # mascara de sondagem
    pos += 4                                    # acao latente
    if no != 0:
        _deslocamento, pos = l2anim._descompacto(dados, pos)
    return pos - comeco


def valor_da_propriedade(mapa, cru):
    """(tipo, nome da estrutura, bytes do valor) de uma propriedade crua."""
    nomes = [n for n, _f in mapa["nomes"]]
    pos = 0
    _i, pos = l2anim._descompacto(cru, pos)
    info = cru[pos]
    pos += 1
    tipo = info & 0x0F
    codigo = (info >> 4) & 0x07
    estrutura = None
    if tipo == 10:
        i, pos = l2anim._descompacto(cru, pos)
        estrutura = nomes[i] if 0 <= i < len(nomes) else None
    if codigo < 5:
        tamanho = l2anim._TAMANHOS_FIXOS[codigo]
    elif codigo == 5:
        tamanho = cru[pos]
        pos += 1
    elif codigo == 6:
        tamanho = int.from_bytes(cru[pos:pos + 2], "little")
        pos += 2
    else:
        tamanho = int.from_bytes(cru[pos:pos + 4], "little")
        pos += 4
    if (info & 0x80) and tipo != 3:
        _i, pos = l2anim._descompacto(cru, pos)
    return tipo, estrutura, bytes(cru[pos:pos + tamanho])


# ---------------------------------------------------------------------------
# Escrever propriedade
# ---------------------------------------------------------------------------
_TIPO_BYTE, _TIPO_INT, _TIPO_BOOL = 1, 2, 3
_TIPO_FLOAT, _TIPO_OBJETO, _TIPO_NOME = 4, 5, 6
_TIPO_ESTRUTURA = 10


def _codigo_do_tamanho(tamanho):
    """O codigo que o formato usa para cada tamanho de valor."""
    for codigo, fixo in sorted(l2anim._TAMANHOS_FIXOS.items()):
        if fixo == tamanho:
            return codigo, b""
    if tamanho <= 0xFF:
        return 5, bytes([tamanho])
    if tamanho <= 0xFFFF:
        return 6, tamanho.to_bytes(2, "little")
    return 7, tamanho.to_bytes(4, "little")


def propriedade(mapa, nome_da_propriedade, tipo, valor, estrutura=None,
                verdadeiro=False):
    """Uma propriedade pronta para entrar no bloco de um objeto."""
    i_nome = indice_do_nome(mapa, nome_da_propriedade)
    if tipo == _TIPO_BOOL:
        # O valor de um booleano mora no BIT ALTO do byte de
        # informacao, e nao nos dados: o que vem depois e um tamanho
        # zero. Medido no lobby que funciona, onde `bLightChanged`
        # ligado e `d3 00`.
        info = _TIPO_BOOL | (5 << 4) | (0x80 if verdadeiro else 0)
        return l2anim.compacto(i_nome) + bytes([info, 0])

    codigo, extra = _codigo_do_tamanho(len(valor))
    info = tipo | (codigo << 4)
    saida = l2anim.compacto(i_nome) + bytes([info])
    if tipo == _TIPO_ESTRUTURA:
        saida += l2anim.compacto(indice_do_nome(mapa, estrutura))
    return saida + extra + valor


def fim_das_propriedades(mapa):
    """O `None` que fecha a lista de propriedades de um objeto."""
    return l2anim.compacto(indice_do_nome(mapa, "None"))


def objeto(mapa, indice):
    return l2anim.compacto(indice)


def vetor(x, y, z):
    return struct.pack("<3f", x, y, z)


def rotador(pitch, yaw, roll):
    return struct.pack("<3i", pitch, yaw, roll)


def flutuante(valor):
    return struct.pack("<f", valor)


# ---------------------------------------------------------------------------
# Acrescentar
# ---------------------------------------------------------------------------
def acrescentar_import(mapa, nome_do_pacote_da_classe, nome_da_classe, dono,
                       nome_do_objeto):
    """
    Poe um import novo e devolve o indice negativo dele.

    Repetido nao entra: um mesmo objeto importado duas vezes e um pacote que
    o cliente carrega duas vezes.
    """
    ja = achar_import(mapa, nome_do_objeto, dono)
    if ja is not None:
        return ja
    mapa["imports"].append({
        "pacote_classe": indice_do_nome(mapa, nome_do_pacote_da_classe),
        "classe": indice_do_nome(mapa, nome_da_classe),
        "dono": dono,
        "nome": indice_do_nome(mapa, nome_do_objeto),
    })
    return -len(mapa["imports"])


def acrescentar_export(mapa, classe, mae, dono, nome_do_objeto, flags, corpo):
    """
    Poe um export novo, com o corpo que vai para o fim do arquivo.

    O `inicio` fica em zero por enquanto: so na gravacao se sabe em que
    posicao o corpo vai cair.
    """
    campos = {
        "classe": classe,
        "mae": mae,
        "dono": dono,
        "nome": indice_do_nome(mapa, nome_do_objeto),
        "flags": flags,
        "tamanho": len(corpo),
        "inicio": 0,
    }
    mapa["exports"].append(campos)
    mapa["novos"].append((len(mapa["exports"]), bytes(corpo)))
    return len(mapa["exports"])


# ---------------------------------------------------------------------------
# Gravar
# ---------------------------------------------------------------------------
def gravar(mapa, destino):
    """
    Grava o mapa com as tabelas novas no fim, sem mover nada do que ja existe.

    Devolve o caminho gravado.
    """
    destino = Path(destino)
    saida = bytearray(mapa["dados"])

    # 1. o corpo de cada objeto novo, um atras do outro
    for indice, corpo in mapa["novos"]:
        mapa["exports"][indice - 1]["inicio"] = len(saida)
        saida += corpo

    # 2. a tabela de nomes inteira
    off_nomes = len(saida)
    for texto, flags in mapa["nomes"]:
        saida += l2anim._escrever_nome(texto, flags)

    # 3. a de imports
    off_imp = len(saida)
    for campos in mapa["imports"]:
        saida += l2anim._escrever_import(campos)

    # 4. a de exports, ja com o inicio de cada corpo novo
    off_exp = len(saida)
    for campos in mapa["exports"]:
        saida += l2anim._escrever_export(campos)

    # 5. o cabecalho passa a apontar para as tabelas novas
    struct.pack_into("<6I", saida, 12,
                     len(mapa["nomes"]), off_nomes,
                     len(mapa["exports"]), off_exp,
                     len(mapa["imports"]), off_imp)

    _acertar_geracoes(saida, len(mapa["nomes"]), len(mapa["exports"]))

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bytes(saida))
    return destino


def _acertar_geracoes(saida, quantos_nomes, quantos_exports):
    """
    A ultima geracao passa a contar o que o pacote tem agora.

    Depois dos offsets vem o GUID (16 bytes) e a lista de geracoes: cada uma
    guarda quantos exports e quantos nomes havia. Deixar a ultima mentindo e
    pedir para o motor desconfiar do arquivo.
    """
    pos = TAMANHO_DO_CABECALHO + 16                 # pula o GUID
    if pos + 4 > len(saida):
        return
    quantas = int.from_bytes(saida[pos:pos + 4], "little")
    pos += 4
    if not quantas or pos + 8 * quantas > len(saida):
        return
    ultima = pos + 8 * (quantas - 1)
    struct.pack_into("<2I", saida, ultima, quantos_exports, quantos_nomes)


# ---------------------------------------------------------------------------
# A tela do video
# ---------------------------------------------------------------------------
# O molde saiu do lobby que funciona: la a tela e um `StaticMeshActor` que
# aponta para a malha `seq` do pacote de video. Medido naquele mapa:
#
#   ponto de entrada do jogador   (-8316.7, 238312.1, -6688.0)  giro 32768
#   tela                          (-9370.0, 238312.1, -6330.0)  giro 16384
#
# ou seja, a tela fica 1053 unidades A FRENTE de quem entra, 358 acima, e
# virada 90 graus para a esquerda em relacao a ele. E essa relacao que se
# leva de um lobby para outro -- a posicao absoluta nao serve, porque cada
# mapa tem o seu proprio mundo.
DISTANCIA_DA_TELA = 1053.3
ALTURA_DA_TELA = -3.0              # praticamente na altura dos olhos
GIRO_DA_TELA = -16384              # um quarto de volta, em unidades do Unreal
ESCALA_DA_TELA = 0.48

# A camera do login e um ponto de interpolacao sem marca. Os outros pontos do
# mapa sao os angulos da criacao de personagem -- vem em grade, todos na mesma
# altura, e com marca dizendo de que raca sao.
SEM_MARCA = ("InterpolationPoint", "", None)

VOLTA = 65536


def cameras(mapa):
    """
    Os pontos de camera do mapa: (indice, classe, posicao, giro, marca).

    Serve para escolher a mao quando o palpite erra -- e tambem para mostrar
    ao usuario quais sao as opcoes.
    """
    achados = []
    for i, campos in enumerate(mapa["exports"], 1):
        classe = classe_do_export(mapa, i)
        if classe not in ("InterpolationPoint", "PlayerStart") or not campos["tamanho"]:
            continue
        lugar = giro = marca = None
        try:
            for nome_da_prop, cru in propriedades(mapa, i):
                tipo, estrutura, valor = valor_da_propriedade(mapa, cru)
                if nome_da_prop == "Location" and len(valor) == 12:
                    lugar = struct.unpack("<3f", valor)
                elif nome_da_prop == "Rotation" and len(valor) == 12:
                    giro = struct.unpack("<3i", valor)
                elif nome_da_prop == "Tag" and tipo == 6:
                    marca = nome(mapa, l2anim._descompacto(valor, 0)[0])
        except Exception:                           # noqa: BLE001
            continue
        if lugar:
            achados.append((i, classe, lugar, giro or (0, 0, 0), marca))
    return achados


def _camera_do_login(mapa):
    """
    O ponto de onde a tela de login e vista.

    Os pontos de interpolacao de um lobby sao, na maioria, os angulos da
    criacao de personagem: vem em grade, na mesma altura, e levam marca com o
    nome da raca. O do login e um que sobra sem marca dessas -- e, como no
    lobby que funciona, ele fica na altura de olho do ponto de entrada.
    """
    pontos = cameras(mapa)
    entradas = [p for p in pontos if p[1] == "PlayerStart"]
    sem_marca = [p for p in pontos
                 if p[1] == "InterpolationPoint"
                 and (p[4] in SEM_MARCA)]
    if not sem_marca:
        return entradas[0] if entradas else None

    # o que estiver na altura de olho de algum ponto de entrada, e mais perto
    # dele, e o candidato -- e o arranjo do lobby que funciona.
    melhor, distancia = None, None
    for ponto in sem_marca:
        for entrada in entradas:
            perto = (abs(ponto[2][0] - entrada[2][0])
                     + abs(ponto[2][1] - entrada[2][1]))
            if distancia is None or perto < distancia:
                melhor, distancia = ponto, perto
    return melhor or sem_marca[0]


def lugar_sugerido(mapa, camera=None):
    """
    Onde plantar a tela neste mapa: (posicao, giro), ou None.

    `camera` permite passar o ponto a mao, quando o palpite erra -- e ele erra
    com facilidade, porque cada lobby arruma as cameras do seu jeito.
    """
    ponto = camera or _camera_do_login(mapa)
    if ponto is None:
        return None
    _indice, _classe, (x, y, z), (_passo, guinada, _rolagem), _marca = ponto
    angulo = (guinada % VOLTA) / VOLTA * 2 * math.pi
    return ((x + DISTANCIA_DA_TELA * math.cos(angulo),
             y + DISTANCIA_DA_TELA * math.sin(angulo),
             z + ALTURA_DA_TELA),
            (0, (guinada + GIRO_DA_TELA) % VOLTA, 0))


def _regiao_de_exemplo(mapa):
    """
    A `Region` de um ator que ja existe neste mapa.

    Ela aponta zona e no do mapa por indice: inventar um valor poria a tela
    numa zona que nao existe. Copiar de um vizinho e o certo.
    """
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) != "StaticMeshActor" or not campos["tamanho"]:
            continue
        try:
            for nome_da_prop, cru in propriedades(mapa, i):
                if nome_da_prop == "Region":
                    _t, _e, valor = valor_da_propriedade(mapa, cru)
                    return valor
        except Exception:                           # noqa: BLE001
            continue
    return None


def quadro_de_um_vizinho(mapa, classe="StaticMeshActor"):
    """
    O quadro de estado copiado de um ator que ja funciona neste mapa.

    Nao se inventa esse bloco. Ele carrega indices que so valem na tabela
    deste arquivo, e um valor errado nao da erro de leitura -- da erro no
    cliente, na hora de carregar o mapa, com o jogo fechando.

    Devolve (bytes do quadro, flags do ator), ou (None, None).
    """
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) != classe or not campos["tamanho"]:
            continue
        if not (campos["flags"] & TEM_PILHA):
            continue
        tamanho = _tamanho_do_quadro(mapa["dados"], campos["inicio"])
        return (bytes(mapa["dados"][campos["inicio"]:
                                    campos["inicio"] + tamanho]),
                campos["flags"])
    return None, None


def _quadro_de_estado(i_classe):
    """
    Um quadro montado a mao, para quando nao ha vizinho de quem copiar.

    O deslocamento e -1 de proposito: e o que diz que este ator nao esta no
    meio de um script. Com zero, o motor tenta retomar o bytecode na posicao
    zero de um script vazio e recusa o mapa.
    """
    return (l2anim.compacto(i_classe) + l2anim.compacto(i_classe)
            + b"\xff" * 8 + b"\xfe\xfe\xfe\xfe"
            + l2anim.compacto(-1))


def plantar_tela(mapa, pacote_do_video, malha="seq", lugar=None, giro=None,
                 escala=ESCALA_DA_TELA, nome_do_ator=None):
    """
    Poe no mapa um ator que mostra a malha da tela do pacote de video.

    `pacote_do_video` e o nome com que o pacote vai ser instalado -- e por
    esse nome que o cliente vai procurar o arquivo, entao ele tem de bater
    com o nome do `.usx`.

    Devolve o indice do export criado.
    """
    i_classe = achar_import(mapa, "StaticMeshActor")
    if i_classe is None:
        raise ErroDeMapa("este mapa nao usa StaticMeshActor; nao sei plantar "
                         "a tela nele.")

    i_pacote = acrescentar_import(mapa, "Core", "Package", 0, pacote_do_video)
    i_malha = acrescentar_import(mapa, "Engine", "StaticMesh", i_pacote, malha)

    sugerido = lugar_sugerido(mapa)
    if lugar is None or giro is None:
        if sugerido is None:
            raise ErroDeMapa("nao achei onde a camera deste lobby fica; "
                             "passe a posicao da tela a mao.")
        lugar = lugar or sugerido[0]
        giro = giro or sugerido[1]

    i_nivel = achar_export(mapa, "LevelInfo0") or 0
    i_volume = achar_export(mapa, "PhysicsVolume0") or 0
    regiao = _regiao_de_exemplo(mapa)

    quadro, flags = quadro_de_um_vizinho(mapa)
    if quadro is None:
        quadro, flags = _quadro_de_estado(i_classe), FLAGS_DO_ATOR

    corpo = bytearray(quadro)
    corpo += propriedade(mapa, "StaticMesh", _TIPO_OBJETO, objeto(mapa, i_malha))
    corpo += propriedade(mapa, "bLightChanged", _TIPO_BOOL, b"", verdadeiro=True)
    if i_nivel:
        corpo += propriedade(mapa, "Level", _TIPO_OBJETO, objeto(mapa, i_nivel))
    if regiao:
        corpo += propriedade(mapa, "Region", _TIPO_ESTRUTURA, regiao,
                             estrutura="PointRegion")
    corpo += propriedade(mapa, "Tag", _TIPO_NOME,
                         l2anim.compacto(indice_do_nome(mapa, "StaticMeshActor")))
    if i_volume:
        corpo += propriedade(mapa, "PhysicsVolume", _TIPO_OBJETO,
                             objeto(mapa, i_volume))
    corpo += propriedade(mapa, "Location", _TIPO_ESTRUTURA,
                         vetor(*lugar), estrutura="Vector")
    corpo += propriedade(mapa, "Rotation", _TIPO_ESTRUTURA,
                         rotador(*giro), estrutura="Rotator")
    corpo += propriedade(mapa, "DrawScale", _TIPO_FLOAT, flutuante(escala))
    corpo += propriedade(mapa, "ColLocation", _TIPO_ESTRUTURA,
                         vetor(*lugar), estrutura="Vector")
    corpo += fim_das_propriedades(mapa)

    nome_do_ator = nome_do_ator or _nome_livre(mapa, "StaticMeshActor")
    return acrescentar_export(mapa, i_classe, 0, 0, nome_do_ator,
                              flags, bytes(corpo))


# As mesmas marcas do ator da tela no lobby que funciona.
FLAGS_DO_ATOR = 0x02060001


def _nome_livre(mapa, prefixo):
    """Um nome de ator que ainda nao existe neste mapa."""
    usados = {n for n, _f in mapa["nomes"]}
    numero = 1
    while "%s%d" % (prefixo, numero) in usados:
        numero += 1
    return "%s%d" % (prefixo, numero)


# ---------------------------------------------------------------------------
# A lista de atores do nivel
# ---------------------------------------------------------------------------
# O motor nao percorre os objetos do pacote: ele percorre esta lista. Um ator
# que existe no arquivo e nao esta aqui nao existe para o jogo.
def achar_nivel(mapa):
    """O indice do export de classe `Level`, ou None."""
    for i in range(1, len(mapa["exports"]) + 1):
        if classe_do_export(mapa, i) == "Level":
            return i
    return None


def _abrir_nivel(mapa, indice):
    """(cabeca, lista de atores, rabo) do objeto de nivel."""
    dados, inicio, fim = _onde_esta_o_corpo(mapa, indice)

    _props, pos = l2anim.ler_propriedades(
        dados, inicio, [n for n, _f in mapa["nomes"]], fim)
    cabeca = bytes(dados[inicio:pos])

    quantos = int.from_bytes(dados[pos:pos + 4], "little")
    pos += 8                                # o numero vem escrito duas vezes

    atores = []
    for _ in range(quantos):
        valor, pos = l2anim._descompacto(dados, pos)
        atores.append(valor)

    return cabeca, atores, bytes(dados[pos:fim])


def _fechar_nivel(cabeca, atores, rabo):
    corpo = bytearray(cabeca)
    corpo += len(atores).to_bytes(4, "little")
    corpo += len(atores).to_bytes(4, "little")
    for valor in atores:
        corpo += l2anim.compacto(valor)
    corpo += rabo
    return bytes(corpo)


def substituir_corpo(mapa, indice, corpo):
    """
    Troca o corpo de um objeto que ja existe.

    O corpo novo vai para o fim do arquivo na hora de gravar -- e por isso
    que ele pode ter tamanho diferente sem empurrar nada.
    """
    mapa["exports"][indice - 1]["tamanho"] = len(corpo)
    # reescrever o mesmo ator duas vezes substitui a entrada da fila, em vez
    # de empilhar outra -- duas entradas para o mesmo indice gravariam o
    # corpo duas vezes e a segunda venceria em silencio
    for posicao, (pendente, _velho) in enumerate(mapa["novos"]):
        if pendente == indice:
            mapa["novos"][posicao] = (indice, bytes(corpo))
            return indice
    mapa["novos"].append((indice, bytes(corpo)))
    return indice


def registrar_no_nivel(mapa, indices):
    """
    Poe os atores na lista do nivel, que e o que faz o jogo enxerga-los.

    Devolve quantos foram acrescentados.
    """
    nivel = achar_nivel(mapa)
    if nivel is None:
        raise ErroDeMapa("este mapa nao tem objeto de nivel; nao sei onde "
                         "inscrever o ator.")

    cabeca, atores, rabo = _abrir_nivel(mapa, nivel)
    postos = 0
    for indice in indices:
        if indice not in atores:
            atores.append(indice)
            postos += 1
    substituir_corpo(mapa, nivel, _fechar_nivel(cabeca, atores, rabo))
    return postos


def atores_do_nivel(mapa):
    """A lista de atores do nivel, para conferir."""
    nivel = achar_nivel(mapa)
    if nivel is None:
        return []
    _cabeca, atores, _rabo = _abrir_nivel(mapa, nivel)
    return atores


# ---------------------------------------------------------------------------
# Clonar um vizinho
# ---------------------------------------------------------------------------
# Um ator de mapa carrega muito mais do que malha e posicao: o grupo a que
# pertence, a zona em que esta, o volume de fisica, as marcas de iluminacao.
# Inventar esses campos da um ator que carrega sem erro e nao aparece --
# neste lobby, porque as cenas sao escolhidas pelo `Group`.
#
# Entao nao se inventa: copia-se o bloco do ator existente mais proximo do
# lugar onde a coisa vai, e troca-se apenas o necessario.
PROPRIEDADES_POR_ATOR = ("StaticMesh", "Location", "ColLocation", "Rotation",
                         "SwayRotationOrig", "DrawScale", "StaticMeshInstance")


def atores_com_lugar(mapa, classe="StaticMeshActor"):
    """[(indice, posicao)] de todo ator daquela classe que tem posicao."""
    achados = []
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) != classe or not campos["tamanho"]:
            continue
        try:
            for nome_da_prop, cru in propriedades(mapa, i):
                if nome_da_prop != "Location":
                    continue
                _t, _e, valor = valor_da_propriedade(mapa, cru)
                if len(valor) == 12:
                    achados.append((i, struct.unpack("<3f", valor)))
                break
        except Exception:                           # noqa: BLE001
            continue
    return achados


def vizinho_mais_perto(mapa, lugar, classe="StaticMeshActor"):
    """O ator existente mais proximo deste ponto, ou None."""
    melhor, distancia = None, None
    for indice, onde in atores_com_lugar(mapa, classe):
        d = ((onde[0] - lugar[0]) ** 2 + (onde[1] - lugar[1]) ** 2
             + (onde[2] - lugar[2]) ** 2)
        if distancia is None or d < distancia:
            melhor, distancia = indice, d
    return melhor


def clonar_ator(mapa, vizinho, trocas, sem=()):
    """
    O corpo de um ator novo, copiado de `vizinho`.

    `trocas` sao as propriedades a substituir, ja prontas em bytes. `sem` sao
    as a deixar de fora -- o `StaticMeshInstance`, por exemplo, aponta para
    um objeto que e daquele ator e nao deste.

    Devolve (corpo, flags), para o export novo nascer com as mesmas marcas.
    """
    campos = mapa["exports"][vizinho - 1]
    dados, inicio, _fim = _onde_esta_o_corpo(mapa, vizinho)
    quadro = b""
    if campos["flags"] & TEM_PILHA:
        tamanho = _tamanho_do_quadro(dados, inicio)
        quadro = bytes(dados[inicio:inicio + tamanho])

    corpo = bytearray(quadro)
    postas = set()
    for nome_da_prop, cru in propriedades(mapa, vizinho):
        if nome_da_prop in sem:
            continue
        if nome_da_prop in trocas:
            corpo += trocas[nome_da_prop]
            postas.add(nome_da_prop)
        else:
            corpo += bytes(cru)
    # o que o vizinho nao tinha, mas foi pedido, entra no fim
    for nome_da_prop, cru in trocas.items():
        if nome_da_prop not in postas:
            corpo += cru
    corpo += fim_das_propriedades(mapa)
    return bytes(corpo), campos["flags"]


# O que NAO se herda ao clonar um ator para receber outra malha.
#
#   material    descrevem os slots da malha de origem; noutra malha, com
#               outra quantidade de slots, derrubam o cliente
#   iluminacao  o `StaticMeshInstance` pertence aquele ator, e nao a este
#   movimento   fazem o objeto se mexer. Foi o que fez a tela de video girar:
#               o vizinho mais proximo era uma queda d'agua animada, e a tela
#               herdou a rotacao dela. O sintoma parecia de posicao -- ora o
#               filme, ora o verso sem textura -- e era de movimento.
SEM_HERDAR = ("Skins", "TexModifyInfo",          # material
              "StaticMeshInstance",              # iluminacao
              "Physics", "RotationRate", "bFixedRotationDir",   # movimento
              "DrawScale3D")                     # formato


def plantar_tela_perto(mapa, pacote_do_video, lugar, giro, escala=ESCALA_DA_TELA,
                       malha="seq", nome_do_ator=None):
    """
    Planta a tela clonando o ator existente mais proximo do lugar escolhido.

    E a forma que funciona: o clone ja vem com o grupo da cena, a zona certa
    e o volume de fisica daquele trecho do mapa.
    """
    i_classe = achar_import(mapa, "StaticMeshActor")
    if i_classe is None:
        raise ErroDeMapa("este mapa nao usa StaticMeshActor.")

    i_pacote = acrescentar_import(mapa, "Core", "Package", 0, pacote_do_video)
    i_malha = acrescentar_import(mapa, "Engine", "StaticMesh", i_pacote, malha)

    vizinho = vizinho_mais_perto(mapa, lugar)
    if vizinho is None:
        raise ErroDeMapa("nao achei nenhum ator de quem copiar.")

    return plantar_malha_perto(mapa, i_malha, lugar, giro, escala, vizinho,
                               nome_do_ator), vizinho


def vizinho_com_a_malha(mapa, i_malha):
    """
    Um ator que ja usa esta malha, se houver.

    Copiar dele e melhor do que copiar de um vizinho qualquer: as
    propriedades de material -- `Skins`, `TexModifyInfo` -- descrevem os
    slots da malha, e as de outra malha nao servem. No pior caso derrubam o
    cliente.
    """
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) != "StaticMeshActor" or not campos["tamanho"]:
            continue
        try:
            for nome_da_prop, cru in propriedades(mapa, i):
                if nome_da_prop != "StaticMesh":
                    continue
                _t, _e, valor = valor_da_propriedade(mapa, cru)
                if l2anim._descompacto(valor, 0)[0] == i_malha:
                    return i
        except Exception:                           # noqa: BLE001
            continue
    return None


def plantar_malha_perto(mapa, i_malha, lugar, giro, escala, vizinho,
                        nome_do_ator=None):
    """O mesmo, para uma malha que ja esta no mapa -- serve de marco."""
    # quem ja usa esta malha e o molde ideal: o material dela vem junto e
    # certo, em vez de vir o de outra malha
    igual = vizinho_com_a_malha(mapa, i_malha)
    if igual is not None:
        vizinho = igual
    trocas = {
        "StaticMesh": propriedade(mapa, "StaticMesh", _TIPO_OBJETO,
                                  objeto(mapa, i_malha)),
        "Location": propriedade(mapa, "Location", _TIPO_ESTRUTURA,
                                vetor(*lugar), estrutura="Vector"),
        "ColLocation": propriedade(mapa, "ColLocation", _TIPO_ESTRUTURA,
                                   vetor(*lugar), estrutura="Vector"),
        "DrawScale": propriedade(mapa, "DrawScale", _TIPO_FLOAT,
                                 flutuante(escala)),
    }
    if giro is not None:
        trocas["Rotation"] = propriedade(mapa, "Rotation", _TIPO_ESTRUTURA,
                                         rotador(*giro), estrutura="Rotator")
        trocas["SwayRotationOrig"] = propriedade(
            mapa, "SwayRotationOrig", _TIPO_ESTRUTURA, rotador(*giro),
            estrutura="Rotator")

    corpo, flags = clonar_ator(mapa, vizinho, trocas, sem=SEM_HERDAR)
    i_classe = mapa["exports"][vizinho - 1]["classe"]
    nome_do_ator = nome_do_ator or _nome_livre(mapa, "StaticMeshActor")
    return acrescentar_export(mapa, i_classe, 0, 0, nome_do_ator, flags, corpo)


def reescrever_ator(mapa, indice, trocas, sem=()):
    """
    Troca propriedades de um ator que ja existe, mantendo o resto.

    O quadro de estado dele e preservado como esta: ele carrega indices que
    so valem para aquele objeto. `trocas` sao propriedades ja em bytes;
    `sem` sao as que saem.

    O corpo novo vai para o fim do arquivo na gravacao -- por isso ele pode
    ter tamanho diferente sem mover nada.
    """
    campos = mapa["exports"][indice - 1]
    dados, inicio, _fim = _onde_esta_o_corpo(mapa, indice)
    quadro = b""
    if campos["flags"] & TEM_PILHA:
        tamanho = _tamanho_do_quadro(dados, inicio)
        quadro = bytes(dados[inicio:inicio + tamanho])

    corpo = bytearray(quadro)
    postas = set()
    for nome_da_prop, cru in propriedades(mapa, indice):
        if nome_da_prop in sem:
            continue
        if nome_da_prop in trocas:
            corpo += trocas[nome_da_prop]
            postas.add(nome_da_prop)
        else:
            corpo += bytes(cru)
    for nome_da_prop, cru in trocas.items():
        if nome_da_prop not in postas:
            corpo += cru
    corpo += fim_das_propriedades(mapa)
    return substituir_corpo(mapa, indice, bytes(corpo))


def travar_movimento(mapa, indices, duracao=0.02):
    """
    Deixa um movimento de camera instantaneo.

    Nao se apaga a acao: apagar mexeria na lista de acoes de quem a chama.
    Encurtar a duracao para quase zero faz a camera chegar ao destino na hora
    e ficar la -- que e o efeito de camera parada.
    """
    for indice in indices:
        reescrever_ator(mapa, indice, {
            "Duration": propriedade(mapa, "Duration", _TIPO_FLOAT,
                                    flutuante(duracao)),
        })
    return len(indices)


def remover_do_nivel(mapa, indices):
    """
    Tira atores da lista do nivel, sem apaga-los do arquivo.

    E o jeito de desligar um ator: o motor percorre a lista, e o que nao
    esta nela nao roda. O objeto continua guardado, entao devolve-lo depois
    e so inscrever de novo.
    """
    nivel = achar_nivel(mapa)
    if nivel is None:
        raise ErroDeMapa("este mapa nao tem objeto de nivel.")

    cabeca, atores, rabo = _abrir_nivel(mapa, nivel)
    fora = set(indices)
    ficam = [a for a in atores if a not in fora]
    tirados = len(atores) - len(ficam)
    substituir_corpo(mapa, nivel, _fechar_nivel(cabeca, ficam, rabo))
    return tirados


def trocar_valor(mapa, cru, novo_valor):
    """
    A mesma propriedade, com outro valor.

    Preserva o indice do nome, o tipo e -- havendo -- o nome da estrutura,
    porque copiar o cabecalho e mais seguro do que remonta-lo. So o tamanho
    e recalculado, ja que o valor mudou de comprimento.
    """
    pos = 0
    i_nome, pos = l2anim._descompacto(cru, pos)
    info = cru[pos]
    pos += 1
    tipo = info & 0x0F
    codigo = (info >> 4) & 0x07
    cabeca = bytearray(l2anim.compacto(i_nome))

    estrutura = None
    if tipo == 10:
        i_est, pos = l2anim._descompacto(cru, pos)
        estrutura = i_est

    if codigo < 5:
        pass
    elif codigo == 5:
        pos += 1
    elif codigo == 6:
        pos += 2
    else:
        pos += 4

    novo_codigo, extra = _codigo_do_tamanho(len(novo_valor))
    cabeca.append(tipo | (novo_codigo << 4) | (info & 0x80))
    if estrutura is not None:
        cabeca += l2anim.compacto(estrutura)
    return bytes(cabeca) + extra + bytes(novo_valor)


def esvaziar_vetor(mapa, indice, nome_da_propriedade):
    """
    Deixa um vetor de objetos sem nenhum item.

    Serve para desligar uma lista de acoes sem apagar as acoes: elas
    continuam no arquivo, e devolve-las e so repor os indices.
    """
    for nome_atual, cru in propriedades(mapa, indice):
        if nome_atual != nome_da_propriedade:
            continue
        return reescrever_ator(mapa, indice,
                               {nome_da_propriedade: trocar_valor(mapa, cru,
                                                                  b"\x00")})
    raise ErroDeMapa("o ator #%d nao tem a propriedade %s"
                     % (indice, nome_da_propriedade))


# ---------------------------------------------------------------------------
# O video na tela de login
# ---------------------------------------------------------------------------
# Um lobby costuma ter tres cenas -- login, selecao e criacao de personagem --
# e cada uma e um `SceneManager` com uma lista de acoes. Ha dois tipos de
# acao que interessam:
#
#   ActionWarp        poe a camera num ponto, e acabou
#   ActionMoveCamera  leva a camera por um percurso, com duracao
#
# Para o video, o salto e o unico que serve. O percurso recomeca toda vez que
# a cena e montada, e uma tela de login e montada mais de uma vez -- ao abrir
# o jogo, ao voltar da selecao de personagem, ao cair a conexao. Com percurso,
# cada uma dessas voltas pega a camera num lugar diferente do caminho e o
# filme aparece cortado, torto ou nao aparece. Com salto, nao ha caminho.
#
# A tela e uma peca so aparentemente. Sao duas:
#
#   a tela    a malha do pacote de video, onde o filme roda
#   o fundo   a mesma malha, muito maior e atras, com uma textura preta. E o
#             que cobre o cenario do mapa no que sobrar da janela
#
# A escala da tela sai de medida, nao de tentativa. O cliente mantem fixa a
# abertura horizontal do campo de visao e deixa a vertical variar com o
# formato da janela -- por isso a largura sempre ficava coberta e a altura
# nao. Medindo duas capturas, em escalas diferentes, a relacao ficou:
#
#     cobertura da altura = 0,83 x escala x (largura / altura)
#
# As duas medidas deram 0,835 e 0,819. Dai sai a escala necessaria para cada
# formato de tela: 5 por 4 pede 0,97; 4 por 3 pede 0,91; 16 por 9 pede 0,68;
# a ultralarga, 0,51. Cobrindo a mais exigente, cobre todas -- e o corte nas
# beiradas fica no minimo que isso permite, porque cobrir a tela inteira
# sempre custa as beiradas de um filme cuja proporcao nao e a da tela.
# O tamanho da tela sai da geometria, e nao de tentativa.
#
# A malha da tela de video mede 2048 por 1152,7 unidades -- 16 por 9 exatos.
# Medindo em duas capturas quanto da janela o filme cobria, e sabendo o
# tamanho da malha, sobra uma incognita so: a abertura da camera. Ela deu
# tangente 0,473, ou seja 50 graus de abertura horizontal -- o mesmo numero
# que o mapa trazia escrito nas subacoes da camera, o que confere a conta por
# outro caminho.
#
# O que a camera alcanca a uma distancia d:
#
#     largura visivel = 2 d tg            altura visivel = largura / formato
#
# Entao cobrir a janela pede duas coisas, e vale a mais exigente. Em tela
# larga manda a largura; em tela alta manda a altura; as duas se encontram em
# 16 por 9, que e a proporcao da propria malha.
TANGENTE_DA_ABERTURA = 0.473       # tg de meia abertura: 50 graus na horizontal
LARGURA_DA_MALHA = 2048.0
ALTURA_DA_MALHA = 1152.7
FORMATO_MAIS_ALTO = 1.25           # 5 por 4, a mais alta das telas de uso comum
FOLGA_DA_TELA = 1.03               # um pouco de margem, para nao raspar
# O fundo preto fica LOGO atras da tela, e nao longe dela. A primeira versao
# copiava o lobby de referencia e o punha 85 unidades atras, grande o
# bastante para cobrir tudo -- e mesmo assim sobrava cenario na janela
# estreita. Medindo a captura, o cenario aparecia a 1,4 vez a altura da tela,
# quando o painel daquele tamanho cobriria 25 vezes: o que se via nao estava
# ALEM do painel, estava NA FRENTE dele. Um lobby tem geometria solta pelo
# mapa, e a camera do video vai parar em canto sem acabamento.
#
# Perto da tela, nada do mapa se mete no meio, e o painel nem precisa ser
# enorme: oito vezes a tela ja cobre uma janela tres vezes mais alta do que
# larga.
PAINEL_SOBRE_A_TELA = 8.0          # quantas vezes o fundo e maior que a tela
RECUO_DO_PAINEL = 20.0             # o quanto o fundo fica atras da tela
MARCAS_DO_LOGIN = ("LOGON", "LOGIN")
TEXTURA_DO_FUNDO = "blk"
_TIPO_VETOR = 9


def escala_para_cobrir(formato=FORMATO_MAIS_ALTO, folga=FOLGA_DA_TELA,
                       distancia=DISTANCIA_DA_TELA):
    """
    A escala da tela para o filme cobrir uma janela deste formato.

    `formato` e largura dividida por altura: 1,78 numa tela de notebook,
    1,60 numa 16 por 10, 1,33 numa 4 por 3, 1,25 numa 5 por 4. Quanto mais
    alta a janela, maior a escala necessaria -- e quanto mais longe a tela,
    tambem.
    """
    if formato <= 0:
        raise ErroDeMapa("formato de tela invalido: %r" % (formato,))
    # a dimensao que falta primeiro e quem manda
    aperta = min(ALTURA_DA_MALHA * formato, LARGURA_DA_MALHA)
    return folga * 2.0 * distancia * TANGENTE_DA_ABERTURA / aperta


def cobertura_da_altura(escala, formato, distancia=DISTANCIA_DA_TELA):
    """Quanto da altura da janela o filme cobre. Um ou mais e cobrir tudo."""
    return (escala * ALTURA_DA_MALHA * formato
            / (2.0 * distancia * TANGENTE_DA_ABERTURA))


def cobertura_da_largura(escala, distancia=DISTANCIA_DA_TELA):
    """O mesmo, na largura. Nao depende do formato da janela."""
    return (escala * LARGURA_DA_MALHA
            / (2.0 * distancia * TANGENTE_DA_ABERTURA))


def telas_do_video(mapa, pacote_do_video, malha="seq",
                   textura=TEXTURA_DO_FUNDO):
    """
    As pecas do video que ja existem no mapa: (tela, fundo).

    Distingue uma da outra pelo material: a que tem a textura preta no lugar
    do filme e o fundo. Serve para acertar um lobby pronto sem plantar peca
    nenhuma. Qualquer uma pode vir vazia.
    """
    i_pacote = achar_import(mapa, pacote_do_video)
    if i_pacote is None:
        return [], []
    i_malha = achar_import(mapa, malha, dono=i_pacote)
    i_textura = achar_import(mapa, textura, dono=i_pacote)
    if i_malha is None:
        return [], []

    telas, fundos = [], []
    for i, campos in enumerate(mapa["exports"], 1):
        if not campos["tamanho"]:
            continue
        try:
            props = dict(propriedades(mapa, i))
        except Exception:                           # noqa: BLE001
            continue
        if "StaticMesh" not in props:
            continue
        _t, _e, valor = valor_da_propriedade(mapa, props["StaticMesh"])
        if l2anim._descompacto(valor, 0)[0] != i_malha:
            continue
        e_fundo = False
        if i_textura is not None and "Skins" in props:
            _t, _e, pele = valor_da_propriedade(mapa, props["Skins"])
            e_fundo = i_textura in _lista_de_indices(pele)
        (fundos if e_fundo else telas).append(i)
    return telas, fundos


def ajustar_tela_ao_formato(mapa, pacote_do_video, formato=FORMATO_MAIS_ALTO,
                            malha="seq"):
    """
    Muda so o tamanho das pecas de video que o mapa ja tem.

    E o caso do lobby pronto: a tela esta no lugar certo, e o que nao serve e
    o tamanho dela para a janela de hoje. A distancia de cada peca ate a
    camera entra na conta, entao vale para qualquer lobby.

    Devolve [(indice, escala velha, escala nova)] do que mudou.
    """
    telas, fundos = telas_do_video(mapa, pacote_do_video, malha=malha)
    if not telas:
        return []

    achada = cena_do_login(mapa)
    olho = None
    if achada is not None:
        for acao in reversed(achada[2]):
            ponto = ponto_de_uma_acao(mapa, acao)
            if ponto:
                olho = lugar_de_um_ator(mapa, ponto)[0]
                break
    if olho is None:
        camera = _camera_do_login(mapa)
        olho = camera[2] if camera else None
    if olho is None:
        raise ErroDeMapa("nao achei a camera do login para medir a distancia.")

    mudou = []
    for indice in telas + fundos:
        lugar, _giro = lugar_de_um_ator(mapa, indice)
        if lugar is None:
            continue
        distancia = math.sqrt(sum((lugar[k] - olho[k]) ** 2 for k in range(3)))
        nova = escala_para_cobrir(formato, distancia=max(1.0, distancia))
        if indice in fundos:
            nova *= PAINEL_SOBRE_A_TELA
        velha = None
        for nome_da_prop, cru in propriedades(mapa, indice):
            if nome_da_prop == "DrawScale":
                velha = struct.unpack("<f", valor_da_propriedade(mapa, cru)[2])[0]
        reescrever_ator(mapa, indice, {
            "DrawScale": propriedade(mapa, "DrawScale", _TIPO_FLOAT,
                                     flutuante(nova)),
        })
        mudou.append((indice, velha, nova))
    return mudou


def marca_do_ator(mapa, indice):
    """O `Tag` de um objeto, que e como as cenas se identificam."""
    try:
        for nome_da_prop, cru in propriedades(mapa, indice):
            if nome_da_prop != "Tag":
                continue
            tipo, _estrutura, valor = valor_da_propriedade(mapa, cru)
            if tipo == _TIPO_NOME:
                return nome(mapa, l2anim._descompacto(valor, 0)[0])
    except Exception:                               # noqa: BLE001
        return None
    return None


def _lista_de_indices(cru):
    """O vetor de objetos do Unreal: um total, e depois os indices."""
    posicao, lista = 1, []
    for _ in range(cru[0] if cru else 0):
        indice, posicao = l2anim._descompacto(cru, posicao)
        lista.append(indice)
    return lista


def cenas(mapa):
    """As cenas do mapa: (indice, marca, [acoes])."""
    achadas = []
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) != "SceneManager" or not campos["tamanho"]:
            continue
        try:
            props = dict(propriedades(mapa, i))
        except Exception:                           # noqa: BLE001
            continue
        acoes = []
        if "Actions" in props:
            _t, _e, valor = valor_da_propriedade(mapa, props["Actions"])
            acoes = _lista_de_indices(valor)
        achadas.append((i, marca_do_ator(mapa, i), acoes))
    return achadas


def cena_do_login(mapa):
    """A cena da tela de login, pela marca. (indice, marca, acoes) ou None."""
    for indice, marca, acoes in cenas(mapa):
        if marca and any(m in marca.upper() for m in MARCAS_DO_LOGIN):
            return indice, marca, acoes
    return None


def ponto_de_uma_acao(mapa, indice):
    """Para que ponto de camera uma acao aponta."""
    try:
        for nome_da_prop, cru in propriedades(mapa, indice):
            if nome_da_prop == "IntPoint":
                _t, _e, valor = valor_da_propriedade(mapa, cru)
                return l2anim._descompacto(valor, 0)[0]
    except Exception:                               # noqa: BLE001
        return None
    return None


def lugar_de_um_ator(mapa, indice):
    """(posicao, giro) de um ator."""
    lugar = giro = None
    for nome_da_prop, cru in propriedades(mapa, indice):
        _t, _e, valor = valor_da_propriedade(mapa, cru)
        if nome_da_prop == "Location" and len(valor) == 12:
            lugar = struct.unpack("<3f", valor)
        elif nome_da_prop == "Rotation" and len(valor) == 12:
            giro = struct.unpack("<3i", valor)
    return lugar, giro or (0, 0, 0)


def saltar_em_vez_de_voar(mapa, cena, ponto):
    """
    A cena passa a ter uma acao so, e ela e um salto ate o ponto.

    O salto nasce de molde: copia-se um `ActionWarp` que o mapa ja usa, e so
    o ponto de destino muda. Um `SceneManager` sem acao nenhuma derruba o
    cliente, entao a troca e sempre por uma, nunca por zero.
    """
    molde = None
    for i, campos in enumerate(mapa["exports"], 1):
        if classe_do_export(mapa, i) == "ActionWarp" and campos["tamanho"]:
            molde = i
            break
    if molde is None:
        raise ErroDeMapa("este mapa nao tem nenhum salto de camera de onde "
                         "copiar; nao sei fixar a camera dele.")

    corpo, flags = clonar_ator(mapa, molde, {
        "IntPoint": propriedade(mapa, "IntPoint", _TIPO_OBJETO,
                                objeto(mapa, ponto)),
    })
    salto = acrescentar_export(mapa, mapa["exports"][molde - 1]["classe"],
                               0, 0, _nome_livre(mapa, "ActionWarp"),
                               flags, corpo)
    reescrever_ator(mapa, cena, {
        "Actions": propriedade(mapa, "Actions", _TIPO_VETOR,
                               b"\x01" + l2anim.compacto(salto)),
    })
    return salto


def plantar_fundo_perto(mapa, pacote_do_video, lugar, giro, escala,
                        textura=TEXTURA_DO_FUNDO, malha="seq"):
    """
    O painel preto atras da tela: a mesma malha, com outra textura.

    A textura vem do proprio pacote de video -- e ela que faz o painel ser
    preto em vez de mostrar o filme de novo, em tamanho grande.
    """
    i_pacote = acrescentar_import(mapa, "Core", "Package", 0, pacote_do_video)
    i_malha = acrescentar_import(mapa, "Engine", "StaticMesh", i_pacote, malha)
    i_textura = acrescentar_import(mapa, "Engine", "Texture", i_pacote, textura)

    vizinho = vizinho_com_a_malha(mapa, i_malha) or vizinho_mais_perto(mapa, lugar)
    if vizinho is None:
        raise ErroDeMapa("nao achei nenhum ator de quem copiar.")

    corpo, flags = clonar_ator(mapa, vizinho, {
        "StaticMesh": propriedade(mapa, "StaticMesh", _TIPO_OBJETO,
                                  objeto(mapa, i_malha)),
        "Location": propriedade(mapa, "Location", _TIPO_ESTRUTURA,
                                vetor(*lugar), estrutura="Vector"),
        "ColLocation": propriedade(mapa, "ColLocation", _TIPO_ESTRUTURA,
                                   vetor(*lugar), estrutura="Vector"),
        "Rotation": propriedade(mapa, "Rotation", _TIPO_ESTRUTURA,
                                rotador(*giro), estrutura="Rotator"),
        "DrawScale": propriedade(mapa, "DrawScale", _TIPO_FLOAT,
                                 flutuante(escala)),
        "Skins": propriedade(mapa, "Skins", _TIPO_VETOR,
                             b"\x01" + l2anim.compacto(i_textura)),
    }, sem=SEM_HERDAR + ("DrawScale3D",))
    return acrescentar_export(mapa, mapa["exports"][vizinho - 1]["classe"],
                              0, 0, _nome_livre(mapa, "StaticMeshActor"),
                              flags, corpo)


def instalar_video_no_login(mapa, pacote_do_video, camera=None,
                            formato=FORMATO_MAIS_ALTO, escala=None,
                            distancia=DISTANCIA_DA_TELA):
    """
    Poe o video na tela de login: camera fixa, tela e fundo.

    `camera` e (x, y, z) ou (x, y, z, giro) para mudar de lugar o ponto da
    camera; sem ela, o ponto fica onde esta e as pecas nascem a frente dele.
    `formato` e a janela mais alta que se quer cobrir; `escala` passa por
    cima da conta, quando se quer um valor a mao.

    Devolve um resumo do que foi feito. Nao grava: quem chama decide isso.
    """
    achada = cena_do_login(mapa)
    if achada is None:
        raise ErroDeMapa("nao achei a cena de login deste mapa.")
    cena, marca, acoes = achada

    ponto = None
    for acao in reversed(acoes):
        ponto = ponto_de_uma_acao(mapa, acao)
        if ponto:
            break
    if ponto is None:
        olho = _camera_do_login(mapa)
        ponto = olho[0] if olho else None
    if ponto is None:
        raise ErroDeMapa("nao achei o ponto de camera do login.")

    if camera is not None:
        lugar_da_camera = tuple(float(v) for v in camera[:3])
        _antes, giro_antes = lugar_de_um_ator(mapa, ponto)
        guinada = int(camera[3]) if len(camera) > 3 else giro_antes[1]
        reescrever_ator(mapa, ponto, {
            "Location": propriedade(mapa, "Location", _TIPO_ESTRUTURA,
                                    vetor(*lugar_da_camera),
                                    estrutura="Vector"),
            "Rotation": propriedade(mapa, "Rotation", _TIPO_ESTRUTURA,
                                    rotador(0, guinada % VOLTA, 0),
                                    estrutura="Rotator"),
        })
    else:
        lugar_da_camera, giro = lugar_de_um_ator(mapa, ponto)
        if lugar_da_camera is None:
            raise ErroDeMapa("o ponto de camera do login nao tem posicao.")
        guinada = giro[1]

    salto = saltar_em_vez_de_voar(mapa, cena, ponto)

    if escala is None:
        escala = escala_para_cobrir(formato)
    angulo = (guinada % VOLTA) / VOLTA * 2 * math.pi
    frente = (math.cos(angulo), math.sin(angulo))
    giro_das_pecas = (0, (guinada + GIRO_DA_TELA) % VOLTA, 0)

    def a_frente(quanto):
        return (lugar_da_camera[0] + quanto * frente[0],
                lugar_da_camera[1] + quanto * frente[1],
                lugar_da_camera[2] + ALTURA_DA_TELA)

    tela, _vizinho = plantar_tela_perto(mapa, pacote_do_video,
                                        a_frente(distancia), giro_das_pecas,
                                        escala=escala)
    fundo = plantar_fundo_perto(mapa, pacote_do_video,
                                a_frente(distancia + RECUO_DO_PAINEL),
                                giro_das_pecas, escala * PAINEL_SOBRE_A_TELA)
    registrar_no_nivel(mapa, [tela, fundo])

    return {"cena": cena, "marca": marca, "acoes_antes": acoes,
            "ponto": ponto, "salto": salto, "tela": tela, "fundo": fundo,
            "escala": escala, "camera": lugar_da_camera, "giro": guinada}


def pacotes_usados(mapa):
    """
    De que pacotes este mapa depende: {nome: quantas referencias}.

    Sao os pacotes de nivel raiz que o mapa importa -- malhas, texturas,
    sons. Os do proprio motor ficam de fora: `Core`, `Engine` e `Editor` nao
    sao arquivo que se copie, vem com o cliente.

    Serve para saber o que precisa viajar junto de um lobby, e o que o
    cliente de destino ja tem.
    """
    raizes = {-(i + 1): nome(mapa, imp["nome"])
              for i, imp in enumerate(mapa["imports"]) if imp["dono"] == 0}
    contagem = {}
    for imp in mapa["imports"]:
        dono = imp["dono"]
        if dono not in raizes:
            continue
        pacote = raizes[dono]
        if pacote in ("Core", "Engine", "Editor"):
            continue
        contagem[pacote] = contagem.get(pacote, 0) + 1
    return contagem


def renomear_pacote(mapa, velho, novo):
    """
    O mapa passa a procurar o pacote por outro nome.

    Serve para instalar o cenario de um lobby com o nome do projeto, em vez
    do nome de quem o fez. O arquivo tem de ser instalado com o mesmo nome
    novo, senao a referencia fica apontando para o vazio.

    Devolve quantas referencias mudaram de nome.
    """
    if velho == novo:
        return 0
    indice_novo = indice_do_nome(mapa, novo)
    mudou = 0
    for i, imp in enumerate(mapa["imports"]):
        if imp["dono"] != 0:
            continue
        if nome(mapa, imp["nome"]) != velho:
            continue
        mapa["imports"][i] = dict(imp, nome=indice_novo)
        mudou += 1
    # o nome tambem aparece nas referencias de dentro dos objetos? Nao: o
    # corpo guarda indices de import, e e o registro do import que carrega o
    # nome. Trocar ali basta.
    return mudou


def objetos_usados(mapa):
    """
    Que objetos o mapa usa de cada pacote: {pacote: {nome: classe}}.

    So as folhas -- o que e `Package` e grupo, nao objeto. E isso que um
    cliente precisa ter dentro dos pacotes dele para o mapa nao aparecer
    sem textura.
    """
    def raiz_de(indice):
        visto = 0
        while indice < 0 and visto < 16:
            imp = mapa["imports"][-indice - 1]
            if imp["dono"] == 0:
                return nome(mapa, imp["nome"])
            indice = imp["dono"]
            visto += 1
        return None

    usados = {}
    for i, imp in enumerate(mapa["imports"]):
        classe = nome(mapa, imp["classe"])
        if classe == "Package" or imp["dono"] == 0:
            continue
        raiz = raiz_de(-(i + 1))
        if raiz in (None, "Core", "Engine", "Editor"):
            continue
        usados.setdefault(raiz, {})[nome(mapa, imp["nome"])] = classe
    return usados


def pacote_da_tela(mapa, malha="seq"):
    """
    De que pacote vem a malha da tela de video deste mapa, se houver.

    Procura pela malha, e nao pelo nome do pacote: o nome muda de um lobby
    para outro, a malha nao. Devolve None num mapa sem tela.
    """
    for imp in mapa["imports"]:
        if nome(mapa, imp["classe"]) != "StaticMesh":
            continue
        if nome(mapa, imp["nome"]).lower() != malha.lower():
            continue
        dono = imp["dono"]
        if dono < 0 and mapa["imports"][-dono - 1]["dono"] == 0:
            return nome(mapa, mapa["imports"][-dono - 1]["nome"])
    return None
