#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O tema da interface: paleta, tipografia, métrica e o estilo de cada widget.

O programa nasceu no tema `vista` do ttk -- o cinza de fábrica do Windows, com
cada tela escolhendo as próprias cores em constantes soltas. Funcionava e
parecia um utilitário de 2009.

Aqui a interface inteira passa a sair de um lugar só. Não é troca de cor: é
**escala de tipo**, **régua de espaçamento** e **estilo por função**, que é o
que separa uma tela desenhada de uma tela pintada.

## A direção

Lineage 2 tem uma linguagem visual conhecida: fundo escuro, quase preto, com
metal envelhecido e ouro gasto por cima. É o que a paleta persegue -- mas sem
virar fantasia: os grounds são neutros e frios, o ouro aparece **num lugar de
cada vez**, e o texto tem contraste de leitura, não de pôster.

O acento é ouro (`#c9a227`). Ele marca o que está ativo, o que está marcado e o
que é a ação principal. Fora disso, nada é dourado -- acento em tudo é acento
em nada.

## A escala de tipo

Quatro papéis, e só:

    TITULO    12pt semibold   o nome da tela
    SUBTITULO 10pt bold       o cabeçalho de um quadro
    CORPO      9pt            tudo o que se lê
    MIUDO      8pt            legenda, contagem, dica

E uma família de largura fixa para o que é código: XML, log, id.

## A régua

Espaçamento em múltiplos de 4. Um controle respira 8; um quadro, 12; uma
seção, 16. Nada de `padx=7` porque ficou bom naquele lugar.

## Por que `clam`

É o único tema embutido do ttk que aceita configurar cor de verdade em todos os
elementos. `vista` e `xpnative` desenham com o tema do sistema operacional e
ignoram metade do que se pede -- num tema escuro isso deixa campo branco no
meio da tela.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


# =========================================================================
# a paleta
# =========================================================================
# Os grounds, do mais fundo para o mais próximo. A janela é o mais escuro; o
# que está por cima dela vem clareando, que é como o olho lê profundidade.
ABISSO = "#14171c"          # o fundo da janela
FUNDO = "#1b1e24"           # a superfície das abas
PAINEL = "#232831"          # quadro, cabeçalho de lista
ELEVADO = "#2b313c"         # campo, botão, o que aceita clique
REALCE = "#343b48"          # o mesmo, com o ponteiro em cima

# As bordas. Duas: a que separa e a que contorna o que está em foco.
BORDA = "#323a46"
BORDA_FORTE = "#46505f"

# O texto. Nunca branco puro -- num fundo escuro ele vibra e cansa.
TEXTO = "#dfe4ea"
TEXTO_FRACO = "#8b96a5"
TEXTO_APAGADO = "#5c6675"

# O acento: ouro gasto. Marca o ativo, o marcado e a ação principal.
OURO = "#c9a227"
OURO_CLARO = "#e3bf4a"
OURO_FUNDO = "#3a3320"      # o ouro rebaixado, para fundo de linha marcada

# Semântica. Separada do acento de propósito: "deu certo" não é "isto é o
# principal", e pintar os dois de ouro apaga a diferença.
BOM = "#6aa84f"
ATENCAO = "#d1913a"
RUIM = "#c0553f"
INFO = "#5b8db8"

# O mesmo trio rebaixado a fundo. São as faixas de aviso da tela de conferência
# -- no tema claro elas eram pastel; aqui a cor precisa vir do outro lado, o
# tanto suficiente para separar a faixa do painel sem competir com o texto.
FUNDO_BOM = "#1e2c22"
FUNDO_ATENCAO = "#33291a"
FUNDO_RUIM = "#33211d"

# Compatibilidade com o nome antigo que as telas usavam.
COR_TEXTO_FRACO = TEXTO_FRACO
COR_FUNDO_ICONE = "#141821"


# =========================================================================
# a tipografia e a régua
# =========================================================================
FAMILIA = "Segoe UI"
FAMILIA_FIXA = "Consolas"

TITULO = (FAMILIA, 12, "bold")
SUBTITULO = (FAMILIA, 10, "bold")
CORPO = (FAMILIA, 9)
CORPO_FORTE = (FAMILIA, 9, "bold")
MIUDO = (FAMILIA, 8)
FIXA = (FAMILIA_FIXA, 9)

# Espaçamento em múltiplos de 4, com nome em vez de número solto.
COLADO = 4
PERTO = 8
FOLGA = 12
SECAO = 16

ALTURA_DA_LINHA = 26        # lista comum
ALTURA_COM_ICONE = 38       # lista que mostra desenho de 32


def _fonte(nome, familia, tamanho, peso="normal"):
    """Registra uma fonte nomeada, para o Tk usar a mesma em toda parte."""
    try:
        f = tkfont.nametofont(nome)
    except tk.TclError:
        f = tkfont.Font(name=nome, exists=False)
    f.configure(family=familia, size=tamanho, weight=peso)
    return f


def aplicar(raiz):
    """
    Veste a janela inteira. Chamar uma vez, logo depois de criar a raiz.

    Devolve o `ttk.Style`, para quem precisar acrescentar um estilo próprio
    depois -- é o caso das listas que desenham ícone e pedem linha mais alta.
    """
    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass                    # tema ausente: o resto ainda melhora o que dá

    # ---- as fontes que o Tk usa sozinho -------------------------------
    _fonte("TkDefaultFont", FAMILIA, 9)
    _fonte("TkTextFont", FAMILIA, 9)
    _fonte("TkMenuFont", FAMILIA, 9)
    _fonte("TkHeadingFont", FAMILIA, 9, "bold")
    _fonte("TkFixedFont", FAMILIA_FIXA, 9)

    raiz.configure(background=ABISSO)

    # ---- os widgets crus do tk, que nao passam pelo ttk ---------------
    # `option_add` alcanca Text, Canvas, Listbox e Menu, que sao os quatro que
    # o programa usa fora do ttk. Sem isto eles ficam brancos no meio do escuro.
    for padrao, valor in (
            ("*Text.background", PAINEL),
            ("*Text.foreground", TEXTO),
            ("*Text.insertBackground", OURO),
            ("*Text.selectBackground", OURO_FUNDO),
            ("*Text.selectForeground", TEXTO),
            ("*Text.highlightThickness", 0),
            ("*Text.borderWidth", 0),
            ("*Text.font", "TkFixedFont"),
            ("*Canvas.background", FUNDO),
            ("*Canvas.highlightThickness", 0),
            ("*Listbox.background", PAINEL),
            ("*Listbox.foreground", TEXTO),
            ("*Menu.background", PAINEL),
            ("*Menu.foreground", TEXTO),
            ("*Menu.activeBackground", OURO_FUNDO),
            ("*Menu.activeForeground", TEXTO),
            ("*Menu.borderWidth", 0),
            ("*Toplevel.background", FUNDO)):
        raiz.option_add(padrao, valor)

    _base(estilo)
    _botoes(estilo)
    _campos(estilo)
    _listas(estilo)
    _abas(estilo)
    _barras(estilo)
    return estilo


# =========================================================================
# base: o que todo widget herda
# =========================================================================
def _base(estilo):
    estilo.configure(".", background=FUNDO, foreground=TEXTO,
                     fieldbackground=ELEVADO, bordercolor=BORDA,
                     lightcolor=BORDA, darkcolor=BORDA,
                     troughcolor=ABISSO, font=CORPO, borderwidth=1,
                     focuscolor=OURO)

    estilo.configure("TFrame", background=FUNDO)
    estilo.configure("TLabel", background=FUNDO, foreground=TEXTO, font=CORPO)

    # Os papéis de texto. Ter nome em vez de repetir `font=("Segoe UI", 8)` em
    # cada tela é o que mantém a escala de pé quando alguém acrescenta uma.
    estilo.configure("Titulo.TLabel", font=TITULO, foreground=TEXTO)
    estilo.configure("Subtitulo.TLabel", font=SUBTITULO, foreground=TEXTO)
    estilo.configure("Fraco.TLabel", font=CORPO, foreground=TEXTO_FRACO)
    estilo.configure("Miudo.TLabel", font=MIUDO, foreground=TEXTO_FRACO)
    estilo.configure("Fixa.TLabel", font=FIXA, foreground=TEXTO)
    estilo.configure("Bom.TLabel", foreground=BOM)
    estilo.configure("Atencao.TLabel", foreground=ATENCAO)
    estilo.configure("Ruim.TLabel", foreground=RUIM)
    estilo.configure("Ouro.TLabel", foreground=OURO, font=CORPO_FORTE)

    # O quadro com título: fundo um passo acima do da aba, e o título em
    # maiúscula espaçada -- é o que faz ele ler como seção e não como caixa.
    estilo.configure("TLabelframe", background=FUNDO, bordercolor=BORDA,
                     borderwidth=1, relief="solid")
    estilo.configure("TLabelframe.Label", background=FUNDO, foreground=OURO,
                     font=(FAMILIA, 8, "bold"))

    estilo.configure("TSeparator", background=BORDA)
    estilo.configure("TPanedwindow", background=ABISSO)
    estilo.configure("Sash", sashthickness=6, gripcount=0)


# =========================================================================
# botões
# =========================================================================
def _botoes(estilo):
    estilo.configure("TButton", background=ELEVADO, foreground=TEXTO,
                     bordercolor=BORDA_FORTE, focusthickness=1,
                     focuscolor=OURO, padding=(FOLGA, COLADO + 1),
                     relief="flat", font=CORPO)
    estilo.map("TButton",
               background=[("disabled", FUNDO), ("pressed", PAINEL),
                           ("active", REALCE)],
               foreground=[("disabled", TEXTO_APAGADO)],
               bordercolor=[("disabled", BORDA), ("active", BORDA_FORTE)])

    # A ação principal da tela. Uma por tela: se duas coisas são principais,
    # nenhuma é.
    estilo.configure("Primario.TButton", background=OURO, foreground=ABISSO,
                     bordercolor=OURO, font=CORPO_FORTE)
    estilo.map("Primario.TButton",
               background=[("disabled", PAINEL), ("pressed", OURO),
                           ("active", OURO_CLARO)],
               foreground=[("disabled", TEXTO_APAGADO)],
               bordercolor=[("disabled", BORDA), ("active", OURO_CLARO)])

    # O que destrói alguma coisa. Vermelho só na borda: um botão inteiro
    # vermelho grita mais alto do que o perigo merece.
    estilo.configure("Perigo.TButton", foreground=RUIM, bordercolor=RUIM)
    estilo.map("Perigo.TButton",
               background=[("active", "#3a2420")],
               foreground=[("disabled", TEXTO_APAGADO)])

    # `indicatorbackground` e `indicatorforeground` -- e NAO `indicatorcolor`.
    #
    # O `clam` desenha a caixinha com esses dois; `indicatorcolor` existe
    # noutros temas e ali e ignorado. Estilizando o nome errado, a caixa ficava
    # com a MESMA cara marcada e desmarcada: a variavel alternava, o desenho
    # nao, e a impressao era a de um controle que nao responde.
    #
    # Marcada: fundo de ouro com o sinal escuro. E o unico par da paleta que
    # nao deixa duvida a um metro da tela.
    for classe in ("TCheckbutton", "TRadiobutton"):
        estilo.configure(classe, background=FUNDO, foreground=TEXTO,
                         focuscolor=OURO, padding=COLADO,
                         indicatorbackground=ELEVADO,
                         indicatorforeground=ABISSO,
                         upperbordercolor=BORDA_FORTE,
                         lowerbordercolor=BORDA_FORTE)
        estilo.map(classe,
                   indicatorbackground=[("disabled", FUNDO),
                                        ("selected", OURO),
                                        ("active", REALCE)],
                   indicatorforeground=[("disabled", TEXTO_APAGADO),
                                        ("selected", ABISSO)],
                   upperbordercolor=[("active", OURO), ("selected", OURO)],
                   lowerbordercolor=[("active", OURO), ("selected", OURO)],
                   foreground=[("disabled", TEXTO_APAGADO)],
                   background=[("active", FUNDO)])


# =========================================================================
# campos
# =========================================================================
def _campos(estilo):
    # O anel de foco é o ouro. Num formulário de trinta campos, saber onde o
    # cursor está é a diferença entre digitar e procurar.
    estilo.configure("TEntry", fieldbackground=ELEVADO, foreground=TEXTO,
                     bordercolor=BORDA, lightcolor=BORDA, darkcolor=BORDA,
                     insertcolor=OURO, padding=(PERTO - 2, COLADO + 1))
    estilo.map("TEntry",
               bordercolor=[("focus", OURO), ("hover", BORDA_FORTE)],
               lightcolor=[("focus", OURO)], darkcolor=[("focus", OURO)],
               fieldbackground=[("disabled", FUNDO), ("readonly", PAINEL)],
               foreground=[("disabled", TEXTO_APAGADO)])

    estilo.configure("TCombobox", fieldbackground=ELEVADO, background=ELEVADO,
                     foreground=TEXTO, bordercolor=BORDA, arrowcolor=TEXTO_FRACO,
                     lightcolor=BORDA, darkcolor=BORDA,
                     padding=(PERTO - 2, COLADO))
    estilo.map("TCombobox",
               bordercolor=[("focus", OURO), ("hover", BORDA_FORTE)],
               lightcolor=[("focus", OURO)], darkcolor=[("focus", OURO)],
               arrowcolor=[("hover", OURO), ("disabled", TEXTO_APAGADO)],
               fieldbackground=[("readonly", ELEVADO), ("disabled", FUNDO)],
               foreground=[("disabled", TEXTO_APAGADO)])

    estilo.configure("TSpinbox", fieldbackground=ELEVADO, foreground=TEXTO,
                     bordercolor=BORDA, arrowcolor=TEXTO_FRACO)

    estilo.configure("TScale", background=FUNDO, troughcolor=ABISSO,
                     bordercolor=BORDA, lightcolor=OURO, darkcolor=OURO)
    estilo.map("TScale", background=[("active", FUNDO)])


# =========================================================================
# listas
# =========================================================================
def _listas(estilo):
    estilo.configure("Treeview", background=PAINEL, fieldbackground=PAINEL,
                     foreground=TEXTO, bordercolor=BORDA, borderwidth=0,
                     rowheight=ALTURA_DA_LINHA, font=CORPO)
    estilo.map("Treeview",
               background=[("selected", OURO_FUNDO)],
               foreground=[("selected", TEXTO)])

    # O cabeçalho não é uma linha da lista: fundo próprio, texto miúdo em
    # maiúscula, e uma borda só embaixo para separar sem desenhar grade.
    estilo.configure("Treeview.Heading", background=ELEVADO,
                     foreground=TEXTO_FRACO, font=(FAMILIA, 8, "bold"),
                     relief="flat", borderwidth=0,
                     padding=(PERTO - 2, COLADO + 1))
    estilo.map("Treeview.Heading",
               background=[("active", REALCE)],
               foreground=[("active", OURO)])

    # A variante de linha alta, para as listas que mostram ícone de 32.
    estilo.configure("Icone.Treeview", rowheight=ALTURA_COM_ICONE)
    estilo.configure("Icone.Treeview.Heading", background=ELEVADO,
                     foreground=TEXTO_FRACO, font=(FAMILIA, 8, "bold"),
                     relief="flat", padding=(PERTO - 2, COLADO + 1))


# =========================================================================
# abas
# =========================================================================
def _abas(estilo):
    estilo.configure("TNotebook", background=ABISSO, borderwidth=0,
                     tabmargins=(0, 0, 0, 0))
    # A aba ativa sobe: fica da cor da superfície e ganha um fio de ouro em
    # cima. É o mesmo truque de sempre, e continua sendo o mais legível.
    estilo.configure("TNotebook.Tab", background=ABISSO,
                     foreground=TEXTO_FRACO, bordercolor=ABISSO,
                     lightcolor=ABISSO, darkcolor=ABISSO, borderwidth=0,
                     padding=(SECAO, PERTO + 1), font=CORPO)
    estilo.map("TNotebook.Tab",
               background=[("selected", FUNDO), ("active", PAINEL)],
               foreground=[("selected", OURO), ("active", TEXTO)],
               lightcolor=[("selected", OURO)],
               expand=[("selected", (0, 0, 0, 0))])


# =========================================================================
# barras
# =========================================================================
def _barras(estilo):
    # Barra fina, sem setas: a roda do mouse já resolve, e as setinhas só
    # ocupam a altura que a lista queria.
    estilo.configure("Vertical.TScrollbar", background=ELEVADO,
                     troughcolor=ABISSO, bordercolor=ABISSO,
                     arrowcolor=TEXTO_APAGADO, lightcolor=ELEVADO,
                     darkcolor=ELEVADO, borderwidth=0, arrowsize=12, width=12)
    estilo.map("Vertical.TScrollbar",
               background=[("active", REALCE), ("pressed", OURO)])
    estilo.configure("Horizontal.TScrollbar", background=ELEVADO,
                     troughcolor=ABISSO, bordercolor=ABISSO,
                     arrowcolor=TEXTO_APAGADO, lightcolor=ELEVADO,
                     darkcolor=ELEVADO, borderwidth=0, arrowsize=12)
    estilo.map("Horizontal.TScrollbar",
               background=[("active", REALCE), ("pressed", OURO)])

    estilo.configure("Horizontal.TProgressbar", background=OURO,
                     troughcolor=ABISSO, bordercolor=BORDA,
                     lightcolor=OURO, darkcolor=OURO, borderwidth=0,
                     thickness=6)
