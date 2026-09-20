#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icone proprio: de uma imagem qualquer a um pacote que o cliente carrega.

Item e habilidade guardam o icone como um texto, `pacote.objeto`. Escolher um
que ja existe e so escrever esse texto; usar um desenho seu exige que o desenho
esteja DENTRO de um pacote Unreal que o cliente saiba abrir. E isso que este
modulo faz, com o caminho que o resto do programa ja usa para textura:

    imagem -> 32x32 RGBA -> DDS comprimido -> `ucc make` -> .u -> Ver121 -> .utx

## Pacote novo, e nao o do cliente

O programa SEMPRE grava num pacote proprio, nunca dentro do Icon.u ou do
Icon.utx do cliente. A razao e de risco, nao de dificuldade: acrescentar um
objeto a um pacote existente obriga a reescrever as tabelas de nome e de
exportacao, e um erro ali nao estraga o icone novo -- estraga os catorze mil
que ja estavam la.

Nao ha perda: o cliente resolve `Pacote.Objeto` procurando `Pacote.utx` nas
pastas de textura, e este cliente ja carrega varios pacotes de icone avulsos
(`IconsByAllInOne`, `MAYKE_MENDES_ICON`, `cartola_by_SHEV`). Um a mais e
rotina.

Acrescentar um segundo icone ao pacote proprio remonta o pacote inteiro: os que
ja estavam sao extraidos de volta e entram junto. E lento, e e o unico jeito
honesto -- meia remontagem deixaria o pacote sem os icones antigos.

## O nome do arquivo importa

A chave do Lineage2Ver121 deriva do NOME DO ARQUIVO. Por isso a criptografia e
sempre feita com o nome final: gravar como temporario e renomear depois produz
um arquivo que o cliente nao decifra.
"""

import re
import shutil
from pathlib import Path

import l2conferir
import l2upscale as motor

try:
    from PIL import Image
except ImportError:
    Image = None

# O tamanho em que o cliente desenha o icone de item e de habilidade.
LADO = 32

# Onde o pacote de icones e instalado. E a pasta que o cliente varre atras de
# textura de interface.
PASTA_NO_CLIENTE = "systextures"

PACOTE_PADRAO = "L2PackToolIcons"

# Nome de objeto Unreal: letra ou sublinhado, depois letras, numeros e
# sublinhado. Espaco e acento passam pelo ucc mas viram dor de cabeca na hora
# de escrever a referencia.
_NOME_VALIDO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,60}$")


class ErroDeIcone(Exception):
    pass


def nome_valido(nome):
    return bool(_NOME_VALIDO.match(nome or ""))


def limpar_nome(texto):
    """Transforma um nome qualquer num nome de objeto aceitavel."""
    limpo = re.sub(r"[^A-Za-z0-9_]", "_", (texto or "").strip())
    limpo = re.sub(r"_+", "_", limpo).strip("_")
    if not limpo:
        limpo = "icone"
    if limpo[0].isdigit():
        limpo = "i_" + limpo
    return limpo[:60]


def pacote_no_cliente(cliente, nome_do_pacote):
    """O .utx daquele nome dentro do cliente, se existir."""
    raiz = l2conferir.raiz_do_cliente(cliente)
    for pasta in (PASTA_NO_CLIENTE, "textures", "system"):
        diretorio = raiz / pasta
        if not diretorio.is_dir():
            continue
        for item in diretorio.iterdir():
            if (item.is_file() and item.suffix.lower() in l2conferir.EXTENSOES
                    and item.stem.lower() == nome_do_pacote.lower()):
                return item
    return None


def objetos_de(caminho):
    """Os icones que ja estao no pacote. Lista vazia se ele nao abrir assim."""
    try:
        return l2conferir.objetos_do_pacote(caminho)
    except Exception:
        return []


def eh_do_cliente(cliente, nome_do_pacote):
    """
    O pacote e um dos originais do jogo?

    Icon.u e Icon.utx do cliente tem milhares de objetos e nenhum deles e
    nosso. Remontar um desses e a unica operacao aqui capaz de estragar o que
    ja funciona, entao ela simplesmente nao acontece.
    """
    achado = pacote_no_cliente(cliente, nome_do_pacote)
    if achado is None:
        return False
    return len(objetos_de(achado)) > 200


# ---------------------------------------------------------------------------
# A imagem
# ---------------------------------------------------------------------------
def preparar(origem, destino, lado=LADO, T=None):
    """
    Deixa a imagem do jeito que o pacote precisa: quadrada, `lado` x `lado`,
    RGBA.

    O redimensionamento e LANCZOS quando encolhe -- que e o caso quase sempre,
    porque desenho de icone costuma vir grande. Imagem nao quadrada e encaixada
    no centro de um quadrado transparente, em vez de esticada: esticar um
    retangulo para 32x32 deforma o desenho.
    """
    if Image is None:
        raise ErroDeIcone("o Pillow nao esta instalado; sem ele nao da para "
                          "preparar a imagem.")
    origem = Path(origem)
    if not origem.is_file():
        raise ErroDeIcone("nao achei a imagem %s" % origem)

    imagem = motor.abrir_imagem(origem, T)
    if imagem.size != (lado, lado):
        largura, altura = imagem.size
        escala = float(lado) / max(largura, altura)
        novo = (max(1, int(round(largura * escala))),
                max(1, int(round(altura * escala))))
        imagem = imagem.resize(novo, Image.LANCZOS)
        if novo != (lado, lado):
            fundo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
            fundo.paste(imagem, ((lado - novo[0]) // 2, (lado - novo[1]) // 2))
            imagem = fundo

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino, "PNG")
    return destino


# ---------------------------------------------------------------------------
# O pacote
# ---------------------------------------------------------------------------
def montar_pacote(T, nome_do_pacote, imagens, trabalho, aolog=None):
    """
    Constroi o .utx a partir de {nome do objeto: caminho de imagem}.

    Devolve o caminho do .utx pronto, ainda no diretorio de trabalho.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    faltam = [n for n in ("texconv", "ucc") if not Path(T.get(n, "")).exists()]
    if faltam:
        raise ErroDeIcone("faltam as ferramentas: %s" % ", ".join(faltam))
    if not imagens:
        raise ErroDeIcone("nenhuma imagem para por no pacote.")

    trabalho = Path(trabalho)
    prontas = trabalho / "png"
    shutil.rmtree(prontas, ignore_errors=True)
    prontas.mkdir(parents=True)

    for nome, origem in sorted(imagens.items()):
        if not nome_valido(nome):
            raise ErroDeIcone("o nome %r nao serve para objeto do pacote." % nome)
        preparar(origem, prontas / (nome + ".png"), T=T)
    anotar("%d imagem(ns) preparada(s) em %dx%d" % (len(imagens), LADO, LADO))

    dds = trabalho / "dds"
    shutil.rmtree(dds, ignore_errors=True)
    comprimidas = motor.comprimir(T, prontas, dds, aviso=anotar)
    if not comprimidas:
        raise ErroDeIcone("o texconv nao comprimiu nada.")
    anotar("%d textura(s) comprimida(s)" % len(comprimidas))

    # Sem grupo: o icone mora na raiz do pacote, que e como o cliente o pede
    # (`Pacote.objeto`, e nao `Pacote.grupo.objeto`).
    grupos = dict((d.stem, "") for d in comprimidas)
    editor = Path(T["ucc"]).parent.parent
    cru, log = motor.montar(T, nome_do_pacote, comprimidas, editor,
                            grupos=grupos)
    if cru is None:
        raise ErroDeIcone("o ucc nao gerou o pacote. Fim do registro:\n%s"
                          % "\n".join(log.strip().split("\n")[-6:]))
    anotar("pacote montado: %s" % cru.name)

    final = trabalho / (nome_do_pacote + ".utx")
    final.unlink(missing_ok=True)
    motor.criptografar(T, cru, final.name, trabalho, cifrar=True, versao="121")
    cru.unlink(missing_ok=True)
    if not final.exists():
        raise ErroDeIcone("a criptografia nao gravou o .utx.")

    conferir(final, sorted(imagens))
    anotar("%s pronto (%.0f KB)" % (final.name, final.stat().st_size / 1024.0))
    return final


def conferir(caminho, esperados):
    """
    Abre o que acabou de sair e confere que os icones estao la dentro.

    Num .utx isto e prova de verdade: a chave do Ver121 deriva do nome do
    arquivo, entao um pacote gravado com o nome errado nem decifra. O erro
    aparece aqui, e nao na tela de inventario.
    """
    try:
        dentro = set(o.lower() for o in l2conferir.objetos_do_pacote(caminho))
    except Exception as erro:
        raise ErroDeIcone("o pacote gerado nao abriu: %s" % erro)

    faltando = [n for n in esperados if n.lower() not in dentro]
    if faltando:
        raise ErroDeIcone("o pacote saiu sem: %s" % ", ".join(faltando[:6]))
    return sorted(dentro)


def extrair_existentes(T, pacote, trabalho, aolog=None):
    """
    Tira do pacote as texturas que ja estao nele, para entrarem na remontagem.

    Sem isto, acrescentar o segundo icone apagaria o primeiro.
    """
    trabalho = Path(trabalho)
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)
    nomes = objetos_de(pacote)
    if not nomes:
        return {}

    gravados = motor.exportar(T, pacote, nomes, trabalho, aolog=aolog)
    achadas = {}
    for arquivo in gravados:
        achadas[arquivo.stem] = arquivo
    if aolog:
        aolog("%d icone(s) recuperado(s) do pacote que ja existia"
              % len(achadas))
    return achadas


def acrescentar(T, cliente, nome_do_pacote, nome_do_objeto, imagem, trabalho,
                aolog=None, instalar_no_cliente=True):
    """Como `montar_para_o_cliente`, devolvendo so a referencia."""
    return montar_para_o_cliente(T, cliente, nome_do_pacote, nome_do_objeto,
                                 imagem, trabalho, aolog,
                                 instalar_no_cliente)[0]


def montar_para_o_cliente(T, cliente, nome_do_pacote, nome_do_objeto, imagem,
                          trabalho, aolog=None, instalar_no_cliente=True):
    """
    O caminho inteiro: imagem -> pacote -> cliente.

    Devolve `(referencia, caminho do .utx)`. O caminho importa para quem vai
    instalar depois, junto com as tabelas: refaze-lo por fora daria errado no
    dia em que o nome do arquivo deixasse de ser o nome do pacote.

    Se o pacote ja existe no cliente e foi feito aqui, o que estava dentro e
    recuperado e remontado junto. Se for um pacote original do jogo, recusa --
    remontar o Icon.utx do cliente poria catorze mil icones em risco por causa
    de um.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    nome_do_pacote = (nome_do_pacote or PACOTE_PADRAO).strip()
    if not nome_valido(nome_do_pacote):
        raise ErroDeIcone("o nome de pacote %r nao serve." % nome_do_pacote)
    nome_do_objeto = (nome_do_objeto or "").strip()
    if not nome_valido(nome_do_objeto):
        raise ErroDeIcone("o nome de ícone %r nao serve. Use letras, numeros e "
                          "sublinhado." % nome_do_objeto)

    if eh_do_cliente(cliente, nome_do_pacote):
        raise ErroDeIcone(
            "%s e um pacote original do cliente, com milhares de icones "
            "dentro. Escolha outro nome de pacote -- o programa cria um novo e "
            "o cliente carrega os dois." % nome_do_pacote)

    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)

    imagens = {}
    existente = pacote_no_cliente(cliente, nome_do_pacote)
    if existente is not None:
        anotar("%s ja existe no cliente; recuperando o que ha dentro"
               % existente.name)
        imagens.update(extrair_existentes(T, existente,
                                          trabalho / "antigos", aolog=aolog))
    if nome_do_objeto in imagens:
        anotar("%s ja existia no pacote e vai ser substituido" % nome_do_objeto)
    imagens[nome_do_objeto] = Path(imagem)

    pacote = montar_pacote(T, nome_do_pacote, imagens, trabalho / "montagem",
                           aolog=anotar)
    if instalar_no_cliente:
        instalar(pacote, cliente, aolog=anotar)
    return "%s.%s" % (nome_do_pacote, nome_do_objeto), pacote


PASTA_GUARDA = "backup_icones"


def instalar(pacote, cliente, aolog=None):
    """
    Poe o pacote na pasta de texturas do cliente, guardando o que estava la.

    A copia vai primeiro para um nome provisorio e so depois e renomeada: um
    cliente com meio .utx nao abre.
    """
    raiz = l2conferir.raiz_do_cliente(cliente)
    destino_pasta = None
    for nome in (PASTA_NO_CLIENTE, "textures"):
        candidato = raiz / nome
        if candidato.is_dir():
            destino_pasta = candidato
            break
    if destino_pasta is None:
        destino_pasta = raiz / PASTA_NO_CLIENTE
        destino_pasta.mkdir(parents=True, exist_ok=True)

    pacote = Path(pacote)
    destino = destino_pasta / pacote.name
    if destino.exists():
        guarda = destino_pasta / PASTA_GUARDA
        guarda.mkdir(exist_ok=True)
        import time
        copia = guarda / ("%s_%s" % (time.strftime("%Y%m%d_%H%M%S"),
                                     destino.name))
        shutil.copy2(destino, copia)
        if aolog:
            aolog("o %s que estava la foi para %s" % (destino.name, copia.name))

    provisorio = destino.with_suffix(destino.suffix + ".parcial")
    provisorio.unlink(missing_ok=True)
    shutil.copy2(pacote, provisorio)
    provisorio.replace(destino)
    if aolog:
        aolog("instalado em %s" % destino)
    return destino
