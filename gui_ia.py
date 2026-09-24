#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A janela que pede arte à IA: ícone, botão ou borda -- parado ou animado.

Ela existe separada das abas porque o pedido é sempre o mesmo, venha de onde
vier: a aba de Itens quer um ícone, a de Glow quer um ícone, quem monta
interface quer um botão. Uma janela só, chamada de todos os lugares, evita
três telas parecidas e três jeitos de escrever o mesmo pedido.

## O que fica com o usuário e o que não fica

O que ele escreve é o DETALHE: o objeto, o material, a cor, o que lembrar. A
parte que mantém o resultado utilizável no jogo -- 32x32, fundo transparente,
sem texto, luz de cima -- é fixa e não aparece como campo. Não é para
esconder: é porque editá-la é a forma mais rápida de receber uma imagem
bonita que não serve como ícone. O pedido montado fica à vista, embaixo, para
quem quiser conferir.

## A animação

Os quadros não são pedidos à IA. Cada chamada desenha de novo, e quadros
desenhados de novo piscam. A arte vem da IA uma vez, e o movimento é feito
sobre ela -- pulso, giro ou varredura --, em ciclo fechado. O pacote sai com
os quadros numerados, que é como o cliente espera uma sequência.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import l2ia
import motor
import tema
from idioma import t

try:
    from PIL import Image, ImageTk
except ImportError:                                 # noqa: BLE001
    Image = ImageTk = None

LADO_DA_PREVIA = 128

TIPOS = (("icone", "ícone de item (32x32)"),
         ("botao", "botão de interface"),
         ("borda", "moldura / borda"))


class JanelaDeArte:
    """
    Devolve em `.resposta` {"imagem": caminho, "nome": ..., "quadros": [...]}.

    `quadros` vem preenchido só quando a animação foi pedida; é uma lista de
    caminhos, na ordem do ciclo.
    """

    def __init__(self, raiz, dono, sugestao="", tipo="icone"):
        self.raiz = raiz
        self.dono = dono
        self.resposta = None
        self.gerada = None          # PIL.Image do que a IA devolveu
        self.previa_tk = None
        self.referencias = []
        self.trabalho = Path(motor.BASE) / "trabalho" / "ia"
        self.trabalho.mkdir(parents=True, exist_ok=True)

        self.janela = ajuda.por_icone(tk.Toplevel(raiz))
        self.janela.title(t("Gerar arte com IA"))
        self.janela.transient(raiz)

        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)

        self._montar_topo(quadro, tipo, sugestao)
        self._montar_referencias(quadro)
        self._montar_observacoes(quadro)
        self._montar_animacao(quadro)
        self._montar_previa_e_acao(quadro)

        self._conferir_o_provedor()
        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        raiz.wait_window(self.janela)

    # -- as partes da tela -------------------------------------------------
    def _montar_topo(self, quadro, tipo, sugestao):
        topo = ttk.Frame(quadro)
        topo.pack(fill="x")

        ttk.Label(topo, text=t("o que gerar:")).pack(side="left")
        self.tipo = tk.StringVar(value=tipo)
        for chave, rotulo in TIPOS:
            ttk.Radiobutton(topo, text=t(rotulo), value=chave,
                            variable=self.tipo).pack(side="left", padx=(8, 0))

        linha = ttk.Frame(quadro)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text=t("o objeto:")).pack(side="left")
        self.objeto = tk.StringVar(value=sugestao)
        ttk.Entry(linha, textvariable=self.objeto).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "O que a arte mostra: uma espada curva de gelo, uma poção "
            "vermelha, um botão de confirmar.@@"
            "Entra no pedido junto com a parte fixa, que é o que mantém o "
            "resultado utilizável no jogo."))

        self.recado = ttk.Label(quadro, foreground=tema.ATENCAO,
                                justify="left", wraplength=560)
        self.recado.pack(anchor="w", pady=(6, 0))

    def _montar_referencias(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Referências (opcional)"),
                               padding=6)
        caixa.pack(fill="x", pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("Imagens que o modelo olha para seguir o estilo. É o "
                         "que faz o resultado parecer com o resto do seu "
                         "cliente, em vez de parecer com a média da "
                         "internet.")).pack(anchor="w")
        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(6, 0))
        self.lista_ref = tk.Listbox(linha, height=3,
                                    background=tema.PAINEL,
                                    foreground=tema.TEXTO,
                                    highlightthickness=1,
                                    highlightbackground=tema.BORDA,
                                    borderwidth=0)
        self.lista_ref.pack(side="left", fill="x", expand=True)
        botoes = ttk.Frame(linha)
        botoes.pack(side="left", padx=(6, 0))
        ttk.Button(botoes, text=t("Juntar…"),
                   command=self.juntar_referencia).pack(fill="x")
        ttk.Button(botoes, text=t("Tirar"),
                   command=self.tirar_referencia).pack(fill="x", pady=(4, 0))

    def _montar_observacoes(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Observações"), padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("O detalhe que você quer: material, cor, época, o "
                         "que lembrar. A parte fixa do pedido — tamanho, "
                         "fundo transparente, sem texto, luz de cima — já "
                         "está garantida e não precisa ser repetida aqui.")
                  ).pack(anchor="w")
        self.observacoes = tk.Text(caixa, height=4, wrap="word",
                                   background=tema.PAINEL,
                                   foreground=tema.TEXTO,
                                   insertbackground=tema.TEXTO,
                                   highlightthickness=1,
                                   highlightbackground=tema.BORDA,
                                   borderwidth=0, font=tema.CORPO)
        self.observacoes.pack(fill="both", expand=True, pady=(6, 0))

    def _montar_animacao(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Animação (opcional)"),
                               padding=6)
        caixa.pack(fill="x", pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("Os quadros não são pedidos à IA: cada chamada "
                         "desenharia de novo e a animação piscaria. A arte "
                         "vem uma vez e o movimento é feito sobre ela, em "
                         "ciclo fechado.")).pack(anchor="w")
        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(6, 0))
        self.animar = tk.BooleanVar(value=False)
        ttk.Checkbutton(linha, text=t("gerar animação"),
                        variable=self.animar).pack(side="left")
        ttk.Label(linha, text=t("modo:")).pack(side="left", padx=(12, 0))
        self.modo = tk.StringVar(value=l2ia.MODOS[0])
        ttk.Combobox(linha, textvariable=self.modo, values=l2ia.MODOS,
                     state="readonly", width=12).pack(side="left", padx=(6, 0))
        ttk.Label(linha, text=t("quadros:")).pack(side="left", padx=(12, 0))
        self.quantos = tk.StringVar(value="8")
        ttk.Spinbox(linha, from_=2, to=32, width=5,
                    textvariable=self.quantos).pack(side="left", padx=(6, 0))

    def _montar_previa_e_acao(self, quadro):
        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(12, 0))

        self.previa = tk.Canvas(baixo, width=LADO_DA_PREVIA,
                                height=LADO_DA_PREVIA,
                                background=tema.ABISSO, highlightthickness=1,
                                highlightbackground=tema.BORDA)
        self.previa.pack(side="left")

        direita = ttk.Frame(baixo)
        direita.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.estado = ttk.Label(direita, foreground=tema.TEXTO_FRACO,
                                justify="left", wraplength=400)
        self.estado.pack(anchor="w")

        acao = ttk.Frame(direita)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_gerar = ttk.Button(acao, text=t("Gerar"),
                                      style="Primario.TButton",
                                      command=self.gerar)
        self.botao_gerar.pack(side="left")
        self.botao_usar = ttk.Button(acao, text=t("Usar esta"),
                                     command=self.usar, state="disabled")
        self.botao_usar.pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Ver o pedido"),
                   command=self.ver_o_pedido).pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Fechar"),
                   command=self.janela.destroy).pack(side="right")

    # -- o provedor --------------------------------------------------------
    def _conferir_o_provedor(self):
        """Diz de cara se dá para gerar, e o que fazer quando não dá."""
        da, porque = l2ia.pronto(para="imagem")
        if da:
            self.recado.config(
                text=t("Usando %s, modelo %s.")
                % (l2ia.PROVEDORES[l2ia.provedor()]["nome"], l2ia.modelo()))
            return
        self.recado.config(text=porque)
        self.botao_gerar.config(state="disabled")

    # -- referências -------------------------------------------------------
    def juntar_referencia(self):
        nomes = filedialog.askopenfilenames(
            title=t("Imagens de referência"), parent=self.janela,
            filetypes=[(t("Imagens"), "*.png *.jpg *.jpeg *.webp *.bmp")])
        for nome in nomes:
            if nome not in self.referencias:
                self.referencias.append(nome)
                self.lista_ref.insert("end", Path(nome).name)

    def tirar_referencia(self):
        marcado = self.lista_ref.curselection()
        if not marcado:
            return
        indice = marcado[0]
        self.lista_ref.delete(indice)
        del self.referencias[indice]

    # -- gerar -------------------------------------------------------------
    def _pedido(self):
        return l2ia.montar_prompt(
            self.tipo.get(),
            self.observacoes.get("1.0", "end").strip(),
            self.objeto.get())

    def ver_o_pedido(self):
        janela = ajuda.por_icone(tk.Toplevel(self.janela))
        janela.title(t("O pedido que vai para a IA"))
        texto = tk.Text(janela, wrap="word", width=78, height=22,
                        background=tema.PAINEL, foreground=tema.TEXTO,
                        borderwidth=0, font=tema.CORPO)
        texto.pack(fill="both", expand=True, padx=10, pady=10)
        texto.insert("1.0", self._pedido())
        texto.config(state="disabled")

    def gerar(self):
        if not self.objeto.get().strip():
            messagebox.showinfo(t("Falta dizer o quê"),
                                t("Escreva o que a arte deve mostrar."))
            return
        self.botao_gerar.config(state="disabled")
        self.botao_usar.config(state="disabled")
        self.estado.config(text=t("pedindo à IA… isso leva alguns segundos."))
        threading.Thread(target=self._gerar_thread, daemon=True).start()

    def _gerar_thread(self):
        try:
            dados = l2ia.gerar_imagem(self._pedido(), self.referencias)
            alvo = self.trabalho / "gerada.png"
            alvo.write_bytes(dados)
            imagem = Image.open(alvo).convert("RGBA") if Image else None
            erro = None
        except Exception as e:                      # noqa: BLE001
            imagem, alvo, erro = None, None, e
        self.raiz.after(0, self._fim_da_geracao, imagem, alvo, erro)

    def _fim_da_geracao(self, imagem, alvo, erro):
        try:
            self.botao_gerar.config(state="normal")
        except tk.TclError:
            return
        if erro is not None:
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para gerar"), str(erro))
            return
        self.gerada = imagem
        self.caminho_gerado = alvo
        self._mostrar(imagem)
        self.estado.config(text=t("pronto: %dx%d. Veja se serve e use, ou "
                                  "gere de novo mudando as observações.")
                           % imagem.size)
        self.botao_usar.config(state="normal")

    def _mostrar(self, imagem):
        if ImageTk is None or imagem is None:
            return
        copia = imagem.copy()
        copia.thumbnail((LADO_DA_PREVIA, LADO_DA_PREVIA), Image.LANCZOS)
        self.previa_tk = ImageTk.PhotoImage(copia)
        self.previa.delete("all")
        self.previa.create_image(LADO_DA_PREVIA // 2, LADO_DA_PREVIA // 2,
                                 image=self.previa_tk)

    # -- usar --------------------------------------------------------------
    def usar(self):
        """Fecha devolvendo o caminho -- e os quadros, se houver animação."""
        if self.gerada is None:
            return
        quadros = []
        if self.animar.get():
            try:
                quantos = max(2, min(32, int(self.quantos.get())))
            except ValueError:
                quantos = 8
            try:
                imagens = l2ia.animar(self.gerada, self.modo.get(), quantos)
            except Exception as erro:               # noqa: BLE001
                messagebox.showerror(t("Não deu para animar"), str(erro))
                return
            for i, imagem in enumerate(imagens):
                alvo = self.trabalho / ("quadro_%02d.png" % i)
                imagem.save(alvo)
                quadros.append(str(alvo))

        self.resposta = {"imagem": str(self.caminho_gerado),
                         "nome": _nome_do_objeto(self.objeto.get()),
                         "quadros": quadros}
        self.janela.destroy()


def _nome_do_objeto(texto):
    """Um nome de objeto a partir do que o usuário escreveu."""
    limpo = "".join(c if c.isalnum() else "_" for c in (texto or "").lower())
    while "__" in limpo:
        limpo = limpo.replace("__", "_")
    return limpo.strip("_")[:28] or "arte_ia"
