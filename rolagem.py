#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Area com barra de rolagem, para conteudo mais alto do que a janela.

O programa nasceu em tela grande. Numa de 1366x768 -- que e a mais comum em
notebook -- quase toda aba pede mais altura do que cabe, e o Tk simplesmente
corta o que sobra: o botao fica fora da janela, sem aviso e sem jeito de
alcanca-lo. A aba de Itens pede 1053 pixels de altura; a de Lobby Video, 1063.

A solucao e por cada aba dentro de um Canvas rolavel. Duas armadilhas conhecidas:

  1. Largura. O Canvas nao estica o que esta dentro dele. Sem ajustar a largura
     do item a cada redimensionamento, todo `fill="x"` de dentro para de
     funcionar e a aba fica espremida a esquerda.

  2. A roda do mouse. O Tk manda o evento para o widget sob o ponteiro, mas o
     Canvas nao tem binding de roda -- so classes como Treeview e Text tem. A
     saida comum, `bind_all`, e pior do que o problema: ela e GLOBAL, entao a
     roda passa a mexer sempre no mesmo canvas, esteja o ponteiro onde estiver,
     e duas areas roláveis brigam pela mesma tecla.

     Aqui ha um unico tratador global que, a partir do widget sob o ponteiro,
     sobe pela arvore ate achar o primeiro que rola. Se for uma lista ou um
     texto, ele nao faz nada -- a classe ja rolou sozinha. Se for uma area
     destas, rola essa. Areas encaixadas funcionam: ganha a de dentro.
"""

import tkinter as tk
from tkinter import ttk

# Classes que ja tratam a roda sozinhas. Encontrar uma delas no caminho
# significa "nao e comigo".
_ROLAM_SOZINHAS = ("Treeview", "Listbox", "Text", "TCombobox", "Spinbox",
                   "TSpinbox")

# {caminho do widget: canvas} das areas vivas neste interpretador.
_areas = {}
_instalado = set()


def _instalar(widget):
    """Prende o tratador da roda uma vez por interpretador Tk."""
    raiz = widget.winfo_toplevel()
    chave = str(raiz)
    if chave in _instalado:
        return
    _instalado.add(chave)
    raiz.bind_all("<MouseWheel>", _ao_girar, add="+")
    # X11 manda botao 4 e 5 em vez de <MouseWheel>.
    raiz.bind_all("<Button-4>", _ao_girar, add="+")
    raiz.bind_all("<Button-5>", _ao_girar, add="+")


def _passos(evento):
    if getattr(evento, "num", None) == 4:
        return -1
    if getattr(evento, "num", None) == 5:
        return 1
    delta = getattr(evento, "delta", 0)
    if not delta:
        return 0
    return -1 if delta > 0 else 1


def _ao_girar(evento):
    alvo = evento.widget
    if isinstance(alvo, str):
        return
    passos = _passos(evento)
    if not passos:
        return

    while alvo is not None:
        classe = alvo.winfo_class()
        if classe in _ROLAM_SOZINHAS:
            return                      # a propria classe ja rolou
        canvas = _areas.get(str(alvo))
        if canvas is not None:
            canvas.yview_scroll(passos, "units")
            return "break"
        alvo = getattr(alvo, "master", None)


def registrar(canvas, dono=None):
    """
    Faz a roda do mouse mexer neste canvas quando o ponteiro estiver sobre ele.

    Serve para canvas que ja existiam com rolagem propria -- a grade de
    texturas, por exemplo -- em vez de eles prenderem um `bind_all` cada.
    """
    _instalar(canvas)
    _areas[str(canvas)] = canvas
    for alvo in (canvas, dono):
        if alvo is not None:
            _areas[str(alvo)] = canvas
            alvo.bind("<Destroy>", lambda e, c=str(alvo): _areas.pop(c, None),
                      add="+")
    return canvas


class Area(ttk.Frame):
    """
    Um quadro que rola. Ponha o conteudo em `.dentro`.

        area = rolagem.Area(pai)
        area.pack(fill="both", expand=True)
        ttk.Label(area.dentro, text="…").pack()

    A barra so aparece quando o conteudo passa da altura disponivel: numa tela
    grande a aba fica exatamente como era antes.
    """

    def __init__(self, pai, **kw):
        ttk.Frame.__init__(self, pai, **kw)

        self.tela = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.barra = ttk.Scrollbar(self, orient="vertical",
                                   command=self.tela.yview)
        self.tela.configure(yscrollcommand=self._mover_barra)
        self.tela.pack(side="left", fill="both", expand=True)

        self.dentro = ttk.Frame(self.tela)
        self._item = self.tela.create_window((0, 0), window=self.dentro,
                                             anchor="nw")

        self._barra_a_vista = False

        self.dentro.bind("<Configure>", self._conteudo_mudou)
        self.tela.bind("<Configure>", self._tela_mudou)
        registrar(self.tela, self.dentro)

    # -- ajustes ------------------------------------------------------------
    def _conteudo_mudou(self, _evento=None):
        self.tela.configure(scrollregion=self.tela.bbox("all"))

    def _tela_mudou(self, evento):
        # O item acompanha a largura da tela: sem isto, `fill="x"` la dentro
        # nao enche nada e a aba encolhe para a esquerda.
        self.tela.itemconfigure(self._item, width=evento.width)

    def _mover_barra(self, inicio, fim):
        """
        Mostra a barra so quando ela serve para alguma coisa.

        E so quando o estado MUDA. Empacotar de novo o que ja esta empacotado
        muda a largura util do canvas, que dispara `<Configure>`, que remede o
        conteudo, que volta para ca -- e no limite em que o conteudo tem quase
        a altura da area os dois estados se alternam e a tela pisca.
        """
        precisa = not (float(inicio) <= 0.0 and float(fim) >= 1.0)
        if precisa != self._barra_a_vista:
            if precisa:
                self.barra.pack(side="right", fill="y")
            else:
                self.barra.pack_forget()
            self._barra_a_vista = precisa
        self.barra.set(inicio, fim)
