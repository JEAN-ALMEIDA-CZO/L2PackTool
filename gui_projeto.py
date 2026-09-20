#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O cabeçalho do programa e a janela de projetos.

O cabeçalho é a marca à esquerda e o projeto em uso à direita dela -- o mesmo
lugar, em toda aba, onde se lê "em que servidor eu estou mexendo". Antes essa
resposta estava espalhada em dezoito campos de pasta, um par por aba, e bastava
um ficar para trás para uma tela gravar no lugar errado sem avisar.

## A pasta do cliente não é a mesma coisa para todas as telas

A maioria guarda a RAIZ do cliente e monta `raiz/system` quando precisa. A aba
de NPC guarda a própria `system`, porque ela procura o `npcgrp.dat` direto no
caminho que recebe.

Isso está na tabela `QUEREM_SYSTEM`, e não num palpite sobre o valor atual: num
programa recém-instalado os campos estão vazios, e palpite sobre vazio erra
calado.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import l2conferir
import l2upscale as motor
import projeto
import tema
from idioma import t

# As telas que querem a pasta `system` em vez da raiz do cliente.
QUEREM_SYSTEM = ("JanelaNpc",)

# Os nomes que as telas dão à variável da pasta do servidor. São dois porque
# as abas nasceram em épocas diferentes; unificar os nomes seria um diff em
# oito arquivos para não mudar nada.
NOMES_DE_SERVIDOR = ("servidor", "pasta_do_servidor")


# =========================================================================
# a marca
# =========================================================================
def logo(widget, altura=28):
    """
    A logo do programa, na altura pedida. `None` se não der para carregar.

    Ela foi desenhada em claro sobre transparente, para barra de título
    escura -- que é exatamente o fundo do cabeçalho. Não precisa do
    escurecimento que o ícone da engrenagem precisa.
    """
    try:
        from PIL import Image, ImageTk

        with Image.open(Path(motor.AQUI) / "recursos" / "logo.png") as bruto:
            arte = bruto.convert("RGBA")
            largura = max(1, int(arte.width * altura / float(arte.height)))
            arte = arte.resize((largura, altura), Image.LANCZOS)
        imagem = ImageTk.PhotoImage(arte)
        widget.imagem_da_logo = imagem          # referência viva
        return imagem
    except Exception:                           # noqa: BLE001
        return None


# =========================================================================
# o cabeçalho
# =========================================================================
class Cabecalho(ttk.Frame):
    """
    A faixa do topo: marca, projeto em uso, e o que vier à direita.

    Quem monta põe os próprios botões em `.direita`.
    """

    def __init__(self, pai, raiz, ao_trocar=None):
        ttk.Frame.__init__(self, pai, padding=(tema.SECAO, 10, tema.SECAO, 10))
        self.raiz = raiz
        self.ao_trocar = ao_trocar

        marca = ttk.Label(self)
        imagem = logo(marca)
        if imagem is not None:
            marca.configure(image=imagem)
        else:
            marca.configure(text="L2PackTool", style="Titulo.TLabel")
        marca.pack(side="left")

        self.direita = ttk.Frame(self)
        self.direita.pack(side="right")

        caixa = ttk.Frame(self)
        caixa.pack(side="left", padx=(tema.SECAO + 8, 0))
        ttk.Label(caixa, text=t("Projeto"), style="Miudo.TLabel").pack(
            anchor="w")

        linha = ttk.Frame(caixa)
        linha.pack(anchor="w")
        self.escolhido = tk.StringVar()
        self.caixa = ttk.Combobox(linha, textvariable=self.escolhido, width=22,
                                  state="readonly")
        self.caixa.pack(side="left")
        self.caixa.bind("<<ComboboxSelected>>", self._ao_escolher)
        ttk.Button(linha, text=t("Projetos…"),
                   command=self.abrir_janela).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Um projeto guarda a pasta do cliente e a do servidor.@@"
            "Escolher o projeto troca as duas em TODAS as abas de uma vez. É "
            "para quem mexe em mais de um servidor: em vez de acertar dezoito "
            "campos, troca-se um."))

        self.resumo = ttk.Label(self, style="Miudo.TLabel", justify="left")
        self.resumo.pack(side="left", padx=(tema.SECAO, 0))

        self.atualizar()

    def atualizar(self):
        """Relê a lista de projetos e o escolhido."""
        nomes = projeto.listar()
        self.caixa.config(values=tuple(nomes) or (t("(nenhum)"),))
        atual = projeto.atual()
        self.escolhido.set(atual or t("(nenhum)"))
        self.caixa.config(state="readonly" if nomes else "disabled")
        d = projeto.dados(atual)
        if not atual:
            self.resumo.config(
                text=t("Nenhum projeto. Crie um em Projetos… para não ter "
                       "que apontar as pastas em cada aba."))
            return
        self.resumo.config(text=t("cliente:  %s\nservidor: %s")
                           % (d["cliente"] or t("—"), d["servidor"] or t("—")))

    def _ao_escolher(self, _evento=None):
        nome = self.escolhido.get()
        if nome and nome in projeto.listar():
            projeto.escolher(nome)
            self.atualizar()
            if self.ao_trocar:
                self.ao_trocar()

    def abrir_janela(self):
        JanelaProjetos(self.raiz)
        self.atualizar()
        if self.ao_trocar:
            self.ao_trocar()


# =========================================================================
# a janela de projetos
# =========================================================================
class JanelaProjetos:
    """Criar, mudar e apagar projeto. Modal, como as outras."""

    def __init__(self, raiz):
        self.raiz = raiz
        self.editando = None            # o nome antes de renomear

        self.janela = tk.Toplevel(raiz)
        self.janela.title(t("Projetos"))
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)

        quadro = ttk.Frame(self.janela, padding=tema.FOLGA)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, style="Fraco.TLabel", justify="left", wraplength=520,
                  text=t("Um projeto guarda a pasta do cliente e a do "
                         "servidor. Escolher o projeto no cabeçalho troca as "
                         "duas em todas as abas.")).pack(anchor="w")

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True, pady=(tema.FOLGA, 0))

        esquerda = ttk.Frame(corpo)
        esquerda.pack(side="left", fill="y")
        self.lista = tk.Listbox(esquerda, width=24, height=12,
                                exportselection=False,
                                background=tema.PAINEL, foreground=tema.TEXTO,
                                selectbackground=tema.OURO_FUNDO,
                                selectforeground=tema.TEXTO,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                borderwidth=0, font=tema.CORPO)
        self.lista.pack(fill="y", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._ao_marcar)

        direita = ttk.Frame(corpo, padding=(tema.FOLGA, 0, 0, 0))
        direita.pack(side="left", fill="both", expand=True)

        self.nome = tk.StringVar()
        self.pasta_cliente = tk.StringVar()
        self.pasta_servidor = tk.StringVar()

        ttk.Label(direita, text=t("nome")).grid(row=0, column=0, sticky="w")
        ttk.Entry(direita, textvariable=self.nome, width=34).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=(0, tema.PERTO))

        for linha, (rotulo, variavel, titulo) in enumerate((
                (t("pasta do cliente"), self.pasta_cliente,
                 t("A pasta do cliente")),
                (t("pasta do servidor"), self.pasta_servidor,
                 t("A pasta do servidor"))), start=1):
            ttk.Label(direita, text=rotulo).grid(row=linha * 2, column=0,
                                                 sticky="w")
            ttk.Entry(direita, textvariable=variavel, width=34).grid(
                row=linha * 2 + 1, column=0, columnspan=2, sticky="ew")
            ttk.Button(direita, text=t("Escolher…"),
                       command=lambda v=variavel, ti=titulo:
                       self._escolher_pasta(v, ti)).grid(
                row=linha * 2 + 1, column=2, padx=(6, 0))
        direita.columnconfigure(1, weight=1)

        botoes = ttk.Frame(direita)
        botoes.grid(row=6, column=0, columnspan=3, sticky="ew",
                    pady=(tema.FOLGA, 0))
        ttk.Button(botoes, text=t("Guardar"), style="Primario.TButton",
                   command=self.guardar).pack(side="left")
        ttk.Button(botoes, text=t("Novo"),
                   command=self.limpar).pack(side="left", padx=(6, 0))
        ttk.Button(botoes, text=t("Apagar"), style="Perigo.TButton",
                   command=self.apagar).pack(side="left", padx=(6, 0))

        self.recado = ttk.Label(direita, style="Atencao.TLabel", wraplength=340,
                                justify="left")
        self.recado.grid(row=7, column=0, columnspan=3, sticky="w",
                         pady=(tema.PERTO, 0))

        fim = ttk.Frame(quadro)
        fim.pack(fill="x", pady=(tema.FOLGA, 0))
        ttk.Button(fim, text=t("Fechar"),
                   command=self.janela.destroy).pack(side="right")

        self._encher()
        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        raiz.wait_window(self.janela)

    # ---- a lista ------------------------------------------------------
    def _encher(self):
        self.lista.delete(0, "end")
        for nome in projeto.listar():
            self.lista.insert("end", nome)
        atual = projeto.atual()
        if atual in projeto.listar():
            indice = projeto.listar().index(atual)
            self.lista.selection_set(indice)
            self._carregar(atual)

    def _ao_marcar(self, _evento=None):
        marcado = self.lista.curselection()
        if marcado:
            self._carregar(self.lista.get(marcado[0]))

    def _carregar(self, nome):
        d = projeto.dados(nome)
        self.editando = nome
        self.nome.set(nome)
        self.pasta_cliente.set(d["cliente"])
        self.pasta_servidor.set(d["servidor"])
        self.recado.config(text="")

    def limpar(self):
        self.editando = None
        self.nome.set("")
        self.pasta_cliente.set("")
        self.pasta_servidor.set("")
        self.lista.selection_clear(0, "end")
        self.recado.config(text="")

    def _escolher_pasta(self, variavel, titulo):
        pasta = filedialog.askdirectory(
            title=titulo, initialdir=variavel.get().strip() or None,
            parent=self.janela)
        if pasta:
            variavel.set(pasta)

    # ---- guardar e apagar ---------------------------------------------
    def guardar(self):
        problema = projeto.guardar(self.nome.get(),
                                   self.pasta_cliente.get().strip(),
                                   self.pasta_servidor.get().strip(),
                                   antigo=self.editando)
        if problema:
            self.recado.config(text=problema)
            return
        self.editando = self.nome.get().strip()
        self.recado.config(text="")
        self._encher()
        projeto.escolher(self.editando)

    def apagar(self):
        nome = (self.nome.get() or "").strip()
        if not nome or nome not in projeto.listar():
            return
        if not messagebox.askyesno(
                t("Apagar o projeto?"),
                t("Apagar o projeto %s. As pastas do cliente e do servidor "
                  "não são tocadas — só o atalho para elas.") % nome,
                parent=self.janela):
            return
        projeto.apagar(nome)
        self.limpar()
        self._encher()


# =========================================================================
# ligar uma tela ao projeto
# =========================================================================
class SeletorDeProjeto(ttk.Frame):
    """
    A tira de projeto que abre cada aba: escolher, e ver para onde aponta.

    O cabeçalho já tem a mesma escolha, mas quem está no meio de uma aba não
    olha para o topo da janela -- olha para a aba. Repetir o controle aqui é o
    que faz a resposta de "em que servidor eu estou mexendo" estar sempre no
    campo de visão de quem vai gravar alguma coisa.

    Todas as tiras compartilham o mesmo projeto: mexer numa muda as outras,
    porque todas se inscrevem no `ao_trocar`.
    """

    def __init__(self, pai, raiz):
        ttk.Frame.__init__(self, pai, padding=(0, 0, 0, tema.PERTO))
        self.raiz = raiz

        ttk.Label(self, text=t("Projeto:")).pack(side="left")
        self.escolhido = tk.StringVar()
        self.caixa = ttk.Combobox(self, textvariable=self.escolhido, width=20,
                                  state="readonly")
        self.caixa.pack(side="left", padx=(6, 0))
        self.caixa.bind("<<ComboboxSelected>>", self._ao_escolher)
        ttk.Button(self, text=t("Projetos…"),
                   command=self._abrir).pack(side="left", padx=(6, 0))

        self.resumo = ttk.Label(self, style="Miudo.TLabel")
        self.resumo.pack(side="left", padx=(tema.FOLGA, 0))

        self.atualizar()
        # A tira morre junto com a aba; sem tirar a inscrição, trocar de
        # projeto depois disso estouraria uma vez por aba morta.
        projeto.ao_trocar(self._de_fora)
        self.bind("<Destroy>", lambda _e: projeto.nao_avisar(self._de_fora))

    def _de_fora(self, _nome, _cliente, _servidor):
        self.atualizar()

    def atualizar(self):
        nomes = projeto.listar()
        self.caixa.config(values=tuple(nomes) or (t("(nenhum)"),),
                          state="readonly" if nomes else "disabled")
        atual = projeto.atual()
        self.escolhido.set(atual or t("(nenhum)"))
        d = projeto.dados(atual)
        if not atual:
            self.resumo.config(text=t("nenhum projeto — crie um em Projetos…"))
        else:
            self.resumo.config(
                text=t("cliente: %s   ·   servidor: %s")
                % (d["cliente"] or t("—"), d["servidor"] or t("—")))

    def _ao_escolher(self, _evento=None):
        nome = self.escolhido.get()
        if nome and nome in projeto.listar():
            projeto.escolher(nome)

    def _abrir(self):
        JanelaProjetos(self.raiz)
        projeto.avisar()


def conferir_pastas(precisa_cliente=True, precisa_servidor=True):
    """
    O que falta configurar no projeto, em frases prontas para a tela.

    Devolve uma lista vazia quando está tudo certo. Cada frase diz **o que
    fazer**, e não só o que está errado: "configure a pasta do cliente em
    Projetos…" resolve; "cliente inválido" manda a pessoa adivinhar.

    A pasta é conferida no disco, e não só no arquivo de projeto. O caso que
    justifica isso é comum: o projeto aponta para um cliente que foi movido ou
    renomeado, e o botão falharia lá dentro, com um erro que não fala de
    pasta nenhuma.
    """
    atual = projeto.atual()
    if not atual:
        return [t("Nenhum projeto escolhido. Crie um em Projetos… com a "
                  "pasta do cliente e a do servidor.")]

    d = projeto.dados(atual)
    faltas = []
    for precisa, qual, caminho, rotulo in (
            (precisa_cliente, "cliente", d["cliente"], t("do cliente")),
            (precisa_servidor, "servidor", d["servidor"], t("do servidor"))):
        if not precisa:
            continue
        if not (caminho or "").strip():
            faltas.append(t("O projeto %s não tem a pasta %s. Ponha ela em "
                            "Projetos…") % (atual, rotulo))
        elif not Path(caminho).is_dir():
            faltas.append(t("A pasta %s do projeto %s não existe mais: %s")
                          % (rotulo, atual, caminho))
    return faltas


def avisar_falta(tela, faltas):
    """
    Põe o recado na tela, onde ela souber mostrar.

    Antes o botão simplesmente ficava cinza quando faltava pasta -- e botão
    cinza não diz o que fazer. Aqui a primeira frase vai para o rótulo de
    estado, que está sempre à vista, e a lista inteira para o registro.
    """
    if not faltas:
        return False
    rotulo = getattr(tela, "estado", None)
    if rotulo is not None:
        try:
            rotulo.config(text=faltas[0], foreground=tema.ATENCAO)
        except tk.TclError:
            pass
    registrar = getattr(tela, "log", None)
    if callable(registrar):
        registrar("")
        for frase in faltas:
            registrar("  " + frase)
    return True


def limpar_aviso(tela):
    """Devolve o rótulo de estado à cor normal, antes de uma nova tentativa."""
    rotulo = getattr(tela, "estado", None)
    if rotulo is not None:
        try:
            rotulo.config(text="", foreground=tema.TEXTO_FRACO)
        except tk.TclError:
            pass


def pedir_pasta(raiz, qual):
    """
    Abre a janela de projetos e devolve a pasta pedida do projeto em uso.

    É o que os botões `Escolher…` das abas chamam no lugar do seletor de
    pasta. A diferença importa: um seletor próprio faria AQUELA aba apontar
    para outro lugar, calada, até a próxima troca de projeto -- que é a
    duplicação que o projeto existe para acabar.

    `qual` é `cliente`, `servidor` ou `system` -- este último para a aba de
    NPC, que quer a pasta `system` e não a raiz.

    Devolve "" quando não há projeto ou a pasta está em branco, e quem chamou
    trata isso como "o usuário desistiu" -- que é o mesmo que o seletor de
    pasta devolvia ao ser cancelado.
    """
    JanelaProjetos(raiz)
    d = projeto.dados(projeto.atual())
    if qual == "servidor":
        return d["servidor"] or ""
    if not d["cliente"]:
        return ""
    base = l2conferir.raiz_do_cliente(d["cliente"])
    return str(base / "system") if qual == "system" else str(base)


def ligar(tela):
    """
    Faz a tela seguir o projeto: agora e a cada troca.

    Não mexe em campo nenhum quando o projeto não tem aquela pasta: apagar o
    caminho que a pessoa apontou à mão seria pior do que deixá-lo.
    """
    quer_system = type(tela).__name__ in QUEREM_SYSTEM

    def campo(atributo):
        """
        A variável daquele nome -- só se for mesmo uma variável do Tk.

        Nome igual não quer dizer coisa igual: a aba de Itens tem um
        `self.servidor` que é um painel inteiro, não um campo. Escrever nele
        pelo nome derrubava a ligação de todas as abas seguintes.
        """
        valor = getattr(tela, atributo, None)
        return valor if isinstance(valor, tk.Variable) else None

    def aplicar(_nome, pasta_cliente, pasta_servidor):
        variavel = campo("cliente")
        if variavel is not None and pasta_cliente:
            raiz = l2conferir.raiz_do_cliente(pasta_cliente)
            variavel.set(str(raiz / "system") if quer_system else str(raiz))
        for atributo in NOMES_DE_SERVIDOR:
            variavel = campo(atributo)
            if variavel is not None and pasta_servidor:
                variavel.set(pasta_servidor)
        atualizar = getattr(tela, "atualizar_botoes", None)
        if callable(atualizar):
            try:
                atualizar()
            except Exception:                       # noqa: BLE001
                pass

    d = projeto.dados(projeto.atual())
    aplicar(projeto.atual(), d["cliente"], d["servidor"])
    projeto.ao_trocar(aplicar)
    _travar_campos(tela)
    return aplicar


def _travar_campos(tela):
    """
    Deixa os campos de pasta somente-leitura: quem manda é o projeto.

    O caminho continua à vista, que é útil -- o que some é a possibilidade de
    digitar ali um caminho diferente do projeto e a aba passar a apontar para
    outro lugar sem nada dizer. Para mudar de verdade há o botão ao lado, que
    abre o projeto.

    A busca é pelo `textvariable`: o nome da variável do Tk é comparável, e
    isso acha o campo sem precisar saber o layout de cada aba -- que é
    diferente em cada uma das nove.
    """
    alvos = set()
    for atributo in ("cliente",) + NOMES_DE_SERVIDOR:
        valor = getattr(tela, atributo, None)
        if isinstance(valor, tk.Variable):
            alvos.add(str(valor))
    if not alvos:
        return
    raiz = getattr(tela, "raiz", None) or getattr(
        getattr(tela, "dono", None), "raiz", None)
    if raiz is None:
        return

    pilha = [raiz]
    while pilha:
        w = pilha.pop()
        pilha.extend(w.winfo_children())
        try:
            if w.winfo_class() != "TEntry":
                continue
            if str(w.cget("textvariable")) in alvos:
                w.config(state="readonly")
        except tk.TclError:
            pass
