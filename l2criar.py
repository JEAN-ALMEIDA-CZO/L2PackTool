# -*- coding: utf-8 -*-
"""
Criar do zero o pacote de um lobby de video.

A aba de video comecou trocando os quadros de um lobby que o cliente ja tinha.
Este modulo vai alem: monta o `M1.usx` inteiro, com o numero de quadros que o
video pedir, e nao o numero que o pacote de origem por acaso tinha.

Por que isso importa: a sequencia tem um numero fixo de lugares, e ele limita o
filme. Um lobby de 181 quadros a 33 por segundo da 5,4 s; querer 30 s dele
significa 6 quadros por segundo, que pica. Montando o pacote, a quantidade de
quadros sai da cadencia do proprio video.

O que NAO e inventado aqui -- e a razao de existir uma "pasta modelo":

  * o `Lobby.unr`, que planta a tela na cena e aponta a camera;
  * os 543 bytes nativos da malha `seq`, que sao geometria, caixa envolvente e
    arvore de colisao. Escrever isso a mao seria chute caro.

O resto -- quadros, `MaterialSequence`, `Shader`, `ConstantColor` -- e escrito
byte a byte aqui, no mesmo formato lido do modelo.

O formato de um quadro, medido e nao suposto:

    [propriedades][4 bytes de rabo][quantos mipmaps][INT salto]
    [indice compacto: quantos bytes][pixeis][INT USize][INT VSize][UBits][VBits]

O `salto` e a posicao ABSOLUTA logo depois dos pixeis -- e a TLazyArray que ja
derrubou este projeto uma vez. Aqui ela e calculada na hora de gravar, quando a
posicao final de cada objeto ja e conhecida.
"""
import json
import math
import shutil
import tempfile
import zipfile
import struct
import time
from pathlib import Path

import l2anim
import l2npc
import l2mapa
import l2seq
import l2upscale as motor
import versao

# Quanto o pacote pode crescer. Cada quadro de 2048x2048 em DXT1 custa 2 MB, e
# um video de trinta segundos a trinta quadros por segundo pediria 1,8 GB. O
# limite nao e tecnico, e de bom senso: passando disso, o programa reduz a
# cadencia e diz que reduziu.
ORCAMENTO_PADRAO = 1200 * 1024 * 1024

NOMES_FIXOS = ("demev", "Shg1", "seq", "bl", "blk")


class ErroCriacao(Exception):
    pass


# ---------------------------------------------------------------------------
# O modelo
# ---------------------------------------------------------------------------
def achar_modelo(pasta):
    """
    Procura na pasta um mapa de lobby e um pacote com MaterialSequence.

    Aceita o arranjo em que esses lobbys circulam: subpastas `maps` e
    `staticmeshes`, com nomes em qualquer caixa.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        return None

    mapa = pacote = None
    for caminho in pasta.rglob("*"):
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() == ".unr" and mapa is None:
            mapa = caminho
        elif caminho.suffix.lower() in (".usx", ".utx") and pacote is None:
            try:
                if l2seq.ler_sequencia(caminho):
                    pacote = caminho
            except Exception:
                pass
    if mapa is None or pacote is None:
        return None

    extras = [c for c in pasta.rglob("*")
              if c.is_file()
              and c.suffix.lower() in (".utx", ".usx", ".unr", ".dat")
              and c != mapa and c != pacote]
    return {"pasta": pasta, "mapa": mapa, "pacote": pacote, "extras": extras}


def ler_molde(caminho):
    """
    Tira do pacote modelo tudo o que vai ser reaproveitado.

    Volta com a tabela de nomes e a de imports inteiras -- e importante que
    fiquem EXATAMENTE como estao, porque os bytes da malha `seq` referem nomes
    e classes por indice. Mudar a ordem da tabela seria reescrever a malha.
    """
    caminho = Path(caminho)
    pacote = l2npc.Pacote(caminho)
    try:
        dados = pacote.dados
        (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
         qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(
            l2anim.CABECALHO, dados)
        nomes_crus, fim_nomes = l2anim._ler_nomes_cru(dados, off_nomes,
                                                      qtd_nomes)
        nomes = [n for n, _f in nomes_crus]

        imports, pos = [], off_imp
        for _ in range(qtd_imp):
            campos, pos = l2anim._ler_import(dados, pos)
            imports.append(campos)
        exports, pos = [], off_exp
        for _ in range(qtd_exp):
            campos, pos = l2anim._ler_export(dados, pos)
            exports.append(campos)

        def achar(nome_alvo):
            for indice, campos in enumerate(exports, 1):
                if nomes[campos["nome"]] == nome_alvo and campos["tamanho"]:
                    return indice, campos
            return None, None

        molde = {
            "arquivo": caminho,
            "versao": versao, "licenciado": licenciado, "flags": flags,
            "off_nomes": off_nomes,
            "nomes": list(nomes_crus),
            "imports": imports,
            "cifrado": l2npc.metodo_do_arquivo(caminho),
        }

        # a malha da tela, copiada inteira
        indice, campos = achar("seq")
        if indice is None:
            raise ErroCriacao("o modelo nao tem a malha `seq` da tela.")
        props_seq, fim_seq = l2anim.ler_propriedades(
            dados, campos["inicio"], nomes,
            campos["inicio"] + campos["tamanho"])
        molde["seq"] = {
            "campos": dict(campos),
            "propriedades": [(n, bytes(c)) for n, c in props_seq],
            "nativo": bytes(dados[fim_seq:campos["inicio"] + campos["tamanho"]]),
            "fim_das_propriedades": fim_seq - campos["inicio"],
        }
        # os INT que apontam para dentro da propria malha
        molde["seq"]["saltos"] = _saltos_internos(
            molde["seq"]["nativo"], campos["inicio"], campos["tamanho"],
            molde["seq"]["fim_das_propriedades"])

        # o rabo de quatro bytes que todo material deste pacote carrega
        indice, campos = achar("bl")
        if indice is not None:
            _p, fim = l2anim.ler_propriedades(
                dados, campos["inicio"], nomes,
                campos["inicio"] + campos["tamanho"])
            molde["rabo"] = bytes(dados[fim:campos["inicio"] +
                                        campos["tamanho"]])
        else:
            molde["rabo"] = b"\x00\x00\x00\x00"

        # uma textura de exemplo, para copiar as propriedades que nao mudam
        for indice, campos in enumerate(exports, 1):
            if l2seq._classe(campos, nomes, imports, exports) != "Texture":
                continue
            props, _fim = l2anim.ler_propriedades(
                dados, campos["inicio"], nomes,
                campos["inicio"] + campos["tamanho"])
            molde["relogio"] = [bytes(c) for n, c in props
                                if n == "InternalTime"]
            molde["flags_do_objeto"] = campos["flags"]
            break

        molde["nome_do_pacote"] = caminho.stem
        return molde
    finally:
        pacote.fechar()


def _saltos_internos(nativo, inicio, tamanho, desloc):
    """
    Onde, dentro do bloco nativo, ha INT apontando para o proprio objeto.

    Sao as TLazyArray da malha. Guardamos a posicao e a distancia ate o FIM do
    objeto, que e o que se mantem quando ele muda de lugar ou de tamanho.
    """
    fim = inicio + tamanho
    achados = []
    for p in range(0, max(0, len(nativo) - 4)):
        valor = int.from_bytes(nativo[p:p + 4], "little")
        if inicio <= valor <= fim + 32:
            achados.append({"onde": p, "ate_o_fim": valor - fim})
    return achados


# ---------------------------------------------------------------------------
# Escrever objetos
# ---------------------------------------------------------------------------
def _propriedade_int(i_nome, valor, indice=None):
    info = 2 | (2 << 4) | (0x80 if indice is not None else 0)
    saida = l2anim.compacto(i_nome) + bytes([info])
    if indice is not None:
        saida += l2anim.compacto(indice)
    return saida + struct.pack("<i", valor)


def _propriedade_byte(i_nome, valor):
    return l2anim.compacto(i_nome) + bytes([1 | (0 << 4), valor & 0xFF])


def _propriedade_bool(i_nome, valor):
    """
    O booleano marcado, como o jogo escreve: `53 00`.

    O valor mora no bit mais alto do byte de tipo e nao gasta espaco,
    mas o codigo de tamanho tem de ser 5 -- "o tamanho vem no proximo
    byte" -- com esse byte em zero. Com codigo 0 o leitor entende que
    ha um byte de valor e come o `None` que fecha a lista.
    """
    return (l2anim.compacto(i_nome)
            + bytes([3 | (5 << 4) | (0x80 if valor else 0)])
            + b"\x00")


class Tabela:
    """A tabela de nomes em construcao: acha ou acrescenta, sem reordenar."""

    def __init__(self, nomes_crus):
        self.itens = list(nomes_crus)
        self.indice = {n: i for i, (n, _f) in enumerate(self.itens)}
        self.flags = self.itens[1][1] if len(self.itens) > 1 else 0

    def __call__(self, texto):
        if texto in self.indice:
            return self.indice[texto]
        self.itens.append((texto, self.flags))
        self.indice[texto] = len(self.itens) - 1
        return self.indice[texto]


def corpo_de_textura(nomes, molde, largura, altura, formato, pixeis):
    """
    Os bytes de um objeto Texture, tirando o INT de salto -- que so pode ser
    escrito quando a posicao final do objeto for conhecida.

    Devolve (antes_do_salto, depois_do_salto), para quem grava juntar os dois
    com o valor certo no meio.
    """
    bits_u = int(math.log(largura, 2))
    bits_v = int(math.log(altura, 2))

    props = bytearray()
    for cru in molde.get("relogio", ()):
        props += cru
    props += _propriedade_byte(nomes("Format"), formato)
    props += _propriedade_byte(nomes("UBits"), bits_u)
    props += _propriedade_byte(nomes("VBits"), bits_v)
    props += _propriedade_int(nomes("USize"), largura)
    props += _propriedade_int(nomes("VSize"), altura)
    props += _propriedade_int(nomes("UClamp"), largura)
    props += _propriedade_int(nomes("VClamp"), altura)
    props += b"\x00"

    antes = bytes(props) + molde["rabo"] + l2anim.compacto(1)
    depois = (l2anim.compacto(len(pixeis)) + pixeis
              + struct.pack("<ii", largura, altura)
              + bytes([bits_u, bits_v]))
    return antes, depois


def corpo_da_sequencia(nomes, molde, indices, segundos, repetir=True):
    """O MaterialSequence: um item por quadro, na ordem."""
    por_quadro = float(segundos) / max(1, len(indices))
    itens = bytearray(l2anim.compacto(len(indices)))
    for indice in indices:
        itens += l2anim.propriedade_objeto(nomes("Material"), indice)
        itens += l2anim.propriedade_float(nomes("Time"), por_quadro)
        itens += _propriedade_byte(nomes("Action"), 0)
        itens += b"\x00"

    corpo = bytearray(l2anim.compacto(nomes("SequenceItems")))
    if len(itens) < 256:
        corpo += bytes([9 | (5 << 4), len(itens)])
    elif len(itens) < 65536:
        corpo += bytes([9 | (6 << 4)]) + struct.pack("<H", len(itens))
    else:
        corpo += bytes([9 | (7 << 4)]) + struct.pack("<I", len(itens))
    corpo += itens

    gravado = struct.unpack("<f", struct.pack("<f", por_quadro))[0]
    corpo += l2anim.propriedade_float(nomes("TotalTime"),
                                      gravado * len(indices))
    if repetir:
        corpo += _propriedade_bool(nomes("Loop"), True)
    corpo += b"\x00" + molde["rabo"]
    return bytes(corpo), gravado


def corpo_do_shader(nomes, molde, indice_da_sequencia):
    corpo = bytearray()
    corpo += l2anim.propriedade_objeto(nomes("Diffuse"), indice_da_sequencia)
    corpo += l2anim.propriedade_objeto(nomes("SelfIllumination"),
                                       indice_da_sequencia)
    corpo += b"\x00" + molde["rabo"]
    return bytes(corpo)


def corpo_da_cor(molde):
    return b"\x00" + molde["rabo"]


def propriedades_da_malha(molde, nomes, indice_do_shader):
    """
    As propriedades da malha `seq`, com o material apontando para o nosso.

    O vetor `Materials` do modelo e copiado como esta; so a referencia de
    objeto dentro dele muda. Assim as tres bandeiras que vem junto -- e que sao
    identificadas por indice de nome -- continuam valendo, porque a tabela de
    nomes do modelo foi preservada inteira.
    """
    saida = bytearray()
    for nome, cru in molde["seq"]["propriedades"]:
        if nome != "Materials":
            saida += cru
            continue
        nome_prop, tipo, indice_vetor, corpo, desloc = l2seq._decodificar(
            cru, [n for n, _f in molde["nomes"]])
        quantos, pos = l2anim._descompacto(corpo, 0)
        novo_corpo = bytearray(l2anim.compacto(quantos))
        for _ in range(quantos):
            internas, pos = l2anim.ler_propriedades(
                corpo, pos, [n for n, _f in molde["nomes"]], len(corpo))
            for n2, c2 in internas:
                if n2 == "Material":
                    novo_corpo += l2anim.propriedade_objeto(
                        nomes("Material"), indice_do_shader)
                else:
                    novo_corpo += c2
            novo_corpo += b"\x00"
        cabeca = bytearray(l2anim.compacto(nomes("Materials")))
        if len(novo_corpo) < 256:
            cabeca += bytes([9 | (5 << 4), len(novo_corpo)])
        else:
            cabeca += bytes([9 | (6 << 4)]) + struct.pack("<H",
                                                          len(novo_corpo))
        saida += bytes(cabeca) + bytes(novo_corpo)
    saida += b"\x00"
    return bytes(saida)


# ---------------------------------------------------------------------------
# Montar o pacote
# ---------------------------------------------------------------------------
def _escrever_textura(arquivo, nomes, molde, largura, altura, formato,
                      pixeis):
    """Grava um objeto Texture e devolve (inicio, tamanho)."""
    antes, depois = corpo_de_textura(nomes, molde, largura, altura, formato,
                                     pixeis)
    inicio = arquivo.tell()
    arquivo.write(antes)
    # O salto aponta para logo depois dos pixeis. So da para escreve-lo aqui,
    # com o arquivo ja posicionado: e endereco absoluto.
    tamanho_compacto = len(l2anim.compacto(len(pixeis)))
    salto = arquivo.tell() + 4 + tamanho_compacto + len(pixeis)
    arquivo.write(struct.pack("<I", salto))
    arquivo.write(depois)
    return inicio, arquivo.tell() - inicio


def _escrever_malha(arquivo, nomes, molde, indice_do_shader):
    """
    Grava a malha da tela, copiada do modelo, com os saltos refeitos.

    Os INT que apontam para dentro dela sao TLazyArray: guardam posicao
    absoluta. Mudando de arquivo e de lugar, cada um tem de ser recalculado --
    e o que se mantem e a distancia ate o FIM do objeto.
    """
    props = propriedades_da_malha(molde, nomes, indice_do_shader)
    nativo = bytearray(molde["seq"]["nativo"])
    inicio = arquivo.tell()
    tamanho = len(props) + len(nativo)
    fim = inicio + tamanho
    for salto in molde["seq"]["saltos"]:
        nativo[salto["onde"]:salto["onde"] + 4] = struct.pack(
            "<I", fim + salto["ate_o_fim"])
    arquivo.write(props)
    arquivo.write(bytes(nativo))
    return inicio, tamanho


def montar(T, molde, quadros, destino, segundos, repetir=True,
           formato="DXT1", lote=16, aolog=None, aoprogresso=None):
    """
    Escreve o pacote inteiro: quadros, sequencia, shader, malha e cor.

    Os quadros sao comprimidos e gravados em lotes. Trezentos quadros de
    2048x2048 dariam um gigabyte e meio de PNG intermediario se tudo fosse
    comprimido antes; em lotes, o disco nunca segura mais do que um punhado.

    A ordem dos objetos e a ordem da tabela de exports, e os indices importam:
    a sequencia aponta os quadros, o shader aponta a sequencia, a malha aponta
    o shader.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    quadros = list(quadros)
    if not quadros:
        raise ErroCriacao("nenhum quadro para montar.")

    nomes = Tabela(molde["nomes"])
    imports = molde["imports"]
    nomes_do_modelo = [n for n, _f in molde["nomes"]]

    def classe(nome_alvo):
        for k, campos in enumerate(imports, 1):
            if nomes_do_modelo[campos["nome"]] == nome_alvo:
                return -k
        raise ErroCriacao("o modelo nao importa a classe %s." % nome_alvo)

    flags_objeto = molde.get("flags_do_objeto", 0x000E0004)
    total = len(quadros)

    nomes_dos_quadros = [nomes("1%04d" % i) for i in range(total)]
    ind_demev = total + 2
    ind_shg = total + 3

    trabalho = destino.parent / "_lote"
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)

    exports = []
    por_quadro = 0.0
    with open(destino, "wb") as arquivo:
        arquivo.write(b"\x00" * molde["off_nomes"])   # espaco do cabecalho

        feitos = 0
        for k in range(0, total, lote):
            pedaco = quadros[k:k + lote]
            pasta = trabalho / ("l%04d" % k)
            dds = motor.comprimir(
                T, pedaco, pasta,
                formatos={p.stem: {"formato": "TEXF_" + formato}
                          for p in pedaco})
            por_nome = {p.stem: p for p in dds}
            for imagem in pedaco:
                arquivo_dds = por_nome.get(imagem.stem)
                if arquivo_dds is None:
                    raise ErroCriacao("o texconv nao comprimiu %s."
                                      % imagem.name)
                bruto = arquivo_dds.read_bytes()
                altura, largura = struct.unpack_from("<ii", bruto, 12)
                pixeis = bruto[128:128 + largura * altura // 2]
                inicio, tamanho = _escrever_textura(
                    arquivo, nomes, molde, largura, altura, 3, pixeis)
                exports.append({"classe": classe("Texture"), "mae": 0,
                                "dono": 0,
                                "nome": nomes_dos_quadros[len(exports)],
                                "flags": flags_objeto, "tamanho": tamanho,
                                "inicio": inicio})
                feitos += 1
                if aoprogresso:
                    aoprogresso(feitos, total)
            shutil.rmtree(pasta, ignore_errors=True)

        # a textura preta que o mapa importa pelo nome
        lado = 256
        inicio, tamanho = _escrever_textura(
            arquivo, nomes, molde, lado, lado, 3,
            b"\x00" * (lado * lado // 2))
        exports.append({"classe": classe("Texture"), "mae": 0, "dono": 0,
                        "nome": nomes("blk"), "flags": flags_objeto,
                        "tamanho": tamanho, "inicio": inicio})

        corpo, por_quadro = corpo_da_sequencia(
            nomes, molde, list(range(1, total + 1)), segundos, repetir)
        inicio = arquivo.tell()
        arquivo.write(corpo)
        exports.append({"classe": classe("MaterialSequence"), "mae": 0,
                        "dono": 0, "nome": nomes("demev"),
                        "flags": flags_objeto, "tamanho": len(corpo),
                        "inicio": inicio})

        corpo = corpo_do_shader(nomes, molde, ind_demev)
        inicio = arquivo.tell()
        arquivo.write(corpo)
        exports.append({"classe": classe("Shader"), "mae": 0, "dono": 0,
                        "nome": nomes("Shg1"), "flags": flags_objeto,
                        "tamanho": len(corpo), "inicio": inicio})

        inicio, tamanho = _escrever_malha(arquivo, nomes, molde, ind_shg)
        exports.append({"classe": classe("StaticMesh"), "mae": 0, "dono": 0,
                        "nome": nomes("seq"), "flags": flags_objeto,
                        "tamanho": tamanho, "inicio": inicio})

        corpo = corpo_da_cor(molde)
        inicio = arquivo.tell()
        arquivo.write(corpo)
        exports.append({"classe": classe("ConstantColor"), "mae": 0,
                        "dono": 0, "nome": nomes("bl"), "flags": flags_objeto,
                        "tamanho": len(corpo), "inicio": inicio})

        off_nomes = arquivo.tell()
        for texto, f in nomes.itens:
            arquivo.write(l2anim._escrever_nome(texto, f))
        off_imp = arquivo.tell()
        for campos in imports:
            arquivo.write(l2anim._escrever_import(campos))
        off_exp = arquivo.tell()
        for campos in exports:
            arquivo.write(l2anim._escrever_export(campos))

        cabecalho = bytearray(struct.calcsize(l2anim.CABECALHO))
        struct.pack_into(l2anim.CABECALHO, cabecalho, 0, 0x9E2A83C1,
                         molde["versao"], molde["licenciado"], molde["flags"],
                         len(nomes.itens), off_nomes, len(exports), off_exp,
                         len(imports), off_imp)
        arquivo.seek(0)
        arquivo.write(bytes(cabecalho))

    shutil.rmtree(trabalho, ignore_errors=True)
    anotar("pacote montado: %d quadros, %.0f MB, %.4f s por quadro"
           % (total, destino.stat().st_size / 1048576.0, por_quadro))
    return {"arquivo": destino, "quadros": total, "por_quadro": por_quadro}


# ---------------------------------------------------------------------------
# Instalar
# ---------------------------------------------------------------------------
PASTA_DE_CADA_TIPO = {".unr": "Maps", ".usx": "StaticMeshes",
                      ".utx": "Textures", ".uax": "Sounds", ".ukx": "Animations"}

# Tabelas do cliente que fazem parte do lobby, e que moram na propria system.
#
# O logongrp.dat guarda onde cada personagem fica parado na tela de entrada.
# Ele e feito junto com o mapa, para AQUELE mapa: as posicoes sao coordenadas
# dentro da cena. Trocar o lobby sem trocar o logongrp deixa os bonecos nas
# posicoes do lobby anterior -- dentro de uma parede, de costas, ou fora do
# quadro.
EXTENSOES_DE_TABELA = (".dat",)


def pasta_do_cliente(system, extensao):
    """A pasta certa para um arquivo, respeitando a caixa que o cliente usa."""
    if extensao.lower() in EXTENSOES_DE_TABELA:
        return Path(system)

    raiz = Path(system).parent
    desejada = PASTA_DE_CADA_TIPO.get(extensao.lower(), "StaticMeshes")
    for caminho in raiz.iterdir():
        if caminho.is_dir() and caminho.name.lower() == desejada.lower():
            return caminho
    nova = raiz / desejada
    nova.mkdir(parents=True, exist_ok=True)
    return nova


def guardar(destino, aolog=None):
    """Poe o que estiver no caminho em backup_lobby, com data no nome."""
    destino = Path(destino)
    if not destino.exists():
        return None
    guarda = destino.parent / "backup_lobby"
    guarda.mkdir(exist_ok=True)
    copia = guarda / ("%s_%s" % (time.strftime("%Y%m%d_%H%M%S"),
                                 destino.name))
    if not copia.exists():
        shutil.copy2(destino, copia)
        if aolog:
            aolog("o %s que estava la foi para %s" % (destino.name, copia.name))
    return copia


def pasta_irma(system, nome_da_pasta):
    """A pasta do cliente com este nome, respeitando a caixa que ele usa."""
    raiz = Path(system).parent
    for caminho in raiz.iterdir():
        if caminho.is_dir() and caminho.name.lower() == nome_da_pasta.lower():
            return caminho
    nova = raiz / nome_da_pasta
    nova.mkdir(parents=True, exist_ok=True)
    return nova


def destino_do_arquivo(system, origem, raiz_do_modelo=None):
    """
    Onde este arquivo vai, dentro do cliente.

    Quando o lobby veio de uma pasta, quem manda e a SUBPASTA de origem: foi
    quem empacotou o lobby que decidiu que aquele `.utx` e de `SysTextures` e
    nao de `Textures`, e a extensao nao sabe a diferenca. Sem subpasta, vale
    a regra por extensao.
    """
    origem = Path(origem)
    if raiz_do_modelo:
        try:
            dentro = origem.relative_to(Path(raiz_do_modelo))
        except ValueError:
            dentro = None
        if dentro is not None and len(dentro.parts) > 1:
            return pasta_irma(system, dentro.parts[0])
    return pasta_do_cliente(system, origem.suffix)


def instalar(system, modelo, pacote=None, aolog=None, guardar_copias=True,
             formato=None, com_video=True, T=None):
    """
    Poe no cliente o lobby criado: o pacote gerado mais o resto do modelo.

    O mapa vem do modelo e depois e acertado aqui -- e o mapa que planta a
    tela na cena e aponta a camera. O `logongrp.dat` diz onde os personagens
    ficam parados dentro dela, e vai junto: trocar o lobby sem ele deixa os
    bonecos em lugar errado.

    `formato` e a janela mais alta que a tela deve cobrir, largura dividida
    por altura. O padrao cobre da ultralarga a 5 por 4, que sao todas as
    telas de uso comum.

    Guardar copia e opcional de proposito: o pacote de um lobby de video passa
    de cem megabytes, e quem ja tem o original noutro lugar nao precisa de
    outra. As tabelas escapam dessa regra e sao guardadas sempre -- elas tem
    kilobytes, e o logongrp.dat do cliente nao se refaz.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    nome = modelo.get("nome_do_arquivo") or "%s.usx" % versao.NOME
    marca = Path(nome).stem

    # o lobby vive compactado ate aqui
    temporaria = None
    if modelo.get("zip") and not modelo.get("mapa"):
        temporaria = Path(tempfile.mkdtemp(prefix="lobby_"))
        modelo = abrir_o_lobby(modelo, temporaria)
        anotar("%s aberto (%d arquivos)"
               % (Path(modelo["zip"]).name, len(modelo["extras"]) + 1))

    try:
        return _instalar_aberto(system, modelo, pacote, aolog, guardar_copias,
                                formato, com_video, nome, marca, T)
    finally:
        if temporaria is not None:
            shutil.rmtree(temporaria, ignore_errors=True)


def _instalar_aberto(system, modelo, pacote, aolog, guardar_copias, formato,
                     com_video, nome, marca, T=None):
    """A instalacao propriamente dita, com o lobby ja aberto em disco."""
    def anotar(texto):
        if aolog:
            aolog(texto)

    renomes = video_com_a_marca(modelo, marca) if com_video else {}
    for velho, novo in renomes.items():
        anotar("%s passa a se chamar %s" % (velho, novo))

    raiz_do_modelo = modelo.get("pasta")
    instalados = []
    mapa_no_cliente = None
    for origem in [modelo["mapa"]] + list(modelo["extras"]):
        como = renomes.get(origem.stem, origem.stem) + origem.suffix
        destino = destino_do_arquivo(system, origem, raiz_do_modelo) / como
        if guardar_copias or origem.suffix.lower() in EXTENSOES_DE_TABELA:
            guardar(destino, aolog)
        shutil.copy2(origem, destino)
        anotar("%s -> %s" % (como, destino.parent.name))
        instalados.append(destino)
        if origem == modelo["mapa"]:
            mapa_no_cliente = destino

    if not any(c.name.lower() == NOME_DAS_POSES for c in instalados):
        anotar("atencao: este lobby nao traz %s -- os personagens podem"
               " aparecer em lugar errado na cena" % NOME_DAS_POSES)

    if pacote is not None:
        destino = pasta_do_cliente(system, ".usx") / nome
        if guardar_copias:
            guardar(destino, aolog)
        shutil.copy2(pacote, destino)
        anotar("%s -> %s (%.0f MB)"
               % (destino.name, destino.parent.name,
                  destino.stat().st_size / 1048576.0))
        instalados.append(destino)

    if mapa_no_cliente is not None:
        if com_video:
            acertar_o_video(mapa_no_cliente, marca, formato, aolog,
                            camera=modelo.get("camera"), renomes=renomes)
        else:
            anotar("lobby classico: o mapa vai como veio da cronica")
        conferir_o_lobby(system, mapa_no_cliente, aolog, T)
    return instalados


EXTENSOES_DE_PACOTE = (".usx", ".utx", ".ukx", ".uax")
FALTAS_QUE_CABEM = 8            # o resto vira uma linha de resumo


def video_com_a_marca(modelo, marca):
    """
    O pacote de video tambem leva a marca, em qualquer modelo.

    Um lobby que ja tem tela procura o pacote dela por um nome proprio -- no
    embutido, `M1`. Como o mapa e reescrito na instalacao, esse nome pode ser
    o do sistema, e o arquivo instalado tem o mesmo. Num lobby sem tela nao
    ha o que renomear: a tela nasce ja apontando para a marca.
    """
    try:
        velho = l2mapa.pacote_da_tela(l2mapa.ler(modelo["mapa"]))
    except Exception:                               # noqa: BLE001
        return {}
    if not velho or velho == marca:
        return {}
    return {velho: marca}


def conferir_o_lobby(system, mapa_no_cliente, aolog=None, T=None):
    """
    Confere se o cliente tem o que o mapa procura -- objeto por objeto.

    O pacote existir nao garante nada: o que deixa o cenario sem textura e
    faltar um objeto DENTRO dele. Um pacote que nao se consegue abrir nao
    vira falta: falta e o que se prova que nao esta la.

    Devolve [(pacote, caminho, [objetos que faltam])].
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    import l2conferir

    try:
        mapa = l2mapa.ler(mapa_no_cliente, T)
        usados = l2mapa.objetos_usados(mapa)
    except Exception as erro:                       # noqa: BLE001
        anotar("nao consegui conferir o mapa (%s)" % erro)
        return []

    raiz = Path(system).parent
    faltas, conferidos = [], 0
    for pacote, objetos in sorted(usados.items()):
        caminho = achar_pacote(raiz, pacote)
        if caminho is None:
            faltas.append((pacote, None, sorted(objetos)))
            continue
        try:
            tem = {n.lower() for n in l2conferir.objetos_do_pacote(caminho)}
        except Exception:                           # noqa: BLE001
            continue
        conferidos += 1
        sumidos = sorted(n for n in objetos if n.lower() not in tem)
        if sumidos:
            faltas.append((pacote, caminho, sumidos))

    if not faltas:
        anotar("conferido: os %d pacotes do lobby estao completos neste"
               " cliente" % conferidos)
        return faltas

    # Num cliente que nao e o de destino, a lista sai enorme e nao informa
    # mais por ser longa: as primeiras ja dizem o que ha de errado.
    for pacote, caminho, sumidos in faltas[:FALTAS_QUE_CABEM]:
        if caminho is None:
            anotar("FALTA o pacote %s -- %d objetos do cenario dependem dele"
                   % (pacote, len(sumidos)))
        else:
            mostra = ", ".join(sumidos[:4])
            anotar("em %s faltam %d objetos: %s%s"
                   % (pacote, len(sumidos), mostra,
                      " ..." if len(sumidos) > 4 else ""))
    if len(faltas) > FALTAS_QUE_CABEM:
        anotar("... e mais %d pacotes na mesma situacao"
               % (len(faltas) - FALTAS_QUE_CABEM))
    anotar("o que falta aparece sem textura no cenario; o video nao depende"
           " disso")
    return faltas


def achar_pacote(raiz, nome_do_pacote):
    """O arquivo de um pacote dentro do cliente, procurando pelo nome."""
    for pasta in ("StaticMeshes", "Textures", "SysTextures", "Animations",
                  "Sounds", "Maps", "system"):
        for variante in (pasta, pasta.lower(), pasta.upper()):
            p = Path(raiz) / variante
            if not p.is_dir():
                continue
            for arquivo in p.iterdir():
                if arquivo.is_file() \
                        and arquivo.stem.lower() == nome_do_pacote.lower():
                    return arquivo
    return None


# O nome e fixo no cliente: e por ele que o jogo procura as poses.
NOME_DAS_POSES = "logongrp.dat"


def acertar_o_video(mapa_no_cliente, pacote_do_video, formato=None,
                    aolog=None, camera=None, renomes=None):
    """
    Deixa a tela do video no tamanho certo para as telas de hoje.

    O que muda de um lobby para outro e so o ponto de partida:

      ja tem a tela    muda o tamanho dela, e mais nada
      nao tem tela     a cena de login e montada -- camera fixa no ponto,
                       tela e fundo preto atras

    Um mapa que o programa nao consegue abrir nao interrompe a instalacao: o
    lobby ja esta no cliente e funciona: o que nao acontece e o ajuste, e
    isso fica dito.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    if formato is None:
        formato = l2mapa.FORMATO_MAIS_ALTO
    try:
        mapa = l2mapa.ler(mapa_no_cliente)
        for velho, novo in (renomes or {}).items():
            l2mapa.renomear_pacote(mapa, velho, novo)
        telas, fundos = l2mapa.telas_do_video(mapa, pacote_do_video)
        if telas:
            mudou = l2mapa.ajustar_tela_ao_formato(mapa, pacote_do_video, formato)
            for indice, velha, nova in mudou:
                anotar("%s #%d: escala %s -> %.2f"
                       % ("fundo" if indice in fundos else "tela", indice,
                          "%.2f" % velha if velha else "?", nova))
        else:
            resumo = l2mapa.instalar_video_no_login(mapa, pacote_do_video,
                                                   camera=camera,
                                                   formato=formato)
            anotar("cena %s: camera fixa em (%.0f, %.0f, %.0f), tela escala"
                   " %.2f e fundo preto"
                   % ((resumo["marca"] or "de login",) + tuple(resumo["camera"])
                      + (resumo["escala"],)))
        l2mapa.gravar(mapa, mapa_no_cliente)
        anotar("tela ajustada para cobrir ate o formato %.2f" % formato)
    except Exception as erro:                       # noqa: BLE001
        anotar("o mapa ficou como veio do modelo (%s)" % erro)


def quadros_do_video(dados, comeco, fim, orcamento=ORCAMENTO_PADRAO,
                     bytes_por_quadro=2048 * 2048 // 2):
    """
    Quantos quadros tirar do trecho, e o que o orcamento obrigou a cortar.

    A conta boa e simples -- cadencia vezes duracao do trecho -- e da o filme
    na velocidade do proprio video. So que cada quadro custa dois megabytes;
    passando do orcamento, a cadencia cai ate caber, e quem chamou fica sabendo
    para poder dizer.
    """
    duracao = max(0.05, float(fim) - float(comeco))
    fps = dados.get("fps") or 25.0
    pedido = max(2, int(round(fps * duracao)))
    cabem = max(2, int(orcamento // bytes_por_quadro))
    quantos = min(pedido, cabem)
    return {
        "quadros": quantos,
        "segundos": duracao,
        "pedido": pedido,
        "cortado": quantos < pedido,
        "por_segundo": quantos / duracao,
        "bytes": quantos * bytes_por_quadro,
    }


# ---------------------------------------------------------------------------
# O modelo embutido
# ---------------------------------------------------------------------------
# Do pacote de video de um lobby -- centenas de megabytes -- o programa aproveita
# so isto: a tabela de nomes, a de imports, os 562 bytes da malha da tela e meia
# duzia de constantes. Tudo junto nao chega a dez kilobytes, entao o molde viaja
# dentro do proprio executavel, e o usuario nunca precisa apontar pasta nenhuma.
#
# O mapa vem inteiro porque tem quatro megabytes e nao da para resumir: e ele
# que planta a tela na cena e aponta a camera.
PASTA_EMBUTIDA = "recursos/lobbies"
NOME_DO_MOLDE = "molde.json"


def _para_texto(molde):
    """O molde como estrutura simples, para virar JSON."""
    return {
        "versao": molde["versao"],
        "licenciado": molde["licenciado"],
        "flags": molde["flags"],
        "off_nomes": molde["off_nomes"],
        "flags_do_objeto": molde.get("flags_do_objeto", 0x000E0004),
        "nome_do_pacote": molde.get("nome_do_pacote", "M1"),
        "arquivo_do_pacote": molde.get("arquivo_do_pacote", "M1.usx"),
        "nome": molde.get("nome", "Lobby"),
        "largura_do_quadro": molde.get("largura_do_quadro", 2048),
        "altura_do_quadro": molde.get("altura_do_quadro", 2048),
        "rabo": molde["rabo"].hex(),
        "relogio": [c.hex() for c in molde.get("relogio", ())],
        "nomes": [[n, f] for n, f in molde["nomes"]],
        "imports": molde["imports"],
        "seq": {
            "propriedades": [[n, c.hex()]
                             for n, c in molde["seq"]["propriedades"]],
            "nativo": molde["seq"]["nativo"].hex(),
            "saltos": molde["seq"]["saltos"],
            "fim_das_propriedades": molde["seq"]["fim_das_propriedades"],
        },
    }


def _de_texto(cru):
    molde = dict(cru)
    molde["rabo"] = bytes.fromhex(cru["rabo"])
    molde["relogio"] = [bytes.fromhex(c) for c in cru.get("relogio", ())]
    molde["nomes"] = [(n, f) for n, f in cru["nomes"]]
    molde["seq"] = {
        "propriedades": [(n, bytes.fromhex(c))
                         for n, c in cru["seq"]["propriedades"]],
        "nativo": bytes.fromhex(cru["seq"]["nativo"]),
        "saltos": cru["seq"]["saltos"],
        "fim_das_propriedades": cru["seq"]["fim_das_propriedades"],
    }
    return molde


def gravar_molde(molde, caminho):
    """Guarda o molde num arquivo pequeno, legivel e versionavel."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(_para_texto(molde), indent=1),
                       encoding="utf-8")
    return caminho


def carregar_molde(caminho):
    return _de_texto(json.loads(Path(caminho).read_text(encoding="utf-8")))


def pasta_embutida():
    """Onde os modelos moram, tanto rodando do fonte quanto do executavel."""
    for raiz in (motor.AQUI, motor.BASE):
        caminho = Path(raiz) / PASTA_EMBUTIDA
        if caminho.is_dir():
            return caminho
    return Path(motor.AQUI) / PASTA_EMBUTIDA


# O cartao de visita de um lobby, dentro do zip dele. Sem ele, o nome sai do
# `LobbyInfo.txt` que os lobbys de cronica ja trazem.
NOME_DO_CARTAO = "lobby.json"


def _cartao_do_zip(caminho):
    """Nome, se leva video e de onde a camera olha -- sem descompactar nada."""
    cartao = {}
    try:
        with zipfile.ZipFile(caminho) as pacote:
            for dentro in pacote.namelist():
                baixo = dentro.lower()
                if baixo.endswith(NOME_DO_CARTAO):
                    cartao.update(json.loads(pacote.read(dentro).decode("utf-8")))
                elif baixo.endswith("lobbyinfo.txt") and "nome" not in cartao:
                    texto = pacote.read(dentro).decode("latin-1")
                    if '"' in texto:
                        cartao["nome"] = texto.split('"')[1].strip()
    except Exception:                               # noqa: BLE001
        return None
    return cartao


def _ler_embutido(caminho):
    """Um lobby compactado, lido pelo cartao. Nada sai do zip aqui."""
    cartao = _cartao_do_zip(caminho)
    if cartao is None:
        return None
    try:
        molde = carregar_molde(pasta_embutida() / NOME_DO_MOLDE)
    except Exception:                               # noqa: BLE001
        molde = {}
    return {"zip": caminho, "pasta": None, "pacote": None,
            "chave": caminho.stem,
            "mapa": None, "extras": [], "molde": molde,
            "nome": cartao.get("nome", caminho.stem),
            "largura": molde.get("largura_do_quadro", 2048),
            "altura": molde.get("altura_do_quadro", 2048),
            # O pacote de video leva o nome do sistema, e nao o do lobby de
            # origem: quem instala nao tem por que anunciar de onde ele veio.
            "nome_do_arquivo": "%s.usx" % versao.NOME,
            # do cartao: se este lobby e o que recebe video, de onde a camera
            # do login olha, e se e ele que vem escolhido ao abrir a aba
            "video": bool(cartao.get("video")),
            "camera": cartao.get("camera"),
            "padrao": bool(cartao.get("padrao"))}


def abrir_o_lobby(modelo, destino):
    """
    Descompacta o lobby e diz onde ficaram o mapa e o resto.

    Fica numa pasta temporaria: guardar os sete abertos em disco seria
    noventa megabytes parados para usar um de cada vez.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(modelo["zip"]) as pacote:
        pacote.extractall(destino)

    # o zip pode ter uma pasta so na raiz, como os das cronicas, ou nao
    raiz = destino
    dentro = [c for c in destino.iterdir()]
    if len(dentro) == 1 and dentro[0].is_dir():
        raiz = dentro[0]

    arquivos = [c for c in sorted(raiz.rglob("*"))
                if c.is_file() and c.suffix.lower() in EXTENSOES_DO_LOBBY]
    mapas = [c for c in arquivos if c.suffix.lower() == ".unr"]
    if not mapas:
        raise ErroCriacao("o lobby %s nao tem mapa dentro" % modelo["chave"])
    return dict(modelo, pasta=raiz, mapa=mapas[0],
                extras=[c for c in arquivos if c != mapas[0]])


def modelos_embutidos():
    """
    Todos os lobbys que acompanham o programa, um por zip.

    Acrescentar outro e largar outro `.zip` aqui -- nao ha codigo a mexer.
    Dentro dele, as pastas do cliente: `maps`, `staticmeshes`, `textures`,
    `music`, `system`.
    """
    pasta = pasta_embutida()
    if not pasta.is_dir():
        return []
    achados = []
    for arquivo in sorted(pasta.glob("*.zip")):
        modelo = _ler_embutido(arquivo)
        if modelo:
            achados.append(modelo)
    # o de video primeiro, e o resto em ordem
    achados.sort(key=lambda m: (not m["video"], m["chave"]))
    return achados


def modelo_embutido(chave=None):
    """O lobby pedido pela chave, ou o que se declarou padrao."""
    achados = modelos_embutidos()
    if not achados:
        return None
    if chave:
        for modelo in achados:
            if modelo["chave"] == chave or modelo["nome"] == chave:
                return modelo
    for modelo in achados:
        if modelo.get("padrao"):
            return modelo
    return achados[0]


def lobby_de_video(modelos=None):
    """O lobby que recebe o video. E nele que a tela e a camera sao montadas."""
    for modelo in (modelos or modelos_embutidos()):
        if modelo.get("video"):
            return modelo
    return None


# ---------------------------------------------------------------------------
# Lobby que mora numa pasta
# ---------------------------------------------------------------------------
# Um lobby de cenario inteiro passa de um gigabyte: ele nao cabe dentro do
# executavel. Fica numa pasta, o usuario aponta, e o programa le de la.
#
# Muitos desses lobbys nao tem tela de video -- sao so cenario. Nesse caso o
# molde que sabe MONTAR o pacote de video continua sendo o embutido, e a tela
# e plantada no mapa na hora de instalar.
EXTENSOES_DO_LOBBY = (".utx", ".usx", ".uax", ".ukx", ".unr", ".dat",
                      ".ogg", ".mp3")


