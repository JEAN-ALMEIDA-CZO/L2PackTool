#!/usr/bin/env python3
"""
Video virando textura animada do Lineage 2.

O cliente nao toca video: nao ha Bink nem codec nenhum na pasta system -- foi
conferido. O que ele tem e o mecanismo do Unreal Engine 2: cada quadro e uma
textura, e a propriedade `AnimNext` de cada uma aponta para a seguinte. O motor
percorre a corrente sozinho, e o ultimo quadro apontando para o primeiro faz o
video repetir. E assim que os "lobbies com video" da comunidade sao feitos.

O problema era escrever essa corrente. O `ucc make` nao tem comando para gravar
propriedade em objeto importado -- foram testadas quatro sintaxes, todas
compilam e nenhuma grava nada -- e por isso a receita que circula manda ligar
quadro por quadro, na mao, no UnrealEd.

Aqui a corrente e escrita DIRETO NO PACOTE, e sem refazer o arquivo. Dois
fatos tornam isso possivel:

  1. o pacote que o ucc monta usa propriedades MARCADAS (licenciado 0), e nao
     o formato nativo do cliente (licenciado 28). Propriedade marcada e
     `[nome][tipo][tamanho][valor]`, e o que o motor nao reconhece ele pula
     pelo tamanho declarado;

  2. tamanho e posicao de cada objeto ficam no indice do pacote em codigo de
     tamanho VARIAVEL. Mudar o tamanho de um objeto obrigaria a refazer o
     arquivo inteiro. Entao nada cresce: as duas entradas `InternalTime` --
     que sao o relogio do motor em tempo de execucao, sem valor num arquivo --
     saem para abrir espaco, e o que sobra vira enchimento com um nome que a
     classe Texture nao conhece.

Conferido com o umodel: depois da escrita ele le
`AnimNext = Texture'Upscaled.quadro01'` em cada quadro, e o arquivo continua
com o mesmo numero de bytes.
"""

import re
import shutil
import struct
from pathlib import Path

import l2npc
import l2upscale as motor

try:
    from PIL import Image, ImageSequence
except ImportError:
    Image = None


# Nomes que precisam existir na tabela de nomes do pacote para a corrente
# poder ser escrita depois. Ver `montar` em l2upscale.
NOMES_DA_CORRENTE = ("AnimNext", "Enchimento", "MinFrameRate",
                     "MaxFrameRate")

# Tamanhos aceitos para o quadro: o Unreal 2 exige potencia de dois.
TAMANHOS = (128, 256, 512, 1024)

# Acima disto o aviso deixa de ser teorico -- o cliente e de 32 bits e a
# corrente inteira fica na memoria de textura enquanto estiver na tela.
LIMITE_DE_MEMORIA = 64 * 1024 * 1024

# O indice do quadro seguinte e gravado como indice compacto do Unreal. Ate 63
# ele cabe num byte so, que e o que permite escrever no lugar sem mexer no
# tamanho do objeto. Acima disso precisaria de dois bytes e o arquivo teria de
# ser refeito -- por isso o limite de quadros.
MAXIMO_DE_QUADROS = 48

EXTENSOES_DE_VIDEO = (".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".m4v")
EXTENSOES_DE_IMAGEM = (".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp")


class ErroAnim(Exception):
    pass


# ---------------------------------------------------------------------------
# Indice compacto
# ---------------------------------------------------------------------------
def compacto(valor):
    """Codifica um inteiro no indice compacto do Unreal."""
    saida = bytearray()
    negativo = valor < 0
    valor = abs(valor)
    b = valor & 0x3F
    if negativo:
        b |= 0x80
    valor >>= 6
    if valor:
        b |= 0x40
    saida.append(b)
    while valor:
        c = valor & 0x7F
        valor >>= 7
        if valor:
            c |= 0x80
        saida.append(c)
    return bytes(saida)


def _descompacto(dados, pos):
    b = dados[pos]
    pos += 1
    negativo = b & 0x80
    valor = b & 0x3F
    if b & 0x40:
        deslocamento = 6
        while True:
            c = dados[pos]
            pos += 1
            valor |= (c & 0x7F) << deslocamento
            deslocamento += 7
            if not (c & 0x80):
                break
    return (-valor if negativo else valor), pos


# ---------------------------------------------------------------------------
# Propriedades marcadas
# ---------------------------------------------------------------------------
_TAMANHOS_FIXOS = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}
TIPO_OBJETO = 5


def propriedade_objeto(i_nome, valor):
    """
    Monta a propriedade marcada `<nome> = <objeto>` em bytes.

    Dois detalhes custaram um pacote inteiro aqui. O indice do nome vai em
    indice compacto -- escrever o numero cru so funciona enquanto ele for menor
    que 64. E o codigo de tamanho no byte de tipo tem de bater com o tamanho
    REAL do valor: num pacote grande o indice do export ocupa dois bytes, e
    declarar um so faz o motor ler a propriedade seguinte fora de lugar (o
    umodel diz "-1 unread bytes" e desiste da textura).
    """
    corpo = compacto(valor)
    codigo = {1: 0, 2: 1, 4: 2}.get(len(corpo))
    if codigo is None:                       # 3 ou 5 bytes: tamanho declarado
        cabeca = bytes([TIPO_OBJETO | (5 << 4), len(corpo)])
    else:
        cabeca = bytes([TIPO_OBJETO | (codigo << 4)])
    return compacto(i_nome) + cabeca + corpo


TIPO_FLOAT = 4
TAXA_PADRAO = 15.0      # quadros por segundo


def propriedade_float(i_nome, valor):
    """A propriedade marcada `<nome> = <float>`. Float ocupa sempre 4 bytes."""
    return (compacto(i_nome) + bytes([TIPO_FLOAT | (2 << 4)])
            + struct.pack("<f", float(valor)))


def ler_propriedades(dados, pos, nomes, limite):
    """
    A lista de propriedades marcadas de um objeto, ate o `None` que a fecha.

    Devolve [(nome, bytes crus)] e a posicao do fim. E deliberadamente literal:
    guarda os bytes de cada propriedade como estao, porque quem reescreve o
    bloco precisa devolver as que ficam sem alterar um bit.
    """
    achadas = []
    while pos < limite:
        comeco = pos
        i_nome, pos = _descompacto(dados, pos)
        nome = nomes[i_nome] if 0 <= i_nome < len(nomes) else "?%d" % i_nome
        if nome == "None":
            return achadas, pos

        info = dados[pos]
        pos += 1
        tipo = info & 0x0F
        codigo = (info >> 4) & 0x07

        if tipo == 10:                                  # STRUCT
            _i, pos = _descompacto(dados, pos)

        if codigo < 5:
            tamanho = _TAMANHOS_FIXOS[codigo]
        elif codigo == 5:
            tamanho = dados[pos]; pos += 1
        elif codigo == 6:
            tamanho = int.from_bytes(dados[pos:pos + 2], "little"); pos += 2
        else:
            tamanho = int.from_bytes(dados[pos:pos + 4], "little"); pos += 4

        if (info & 0x80) and tipo != 3:                 # indice do array
            _i, pos = _descompacto(dados, pos)

        pos += tamanho
        achadas.append((nome, bytes(dados[comeco:pos])))

    raise ErroAnim("a lista de propriedades nao terminou dentro do objeto")


# ---------------------------------------------------------------------------
# Mipmaps: o deslocamento que nao pode mentir
# ---------------------------------------------------------------------------
# Aqui mora a armadilha que derrubou o cliente com "Serial size mismatch".
#
# Os mipmaps de uma textura sao gravados em TLazyArray, e uma TLazyArray comeca
# com um INT que e a POSICAO NO ARQUIVO logo depois dos dados -- o motor pula
# para la quando nao quer carregar o bloco. E posicao ABSOLUTA, nao relativa ao
# objeto.
#
# Ou seja: mover um objeto de lugar sem mexer nesse numero deixa o arquivo com
# tabelas perfeitas e conteudo mentiroso. O umodel nem repara, porque le tudo
# em vez de pular; o cliente repara na hora, e o erro aparece numa textura
# qualquer que veio DEPOIS da que mudou -- nunca na que mudou. Foi por isso que
# custou a achar.
#
# A licao que ficou no formato do gravador: nao mover nada. O que muda vai para
# o fim do arquivo, e so esse objeto tem os seus saltos corrigidos.
#
# Cada mipmap e:  [INT salto][indice compacto: quantos bytes][bytes]
#                 [INT USize][INT VSize][BYTE UBits][BYTE VBits]
# e `salto` aponta para logo depois dos bytes -- dez antes do fim, no caso de
# uma textura de um mip so.
DEPOIS_DO_MIPMAP = 10           # USize, VSize, UBits, VBits


def posicoes_de_mipmap(dados, inicio, tamanho, fim_das_propriedades):
    """
    Onde estao os INT de salto desta textura, ou None se nao for uma.

    A conferencia e severa de proposito: a caminhada tem de bater o salto de
    cada mip e terminar exatamente no fim do objeto. Um palpite que "quase"
    fecha seria pior do que nao mexer.
    """
    fim = inicio + tamanho
    # A janela e generosa porque nem sempre o vetor vem logo depois das
    # propriedades: nas texturas do cliente ha quatro bytes antes, e num pacote
    # que o ucc montou inteiro a lista de propriedades vem VAZIA e os campos
    # viram bloco nativo -- 52 bytes antes do vetor. Procurar e barato; o que
    # decide e a caminhada, que so fecha no lugar certo.
    for comeco in range(fim_das_propriedades,
                        min(fim_das_propriedades + 160, fim)):
        pos = comeco
        try:
            quantos, pos = _descompacto(dados, pos)
        except (IndexError, ValueError):
            continue
        if not 1 <= quantos <= 32:
            continue

        posicoes, certo = [], True
        for _ in range(quantos):
            if pos + 4 > fim:
                certo = False
                break
            salto = int.from_bytes(dados[pos:pos + 4], "little")
            posicoes.append(pos)
            pos += 4
            try:
                quantidade, pos = _descompacto(dados, pos)
            except (IndexError, ValueError):
                certo = False
                break
            pos += quantidade
            if salto != pos or pos + DEPOIS_DO_MIPMAP > fim:
                certo = False
                break
            pos += DEPOIS_DO_MIPMAP
        if certo and pos == fim:
            return posicoes
    return None


def gravar_pacote(caminho, bruto, cabecalho, nomes, imports, tabela,
                  insercoes, nomes_mudaram):
    """
    Grava o pacote com `insercoes` aplicadas, sem mover mais nada.

    `insercoes` e {indice do export (1 a N): (posicao absoluta, bytes)}. Cada
    objeto tocado e recopiado para o FIM do arquivo, com os saltos de mipmap
    recalculados; a copia velha fica onde estava, como peso morto. Sai caro em
    bytes e sai barato em risco: todo objeto que nao foi pedido continua no
    endereco em que o proprio conteudo dele diz que esta.

    A tabela de nomes, quando cresce, tambem vai para o fim -- pelo mesmo
    motivo. O cabecalho diz onde ela esta, entao a posicao nao importa.
    """
    (assinatura, versao, licenciado, flags, _qtd_nomes, off_nomes,
     _qtd_exp, off_exp, _qtd_imp, off_imp) = cabecalho
    texto_dos_nomes = [n for n, _f in nomes]

    base = min(off_imp, off_exp)
    saida = bytearray(bruto[:base])     # cabecalho, nomes e objetos, intactos

    for indice in sorted(insercoes):
        campos = tabela[indice - 1]
        inicio, tamanho = campos["inicio"], campos["tamanho"]
        posicao, pedaco = insercoes[indice]

        _props, fim_props = ler_propriedades(bruto, inicio, texto_dos_nomes,
                                             inicio + tamanho)
        saltos = posicoes_de_mipmap(bruto, inicio, tamanho, fim_props)
        if saltos is None:
            raise ErroAnim(
                "nao reconheci os mipmaps de %s -- sem isso nao da para "
                "move-lo de lugar com seguranca."
                % texto_dos_nomes[campos["nome"]])

        corpo = bytearray(bruto[inicio:inicio + tamanho])
        corpo[posicao - inicio:posicao - inicio] = pedaco

        novo_inicio = len(saida)
        # Todo byte depois da insercao anda isto:
        andou = (novo_inicio - inicio) + len(pedaco)
        for p in saltos:
            dentro = p - inicio + len(pedaco)
            valor = int.from_bytes(corpo[dentro:dentro + 4], "little")
            corpo[dentro:dentro + 4] = (valor + andou).to_bytes(4, "little")

        campos["inicio"] = novo_inicio
        campos["tamanho"] = len(corpo)
        saida += corpo

    if nomes_mudaram:
        off_nomes = len(saida)
        for texto, f in nomes:
            saida += _escrever_nome(texto, f)

    novo_off_imp = len(saida)
    for campos in imports:
        saida += _escrever_import(campos)
    novo_off_exp = len(saida)
    for campos in tabela:
        saida += _escrever_export(campos)

    struct.pack_into(CABECALHO, saida, 0, assinatura, versao, licenciado,
                     flags, len(nomes), off_nomes, len(tabela), novo_off_exp,
                     len(imports), novo_off_imp)
    Path(caminho).write_bytes(bytes(saida))
    return len(saida)


def escrever_corrente(caminho, prefixo="quadro", ciclico=True, aolog=None):
    """
    Liga as texturas do pacote numa corrente de animacao, em ordem de nome.

    O arquivo e reescrito com o MESMO tamanho -- ver o cabecalho do modulo. As
    propriedades que ficam sao copiadas byte a byte; so o relogio sai.

    Devolve a lista de ligacoes feitas, como (quadro, proximo).
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    caminho = Path(caminho)
    conteudo = bytearray(caminho.read_bytes())

    pacote = l2npc.Pacote(caminho)
    try:
        nomes, dados = pacote.nomes, pacote.dados
        if "AnimNext" not in nomes:
            raise ErroAnim(
                "o pacote nao tem o nome 'AnimNext' na tabela de nomes. Ele "
                "precisa ser montado com nomes_extras=%r." % (NOMES_DA_CORRENTE,))
        i_anim = nomes.index("AnimNext")
        i_ench = nomes.index("Enchimento") if "Enchimento" in nomes else i_anim

        quadros = sorted(
            ((i, e) for i, e in enumerate(pacote.exports, 1)
             if str(e["nome"]).startswith(prefixo)),
            key=lambda par: str(par[1]["nome"]))
        if len(quadros) < 2:
            raise ErroAnim("achei %d quadro(s) com o prefixo %r -- preciso de "
                           "pelo menos dois." % (len(quadros), prefixo))
        if len(quadros) > MAXIMO_DE_QUADROS:
            raise ErroAnim("%d quadros e demais: acima de %d o indice do "
                           "proximo quadro deixa de caber num byte."
                           % (len(quadros), MAXIMO_DE_QUADROS))

        ligacoes = []
        for k, (indice, e) in enumerate(quadros):
            if k + 1 == len(quadros) and not ciclico:
                continue
            proximo_i, proximo_e = quadros[(k + 1) % len(quadros)]

            props, fim = ler_propriedades(dados, e["inicio"], nomes,
                                          e["inicio"] + e["tamanho"])
            total = fim - e["inicio"]

            novo = bytearray()
            for nome, cru in props:
                if nome in ("InternalTime", "AnimNext", "Enchimento"):
                    continue                    # relogio e sobras de outra vez
                novo += cru

            novo += propriedade_objeto(i_anim, proximo_i)

            sobra = total - len(novo) - 1                # -1 do None final
            if sobra < 0:
                raise ErroAnim("nao ha espaco no objeto %s para a corrente "
                               "(%d bytes a mais)." % (e["nome"], -sobra))
            if sobra:
                # Enchimento: propriedade que a classe Texture nao conhece,
                # entao o motor a pula pelo tamanho declarado. Cabecalho de 3
                # bytes; com sobra menor que isso, a lista so encurta e o resto
                # fica como estava.
                cabeca = compacto(i_ench) + bytes([0x01 | (5 << 4)])
                corpo = max(0, sobra - len(cabeca) - 1)
                novo += cabeca + bytes([corpo]) + b"\x00" * corpo
                novo = novo[:total - 1]
            novo += b"\x00"                              # None

            if len(novo) != total:
                raise ErroAnim("o bloco de %s mudou de tamanho (%d != %d)."
                               % (e["nome"], len(novo), total))

            conteudo[e["inicio"]:e["inicio"] + total] = novo
            ligacoes.append((str(e["nome"]), str(proximo_e["nome"])))
    finally:
        pacote.fechar()

    caminho.write_bytes(bytes(conteudo))
    anotar("corrente escrita: %d ligacoes, arquivo com os mesmos %d bytes"
           % (len(ligacoes), caminho.stat().st_size))
    return ligacoes


# ---------------------------------------------------------------------------
# Reescrever o pacote com a corrente
# ---------------------------------------------------------------------------
# O caminho acima -- escrever no lugar, sem mudar tamanho -- so funciona quando
# o ucc guarda as texturas com propriedades marcadas, e ele so faz isso em
# pacotes pequenos: medido, com tres quadros de 256 o bloco tem 53 bytes, e com
# oito ele ja vem com 1 byte, tudo nativo. Como o video util tem mais de tres
# quadros, o normal e precisar CRESCER o objeto.
#
# Crescer da certo porque o pacote tem esta ordem:
#
#     cabecalho (64) | tabela de nomes | dados dos objetos | imports | exports
#
# As tabelas de import e export ficam DEPOIS dos dados. Entao inserir bytes num
# objeto so empurra o que vem depois dele: as duas tabelas mudam de lugar (o
# cabecalho aponta para elas) e os deslocamentos dos objetos seguintes somam a
# diferenca. A tabela de exports e reescrita inteira de qualquer jeito, e como
# ela e a ultima, o tamanho dela nao afeta mais nada -- por isso uma passada
# basta, sem aquele vaivem de ajustar tamanho que muda o proprio tamanho.
CABECALHO = "<IHHIIIIIII"        # assinatura, versao, licenciado, flags,
                                 # nomes(qtd, off), exports(qtd, off),
                                 # imports(qtd, off)


def _ler_export(dados, pos):
    """Um registro da tabela de exports, com os campos crus."""
    campos = {}
    campos["classe"], pos = _descompacto(dados, pos)
    campos["mae"], pos = _descompacto(dados, pos)
    campos["dono"] = int.from_bytes(dados[pos:pos + 4], "little", signed=True)
    pos += 4
    campos["nome"], pos = _descompacto(dados, pos)
    campos["flags"] = int.from_bytes(dados[pos:pos + 4], "little")
    pos += 4
    campos["tamanho"], pos = _descompacto(dados, pos)
    campos["inicio"] = 0
    if campos["tamanho"] > 0:
        campos["inicio"], pos = _descompacto(dados, pos)
    return campos, pos


def _escrever_export(campos):
    saida = bytearray()
    saida += compacto(campos["classe"])
    saida += compacto(campos["mae"])
    saida += int(campos["dono"]).to_bytes(4, "little", signed=True)
    saida += compacto(campos["nome"])
    saida += int(campos["flags"]).to_bytes(4, "little")
    saida += compacto(campos["tamanho"])
    if campos["tamanho"] > 0:
        saida += compacto(campos["inicio"])
    return bytes(saida)


def reescrever_com_corrente(caminho, prefixo="quadro", ciclico=True, aolog=None,
                            ordem=None, taxa=TAXA_PADRAO):
    """
    Refaz o pacote acrescentando a propriedade AnimNext em cada quadro.

    Diferente de `escrever_corrente`, aqui o objeto PODE crescer -- e o que
    permite animar pacotes de qualquer tamanho. Quem cresce vai para o fim do
    arquivo, com os saltos de mipmap refeitos; ver `gravar_pacote`. Devolve a
    lista de ligacoes.

    `ordem` e a sequencia de nomes de textura a ligar, do primeiro ao ultimo.
    Serve para o caso que importa de verdade: o primeiro quadro tem de ser a
    textura que o mapa ja pede pelo nome, e so os demais e que sao nossos.
    Sem `ordem`, liga todas as que comecarem com `prefixo`, em ordem de nome.

    `taxa` e a velocidade em quadros por segundo. Sem ela o motor herda o
    padrao da classe, que e zero -- e ai ou a corrente nao anda, ou anda um
    quadro por quadro desenhado, que num video de oito quadros vira um piscar.
    As texturas animadas do proprio cliente trazem 20 aqui.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    caminho = Path(caminho)
    bruto = bytearray(caminho.read_bytes())

    (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
     qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(CABECALHO, bruto)
    if assinatura != 0x9E2A83C1:
        raise ErroAnim("%s nao e um pacote Unreal." % caminho.name)

    pacote = l2npc.Pacote(caminho)
    try:
        nomes = list(pacote.nomes)
        if "AnimNext" not in nomes:
            raise ErroAnim("o pacote nao tem 'AnimNext' na tabela de nomes; "
                           "monte com nomes_extras=%r." % (NOMES_DA_CORRENTE,))
        i_anim = nomes.index("AnimNext")
        faltando = [n for n in ("MinFrameRate", "MaxFrameRate")
                    if n not in nomes]
        if taxa and faltando:
            raise ErroAnim("o pacote nao tem os nomes %s; monte com "
                           "nomes_extras=%r." % (", ".join(faltando),
                                                 NOMES_DA_CORRENTE))
        i_min = nomes.index("MinFrameRate") if taxa else 0
        i_max = nomes.index("MaxFrameRate") if taxa else 0
        exports_lidos = list(pacote.exports)

        # Onde acaba a lista de propriedades de cada quadro, lido AGORA: o
        # `dados` do pacote e um mmap, e ele morre quando o pacote fecha.
        def eh_quadro(nome):
            return (nome in ordem) if ordem else nome.startswith(prefixo)

        fins = {}
        for i, e in enumerate(pacote.exports, 1):
            if eh_quadro(str(e["nome"])) and e["tamanho"]:
                props, fim = ler_propriedades(pacote.dados, e["inicio"], nomes,
                                              e["inicio"] + e["tamanho"])
                if any(nome == "AnimNext" for nome, _ in props):
                    raise ErroAnim("%s ja tem AnimNext." % e["nome"])
                fins[i] = fim
    finally:
        pacote.fechar()

    # ---- a tabela de exports, crua ----
    tabela, pos = [], off_exp
    for _ in range(qtd_exp):
        campos, pos = _ler_export(bruto, pos)
        tabela.append(campos)
    fim_tabela = pos
    if fim_tabela > len(bruto):
        raise ErroAnim("a tabela de exports passa do fim do arquivo.")

    if ordem:
        por_nome = {str(e["nome"]): (i, e)
                    for i, e in enumerate(exports_lidos, 1)}
        faltando = [n for n in ordem if n not in por_nome]
        if faltando:
            raise ErroAnim("estas texturas nao estao no pacote: %s"
                           % ", ".join(faltando))
        quadros = [por_nome[n] for n in ordem]
    else:
        quadros = sorted(
            ((i, e) for i, e in enumerate(exports_lidos, 1)
             if str(e["nome"]).startswith(prefixo)),
            key=lambda par: str(par[1]["nome"]))
    if len(quadros) < 2:
        raise ErroAnim("preciso de pelo menos dois quadros; achei %d."
                       % len(quadros))

    # ---- o que inserir em cada quadro, e onde ----
    insercoes = {}          # indice do export -> (posicao no arquivo, bytes)
    ligacoes = []
    for k, (indice, e) in enumerate(quadros):
        if k + 1 == len(quadros) and not ciclico:
            continue
        proximo_i, proximo_e = quadros[(k + 1) % len(quadros)]

        # A propriedade entra antes do None que fecha a lista -- ou seja, no
        # ultimo byte do bloco.
        posicao = fins[indice] - 1
        pedaco = propriedade_objeto(i_anim, proximo_i)
        if taxa:
            pedaco += (propriedade_float(i_min, taxa)
                       + propriedade_float(i_max, taxa))
        insercoes[indice] = (posicao, pedaco)
        ligacoes.append((str(e["nome"]), str(proximo_e["nome"])))

    # ---- grava ----
    imports, pos = [], off_imp
    for _ in range(qtd_imp):
        campos, pos = _ler_import(bruto, pos)
        imports.append(campos)

    tamanho = gravar_pacote(
        caminho, bruto,
        (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
         qtd_exp, off_exp, qtd_imp, off_imp),
        [(n, 0) for n in nomes], imports, tabela, insercoes,
        nomes_mudaram=False)
    anotar("pacote refeito: %d ligacoes, %d -> %d bytes"
           % (len(ligacoes), len(bruto), tamanho))
    return ligacoes


# ---------------------------------------------------------------------------
# Ligar uma textura de OUTRO pacote a corrente
# ---------------------------------------------------------------------------
# Por que isto existe: o cenario do lobby nao esta no mapa nem num .utx. O
# Lobby.unr desenha malhas que moram no o pacote de cenario do lobby, e a pele de cada
# malha -- inclusive o ceu, que e a maior superficie da tela -- e uma textura
# guardada dentro do proprio .usx. Remontar um .usx de 48 MB com o ucc esta
# fora de alcance: ele tem malha junto, e o ucc nao devolve malha do jeito que
# ela saiu.
#
# Mas nao e preciso remontar nada. Basta que a textura do ceu ganhe um
# `AnimNext` apontando para FORA do pacote: os quadros ficam num .utx nosso, e
# o .usx so ganha duas linhas na tabela de importacao (o pacote e o primeiro
# quadro) mais a propriedade na textura. Dali em diante a corrente roda inteira
# dentro do nosso arquivo, em ciclo.
#
# Referencia de objeto no Unreal 2: positivo e indice de export, negativo e
# -(indice de import), zero e nulo. Por isso o alvo aqui e um numero negativo.
def _ler_nomes_cru(bruto, pos, quantos):
    """[(nome, flags)] e a posicao logo depois da tabela."""
    itens = []
    for _ in range(quantos):
        tam, pos = _descompacto(bruto, pos)
        nome = bytes(bruto[pos:pos + tam - 1]).decode("latin-1")
        pos += tam
        flags = int.from_bytes(bruto[pos:pos + 4], "little")
        pos += 4
        itens.append((nome, flags))
    if itens:
        itens[0] = ("None", itens[0][1])
    return itens, pos


def _escrever_nome(nome, flags):
    cru = nome.encode("latin-1") + b"\x00"
    return compacto(len(cru)) + cru + int(flags).to_bytes(4, "little")


def _ler_import(bruto, pos):
    campos = {}
    campos["pacote_classe"], pos = _descompacto(bruto, pos)
    campos["classe"], pos = _descompacto(bruto, pos)
    campos["dono"] = int.from_bytes(bruto[pos:pos + 4], "little", signed=True)
    pos += 4
    campos["nome"], pos = _descompacto(bruto, pos)
    return campos, pos


def _escrever_import(campos):
    return (compacto(campos["pacote_classe"]) + compacto(campos["classe"])
            + int(campos["dono"]).to_bytes(4, "little", signed=True)
            + compacto(campos["nome"]))


def ligar_para_pacote(caminho, textura, pacote_novo, quadro, aolog=None,
                      grupo=None, taxa=TAXA_PADRAO):
    """
    Faz `textura` (deste pacote) apontar para `pacote_novo.quadro`.

    Serve para .usx e .unr tanto quanto para .utx: nada aqui passa pelo ucc --
    o arquivo e reescrito como esta, com nomes e importacoes a mais.

    Nada e empurrado de lugar: a tabela de nomes maior e o objeto alterado vao
    para o fim do arquivo, e o cabecalho passa a apontar para la. Isso nao e
    economia, e necessidade -- ver o comentario de `gravar_pacote`.

    Devolve o endereco completo do alvo.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    caminho = Path(caminho)
    bruto = bytearray(caminho.read_bytes())
    (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
     qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(CABECALHO, bruto)
    if assinatura != 0x9E2A83C1:
        raise ErroAnim("%s nao e um pacote Unreal." % caminho.name)

    nomes, fim_nomes = _ler_nomes_cru(bruto, off_nomes, qtd_nomes)
    lista_nomes = [n for n, _f in nomes]

    imports, pos = [], off_imp
    for _ in range(qtd_imp):
        campos, pos = _ler_import(bruto, pos)
        imports.append(campos)

    tabela, pos = [], off_exp
    for _ in range(qtd_exp):
        campos, pos = _ler_export(bruto, pos)
        tabela.append(campos)

    # ---- qual export e a textura ----
    def nome_de(i):
        return lista_nomes[i] if 0 <= i < len(lista_nomes) else "?"

    candidatos = [(i, c) for i, c in enumerate(tabela, 1)
                  if nome_de(c["nome"]).lower() == textura.lower()]
    if not candidatos:
        raise ErroAnim("nao achei a textura %r em %s."
                       % (textura, caminho.name))
    if len(candidatos) > 1 and grupo:
        curto = grupo.split(".")[-1].lower()
        iguais = [(i, c) for i, c in candidatos
                  if c["dono"] > 0
                  and nome_de(tabela[c["dono"] - 1]["nome"]).lower() == curto]
        candidatos = iguais or candidatos
    indice_alvo, alvo = candidatos[0]
    if not alvo["tamanho"]:
        raise ErroAnim("a textura %r nao tem dados neste pacote." % textura)

    # ---- os nomes que faltam ----
    flags_padrao = nomes[min(1, len(nomes) - 1)][1]
    indice_de = {}

    def nome(texto):
        if texto in indice_de:
            return indice_de[texto]
        for i, n in enumerate(lista_nomes):
            if n == texto:
                indice_de[texto] = i
                return i
        lista_nomes.append(texto)
        nomes.append((texto, flags_padrao))
        indice_de[texto] = len(lista_nomes) - 1
        return indice_de[texto]

    i_anim = nome("AnimNext")
    i_min, i_max = nome("MinFrameRate"), nome("MaxFrameRate")
    i_core, i_pacote_classe = nome("Core"), nome("Package")
    i_engine, i_textura_classe = nome("Engine"), nome("Texture")
    i_novo, i_quadro = nome(pacote_novo), nome(quadro)

    # ---- as duas importacoes ----
    imports.append({"pacote_classe": i_core, "classe": i_pacote_classe,
                    "dono": 0, "nome": i_novo})
    indice_pacote = len(imports)
    imports.append({"pacote_classe": i_engine, "classe": i_textura_classe,
                    "dono": -indice_pacote, "nome": i_quadro})
    indice_quadro = len(imports)

    # ---- onde a propriedade entra ----
    props, fim_props = ler_propriedades(bruto, alvo["inicio"], lista_nomes,
                                        alvo["inicio"] + alvo["tamanho"])
    if any(n == "AnimNext" for n, _c in props):
        raise ErroAnim("%s ja tem AnimNext -- restaure o arquivo original "
                       "antes de refazer." % textura)
    pedaco = propriedade_objeto(i_anim, -indice_quadro)
    # A velocidade tambem vai aqui: a textura do cliente e o primeiro elo da
    # corrente, e quem manda no passo e o elo que esta na tela.
    gravadas = {n for n, _c in props}
    if taxa and "MinFrameRate" not in gravadas:
        pedaco += propriedade_float(i_min, taxa)
    if taxa and "MaxFrameRate" not in gravadas:
        pedaco += propriedade_float(i_max, taxa)

    # ---- grava ----
    tamanho = gravar_pacote(
        caminho, bruto,
        (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
         qtd_exp, off_exp, qtd_imp, off_imp),
        nomes, imports, tabela,
        {indice_alvo: (fim_props - 1, pedaco)},   # antes do None que fecha
        nomes_mudaram=True)

    completo = "%s.%s" % (pacote_novo, quadro)
    anotar("%s: %s passou a apontar para %s (%d -> %d bytes)"
           % (caminho.name, textura, completo, len(bruto), tamanho))
    return completo


def conferir_corrente(T, caminho, objeto=None):
    """
    Pergunta ao umodel o que ele le. E a conferencia honesta: quem valida nao
    e o mesmo codigo que escreveu.

    Devolve {textura: proxima}. Repare que o pacote do cliente pode ja vir com
    correntes proprias -- o FX_E_T.utx tem sete --, entao contar quantas o
    umodel acha nao prova nada; quem confere tem de procurar as SUAS ligacoes,
    uma a uma.
    """
    caminho = Path(caminho)
    argumentos = [T["umodel"], "-dump", "-game=l2",
                  "-path=" + str(caminho.parent), caminho.name]
    if objeto:
        # Num pacote de 48 MB, despejar tudo leva minutos e enche o disco de
        # malha exportada. Com o nome, o umodel abre so aquele objeto.
        argumentos.append(objeto)
    _codigo, texto = motor.executar(argumentos, limite=600)

    atual, achados = objeto, {}
    for linha in texto.split("\n"):
        m = re.search(r"ObjectName:\s*(\S+)", linha)
        if m:
            atual = m.group(1)
        m = re.search(r"AnimNext\s*=\s*Texture'([^']+)'", linha)
        if m and atual:
            achados[atual] = m.group(1).split(".")[-1]
    return achados


# ---------------------------------------------------------------------------
# Animar uma textura que ja existe num pacote do cliente
# ---------------------------------------------------------------------------
# O primeiro quadro da corrente NAO e nosso: e a textura que o mapa do lobby ja
# pede pelo nome. Trocamos o conteudo dela pelo primeiro quadro do video e
# penduramos os demais atras. Assim o mapa nao muda uma virgula -- ele pede o
# mesmo `pacote.grupo.nome` de sempre, e o motor segue a corrente sozinho.
#
# E por isso que o grupo tem de ser preservado ao remontar: `pacote.grupo.nome`
# e o endereco inteiro, e trocar o grupo e mudar o endereco.
PREFIXO_DOS_QUADROS = "l2pt_quadro"


def grupos_do_pacote(T, caminho, trabalho):
    """
    {nome da textura: grupo} de um pacote -- o endereco de cada uma.

    O grupo e o objeto "dono" da textura na tabela de exports. Textura solta na
    raiz do pacote fica sem grupo, e ai o padrao do ucc serve.
    """
    pacote = l2npc.Pacote(caminho, ferramentas=T, temporario=trabalho)
    try:
        por_indice = {i: e for i, e in enumerate(pacote.exports, 1)}
        achados = {}
        for e in pacote.exports:
            dono = e.get("dono") or 0
            if dono > 0 and dono in por_indice:
                achados[str(e["nome"])] = str(por_indice[dono]["nome"])
        return achados
    finally:
        pacote.fechar()


def texturas_do_pacote(T, caminho, trabalho):
    """Nome, tamanho, formato e grupo de cada textura -- para a tela escolher."""
    inventario = motor.inventario(T, caminho)
    grupos = grupos_do_pacote(T, caminho, trabalho)
    saida = []
    for chave, dados in sorted(inventario.items()):
        nome = dados.get("nome", chave)
        saida.append({
            "nome": nome,
            "largura": int(dados.get("largura") or 0),
            "altura": int(dados.get("altura") or 0),
            "formato": (dados.get("formato") or "").replace("TEXF_", ""),
            "grupo": grupos.get(nome, ""),
            "alfa": bool(dados.get("alfa")),
        })
    return saida


def texturas_do_mapa(T, mapa, system, trabalho):
    """
    As texturas que o MAPA do lobby carrega, com o arquivo de cada uma.

    Esta e a lista que importa. Escolher pelo nome do pacote -- "tem lobby no
    nome, deve ser do lobby" -- parece razoavel e esta errado: neste cliente o
    Lobby.unr nao usa uma textura sequer de l2_lobby_t.utx nem de
    lobby_terrain_t.utx. Ele usa o pacote de cenario do lobby, FX_E_T.utx, T_texture.utx e
    mais tres. Animar textura que o mapa nao pede nao muda nada na tela, e o
    programa fica dizendo que deu certo.

    A tabela de imports do mapa diz a verdade: cada textura aparece la com o
    pacote e o grupo a que pertence. Devolve uma lista de dicionarios com
    `pacote` (o arquivo), `nome`, `grupo` e `suportado` -- este ultimo so diz
    se o arquivo foi encontrado no cliente.

    Cuidado com o que esta lista NAO tem: a pele das malhas. O ceu do lobby, a
    maior superficie da tela, e uma textura de dentro do o pacote de cenario do lobby
    referida pela propria malha do domo -- o mapa nunca a importa, e por isso
    ela nao aparece aqui. Quem quer a lista do que da para animar tem de somar
    a isto o conteudo dos pacotes citados; ver `pacotes_do_mapa`.
    """
    mapa, system = Path(mapa), Path(system)
    pacote = l2npc.Pacote(mapa, ferramentas=T, temporario=Path(trabalho))
    try:
        imps = pacote.imports

        def cadeia(imp):
            partes, atual, guarda = [str(imp["nome"])], imp["dono"], 0
            while atual < 0 and guarda < 8:
                pai = imps[-atual - 1]
                partes.append(str(pai["nome"]))
                atual, guarda = pai["dono"], guarda + 1
            return list(reversed(partes))

        caminhos = [cadeia(i) for i in imps if str(i["classe"]) == "Texture"]
    finally:
        pacote.fechar()

    # Onde mora cada pacote citado.
    raiz = system.parent
    arquivos = {}
    for pasta in raiz.iterdir():
        if not pasta.is_dir():
            continue
        for arquivo in pasta.iterdir():
            if arquivo.suffix.lower() in (".utx", ".usx", ".u"):
                arquivos.setdefault(arquivo.stem.lower(), arquivo)

    achados, vistos = [], set()
    for partes in caminhos:
        nome_pacote, nome = partes[0], partes[-1]
        grupo = ".".join(partes[1:-1])
        chave = (nome_pacote.lower(), nome.lower())
        if chave in vistos:
            continue
        vistos.add(chave)
        arquivo = arquivos.get(nome_pacote.lower())
        achados.append({
            "pacote": arquivo,
            "pacote_nome": nome_pacote,
            "nome": nome,
            "grupo": grupo,
            "suportado": bool(arquivo),
        })
    return achados


def pacotes_do_mapa(T, mapa, system, trabalho):
    """Os arquivos que o mapa do lobby usa, sem repetir e na ordem de uso."""
    vistos, arquivos = set(), []
    for item in texturas_do_mapa(T, mapa, system, trabalho):
        caminho = item["pacote"]
        if caminho and caminho not in vistos:
            vistos.add(caminho)
            arquivos.append(caminho)
    return arquivos


def animar_textura(T, pacote_origem, textura, quadros, trabalho, destino,
                   aoprogresso=None, aolog=None):
    """
    Refaz um pacote do cliente com UMA textura virando video.

    Tudo o mais do pacote volta como estava: mesmo nome, mesmo grupo, mesmo
    formato de cada textura. So a escolhida vira o primeiro quadro, e os outros
    quadros entram como texturas novas, penduradas na corrente.

    Devolve (arquivo criptografado, ligacoes).
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    pacote_origem = Path(pacote_origem)
    trabalho, destino = Path(trabalho), Path(destino)
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)
    destino.mkdir(parents=True, exist_ok=True)

    quadros = list(quadros)
    if len(quadros) < 2:
        raise ErroAnim("preciso de pelo menos dois quadros.")
    if len(quadros) > MAXIMO_DE_QUADROS:
        raise ErroAnim("%d quadros e demais (o maximo e %d)."
                       % (len(quadros), MAXIMO_DE_QUADROS))

    # ---- o pacote original, aberto e extraido ----
    anotar("abrindo %s..." % pacote_origem.name)
    claro, _obs = motor.descriptografar(T, pacote_origem, trabalho / "claro")
    inventario = motor.inventario(T, pacote_origem)
    grupos = grupos_do_pacote(T, pacote_origem, trabalho / "claro")

    imagens, _log = motor.extrair(T, claro, trabalho / "extraido")
    if not imagens:
        raise ErroAnim("nao consegui extrair as texturas de %s."
                       % pacote_origem.name)
    pngs = motor.converter(imagens, trabalho / "png", ".png")
    anotar("%d texturas no pacote." % len(pngs))

    alvo = next((p for p in pngs if p.stem.lower() == textura.lower()), None)
    if alvo is None:
        raise ErroAnim("nao achei a textura %r no pacote. Ha: %s"
                       % (textura, ", ".join(sorted(p.stem for p in pngs))[:200]))

    # ---- o primeiro quadro toma o lugar da textura escolhida ----
    largura = int((inventario.get(alvo.stem.lower()) or {}).get("largura") or 0)
    altura = int((inventario.get(alvo.stem.lower()) or {}).get("altura") or 0)
    lado = max(largura, altura) or 256
    from PIL import Image as _Image
    with _Image.open(quadros[0]) as primeiro:
        _encaixar(primeiro.convert("RGB"), lado).save(alvo)
    anotar("%s virou o primeiro quadro (%dx%d)." % (alvo.stem, lado, lado))

    # ---- os demais entram como texturas novas, no mesmo grupo ----
    #
    # TODA textura recebe grupo explicito, inclusive as que nao tem nenhum: sem
    # isso o padrao do `montar` ("Upscaled") entraria no lugar do vazio, e uma
    # textura que morava em `pacote.nome` passaria a morar em
    # `pacote.Upscaled.nome` -- endereco diferente, mapa sem achar.
    grupos = {imagem.stem: grupos.get(imagem.stem, "") for imagem in pngs}
    grupo = grupos.get(alvo.stem, "")
    entrada = list(pngs)
    nomes_em_ordem = [alvo.stem]
    for i, quadro in enumerate(quadros[1:], 1):
        novo = trabalho / "png" / ("%s%02d.png" % (PREFIXO_DOS_QUADROS, i))
        with _Image.open(quadro) as im:
            _encaixar(im.convert("RGB"), lado).save(novo)
        entrada.append(novo)
        nomes_em_ordem.append(novo.stem)
        grupos[novo.stem] = grupo       # o mesmo da textura que eles animam

    # ---- cada uma no formato que ela tinha ----
    #
    # Textura comprimida vai como DDS; textura CRUA (RGBA8, P8, L8) vai como
    # TGA. Nao e preferencia: o `ucc` recusa o DDS sem compressao que o texconv
    # produz -- "DDSD_LINEARSIZE flag is not set", e o import falha. Com TGA ele
    # importa e a textura sai RGBA8 do outro lado, que e o que se queria.
    formatos = dict(inventario)
    for nome in nomes_em_ordem[1:]:
        formatos[nome.lower()] = {"formato": "TEXF_DXT1"}

    comprimidas, cruas = [], []
    for imagem in entrada:
        formato = (formatos.get(imagem.stem.lower()) or {}).get("formato", "")
        (comprimidas if formato.startswith("TEXF_DXT") else cruas).append(imagem)

    anotar("%d texturas comprimidas, %d cruas." % (len(comprimidas), len(cruas)))
    prontas = []
    if comprimidas:
        prontas += motor.comprimir(T, comprimidas, trabalho / "dds",
                                   formatos=formatos, progresso=aoprogresso)
    if cruas:
        pasta_tga = trabalho / "tga"
        pasta_tga.mkdir(parents=True, exist_ok=True)
        for imagem in cruas:
            with _Image.open(imagem) as im:
                alvo_tga = pasta_tga / (imagem.stem + ".tga")
                im.convert("RGBA").save(alvo_tga)
            prontas.append(alvo_tga)

    dds = prontas
    if len(dds) < len(entrada):
        faltando = {p.stem.lower() for p in entrada} - {p.stem.lower() for p in dds}
        raise ErroAnim("nao consegui preparar estas texturas: %s"
                       % ", ".join(sorted(faltando))[:200])

    # ---- remonta com os grupos originais ----
    nome_pacote = pacote_origem.stem
    anotar("montando %s..." % pacote_origem.name)
    montado, _log = motor.montar(T, nome_pacote, dds,
                                 Path(T["ucc"]).parent.parent,
                                 nomes_extras=NOMES_DA_CORRENTE, grupos=grupos)
    if montado is None:
        # O log do compilador e a unica pista util quando ele recusa: sem
        # mostra-lo, o usuario fica com "nao montou" e mais nada.
        for linha in (_log or "").strip().split("\n")[-14:]:
            if linha.strip():
                anotar("    " + linha.strip())
        raise ErroAnim("o `ucc make` nao montou o pacote. Veja o andamento.")

    cru = trabalho / pacote_origem.name
    shutil.copy2(montado, cru)

    ligacoes = reescrever_com_corrente(cru, ordem=nomes_em_ordem, aolog=aolog)
    lidas = conferir_corrente(T, cru)
    achadas = [(a, b) for a, b in ligacoes if lidas.get(a) != b]
    if achadas:
        raise ErroAnim(
            "o umodel nao le %d das %d ligacoes que escrevi (%s) -- nao vou "
            "instalar isso."
            % (len(achadas), len(ligacoes),
               ", ".join("%s->%s" % par for par in achadas[:4])))
    anotar("conferido: o umodel le as %d ligacoes." % len(ligacoes))

    cifrado = l2npc.metodo_do_arquivo(pacote_origem) is not None
    arquivo, integro = motor.criptografar(T, cru, pacote_origem.name, destino,
                                          cifrado)
    if arquivo is None:
        raise ErroAnim("nao consegui gravar o pacote final.")
    anotar("%s pronto (%d bytes)%s"
           % (arquivo.name, arquivo.stat().st_size,
              "" if integro else "  [AVISO: ida e volta nao confere]"))
    return arquivo, ligacoes


PREFIXO_DE_FORA = "quadro"


def animar_de_fora(T, alvo, textura, quadros, trabalho, destino,
                   nome_pacote="L2PTVideo", grupo=None, aolog=None,
                   taxa=TAXA_PADRAO):
    """
    Poe video numa textura que mora num pacote que nao da para remontar.

    E o caminho do lobby de verdade. O ceu, o chao e a decoracao da tela de
    login deste cliente estao dentro do o pacote de cenario do lobby -- 48 MB de malha e
    textura no mesmo arquivo. O ucc nao devolve malha, entao remontar esta
    fora de questao; mas o arquivo nao precisa ser remontado, so reescrito.

    Saem dois arquivos: o `.utx` com os quadros, e o pacote alvo com duas
    importacoes e uma propriedade a mais. Nenhuma textura do alvo muda de
    conteudo, de grupo ou de endereco.

    Devolve (arquivo dos quadros, arquivo alvo, endereco do primeiro quadro).
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    alvo = Path(alvo)
    trabalho, destino = Path(trabalho), Path(destino)
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)
    destino.mkdir(parents=True, exist_ok=True)

    quadros = list(quadros)
    if len(quadros) < 2:
        raise ErroAnim("preciso de pelo menos dois quadros.")
    if len(quadros) > MAXIMO_DE_QUADROS:
        raise ErroAnim("%d quadros e demais (o maximo e %d)."
                       % (len(quadros), MAXIMO_DE_QUADROS))

    # Nomes proprios e previsiveis: o primeiro quadro vira o endereco que o
    # pacote alvo vai importar, entao ele nao pode depender do nome do arquivo
    # de video que o usuario escolheu.
    renomeados = []
    pasta = trabalho / "quadros"
    pasta.mkdir()
    for i, q in enumerate(quadros):
        novo = pasta / ("%s%02d%s" % (PREFIXO_DE_FORA, i, Path(q).suffix))
        shutil.copy2(q, novo)
        renomeados.append(novo)
    primeiro = renomeados[0].stem

    arquivo_quadros, ligacoes = montar_animacao(
        T, renomeados, nome_pacote, trabalho / "montagem", destino,
        aolog=aolog, grupo="",        # na raiz: o endereco fica pacote.nome
        taxa=taxa)

    # ---- o pacote alvo ----
    anotar("abrindo %s..." % alvo.name)
    metodo = l2npc.metodo_do_arquivo(alvo)
    claro, _obs = motor.descriptografar(T, alvo, trabalho / "claro")
    cru = trabalho / alvo.name
    shutil.copy2(claro, cru)

    endereco = ligar_para_pacote(cru, textura, nome_pacote, primeiro,
                                 aolog=aolog, grupo=grupo, taxa=taxa)

    lidas = conferir_corrente(T, cru, objeto=textura)
    # O umodel devolve o nome com as maiusculas do pacote (lobby_sky_CT), e o
    # que veio da lista pode estar em outra caixa. Comparar cru dava "nao le".
    por_caixa = {k.lower(): v for k, v in lidas.items()}
    achado = por_caixa.get(textura.lower()) or por_caixa.get(primeiro.lower())
    if achado is None:
        raise ErroAnim("reescrevi %s mas o umodel nao le o AnimNext de %s -- "
                       "nao vou instalar isso." % (alvo.name, textura))
    anotar("conferido: o umodel le %s -> %s." % (textura, achado))

    arquivo_alvo, integro = motor.criptografar(
        T, cru, alvo.name, destino, metodo is not None, versao=metodo or "121")
    if arquivo_alvo is None:
        raise ErroAnim("nao consegui gravar %s." % alvo.name)
    anotar("%s pronto (%d bytes)%s"
           % (arquivo_alvo.name, arquivo_alvo.stat().st_size,
              "" if integro else "  [AVISO: ida e volta nao confere]"))
    return arquivo_quadros, arquivo_alvo, endereco


def instalar_pacote(arquivo, pasta_original, aolog=None):
    """Poe o pacote no cliente, guardando o que estava la em backup_lobby."""
    arquivo, pasta = Path(arquivo), Path(pasta_original)
    destino = pasta / arquivo.name
    if destino.exists():
        guarda = pasta / "backup_lobby"
        guarda.mkdir(exist_ok=True)
        import time as _time
        copia = guarda / ("%s_%s" % (_time.strftime("%Y%m%d_%H%M%S"),
                                     destino.name))
        shutil.copy2(destino, copia)
        if aolog:
            aolog("o %s que estava la foi para %s" % (destino.name, copia))
    shutil.copy2(arquivo, destino)
    if aolog:
        aolog("%s instalado em %s" % (destino.name, pasta))
    return destino


# ---------------------------------------------------------------------------
# Os quadros
# ---------------------------------------------------------------------------
def ffmpeg(T=None):
    """O ffmpeg, se houver: no config.ini, em ferramentas/ ou no PATH."""
    # is_file() e nao exists(): quando a busca automatica falha, o
    # carregar_config deixa no lugar a PASTA onde a ferramenta deveria estar, e
    # uma pasta "existe" -- executa-la daria um erro sem sentido nenhum.
    candidato = (T or {}).get("ffmpeg")
    if candidato and Path(candidato).is_file():
        return Path(candidato)
    achado = shutil.which("ffmpeg")
    if achado:
        return Path(achado)
    for raiz in (motor.BASE, motor.AQUI):
        for caminho in (raiz / motor.FERRAMENTAS_DIR).rglob("ffmpeg.exe"):
            return caminho
    return None


def contar_quadros(origem, T=None):
    """Quantos quadros a origem tem, sem extrair nada. None quando so o ffmpeg sabe."""
    origem = Path(origem)
    if origem.is_dir():
        return len([p for p in origem.iterdir()
                    if p.suffix.lower() in EXTENSOES_DE_IMAGEM])
    if origem.suffix.lower() in EXTENSOES_DE_VIDEO:
        return None
    if Image is None:
        raise ErroAnim("Pillow nao esta disponivel.")
    with Image.open(origem) as im:
        return getattr(im, "n_frames", 1)


def extrair_quadros(origem, destino, lado=256, maximo=16, T=None, aolog=None):
    """
    Poe os quadros em destino/, quadrados e no tamanho pedido.

    A imagem e ENCAIXADA, nao esticada: entra inteira, centralizada, com o
    resto preto. Esticar um video 16:9 num quadrado deformaria tudo, e o lobby
    e justamente onde o jogador fica olhando.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    if Image is None:
        raise ErroAnim("Pillow nao esta disponivel.")
    if lado not in TAMANHOS:
        raise ErroAnim("o lado do quadro tem de ser um de %s"
                       % ", ".join(str(x) for x in TAMANHOS))
    maximo = min(maximo, MAXIMO_DE_QUADROS)

    origem, destino = Path(origem), Path(destino)
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    bruto = destino / "_bruto"

    if origem.is_dir():
        brutos = sorted(p for p in origem.iterdir()
                        if p.suffix.lower() in EXTENSOES_DE_IMAGEM)
        anotar("pasta com %d imagens." % len(brutos))
    elif origem.suffix.lower() in EXTENSOES_DE_VIDEO:
        brutos = _do_video(origem, bruto, T, anotar)
    else:
        brutos = _da_animacao(origem, bruto, anotar)

    if not brutos:
        raise ErroAnim("nao consegui tirar quadro nenhum de %s" % origem.name)

    # Quadros demais: espacar ao longo da animacao preserva o movimento
    # inteiro; pegar os primeiros cortaria o video no meio.
    if len(brutos) > maximo:
        passo = len(brutos) / float(maximo)
        brutos = [brutos[int(i * passo)] for i in range(maximo)]
        anotar("reduzido para %d quadros, espacados ao longo do video." % maximo)

    saidas = []
    for i, arquivo in enumerate(brutos):
        with Image.open(arquivo) as im:
            quadro = im.convert("RGB")
        alvo = destino / ("quadro%02d.png" % i)
        _encaixar(quadro, lado).save(alvo)
        saidas.append(alvo)

    shutil.rmtree(bruto, ignore_errors=True)
    anotar("%d quadros de %dx%d prontos." % (len(saidas), lado, lado))
    return saidas


def _encaixar(imagem, lado):
    copia = imagem.copy()
    copia.thumbnail((lado, lado), Image.LANCZOS)
    fundo = Image.new("RGB", (lado, lado), (0, 0, 0))
    fundo.paste(copia, ((lado - copia.width) // 2, (lado - copia.height) // 2))
    return fundo


def _da_animacao(origem, destino, anotar):
    destino.mkdir(parents=True, exist_ok=True)
    saidas = []
    with Image.open(origem) as im:
        anotar("%s: %d quadros." % (origem.name, getattr(im, "n_frames", 1)))
        for i, quadro in enumerate(ImageSequence.Iterator(im)):
            alvo = destino / ("bruto%04d.png" % i)
            quadro.convert("RGB").save(alvo)
            saidas.append(alvo)
    return saidas


def _do_video(origem, destino, T, anotar):
    exe = ffmpeg(T)
    if exe is None:
        raise ErroAnim(
            "nao achei o ffmpeg, que e quem abre video. Ele acompanha o "
            "programa em ferramentas/ffmpeg/; se a pasta sumiu, aponte "
            "ffmpeg= na secao [ferramentas] do config.ini. Sem ele: converta "
            "o video para GIF e use o GIF.")
    destino.mkdir(parents=True, exist_ok=True)
    anotar("extraindo quadros com o ffmpeg...")
    padrao = str(destino / "bruto%04d.png")

    # Um arquivo por quadro do video, sem repetir nem descartar. O nome dessa
    # opcao mudou: ate a versao 8 era `-vsync 0`, e na 9 ela foi REMOVIDA
    # ("Unrecognized option 'vsync'"). Como o usuario pode ter qualquer uma das
    # duas, tenta a nova, depois a velha, e por fim sem nenhuma -- que tambem
    # extrai, so podendo repetir quadro em video de taxa variavel.
    for extra in (["-fps_mode", "passthrough"], ["-vsync", "0"], []):
        _codigo, texto = motor.executar(
            [exe, "-y", "-i", str(origem)] + extra + [padrao], limite=1800)
        saidas = sorted(destino.glob("bruto*.png"))
        if saidas:
            return saidas
        if ("Unrecognized option" not in texto
                and "Option not found" not in texto):
            # Falhou por outro motivo; trocar de opcao nao vai ajudar.
            ultimas = [l.strip() for l in texto.strip().split("\n")[-3:]]
            anotar("o ffmpeg nao extraiu: %s" % " / ".join(ultimas))
            break
    return []


# ---------------------------------------------------------------------------
# O pacote animado
# ---------------------------------------------------------------------------
def montar_animacao(T, quadros, nome, trabalho, destino, formato="DXT1",
                    aolog=None, grupo="Upscaled", taxa=TAXA_PADRAO):
    """
    Junta os quadros num .utx com a corrente ja escrita e criptografado.

    Devolve (arquivo, ligacoes). O caminho e o mesmo que a aba de texturas usa
    e que o cliente aceita: texconv comprime, `ucc make` monta, a corrente e
    escrita, l2encdec criptografa.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,30}", nome):
        raise ErroAnim("o nome do pacote deve comecar com letra e conter so "
                       "letras, numeros e _ (recebi %r)" % nome)

    trabalho, destino = Path(trabalho), Path(destino)
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)
    destino.mkdir(parents=True, exist_ok=True)

    quadros = list(quadros)
    anotar("comprimindo %d quadros em %s..." % (len(quadros), formato))
    dds = motor.comprimir(T, quadros, trabalho / "dds",
                          formatos={q.stem: {"formato": "TEXF_" + formato}
                                    for q in quadros})
    if not dds:
        raise ErroAnim("o texconv nao gerou DDS nenhum.")

    anotar("montando %s.utx..." % nome)
    pacote, _log = motor.montar(T, nome, dds, Path(T["ucc"]).parent.parent,
                                nomes_extras=NOMES_DA_CORRENTE,
                                grupos={q.stem: grupo for q in quadros})
    if pacote is None:
        raise ErroAnim("o `ucc make` nao montou o pacote. Veja o andamento.")

    cru = trabalho / (nome + ".utx")
    shutil.copy2(pacote, cru)
    # O reescritor serve sempre; o gravador no lugar so serve em pacote
    # pequeno. Ver o comentario de reescrever_com_corrente.
    ligacoes = reescrever_com_corrente(cru, aolog=aolog, taxa=taxa)

    lidas = conferir_corrente(T, cru)
    achadas = [(a, b) for a, b in ligacoes if lidas.get(a) != b]
    if achadas:
        raise ErroAnim(
            "o umodel nao le %d das %d ligacoes que escrevi (%s) -- nao vou "
            "instalar isso."
            % (len(achadas), len(ligacoes),
               ", ".join("%s->%s" % par for par in achadas[:4])))
    anotar("conferido: o umodel le as %d ligacoes." % len(ligacoes))

    arquivo, integro = motor.criptografar(T, cru, nome + ".utx", destino, True)
    if arquivo is None:
        raise ErroAnim("nao consegui criptografar o pacote.")
    anotar("%s pronto (%d bytes)%s"
           % (arquivo.name, arquivo.stat().st_size,
              "" if integro else "  [AVISO: ida e volta nao confere]"))
    return arquivo, ligacoes
