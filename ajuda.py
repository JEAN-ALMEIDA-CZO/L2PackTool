#!/usr/bin/env python3
"""
Ajuda de canto de tela: o balãozinho que aparece ao parar o mouse.

Existe para tirar explicação de dentro da janela. Um campo chamado "Social ao
clicar" não diz nada a quem nunca criou NPC, mas escrever o parágrafo inteiro
ao lado dele entulharia o formulário -- e quem já sabe teria de ler de novo
toda vez. O `?` ao lado do campo resolve os dois casos: some do caminho de quem
sabe, e responde a quem não sabe.

Duas peças:

    Dica(widget, "texto")     prende o balão a qualquer widget
    ajuda(pai, "texto")       devolve o `?` já com o balão prendido

O `?` é desenhado com o Pillow, e não escrito com uma fonte. Emoji e símbolo
raro dependem da fonte que a máquina tiver: o `⚙` desta mesma janela chegou a
sair como uma pena em outra máquina. Um desenho de 14 pixels sai igual em
qualquer lugar.
"""

import tkinter as tk
from tkinter import ttk

import tema

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:                 # sem Pillow o `?` vira texto comum
    Image = None


# Milissegundos parado sobre o alvo antes de o balão abrir. Curto demais e ele
# pisca ao atravessar a tela com o mouse; longo demais e ninguém descobre que
# existe.
ESPERA = 400

LADO = 14
COR_FUNDO = (91, 141, 184)
COR_TEXTO = (255, 255, 255)

# Um PhotoImage precisa de referência viva ou o Tk o coleta e o rótulo fica em
# branco. O desenho é sempre o mesmo, mas a imagem não: ela nasce dentro de UM
# interpretador Tk e não vale em outro -- usar a de uma janela já fechada dá
# `image "pyimage3" doesn't exist`. Por isso a cópia é guardada por
# interpretador, e não uma só para o programa inteiro.
_icones = {}


def _desenhar_icone():
    """O `?` redondo, desenhado grande e reduzido -- é o que deixa a borda lisa."""
    escala = 4
    lado = LADO * escala
    imagem = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(imagem)
    d.ellipse((0, 0, lado - 1, lado - 1), fill=COR_FUNDO)

    fonte = None
    for nome in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            fonte = ImageFont.truetype(nome, int(lado * 0.72))
            break
        except OSError:
            continue
    if fonte is None:
        fonte = ImageFont.load_default()

    caixa = d.textbbox((0, 0), "?", font=fonte)
    d.text(((lado - (caixa[2] - caixa[0])) / 2 - caixa[0],
            (lado - (caixa[3] - caixa[1])) / 2 - caixa[1]),
           "?", font=fonte, fill=COR_TEXTO)

    return imagem.resize((LADO, LADO), Image.LANCZOS)


def icone(widget):
    """
    O `?` pronto para usar nesta janela, ou None se o Pillow não estiver aqui.

    `widget` diz em qual interpretador a imagem tem de nascer -- ver o
    comentário de `_icones`.
    """
    if Image is None:
        return None

    chave = id(widget.tk)
    guardado = _icones.get(chave)
    if guardado is not None:
        try:
            guardado.width()            # o interpretador ainda está vivo?
            return guardado
        except Exception:
            _icones.pop(chave, None)

    try:
        novo = ImageTk.PhotoImage(_desenhar_icone(), master=widget)
    except Exception:
        return None
    _icones[chave] = novo
    return novo


def por_icone(janela):
    """
    Poe o icone do programa numa janela.

    Sem isto o Tk usa o icone dele -- a pena --, e a janela filha parece de
    outro programa. Falha em silencio: nao achar o arquivo nao pode impedir a
    janela de abrir.
    """
    import motor
    caminho = motor.AQUI / "recursos" / "icone.ico"
    try:
        janela.iconbitmap(str(caminho))
    except Exception:
        pass
    return janela


def ajustar_a_tela(janela, largura_minima=0, altura_minima=0, folga=80):
    """
    Dá à janela o tamanho que ela pede -- até onde a tela comporta.

    Uma modal que se mede pelo conteúdo cresce até passar do monitor, e o que
    sobra não fica só escondido: fica **inalcançável**, porque a parte de
    baixo, onde moram os botões, sai por fora da área de trabalho.

    A `folga` desconta a barra de tarefas e a barra de título; sem ela a
    janela nasce com os botões atrás da barra do Windows.

    Devolve `True` quando teve de encolher -- quem chamou usa isso para
    decidir se precisa de rolagem.
    """
    try:
        janela.update_idletasks()
        pedida_l = max(janela.winfo_reqwidth(), largura_minima)
        pedida_a = max(janela.winfo_reqheight(), altura_minima)
        cabe_l = janela.winfo_screenwidth() - 40
        cabe_a = janela.winfo_screenheight() - folga
        largura, altura = min(pedida_l, cabe_l), min(pedida_a, cabe_a)
        janela.geometry("%dx%d" % (largura, altura))
        janela.minsize(min(largura_minima or largura, cabe_l),
                       min(altura_minima or altura, cabe_a))
        return (largura, altura) != (pedida_l, pedida_a)
    except tk.TclError:
        return False


def centralizar(janela):
    """
    Põe a janela no meio da que a abriu -- ou da tela, se ela não for filha.

    O Tk deixa a posição a cargo do gerenciador de janelas, que na prática
    abre a modal no canto ou por cima de outra coisa. Com dois monitores ela
    chega a nascer no monitor errado, e a pessoa acha que o botão não fez
    nada.

    O `update_idletasks` vem antes de propósito: sem ele a janela ainda mede
    1x1 e a conta joga ela para fora da tela.
    """
    try:
        janela.update_idletasks()
        largura = janela.winfo_width() or janela.winfo_reqwidth()
        altura = janela.winfo_height() or janela.winfo_reqheight()
        tela_l = janela.winfo_screenwidth()
        tela_a = janela.winfo_screenheight()

        pai = janela.master
        if pai is not None and pai.winfo_exists() and pai.winfo_viewable():
            x = pai.winfo_rootx() + (pai.winfo_width() - largura) // 2
            y = pai.winfo_rooty() + (pai.winfo_height() - altura) // 2
        else:
            x = (tela_l - largura) // 2
            y = (tela_a - altura) // 2

        # Nunca fora da tela: janela com a barra de título acima do topo não
        # se arrasta de volta, e aí só fechando no teclado.
        x = max(0, min(x, tela_l - largura))
        y = max(0, min(y, tela_a - altura))
        janela.geometry("+%d+%d" % (x, y))
    except tk.TclError:
        pass
    return janela


class Dica:
    """
    Balão de ajuda preso a um widget.

    Some sozinho ao sair do widget, ao clicar e ao fechar a janela. O texto é
    lido na hora de abrir, e não na hora de prender: assim a mesma dica
    acompanha uma troca de idioma se o widget sobreviver a ela.
    """

    def __init__(self, widget, texto, largura=340):
        self.widget = widget
        self.texto = texto
        self.largura = largura
        self.balao = None
        self.marcado = None

        widget.bind("<Enter>", self._entrou, add="+")
        widget.bind("<Leave>", self._saiu, add="+")
        widget.bind("<ButtonPress>", self._saiu, add="+")
        widget.bind("<Destroy>", self._saiu, add="+")

    def _entrou(self, _evento=None):
        self._cancelar()
        self.marcado = self.widget.after(ESPERA, self._mostrar)

    def _saiu(self, _evento=None):
        self._cancelar()
        self._esconder()

    def _cancelar(self):
        if self.marcado is not None:
            try:
                self.widget.after_cancel(self.marcado)
            except Exception:
                pass
            self.marcado = None

    def _mostrar(self):
        self.marcado = None
        if self.balao is not None or not self.widget.winfo_exists():
            return

        texto = self.texto() if callable(self.texto) else self.texto
        if not texto:
            return

        self.balao = tk.Toplevel(self.widget)
        self.balao.wm_overrideredirect(True)          # sem barra de título
        self.balao.attributes("-topmost", True)
        # O balão é a superfície mais alta da tela, e por isso é o ground mais
        # claro da paleta com uma borda de ouro rebaixado: ele precisa flutuar
        # acima do painel sem virar um retângulo aceso no meio do escuro.
        tk.Label(self.balao, text=texto, justify="left", wraplength=self.largura,
                 background=tema.ELEVADO, foreground=tema.TEXTO,
                 relief="solid", borderwidth=1,
                 highlightbackground=tema.BORDA_FORTE,
                 padx=8, pady=6, font=tema.CORPO).pack()

        # Abaixo do widget, alinhado à esquerda dele, e puxado para dentro da
        # tela quando não couber -- um balão cortado pela borda não se lê.
        self.balao.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        largura_tela = self.balao.winfo_screenwidth()
        altura_tela = self.balao.winfo_screenheight()
        if x + self.balao.winfo_width() > largura_tela - 8:
            x = max(8, largura_tela - 8 - self.balao.winfo_width())
        if y + self.balao.winfo_height() > altura_tela - 8:
            y = max(8, self.widget.winfo_rooty() - self.balao.winfo_height() - 4)
        self.balao.wm_geometry("+%d+%d" % (x, y))

    def _esconder(self):
        if self.balao is not None:
            try:
                self.balao.destroy()
            except Exception:
                pass
            self.balao = None


def ajuda(pai, texto, largura=340, **empacotar):
    """
    O `?` com a dica já prendida. Devolve o rótulo, para quem quiser posicionar.

    `empacotar` COMPLETA o pack padrão, em vez de substituí-lo: o `?` nasce à
    esquerda, ao lado do campo que explica, e quem passa só um `padx` continua
    tendo o `side="left"`. Substituir custou caro uma vez -- os ícones foram
    parar empilhados no topo do formulário, longe dos campos.
    """
    imagem = icone(pai)
    if imagem is not None:
        alvo = ttk.Label(pai, image=imagem, cursor="question_arrow")
        alvo.imagem = imagem              # referência viva
    else:
        alvo = ttk.Label(pai, text="(?)", foreground=tema.INFO,
                         cursor="question_arrow")

    Dica(alvo, texto, largura)
    if empacotar.pop("grid", False):
        alvo.grid(**empacotar)
    else:
        opcoes = {"side": "left", "padx": (4, 0)}
        opcoes.update(empacotar)
        alvo.pack(**opcoes)
    return alvo
