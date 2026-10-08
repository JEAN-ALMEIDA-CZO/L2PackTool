#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A tela de abertura: a logo, o nome, a versão e a barra de carregamento.

O programa leva alguns segundos para montar as doze abas, e a versão
Completa ainda descompacta 300 MB antes disso. Sem abertura, quem clica no
atalho fica olhando para nada e clica de novo -- e abre duas cópias.

São duas metades com a mesma cara:

  1. a imagem `recursos/abertura.png`, que o PyInstaller mostra enquanto o
     executável se descompacta, antes de o Python existir. Ela é desenhada
     por `arte_da_abertura.py` a cada compilação, com a versão do momento;
  2. esta janela, aberta no mesmo lugar e no mesmo tamanho, com a barra
     animada que avança aba por aba. Ao abrir, ela fecha a imagem do
     PyInstaller -- a troca não aparece.

A janela roda na própria linha de execução, com um interpretador Tk só
dela: a barra e o brilho animam o tempo todo, mesmo quando uma aba demora
para montar.
"""

import threading
import time
import tkinter as tk

import tema

LARGURA, ALTURA = 560, 320
BARRA_X, BARRA_Y, BARRA_L, BARRA_A = 70, 238, 420, 6
TEXTO_Y = 262


def _versao():
    try:
        import versao
        return ".".join(str(n) for n in versao.VERSAO[:3])
    except Exception:                               # noqa: BLE001
        return ""


def _fechar_a_imagem_do_pyinstaller():
    try:
        import pyi_splash                           # so existe no executavel
        pyi_splash.close()
    except Exception:                               # noqa: BLE001
        pass


def avisar_pyinstaller(texto):
    """O texto de andamento na imagem do PyInstaller, antes da janela."""
    try:
        import pyi_splash
        pyi_splash.update_text(texto)
    except Exception:                               # noqa: BLE001
        pass


class Abertura:
    """
    A janela de abertura, na própria linha de execução e com o próprio Tk.

    Na mesma linha da janela principal ela congelava: a aba Lobby Vídeo leva
    alguns segundos para varrer os lobbies, e enquanto isso nada se redesenha.
    Separada, ela anima a 60 quadros por segundo o tempo todo -- é o que o
    PyInstaller faz com a imagem dele. A linha principal só conta os passos
    (`avancar`) e muda o texto; não toca em widget nenhum daqui.
    """

    def __init__(self, raiz=None, passos=14, texto="Carregando o sistema…"):
        self.passos = max(1, passos)
        self.feitos = 0
        self.texto = texto
        self.mostrado = 0.0          # fracao desenhada, que persegue o alvo
        self.inicio = time.monotonic()
        self._acabar = False
        self._pronta = threading.Event()
        self._fechada = threading.Event()
        self._linha = threading.Thread(target=self._rodar, name="abertura",
                                       daemon=True)
        self._linha.start()
        self._pronta.wait(5)

    # ---- tudo daqui para baixo roda na linha da abertura -------------------
    def _rodar(self):
        try:
            topo = self.topo = tk.Tk()
            topo.withdraw()
            topo.overrideredirect(True)
            topo.configure(background=tema.OURO)
            try:
                topo.attributes("-topmost", True)
            except tk.TclError:
                pass
            x = (topo.winfo_screenwidth() - LARGURA) // 2
            y = (topo.winfo_screenheight() - ALTURA) // 2
            topo.geometry("%dx%d+%d+%d" % (LARGURA, ALTURA, x, y))
            self._montar(topo)
            topo.deiconify()
            topo.update()
            _fechar_a_imagem_do_pyinstaller()
        except Exception:                           # noqa: BLE001
            _fechar_a_imagem_do_pyinstaller()
            self._logo = self.tela = self.topo = None
            import gc
            gc.collect()
            self._pronta.set()
            self._fechada.set()
            return
        self._pronta.set()
        self._quadro()
        try:
            topo.mainloop()
        finally:
            # O interpretador Tk tem de morrer NESTA linha. Se a ultima
            # referencia caisse na linha principal, o Tcl abortaria o
            # programa ao sair ("async handler deleted by the wrong
            # thread"). Widgets e Tk se referenciam em ciclo: soltar tudo e
            # coletar aqui mesmo.
            try:
                topo.destroy()
            except tk.TclError:
                pass
            self._logo = self.tela = self.cheio = self.brilho = None
            self.rotulo = self.topo = None
            del topo
            import gc
            gc.collect()
            self._fechada.set()

    def _montar(self, topo):
        tela = self.tela = tk.Canvas(topo, width=LARGURA - 2, height=ALTURA - 2,
                                     background=tema.ABISSO, highlightthickness=0,
                                     borderwidth=0)
        tela.place(x=1, y=1)
        self._logo = self._carregar_logo(topo, 78)
        if self._logo is not None:
            tela.create_image(LARGURA // 2, 92, image=self._logo)
        tela.create_text(LARGURA // 2, 168, text="L2PackTool", fill=tema.OURO,
                         font=(tema.FAMILIA, 20, "bold"))
        versao = _versao()
        tela.create_text(LARGURA // 2, 198, fill=tema.TEXTO_FRACO,
                         font=(tema.FAMILIA, 10),
                         text=("versão %s" % versao) if versao else "")
        tela.create_rectangle(BARRA_X, BARRA_Y, BARRA_X + BARRA_L,
                              BARRA_Y + BARRA_A, fill=tema.PAINEL, width=0)
        self.cheio = tela.create_rectangle(BARRA_X, BARRA_Y, BARRA_X,
                                           BARRA_Y + BARRA_A, fill=tema.OURO,
                                           width=0)
        self.brilho = tela.create_rectangle(0, BARRA_Y, 0, BARRA_Y + BARRA_A,
                                            fill=tema.OURO_CLARO, width=0)
        self._texto_mostrado = self.texto
        self.rotulo = tela.create_text(LARGURA // 2, TEXTO_Y, text=self.texto,
                                       fill=tema.TEXTO_FRACO,
                                       font=(tema.FAMILIA, 9))
        tela.create_text(LARGURA // 2, ALTURA - 22, fill=tema.TEXTO_APAGADO,
                         font=(tema.FAMILIA, 8),
                         text="ferramentas de cliente e servidor para Lineage II")

    @staticmethod
    def _carregar_logo(mestre, altura):
        # Com `master` explicito: esta linha tem o proprio interpretador, e a
        # imagem tem de morar nele.
        try:
            from PIL import Image, ImageTk
            import motor
            from pathlib import Path
            with Image.open(Path(motor.AQUI) / "recursos" / "logo.png") as bruto:
                arte = bruto.convert("RGBA")
                largura = max(1, int(arte.width * altura / float(arte.height)))
                arte = arte.resize((largura, altura), Image.LANCZOS)
            return ImageTk.PhotoImage(arte, master=mestre)
        except Exception:                           # noqa: BLE001
            return None

    def _desenhar(self):
        alvo = min(1.0, self.feitos / float(self.passos))
        # avanco suave: a barra persegue o alvo, nunca salta
        self.mostrado += (alvo - self.mostrado) * 0.18
        if alvo - self.mostrado < 0.002:
            self.mostrado = alvo
        fim = BARRA_X + BARRA_L * self.mostrado
        self.tela.coords(self.cheio, BARRA_X, BARRA_Y, fim, BARRA_Y + BARRA_A)
        # o brilho corre dentro da parte cheia, sem parar
        largura_brilho = 70
        ciclo = (time.monotonic() - self.inicio) * 260.0
        percurso = max(1.0, fim - BARRA_X + largura_brilho)
        pos = BARRA_X - largura_brilho + (ciclo % percurso)
        self.tela.coords(self.brilho, max(BARRA_X, pos), BARRA_Y,
                         min(fim, pos + largura_brilho), BARRA_Y + BARRA_A)
        if self.texto != self._texto_mostrado:
            self._texto_mostrado = self.texto
            self.tela.itemconfigure(self.rotulo, text=self.texto)

    def _quadro(self):
        try:
            self._desenhar()
            if self._acabar and self.mostrado >= 0.999:
                self.topo.after(120, self.topo.quit)
                return
            self.topo.after(16, self._quadro)
        except tk.TclError:
            pass

    # ---- o que a linha principal chama -------------------------------------
    def avancar(self, texto=None):
        """Um passo concluido. So muda numeros: quem desenha e a outra linha."""
        self.feitos += 1
        if texto:
            self.texto = texto

    def fechar(self):
        """Completa a barra e some (espera no maximo um segundo e meio)."""
        self.feitos = self.passos
        self._acabar = True
        self._fechada.wait(1.5)
