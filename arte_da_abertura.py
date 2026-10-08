#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Desenha `recursos/abertura.png`, a imagem que o PyInstaller mostra enquanto o
executável se descompacta.

Tem de ser a MESMA cara de `abertura.py` -- tamanho, cores, posição da logo,
do nome, da versão e da barra --, porque a janela animada abre exatamente em
cima dela e a fecha. Qualquer diferença vira um piscar na troca.

Roda a cada compilação (`compilar.py` chama), porque a versão está escrita
na imagem.

    python arte_da_abertura.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import abertura
import tema
import versao

BASE = Path(__file__).parent
SAIDA = BASE / "recursos" / "abertura.png"
FONTES = Path(r"C:\Windows\Fonts")


def _cor(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


def _fonte(arquivo, pontos):
    # o Tk mede em pontos a 96 dpi: 1 pt = 96/72 px
    try:
        return ImageFont.truetype(str(FONTES / arquivo), round(pontos * 96 / 72))
    except OSError:
        return ImageFont.load_default()


def _centro(desenho, y, texto, fonte, cor):
    caixa = desenho.textbbox((0, 0), texto, font=fonte, anchor="mm")
    desenho.text((abertura.LARGURA // 2, y), texto, font=fonte, fill=cor, anchor="mm")
    return caixa


def desenhar(saida=SAIDA):
    L, A = abertura.LARGURA, abertura.ALTURA
    img = Image.new("RGB", (L, A), _cor(tema.OURO))
    d = ImageDraw.Draw(img)
    d.rectangle((1, 1, L - 2, A - 2), fill=_cor(tema.ABISSO))

    with Image.open(BASE / "recursos" / "logo.png") as bruto:
        logo = bruto.convert("RGBA")
        alt = 78
        larg = max(1, int(logo.width * alt / float(logo.height)))
        logo = logo.resize((larg, alt), Image.LANCZOS)
    img.paste(logo, (L // 2 - larg // 2, 92 - alt // 2), logo)

    _centro(d, 168, "L2PackTool", _fonte("segoeuib.ttf", 20), _cor(tema.OURO))
    texto_versao = "versão %s" % ".".join(str(n) for n in versao.VERSAO[:3])
    _centro(d, 198, texto_versao, _fonte("segoeui.ttf", 10), _cor(tema.TEXTO_FRACO))

    x, y = abertura.BARRA_X, abertura.BARRA_Y
    d.rectangle((x, y, x + abertura.BARRA_L - 1, y + abertura.BARRA_A - 1),
                fill=_cor(tema.PAINEL))
    # o mesmo texto com que a abertura animada comeca -- a troca nao aparece
    _centro(d, abertura.TEXTO_Y, "Carregando o sistema…",
            _fonte("segoeui.ttf", 9), _cor(tema.TEXTO_FRACO))
    _centro(d, A - 22, "ferramentas de cliente e servidor para Lineage II",
            _fonte("segoeui.ttf", 8), _cor(tema.TEXTO_APAGADO))

    saida.parent.mkdir(parents=True, exist_ok=True)
    img.save(saida)
    return saida



if __name__ == "__main__":
    print(desenhar())
