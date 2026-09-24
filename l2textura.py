#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trocar UMA textura dentro de um pacote, sem remontar o pacote.

Por que existe: o caminho normal -- extrair tudo, comprimir tudo, `ucc make`
-- tem dois defeitos que nao se contornam. O `ucc make` so sabe CRIAR pacote
do zero, entao mudar uma textura obriga a reconstruir todas; e o importador
dele so aceita DDS comprimido (`Format 0000 is not DXTn`), entao pacote de
interface, que costuma ser RGBA8 do inicio ao fim, nao volta de jeito
nenhum.

Aqui o pacote e editado no lugar, como o `l2mapa` faz com mapa compilado: o
corpo novo vai para o fim do arquivo, as tabelas sao reescritas e nada do que
ja existia se move. A textura continua no formato em que estava -- RGBA8
segue RGBA8.

O corpo de uma Texture, medido num pacote do cliente e nao suposto:

    [propriedades]  UBits, VBits, USize, VSize, UClamp, VClamp, Format...
    [prefixo]       bytes nativos que nao se mexe
    [quantos mips]  indice compacto
    para cada mip:
        [INT salto]     posicao ABSOLUTA do fim dos pixeis
        [compacto]      quantos bytes de pixel
        [pixeis]
        [INT USize][INT VSize][byte UBits][byte VBits]

O `salto` e uma TLazyArray: guarda posicao absoluta dentro do arquivo. Mudar
o tamanho de qualquer coisa antes dele sem recalcular corrompe o pacote em
silencio -- foi a pedra que ja derrubou este projeto uma vez, e por isso o
valor e escrito na gravacao, quando a posicao final do corpo e conhecida.
"""

import struct
from pathlib import Path

import l2anim
import l2mapa

# Os campos de tamanho aparecem em tres lugares e precisam concordar: na
# lista de propriedades, no rodape de cada mip, e -- indiretamente -- no
# tamanho dos pixeis.
PROPRIEDADES_DE_TAMANHO = ("USize", "VSize", "UClamp", "VClamp")
PROPRIEDADES_DE_BITS = ("UBits", "VBits")


class ErroDeTextura(Exception):
    pass


def _indice_do_nome(pacote, procurado):
    """O indice do nome, ou None. Ha pacote com `None` repetido na tabela."""
    for i, (texto, _flags) in enumerate(pacote["nomes"]):
        if texto == procurado:
            return i
    return None


def ler(pacote, indice):
    """
    Disseca o corpo de uma Texture.

    Nao depende de ler a lista de propriedades ate o fim: a tabela de nomes
    de alguns pacotes tem `None` em dois indices, e um leitor generico para
    no primeiro. O que se procura aqui e o primeiro `salto`, que e
    reconhecivel pelo valor -- ele aponta para dentro do proprio corpo.
    """
    campos = pacote["exports"][indice - 1]
    if not campos["tamanho"]:
        raise ErroDeTextura("o objeto %d nao tem corpo" % indice)
    dados = pacote["dados"]
    inicio = campos["inicio"]
    fim = inicio + campos["tamanho"]

    comeco, mips = _achar_os_mips(dados, inicio, fim)
    return {"indice": indice,
            "cabeca": bytes(dados[inicio:comeco]),   # tudo antes do 1o mip
            "mips": mips}


def _achar_os_mips(dados, inicio, fim):
    """
    Onde a lista de mips comeca, e o que ha nela.

    Nao se adivinha pelo valor de um INT: qualquer quatro bytes do cabecalho
    podem, por acaso, parecer uma posicao valida -- e foi o que aconteceu
    assim que a textura mudou de tamanho. Aqui se TENTA ler a lista inteira
    a partir de cada posicao possivel, e vale a que fecha exatamente no fim
    do corpo. Ou a leitura casa com o arquivo inteiro, ou nao e ela.
    """
    # Ate onde procurar o comeco. Eram 256 bytes, medidos em pacote de
    # servidor privado; num Icon.utx oficial do Kamael a lista de mips so
    # comeca no byte 1273, porque a lista de propriedades e bem maior. O
    # limite existe so para nao varrer megabytes a toa -- quem valida e a
    # leitura inteira, que tem de fechar exatamente no fim do corpo.
    ate = min(inicio + 8192, fim)
    for comeco in range(inicio, ate):
        lidos = _tentar_ler_mips(dados, comeco, fim)
        if lidos is not None:
            return comeco, lidos
    raise ErroDeTextura("nao entendi o corpo desta textura; o pacote pode "
                        "guardar textura noutro formato")


def _tentar_ler_mips(dados, comeco, fim):
    """A lista de mips a partir daqui, ou None se nao fechar no fim."""
    try:
        quantos, p = l2anim._descompacto(dados, comeco)
    except Exception:                               # noqa: BLE001
        return None
    if not 1 <= quantos <= 16:
        return None

    mips = []
    for _ in range(quantos):
        if p + 4 > fim:
            return None
        salto_em = p
        p += 4
        try:
            tamanho, p = l2anim._descompacto(dados, p)
        except Exception:                           # noqa: BLE001
            return None
        if tamanho <= 0 or p + tamanho + 10 > fim:
            return None
        pixeis_em = p
        p += tamanho
        largura, altura = struct.unpack_from("<ii", dados, p)
        p += 8
        bits_u, bits_v = dados[p], dados[p + 1]
        p += 2
        if not (0 < largura <= 8192 and 0 < altura <= 8192):
            return None
        if largura & (largura - 1) or altura & (altura - 1):
            return None                             # nao e potencia de dois
        mips.append({"salto_em": salto_em - comeco,
                     "pixeis": bytes(dados[pixeis_em:pixeis_em + tamanho]),
                     "largura": largura, "altura": altura,
                     "bits_u": bits_u, "bits_v": bits_v})
    return mips if p == fim else None


def trocar(pacote, indice, mips):
    """
    Poe outros pixeis na textura, mantendo o resto do corpo.

    `mips` e [{pixeis, largura, altura}] do maior para o menor. O corpo novo
    entra na fila do `l2mapa`, e o salto de cada mip fica pendente: so na
    gravacao se sabe onde o corpo vai cair.
    """
    if not mips:
        raise ErroDeTextura("nenhum mipmap para gravar")
    velha = ler(pacote, indice)

    # a cabeca vai como estava; a contagem de mips e escrita de novo, porque
    # pode mudar
    corpo = bytearray(velha["cabeca"]) + l2anim.compacto(len(mips))

    pendentes = []
    for mip in mips:
        largura, altura = int(mip["largura"]), int(mip["altura"])
        pixeis = mip["pixeis"]
        pendentes.append((len(corpo), None))        # onde o salto vai ficar
        corpo += b"\x00\x00\x00\x00"                # reservado
        corpo += l2anim.compacto(len(pixeis))
        corpo += pixeis
        pendentes[-1] = (pendentes[-1][0], len(corpo))
        corpo += struct.pack("<ii", largura, altura)
        corpo += bytes([_bits(largura), _bits(altura)])

    maior = mips[0]
    _acertar_tamanho_nas_propriedades(pacote, corpo, velha["cabeca"],
                                      int(maior["largura"]),
                                      int(maior["altura"]))

    l2mapa.substituir_corpo(pacote, indice, bytes(corpo))
    pacote.setdefault("saltos", {})[indice] = pendentes
    return {"mips": len(mips), "largura": maior["largura"],
            "altura": maior["altura"], "bytes": len(corpo)}


def _bits(medida):
    """log2 da medida, que e o que UBits e VBits guardam."""
    bits = 0
    while (1 << (bits + 1)) <= medida:
        bits += 1
    return bits


def _acertar_tamanho_nas_propriedades(pacote, corpo, cabeca, largura, altura):
    """
    USize, VSize, UClamp, VClamp, UBits e VBits, na lista de propriedades.

    Sao escritos no lugar, sem mover nada: o valor de um INT ocupa quatro
    bytes tanto para 64 quanto para 2048, e o de UBits, um. Assim a cabeca
    nao muda de tamanho e o resto do corpo continua valendo.
    """
    valores = {"USize": largura, "VSize": altura,
               "UClamp": largura, "VClamp": altura}
    bits = {"UBits": _bits(largura), "VBits": _bits(altura)}

    for nome, valor in list(valores.items()) + list(bits.items()):
        indice = _indice_do_nome(pacote, nome)
        if indice is None:
            continue
        marca = l2anim.compacto(indice)
        procurado = bytes(marca) + (b"\x22" if nome in valores else b"\x01")
        posicao = bytes(cabeca).find(procurado)
        if posicao < 0:
            continue
        campo = posicao + len(procurado)
        if nome in valores:
            struct.pack_into("<i", corpo, campo, valor)
        else:
            corpo[campo] = valor


def gravar(pacote, destino):
    """
    Grava o pacote, acertando o salto de cada mip.

    O `l2mapa.gravar` poe os corpos novos no fim do arquivo, e so entao a
    posicao absoluta existe -- por isso o salto e escrito aqui, e nao na
    hora de montar o corpo. Fora isso, faz o mesmo que ele: nada do que ja
    estava no arquivo se move.
    """
    destino = Path(destino)
    saida = bytearray(pacote["dados"])
    pendentes = pacote.get("saltos") or {}

    for indice, corpo in pacote["novos"]:
        posicao = len(saida)
        pacote["exports"][indice - 1]["inicio"] = posicao
        corpo = bytearray(corpo)
        for salto_em, fim_dos_pixeis in pendentes.get(indice, ()):
            struct.pack_into("<i", corpo, salto_em, posicao + fim_dos_pixeis)
        saida += corpo

    off_nomes = len(saida)
    for texto, flags in pacote["nomes"]:
        saida += l2anim._escrever_nome(texto, flags)

    off_imp = len(saida)
    for campos in pacote["imports"]:
        saida += l2anim._escrever_import(campos)

    off_exp = len(saida)
    for campos in pacote["exports"]:
        saida += l2anim._escrever_export(campos)

    struct.pack_into("<6I", saida, 12,
                     len(pacote["nomes"]), off_nomes,
                     len(pacote["exports"]), off_exp,
                     len(pacote["imports"]), off_imp)
    l2mapa._acertar_geracoes(saida, len(pacote["nomes"]), len(pacote["exports"]))

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bytes(saida))
    return destino


def texturas(pacote):
    """[(indice, nome, largura, altura)] das texturas do pacote."""
    achadas = []
    for i, campos in enumerate(pacote["exports"], 1):
        if not campos["tamanho"]:
            continue
        if l2mapa.classe_do_export(pacote, i) != "Texture":
            continue
        try:
            info = ler(pacote, i)
        except ErroDeTextura:
            continue
        maior = info["mips"][0]
        achadas.append((i, l2mapa.nome(pacote, campos["nome"]),
                        maior["largura"], maior["altura"]))
    return achadas


# ---------------------------------------------------------------------------
# Do que a textura e feita, e como refaze-la
# ---------------------------------------------------------------------------
# Os numeros do enum de formato do motor Unreal. So estes aparecem em pacote
# de Lineage 2; o resto o programa recusa em vez de adivinhar.
FORMATOS = {0: "P8", 3: "DXT1", 4: "RGB8", 5: "RGBA8", 7: "DXT3", 8: "DXT5"}
BYTES_POR_PIXEL = {"RGBA8": 4, "RGB8": 3}
BLOCO = {"DXT1": 8, "DXT3": 16, "DXT5": 16}     # bytes por bloco de 4x4
PARA_TEXCONV = {"DXT1": "BC1_UNORM", "DXT3": "BC2_UNORM", "DXT5": "BC3_UNORM"}


def formato(pacote, indice):
    """
    O formato desta textura, lido da propriedade `Format` dela.

    Sem a propriedade, o formato e o padrao do motor -- P8 --, mas nenhum
    pacote de textura do jogo depende disso. Devolve o nome, ou None quando
    o numero nao e de um formato conhecido.
    """
    cabeca = ler(pacote, indice)["cabeca"]
    indice_do_nome = _indice_do_nome(pacote, "Format")
    if indice_do_nome is None:
        return None
    marca = bytes(l2anim.compacto(indice_do_nome)) + b"\x01"
    posicao = cabeca.find(marca)
    if posicao < 0:
        return None
    return FORMATOS.get(cabeca[posicao + len(marca)])


def tamanho_esperado(nome_do_formato, largura, altura):
    """Quantos bytes um mip deste tamanho ocupa, neste formato."""
    if nome_do_formato in BYTES_POR_PIXEL:
        return largura * altura * BYTES_POR_PIXEL[nome_do_formato]
    if nome_do_formato in BLOCO:
        colunas = max(1, (largura + 3) // 4)
        linhas = max(1, (altura + 3) // 4)
        return colunas * linhas * BLOCO[nome_do_formato]
    return None


def mips_da_imagem(T, imagem, nome_do_formato, quantos, trabalho):
    """
    A imagem virada em mipmaps, no formato em que a textura estava.

    `quantos` vem da textura antiga: um pacote que guarda so o nivel maior
    continua com um; um que guarda a cadeia inteira recebe a cadeia inteira,
    reduzida a partir da imagem nova.

    Precisa do texconv para os formatos DXT -- comprimir bloco a mao seria
    reescrever um compressor, e mal.
    """
    from PIL import Image

    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    niveis = []
    largura, altura = imagem.size
    for k in range(max(1, quantos)):
        if k:
            largura = max(1, largura // 2)
            altura = max(1, altura // 2)
        nivel = imagem if k == 0 else imagem.resize((largura, altura),
                                                    Image.LANCZOS)
        niveis.append((nivel, largura, altura))

    saida = []
    for k, (nivel, largura, altura) in enumerate(niveis):
        if nome_do_formato in BYTES_POR_PIXEL:
            ordem = "BGRA" if nome_do_formato == "RGBA8" else "BGR"
            saida.append({"pixeis": nivel.convert("RGBA").tobytes("raw", ordem),
                          "largura": largura, "altura": altura})
            continue
        if nome_do_formato not in PARA_TEXCONV:
            raise ErroDeTextura("nao sei escrever textura em %s"
                                % nome_do_formato)
        saida.append({"pixeis": _comprimir_um(T, nivel, nome_do_formato,
                                              trabalho, k),
                      "largura": largura, "altura": altura})
    return saida


def _comprimir_um(T, imagem, nome_do_formato, trabalho, nivel):
    """Os bytes DXT de um nivel, pelo texconv, sem o cabecalho do DDS."""
    import subprocess

    png = trabalho / ("nivel%d.png" % nivel)
    imagem.convert("RGBA").save(png)
    subprocess.run([str(T["texconv"]), "-nologo", "-y", "-m", "1",
                    "-f", PARA_TEXCONV[nome_do_formato],
                    "-o", str(trabalho), str(png)],
                   capture_output=True)
    dds = trabalho / (png.stem + ".DDS")
    if not dds.exists():
        dds = trabalho / (png.stem + ".dds")
    if not dds.exists():
        raise ErroDeTextura("o texconv nao gerou o DDS do nivel %d" % nivel)
    cru = dds.read_bytes()
    # 4 bytes de assinatura + 124 de cabecalho; DX10 acrescenta 20, e o
    # texconv so os escreve em formato que aqui nao se usa
    return cru[128:]


def aplicar(T, pacote, trocas, trabalho, aolog=None):
    """
    Poe as imagens novas no pacote, cada uma no formato em que estava.

    `trocas` e {nome da textura: caminho da imagem}. O que nao esta aqui nao
    e tocado -- e essa e a diferenca para o caminho antigo, que reescrevia o
    pacote inteiro por causa de uma textura.

    Devolve [(nome, largura, altura, formato)] do que foi trocado.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    from PIL import Image

    feitas = []
    for numero, (nome, caminho) in enumerate(sorted(trocas.items()), 1):
        indice = l2mapa.achar_export(pacote, nome)
        if not indice:
            anotar("%s: nao existe neste pacote" % nome)
            continue
        try:
            velha = ler(pacote, indice)
        except ErroDeTextura as erro:
            anotar("%s: %s" % (nome, erro))
            continue

        qual = formato(pacote, indice) or "RGBA8"
        quantos = len(velha["mips"])
        imagem = Image.open(caminho).convert("RGBA")
        novos = mips_da_imagem(T, imagem, qual,
                               quantos, Path(trabalho) / ("t%d" % numero))
        trocar(pacote, indice, novos)
        feitas.append((nome, imagem.width, imagem.height, qual))
        anotar("%s: %dx%d -> %dx%d, %s, %d mip%s"
               % (nome, velha["mips"][0]["largura"],
                  velha["mips"][0]["altura"], imagem.width, imagem.height,
                  qual, quantos, "" if quantos == 1 else "s"))
    return feitas
