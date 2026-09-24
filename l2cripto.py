#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A criptografia do cliente do Lineage 2, feita aqui dentro.

## Por que não depender do l2encdec

Ele é um executável de terceiro que nem sempre está instalado, às vezes é
barrado pelo antivírus, e descarta os últimos bytes de todo arquivo achando
que são assinatura -- o que já fez pacote bom parecer quebrado. Tendo os
formatos aqui, o programa abre e grava sozinho, e o l2encdec passa a ser
reserva em vez de dependência.

E há a razão que importa: o l2encdec tem UMA chave, a mesma para todo mundo.
Arquivo fechado com ela é aberto por qualquer pessoa que tenha o programa.
Aqui a chave é derivada de uma frase que só o dono sabe, e a frase não é
guardada em lugar nenhum -- nem no programa, nem no arquivo de configuração,
nem no cliente.

## O que a chave própria protege

A ESCRITA: sem a frase, ninguém gera arquivo que o cliente daquele servidor
aceite.

A LEITURA não, e nenhum esquema do lado do cliente protege. Para jogar, o
cliente precisa abrir os arquivos, e por isso carrega dentro de si o que
precisa para abri-los. Quem tem o cliente pode chegar lá. O que a chave
própria faz é tirar o servidor da lista dos que se abrem com um clique em
ferramenta pública.

## O que há aqui

`abrir` e `fechar` cuidam dos formatos do cliente pelo cabeçalho do arquivo;
`par_da_frase` deriva a chave; `chave_do_cliente` e `trocar_chave_do_cliente`
leem e escrevem a chave que o executável guarda, onde ele a guarda em texto.

Tudo o que este módulo grava passa por ida e volta antes de substituir
qualquer coisa -- ver `l2protecao`, que é quem orquestra isso.
"""


import hashlib
import re
import struct
import zlib
from pathlib import Path

CABECALHO = 28                  # "Lineage2VerNNN" em UTF-16LE
BLOCO = 128                     # 1024 bits de RSA
FATIA = 124                     # o que cabe de dados num bloco
RABO = 20                       # os bytes de fecho, em claro
CHAVE_111 = 0xAC

# Os metodos que este modulo faz sozinho. O resto continua com o l2encdec.
NATIVOS = ("111", "120", "121", "411", "412", "413", "414")
SO_XOR = ("111", "120", "121")


class ErroDeCripto(Exception):
    pass


# ---------------------------------------------------------------------------
# O cabecalho
# ---------------------------------------------------------------------------
def metodo(dados_ou_caminho):
    """O numero do metodo ("413"), ou None se o arquivo nao for cifrado."""
    dados = (dados_ou_caminho if isinstance(dados_ou_caminho, (bytes, bytearray))
             else Path(dados_ou_caminho).read_bytes()[:CABECALHO])
    if len(dados) < CABECALHO:
        return None
    try:
        rotulo = bytes(dados[:CABECALHO]).decode("utf-16-le")
    except UnicodeDecodeError:
        return None
    casou = re.fullmatch(r"Lineage2Ver(\d{3})", rotulo)
    return casou.group(1) if casou else None


def cabecalho_de(met):
    return ("Lineage2Ver%s" % met).encode("utf-16-le")


# ---------------------------------------------------------------------------
# O rabo
# ---------------------------------------------------------------------------
def _rabo(conteudo, modelo=None):
    """
    Os 20 bytes de fecho: dois numeros do original e o CRC32 do que veio antes.

    Quando ha um arquivo de origem, os dois numeros vem dele -- copiar o que o
    cliente ja aceitava custa nada e evita descobrir do jeito ruim que ele
    olhava para algum deles.
    """
    a, b = (0, 0)
    if modelo and len(modelo) >= RABO:
        a, b = struct.unpack_from("<II", bytes(modelo), 4)
    return struct.pack("<IIIII", 0, a, b,
                       zlib.crc32(conteudo) & 0xFFFFFFFF, 0)


def conferir_rabo(dados):
    """(tem rabo, o CRC bate?) -- o rabo e opcional, e ha arquivo sem ele."""
    if len(dados) < RABO:
        return False, False
    rabo = dados[-RABO:]
    zeros = struct.unpack_from("<I", rabo, 0)[0] == 0 and \
        struct.unpack_from("<I", rabo, 16)[0] == 0
    if not zeros:
        return False, False
    esperado = struct.unpack_from("<I", rabo, 12)[0]
    return True, (zlib.crc32(dados[:-RABO]) & 0xFFFFFFFF) == esperado


# ---------------------------------------------------------------------------
# XOR: 111, 120, 121
# ---------------------------------------------------------------------------
def chave_xor(met, nome_do_arquivo):
    """
    O byte que abre um arquivo XOR.

    Num dos formatos ela e constante; no outro sai do NOME do arquivo, e por
    isso renomear um desses o torna ilegivel -- o programa avisa quando isso
    acontece.
    """
    if met == "111":
        return CHAVE_111
    nome = Path(nome_do_arquivo).name.lower().encode("latin-1", "ignore")
    return sum(nome) & 0xFF


def abrir_xor(dados, met, nome_do_arquivo, com_rabo=None):
    """
    Devolve (conteudo, rabo). `com_rabo` força a decisão quando ela importa.

    Sem forçar, o rabo é reconhecido pelo formato: quatro zeros na frente,
    quatro no fim e o CRC batendo. Arquivo sem rabo entrega tudo como
    conteúdo -- que é o caso que fazia o l2encdec cortar 20 bytes bons.
    """
    corpo = bytes(dados)[CABECALHO:]
    chave = chave_xor(met, nome_do_arquivo)
    aberto = bytes(b ^ chave for b in corpo)
    tem, bate = conferir_rabo(bytes(dados))
    usa_rabo = tem and bate if com_rabo is None else com_rabo
    if usa_rabo:
        return aberto[:-RABO], bytes(dados)[-RABO:]
    return aberto, b""


def fechar_xor(conteudo, met, nome_do_arquivo, rabo_modelo=None):
    """O arquivo inteiro: cabeçalho, conteúdo cifrado e rabo com o CRC novo."""
    chave = chave_xor(met, nome_do_arquivo)
    saida = bytearray(cabecalho_de(met))
    saida += bytes(b ^ chave for b in conteudo)
    saida += _rabo(bytes(saida), rabo_modelo)
    return bytes(saida)


# ---------------------------------------------------------------------------
# RSA: 411 a 414
# ---------------------------------------------------------------------------
def expoente_que_abre(dados, modulo, candidatos=None):
    """
    Qual expoente publico abre este arquivo com este modulo.

    Nao se escolhe por cronica: o Ver412 do C3 abre com 0x25 e o Ver413 do C5
    nao, e essa lista muda de cliente para cliente. Tenta-se, e vale o que
    produzir um primeiro bloco com tamanho declarado plausivel -- o mesmo
    criterio que separa chave certa de chave errada.
    """
    corpo = bytes(dados)[CABECALHO:]
    if len(corpo) < BLOCO:
        return None
    primeiro = int.from_bytes(corpo[:BLOCO], "big")
    for expoente in (candidatos or EXPOENTES_CONHECIDOS):
        claro = pow(primeiro, expoente, modulo).to_bytes(BLOCO, "big")
        tamanho = struct.unpack_from(">I", claro, 0)[0]
        if 0 < tamanho <= FATIA:
            return expoente
    return None


def abrir_41x(dados, modulo, expoente):
    """
    Devolve (conteudo, rabo) de um arquivo 41x.

    O expoente aqui e o PUBLICO -- o mesmo que o cliente usa para ler. Foi
    assim que este modulo foi conferido: lendo com a chave que estava dentro
    do L2.exe e comparando com o que o l2encdec devolve.
    """
    corpo = bytes(dados)[CABECALHO:]
    quantos = len(corpo) // BLOCO
    if not quantos:
        raise ErroDeCripto("o corpo não tem nem um bloco de 128 bytes.")

    fatias = []
    for i in range(quantos):
        cifrado = int.from_bytes(corpo[i * BLOCO:(i + 1) * BLOCO], "big")
        claro = pow(cifrado, expoente, modulo).to_bytes(BLOCO, "big")
        tamanho = struct.unpack_from(">I", claro, 0)[0]
        if not 0 < tamanho <= FATIA:
            raise ErroDeCripto(
                "bloco %d declara %d bytes, o que não cabe: a chave usada não "
                "é a deste arquivo." % (i, tamanho))
        # O pedaco de dados fica encostado no fim do bloco, e o enchimento
        # vem depois dos dados dentro dele: por isso nao basta pegar os
        # ultimos bytes declarados -- isso pegaria o enchimento e perderia o
        # comeco.
        largura = (tamanho + 3) & ~3
        comeco = BLOCO - largura
        fatias.append(claro[comeco:comeco + tamanho])

    fluxo = b"".join(fatias)
    if len(fluxo) < 4:
        raise ErroDeCripto("o fluxo saiu curto demais para ter tamanho.")
    aberto = struct.unpack_from("<I", fluxo, 0)[0]
    # `max_length` porque o fim do fluxo leva zeros de enchimento: parar no
    # tamanho declarado e o que o cliente faz, e e o que evita o falso erro
    # "incorrect data check" no ultimo pedaco.
    try:
        conteudo = zlib.decompressobj().decompress(fluxo[4:], aberto or 1)
    except zlib.error as erro:
        raise ErroDeCripto("o zlib recusou o fluxo: %s" % erro)
    if aberto and len(conteudo) != aberto:
        raise ErroDeCripto("o arquivo diz %d bytes e saíram %d."
                           % (aberto, len(conteudo)))
    return conteudo, bytes(dados)[quantos * BLOCO + CABECALHO:]


def fechar_41x(conteudo, modulo, expoente_privado, met="413",
               rabo_modelo=None, nivel=9):
    """
    Monta um 41x com a chave dada. `expoente_privado` e o que sela.

    O arranjo dos blocos segue o do proprio cliente, conferido contra
    arquivos que ele aceita -- e a unica forma de o jogo ler o que sai daqui.
    """
    comprimido = zlib.compress(bytes(conteudo), nivel)
    fluxo = struct.pack("<I", len(conteudo)) + comprimido
    sobra = (-len(fluxo)) % 4
    cheio = fluxo + b"\x00" * sobra

    saida = bytearray(cabecalho_de(met))
    for i in range(0, len(cheio), FATIA):
        fatia = cheio[i:i + FATIA]
        # O tamanho util desconta o enchimento, que so existe na ultima fatia.
        util = len(fatia) - (sobra if i + FATIA >= len(cheio) else 0)
        bloco = (struct.pack(">I", util)
                 + b"\x00" * (BLOCO - 4 - len(fatia))
                 + fatia)
        numero = int.from_bytes(bloco, "big")
        if numero >= modulo:
            raise ErroDeCripto("bloco maior que o módulo; a chave precisa ter "
                               "1024 bits.")
        saida += pow(numero, expoente_privado, modulo).to_bytes(BLOCO, "big")
    saida += _rabo(bytes(saida), rabo_modelo)
    return bytes(saida)


# ---------------------------------------------------------------------------
# A chave do cliente, e a chave de quem usa
# ---------------------------------------------------------------------------
# Parte dos clientes guarda o modulo como texto dentro do executavel, e ai
# ele e trocavel. Do Kamael em diante o executavel vem empacotado: a chave so
# existe em memoria, entregue pelo loader, e trocar exigiria um loader
# proprio -- o programa diz isso na tela em vez de tentar.
HEXA_DA_CHAVE = re.compile(rb"[0-9a-fA-F]{256}")
EXPOENTE_413 = 0x25             # medido no C3; o 411/412/414 usam outros
EXPOENTES_CONHECIDOS = (0x25, 0x1d, 0x11, 0x23)


def chave_do_cliente(caminho):
    """(modulo, posicao) achados num executável do cliente, ou (None, None)."""
    dados = Path(caminho).read_bytes()
    achado = HEXA_DA_CHAVE.search(dados)
    if not achado:
        return None, None
    return int(achado.group().decode(), 16), achado.start()


def onde_trocar_a_chave(system):
    """
    Os arquivos do cliente que guardam o módulo, e onde ele está em cada um.

    Devolve [(caminho, posição, módulo)]. Lista vazia quer dizer cliente
    empacotado -- Kamael em diante --, e aí a chave não se troca por aqui.
    """
    system = Path(system)
    achados = []
    for nome in ("l2.exe", "L2.exe", "engine.dll", "Engine.dll",
                 "LineageII.exe"):
        alvo = system / nome
        if not alvo.is_file():
            continue
        modulo, posicao = chave_do_cliente(alvo)
        if modulo is not None and not any(a[0].name.lower() == nome.lower()
                                          for a in achados):
            achados.append((alvo, posicao, modulo))
    return achados


def par_da_frase(frase, expoente=EXPOENTE_413, bits=1024):
    """
    Gera o par RSA a partir de uma frase -- a mesma frase, o mesmo par.

    Ser derivado e de proposito: a chave nao fica so num arquivo que se perde
    com o disco. Quem tem a frase refaz o par em qualquer maquina; quem nao
    tem, nao gera arquivo que o cliente aceite. A frase nao e guardada.

    Devolve {"modulo", "publico", "privado", "bits"}.
    """
    frase = (frase or "").strip()
    if len(frase) < 8:
        raise ErroDeCripto("a frase precisa de pelo menos 8 caracteres.")

    metade = bits // 2
    p = _primo_da_semente(frase, "p", metade, expoente)
    q = _primo_da_semente(frase, "q", metade, expoente)
    while q == p:
        q = _primo_da_semente(frase + "!", "q", metade, expoente)
    n = p * q
    if n.bit_length() != bits:
        # Os dois primos vem com o bit alto ligado, entao isto nao acontece;
        # ficar calado se acontecesse seria gravar arquivo que nao abre.
        raise ErroDeCripto("o módulo saiu com %d bits, e precisa de %d."
                           % (n.bit_length(), bits))
    d = pow(expoente, -1, (p - 1) * (q - 1))
    return {"modulo": n, "publico": expoente, "privado": d, "bits": bits}


def _primo_da_semente(frase, marca, bits, expoente):
    """Um primo determinístico a partir da frase: mesma frase, mesmo primo."""
    semente = hashlib.pbkdf2_hmac("sha256", frase.encode("utf-8"),
                                  b"L2PackTool/" + marca.encode("ascii"),
                                  200000, dklen=bits // 8)
    numero = int.from_bytes(semente, "big")
    # Os DOIS bits altos ligados: com so o mais alto, o produto dos dois
    # primos cai em 1023 bits metade das vezes, e a chave precisa ter 1024
    # para preencher os 256 caracteres hexa que o cliente guarda.
    numero |= (3 << (bits - 2)) | 1
    while not (_e_primo(numero) and (numero - 1) % expoente):
        numero += 2
    return numero


def _e_primo(numero, voltas=32):
    """Miller-Rabin. Com 32 voltas o engano é menos provável que o disco errar."""
    if numero < 2:
        return False
    for pequeno in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if numero % pequeno == 0:
            return numero == pequeno
    d, r = numero - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for base in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)[:voltas]:
        x = pow(base, d, numero)
        if x in (1, numero - 1):
            continue
        for _ in range(r - 1):
            x = x * x % numero
            if x == numero - 1:
                break
        else:
            return False
    return True


def trocar_chave_do_cliente(caminho, modulo_novo, bits=1024):
    """
    Escreve o módulo novo no executável, no lugar exato do antigo.

    Mesmo tamanho, mesma posição: 256 caracteres hexa por 256. Nada se move, e
    por isso não há o que desalinhar. Devolve (módulo antigo, módulo novo).
    """
    caminho = Path(caminho)
    dados = bytearray(caminho.read_bytes())
    achado = HEXA_DA_CHAVE.search(bytes(dados))
    if not achado:
        raise ErroDeCripto("%s não guarda a chave em hexa; este cliente é dos "
                           "que recebem a chave por loader." % caminho.name)
    novo = "%0*x" % (bits // 4, modulo_novo)
    if len(novo) != len(achado.group()):
        raise ErroDeCripto("a chave nova tem %d caracteres e a do cliente tem "
                           "%d." % (len(novo), len(achado.group())))
    antigo = int(achado.group().decode(), 16)
    dados[achado.start():achado.end()] = novo.encode("ascii")
    caminho.write_bytes(bytes(dados))
    return antigo, modulo_novo


# ---------------------------------------------------------------------------
# A porta de entrada
# ---------------------------------------------------------------------------
def abrir(caminho, modulo=None, expoente=None):
    """
    Abre qualquer formato que este módulo saiba, pelo cabeçalho do arquivo.

    Devolve (conteúdo, método, rabo). Para 41x a chave é obrigatória: sem ela
    não há o que tentar, e adivinhar seria devolver lixo com cara de dado.
    """
    caminho = Path(caminho)
    dados = caminho.read_bytes()
    met = metodo(dados)
    if met is None:
        return dados, None, b""
    if met in SO_XOR:
        conteudo, rabo = abrir_xor(dados, met, caminho.name)
        return conteudo, met, rabo
    if met in NATIVOS:
        if modulo is None:
            raise ErroDeCripto("%s é %s e precisa da chave para abrir."
                               % (caminho.name, met))
        if expoente is None:
            expoente = expoente_que_abre(dados, modulo)
            if expoente is None:
                raise ErroDeCripto(
                    "nenhum expoente conhecido abre %s com essa chave -- o "
                    "arquivo é de outro par." % caminho.name)
        conteudo, rabo = abrir_41x(dados, modulo, expoente)
        return conteudo, met, rabo
    raise ErroDeCripto("método %s ainda não é feito aqui dentro." % met)


def fechar(conteudo, destino, met, modulo=None, privado=None, rabo_modelo=None):
    """Grava `conteúdo` cifrado no método pedido. Devolve o caminho."""
    destino = Path(destino)
    if met in SO_XOR:
        bruto = fechar_xor(conteudo, met, destino.name, rabo_modelo)
    elif met in NATIVOS:
        if modulo is None or privado is None:
            raise ErroDeCripto("gravar em %s precisa da chave privada." % met)
        bruto = fechar_41x(conteudo, modulo, privado, met, rabo_modelo)
    else:
        raise ErroDeCripto("método %s ainda não é feito aqui dentro." % met)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bruto)
    return destino
