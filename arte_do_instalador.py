#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
As imagens do instalador, desenhadas a partir da marca e da paleta.

O Inno Setup mostra duas: o painel alto da esquerda, nas telas de abertura e
de fim, e o selo pequeno do canto superior direito, nas demais. Ele quer
BMP -- PNG nao serve -- e escolhe sozinho o tamanho mais proximo da escala
do monitor, entao cada uma sai em varias medidas. Numa tela de 200% o painel
de 164 pixels ficaria borrado.

O desenho nao inventa identidade: fundo, ouro e tipografia sao os mesmos de
`tema.py`, que e o que o usuario ja ve na janela do programa.

    python arte_do_instalador.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

import tema

BASE = Path(__file__).parent
PASTA = BASE / "recursos" / "instalador"
LOGO = BASE / "recursos" / "logo.png"
ICONE = BASE / "recursos" / "icone.ico"

# As escalas que o Inno procura. A de 100% e a medida de referencia; as
# outras sao a mesma arte redesenhada, e nao esticada.
ESCALAS = (1.0, 1.25, 1.5, 1.75, 2.0)
PAINEL = (164, 314)         # WizardImageFile
SELO = (55, 58)             # WizardSmallImageFile


def cor(texto):
    """De `#rrggbb` para (r, g, b)."""
    texto = texto.lstrip("#")
    return tuple(int(texto[i:i + 2], 16) for i in (0, 2, 4))


def degrade(largura, altura, de_cima, de_baixo):
    """Um fundo que escurece de cima para baixo, na diagonal."""
    imagem = Image.new("RGB", (largura, altura))
    pixels = imagem.load()
    for y in range(altura):
        for x in range(largura):
            # a diagonal faz a luz vir do alto a esquerda, como no programa
            t = (y / altura) * 0.82 + (1 - x / largura) * 0.18
            pixels[x, y] = tuple(
                int(de_cima[c] + (de_baixo[c] - de_cima[c]) * t)
                for c in range(3))
    return imagem


def painel(escala):
    """O painel alto da esquerda, com a marca e um fio de ouro."""
    largura, altura = (int(round(PAINEL[0] * escala)),
                       int(round(PAINEL[1] * escala)))
    imagem = degrade(largura, altura, cor(tema.PAINEL), cor(tema.ABISSO))
    desenho = ImageDraw.Draw(imagem)

    # a marca, no terco de cima, com margem de um oitavo da largura
    marca = Image.open(LOGO).convert("RGBA")
    alvo = int(largura * 0.76)
    marca = marca.resize((alvo, max(1, int(marca.height * alvo / marca.width))),
                         Image.LANCZOS)
    imagem.paste(marca, ((largura - marca.width) // 2,
                         int(altura * 0.30) - marca.height // 2), marca)

    # o fio de ouro, logo abaixo da marca
    y = int(altura * 0.38)
    meio = largura // 2
    braco = int(largura * 0.24)
    desenho.line([(meio - braco, y), (meio + braco, y)],
                 fill=cor(tema.OURO), width=max(1, int(escala)))

    # A versao NAO entra aqui. Desenhada, ela obrigaria a regerar os cinco
    # BMPs a cada numero novo -- e a esquecer de regerar em algum deles, que
    # e como um instalador acaba anunciando a versao errada. O numero vive
    # nos lugares onde e lido por programa: o recurso dos executaveis, o
    # cabecalho do instalador, o nome do arquivo de saida e a tela de Sobre.
    return imagem


def selo(escala):
    """O selo pequeno do canto: so o icone, sobre o mesmo fundo."""
    largura, altura = (int(round(SELO[0] * escala)),
                       int(round(SELO[1] * escala)))
    imagem = degrade(largura, altura, cor(tema.PAINEL), cor(tema.ABISSO))
    icone = Image.open(ICONE).convert("RGBA")
    alvo = int(min(largura, altura) * 0.74)
    icone = icone.resize((alvo, alvo), Image.LANCZOS)
    imagem.paste(icone, ((largura - alvo) // 2, (altura - alvo) // 2), icone)
    return imagem


def nome(prefixo, escala):
    """`painel-100.bmp`, `painel-125.bmp`... como o Inno espera ler."""
    return "%s-%d.bmp" % (prefixo, int(round(escala * 100)))


def escrever():
    PASTA.mkdir(parents=True, exist_ok=True)
    feitos = []
    for escala in ESCALAS:
        for prefixo, desenhar in (("painel", painel), ("selo", selo)):
            alvo = PASTA / nome(prefixo, escala)
            desenhar(escala).save(alvo, "BMP")
            feitos.append(alvo)
    return feitos


if __name__ == "__main__":
    for caminho in escrever():
        imagem = Image.open(caminho)
        print("%-22s %sx%s  %d KB"
              % (caminho.name, imagem.width, imagem.height,
                 caminho.stat().st_size // 1024))
