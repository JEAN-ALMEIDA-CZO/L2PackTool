#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A janela de escolher icone, usada pela aba de Itens e pela de Habilidades.

Duas formas de escolher, uma em cada aba:

  Do cliente     a lista do que ja esta instalado, com filtro e previa. Sao
                 13.690 icones neste cliente, e o nome nao diz nada -- por isso
                 a previa, no tamanho em que o jogo desenha.

  Imagem propria um desenho seu, que vira um pacote .utx e e instalado no
                 cliente. O programa grava num pacote PROPRIO, nunca dentro do
                 Icon.utx do jogo: um erro no pacote proprio custa um icone, e
                 no do jogo custaria catorze mil.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import l2icone
import motor
import rolagem
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE
LADO = l2icone.LADO

TIPOS_DE_IMAGEM = (
    (N_("Imagens"), "*.png *.jpg *.jpeg *.bmp *.tga *.dds *.gif *.webp"),
    (N_("Todos"), "*.*"),
)


class PainelDeIcone(ttk.Frame):
    """
    Escolher o icone VENDO, dentro da propria janela que esta criando.

    A lista de nomes nao resolve: `icon.skill1345` nao diz nada, e sao 13.690
    deles. A grade mostra a arte, que e o unico jeito honesto de escolher um
    desenho.

    A grade so desenha um punhado por vez. Montar catorze mil miniaturas
    congelaria a janela por minutos, e ninguem olha catorze mil icones -- quem
    procura, filtra. O rodape diz quantos ficaram de fora.

    A imagem propria sai daqui **preparada, e nao instalada**: o pacote fica na
    pasta de saida junto com as tabelas, e entra no cliente no mesmo
    "Instalar no cliente". Instalar na hora punha um icone dentro do cliente
    enquanto a habilidade dele ainda nao existia em lugar nenhum.
    """

    TETO = 240
    COLUNAS = 8

    def __init__(self, pai, dono, catalogo, atual="", saida=None,
                 ao_mudar=None):
        ttk.Frame.__init__(self, pai)
        self.dono = dono
        self.referencia = atual or ""
        # Os icones do MESMO pacote do atual vem primeiro. Copiando uma
        # habilidade, a grade abre nos icones de habilidade em vez de na letra
        # A do catalogo inteiro -- e nada fica escondido, que e o que um
        # filtro fixo faria com os pacotes proprios de quem usa o programa.
        self.catalogo = sorted(catalogo, key=self._ordem(self.referencia))
        self.saida = Path(saida) if saida else None
        self.ao_mudar = ao_mudar
        self.pendente = None            # o .utx feito e ainda nao instalado
        self.celulas = {}           # {referencia: (cela, dentro)} a vista
        self.viveiro = []           # as celulas ja criadas, em ordem
        self.mostrados = []
        self.rodando = False
        self.marcada = None         # a cela que esta com a borda azul
        self._pedidos = 0
        self._digitando = None      # o `after` que espera a pessoa parar

        self._montar_grade()
        self._montar_propria()
        self.preencher()

    @staticmethod
    def _ordem(atual):
        """
        Quem parece com o icone atual vem primeiro.

        So agrupar por pacote nao bastava: copiando uma habilidade, o pacote e
        `icon` -- o mesmo de catorze mil icones -- e a grade abria nos
        acessorios. O nome dentro do pacote e que separa, em duas voltas: o
        nome sem os digitos (`skill0001` -> `skill`) e, mais largo, a familia
        antes do primeiro sublinhado (`weapon_small_sword_i00` -> `weapon`).
        Quem copia uma espada quer ver armas, e nao acessorios.

        Nada some por isso. Um filtro fixo esconderia os pacotes proprios de
        quem usa o programa; uma ordem so muda por onde se comeca a olhar.
        """
        pacote, _ponto, objeto = (atual or "").lower().partition(".")
        raiz = objeto.rstrip("0123456789") or objeto
        familia = objeto.split("_")[0]      # weapon, armor, skill, accessary

        def chave(referencia):
            baixo = referencia.lower()
            dele, _p, nome = baixo.partition(".")
            if not pacote or dele != pacote:
                return (3, baixo)
            if raiz and nome.startswith(raiz):
                return (0, baixo)
            if familia and nome.startswith(familia):
                return (1, baixo)
            return (2, baixo)
        return chave

    # ---- a grade ---------------------------------------------------------
    def _montar_grade(self):
        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        # Comeca SEM filtro. A janela antiga pre-enchia a busca com o nome do
        # icone atual, o que na lista poupava rolagem; numa grade, esconde
        # justamente o que ela existe para mostrar -- abria com um icone so.
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(topo, textvariable=self.filtro, width=24)
        entrada.pack(side="left", padx=(6, 0))
        # Refazer a grade a cada tecla e trabalho jogado fora: quem digita
        # "weapon" pediria seis grades, e so a ultima interessa.
        entrada.bind("<KeyRelease>", lambda _e: self._filtrar_daqui_a_pouco())
        self.conta = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        # Largura FIXA, em caracteres. Sem isto, escolher um icone de nome
        # comprido alargava o painel, a pagina, o caderno e a janela -- e a
        # tela inteira se remontava a cada clique.
        self.escolhido = ttk.Label(topo, text="", foreground=tema.TEXTO_FRACO,
                                   font=("Segoe UI", 8), width=34,
                                   anchor="e")
        self.escolhido.pack(side="right")

        self.area = rolagem.Area(self)
        self.area.pack(fill="both", expand=True, pady=(6, 0))
        # A altura vai no canvas: um ttk.Frame ignora `height` quando tem
        # filho empacotado, e a grade cresceria ate empurrar os botoes da
        # janela para fora da tela.
        self.area.tela.config(height=210)
        self.grade = self.area.dentro

    def _filtrar_daqui_a_pouco(self):
        """Refaz a grade quando a pessoa para de digitar, e não a cada tecla."""
        if self._digitando is not None:
            try:
                self.after_cancel(self._digitando)
            except tk.TclError:
                pass
        self._digitando = self.after(220, self._filtrar_agora)

    def _filtrar_agora(self):
        self._digitando = None
        self.preencher()

    def _celula(self, indice):
        """
        A célula de número `indice`, criada uma vez só.

        Widget é caro de criar e caro de destruir. Refazendo as 240 a cada
        tecla, a grade nascia do zero na frente de quem digitava -- e a barra
        de rolagem aparecia e sumia junto. Aqui elas são um viveiro: quem sai
        do filtro é escondido, não destruído.
        """
        while len(self.viveiro) <= indice:
            # `highlightcolor` junto com `highlightbackground`: o anel tem
            # duas cores, uma para com foco e outra para sem, e deixar a de
            # foco no padrao do sistema punha um anel cinza na celula clicada,
            # ao lado do anel azul da escolhida.
            cela = tk.Frame(self.grade, bg=COR_FUNDO_ICONE, width=LADO + 12,
                            height=LADO + 12, highlightthickness=2,
                            highlightbackground=COR_FUNDO_ICONE,
                            highlightcolor=COR_FUNDO_ICONE, takefocus=0)
            cela.grid_propagate(False)
            dentro = tk.Label(cela, bg=COR_FUNDO_ICONE, fg=tema.TEXTO_APAGADO, text="",
                              font=("Segoe UI", 7))
            dentro.pack(expand=True)
            # A referência da célula muda a cada filtro, então o clique lê o
            # atributo em vez de fechar sobre um valor de agora.
            for alvo in (cela, dentro):
                alvo.bind("<Button-1>",
                          lambda _e, c=cela: self.escolher(c.referencia))
            cela.referencia = ""
            cela.a_vista = False
            ajuda.Dica(cela, lambda c=cela: c.referencia)
            self.viveiro.append((cela, dentro))
        return self.viveiro[indice]

    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        casaram = [r for r in self.catalogo
                   if not procurado or procurado in r.lower()]
        self.mostrados = casaram[:self.TETO]

        self.celulas = {}
        self._pedidos += 1              # invalida o que estava a caminho

        for i, referencia in enumerate(self.mostrados):
            cela, dentro = self._celula(i)
            self.celulas[referencia] = (cela, dentro)
            if not cela.a_vista:
                # A célula de índice `i` ocupa sempre a mesma casa da grade:
                # só precisa de `grid` na primeira vez e ao voltar de um
                # filtro que a tinha escondido.
                cela.grid(row=i // self.COLUNAS, column=i % self.COLUNAS,
                          padx=2, pady=2)
                cela.a_vista = True
            if cela.referencia == referencia:
                continue            # mesma célula, mesmo ícone: nada a fazer
            cela.referencia = referencia
            pronta = self.dono.icones.get(referencia)
            if pronta is not None:
                dentro.config(image=pronta, text="")
            else:
                dentro.config(image="", text="")
            dentro.imagem = pronta
            if cela is self.marcada:
                cela.config(highlightbackground=COR_FUNDO_ICONE,
                            highlightcolor=COR_FUNDO_ICONE)
                self.marcada = None     # a borda foi apagada: nao e mais ela

        # `grid_remove` guarda a posição e não destrói: a próxima busca as
        # aproveita de volta sem criar nada.
        for cela, _dentro in self.viveiro[len(self.mostrados):]:
            cela.referencia = ""
            if cela.a_vista:
                cela.grid_remove()
                cela.a_vista = False

        de_fora = len(casaram) - len(self.mostrados)
        self.conta.config(
            text=(t("%d de %d — refine a busca para ver o resto")
                  % (len(self.mostrados), len(casaram)) if de_fora
                  else t("%d ícones") % len(casaram)))
        self._marcar()
        self.after(50, self._ver_o_escolhido)
        threading.Thread(target=self._pintar_thread,
                         args=(list(self.mostrados), self._pedidos),
                         daemon=True).start()

    def _pintar_thread(self, referencias, pedido):
        for referencia in referencias:
            if pedido != self._pedidos:
                return              # o filtro mudou; este lote nao vale mais
            if referencia in self.dono.icones:
                imagem = None       # ja esta no cache do dono
            else:
                imagem = self.dono.carregar_icone(referencia)
            try:
                self.after(0, self._pintar, referencia, imagem, pedido)
            except tk.TclError:
                return              # a janela fechou

    def _pintar(self, referencia, imagem, pedido):
        if pedido != self._pedidos or referencia not in self.celulas:
            return
        foto = self.dono.icones.get(referencia)
        if foto is None and imagem is not None and ImageTk is not None:
            foto = ImageTk.PhotoImage(imagem)
            self.dono.icones[referencia] = foto
        _cela, dentro = self.celulas[referencia]
        try:
            if foto is None:
                dentro.config(image="", text="?")
            else:
                dentro.config(image=foto, text="")
                dentro.imagem = foto
        except tk.TclError:
            pass

    def _ver_o_escolhido(self):
        """
        Rola ate o icone que esta escolhido, se ele estiver nesta pagina.

        Abrir a grade no topo com a escolha tres telas abaixo faria parecer que
        nada estava escolhido. Precisa do `after`: antes de o Tk desenhar, a
        cela ainda nao tem posicao.
        """
        cela = (self.celulas.get(self.referencia) or (None, None))[0]
        if cela is None or not cela.winfo_exists():
            return
        try:
            altura = max(1, self.grade.winfo_reqheight())
            self.area.tela.yview_moveto(max(0.0, (cela.winfo_y() - 8.0)
                                            / altura))
        except tk.TclError:
            pass

    def escolher(self, referencia):
        self.referencia = referencia
        self.pendente = None        # escolheu do cliente: nao ha pacote a por
        self._marcar()
        if self.ao_mudar:
            self.ao_mudar(referencia)

    def _marcar(self):
        """
        Passa a borda azul para o escolhido. Só duas células mudam.

        Percorrer as 240 a cada clique era trabalho para nada, e cada `config`
        num widget é uma volta ao Tk.
        """
        nova = (self.celulas.get(self.referencia) or (None, None))[0]
        if nova is self.marcada:
            self._dizer_o_escolhido()
            return
        if self.marcada is not None and self.marcada.winfo_exists():
            self.marcada.config(highlightbackground=COR_FUNDO_ICONE,
                                highlightcolor=COR_FUNDO_ICONE)
        if nova is not None:
            nova.config(highlightbackground=tema.INFO,
                        highlightcolor=tema.INFO)
        self.marcada = nova
        self._dizer_o_escolhido()

    def _dizer_o_escolhido(self):
        """
        O nome do escolhido, cortado pela esquerda para caber na largura fixa.

        Cortar pelo fim esconderia justamente o que distingue um ícone do
        outro: `icon.weapon_sword_i00` e `icon.weapon_sword_i01` só diferem na
        última letra.
        """
        nome = self.referencia or t("nenhum escolhido")
        if len(nome) > 33:
            nome = "…" + nome[-32:]
        self.escolhido.config(text=nome)

    # ---- imagem propria --------------------------------------------------
    def _montar_propria(self):
        caixa = ttk.LabelFrame(self, text=t("Usar uma imagem minha"), padding=6)
        caixa.pack(fill="x", pady=(8, 0))
        caixa.columnconfigure(1, weight=1)

        ttk.Label(caixa, justify="left", wraplength=430,
                  foreground=COR_TEXTO_FRACO,
                  text=t("A imagem é ajustada para o tamanho escolhido e vira "
                         "um pacote de textura seu. Ele sai junto com as "
                         "tabelas e entra no cliente em Instalar no cliente — "
                         "os pacotes do jogo não são tocados.")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        ttk.Label(caixa, text=t("imagem:")).grid(row=1, column=0, sticky="w")
        self.arquivo = tk.StringVar()
        ttk.Entry(caixa, textvariable=self.arquivo).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        acoes_da_imagem = ttk.Frame(caixa)
        acoes_da_imagem.grid(row=1, column=3, sticky="w", padx=(6, 0))
        ttk.Button(acoes_da_imagem, text=t("Escolher…"),
                   command=self.escolher_arquivo).pack(side="left")
        ttk.Button(acoes_da_imagem, text=t("IA…"), width=5,
                   command=self.gerar_com_ia).pack(side="left", padx=(4, 0))
        # 32 na maioria das cronicas, 64 em algumas: forcar um dos dois
        # jogaria fora metade do desenho no cliente errado.
        ttk.Label(acoes_da_imagem, text=t("tamanho:")).pack(side="left",
                                                            padx=(8, 0))
        self.lado_do_icone = tk.StringVar(value="32")
        caixa_lado = ttk.Combobox(acoes_da_imagem,
                                  textvariable=self.lado_do_icone,
                                  values=("32", "64"), state="readonly",
                                  width=4)
        caixa_lado.pack(side="left", padx=(4, 0))
        caixa_lado.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_previa(
            self.arquivo.get().strip()))

        ttk.Label(caixa, text=t("nome do ícone:")).grid(row=2, column=0,
                                                        sticky="w",
                                                        pady=(6, 0))
        self.nome_do_icone = tk.StringVar()
        ttk.Entry(caixa, textvariable=self.nome_do_icone, width=18).grid(
            row=2, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        ttk.Label(caixa, text=t("pacote:")).grid(row=2, column=2, sticky="e",
                                                 pady=(6, 0))
        self.pacote = tk.StringVar(
            value=motor.ler_opcao("icone", "pacote", l2icone.PACOTE_PADRAO))
        ttk.Entry(caixa, textvariable=self.pacote, width=16).grid(
            row=2, column=3, sticky="w", padx=(6, 0), pady=(6, 0))

        linha = ttk.Frame(caixa)
        linha.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.previa = self._moldura(linha)
        self.botao_preparar = ttk.Button(linha, text=t("Preparar o ícone"),
                                         command=self.preparar,
                                         state="disabled")
        self.botao_preparar.pack(side="left", padx=(10, 0))
        self.estado = ttk.Label(linha, text="", foreground=COR_TEXTO_FRACO,
                                wraplength=280, justify="left")
        self.estado.pack(side="left", padx=(10, 0))

    @staticmethod
    def _moldura(pai):
        moldura = tk.Frame(pai, bg=COR_FUNDO_ICONE, width=LADO + 10,
                           height=LADO + 10, highlightthickness=1,
                           highlightbackground=tema.BORDA,
                           highlightcolor=tema.BORDA)
        moldura.pack(side="left")
        moldura.pack_propagate(False)
        rotulo = tk.Label(moldura, bg=COR_FUNDO_ICONE, fg=tema.TEXTO_APAGADO, text="—",
                          font=("Segoe UI", 8))
        rotulo.pack(expand=True)
        return rotulo


    def gerar_com_ia(self):
        """Abre a janela que pede a arte à IA e traz o resultado para cá."""
        import gui_ia
        feito = gui_ia.JanelaDeArte(
            self.raiz, self, sugestao=self.nome_do_icone.get(),
            pai=self.winfo_toplevel()).resposta
        if not feito:
            return
        self.arquivo.set(str(feito["imagem"]))
        if feito.get("nome") and not self.nome_do_icone.get().strip():
            self.nome_do_icone.set(feito["nome"])
        self.mostrar_previa_propria()
        self.mostrar_referencia()
        if feito.get("quadros"):
            self.log(t("\nA IA gerou %d quadros de animação. Eles viram um "
                       "pacote só, com os objetos numerados, ao criar.")
                     % len(feito["quadros"]))
        self.quadros_da_ia = feito.get("quadros") or []
        if feito.get("lado"):
            self.lado_do_icone.set(str(feito["lado"]))
            self._mostrar_previa(self.arquivo.get().strip())

    def escolher_arquivo(self):
        caminho = filedialog.askopenfilename(
            title=t("Escolha a imagem"),
            filetypes=[(t(nome), padrao) for nome, padrao in TIPOS_DE_IMAGEM],
            parent=self.winfo_toplevel())
        if not caminho:
            return
        self.arquivo.set(caminho)
        if not self.nome_do_icone.get().strip():
            self.nome_do_icone.set(l2icone.limpar_nome(Path(caminho).stem))
        self._mostrar_previa(caminho)
        self.botao_preparar.config(state="normal")

    def _mostrar_previa(self, caminho):
        """Mostra como a imagem vai ficar depois do corte para o tamanho."""
        if Image is None:
            return
        try:
            destino = (Path(self.dono.trabalho()) / "icone_proprio"
                       / "previa.png")
            l2icone.preparar(caminho, destino, lado=self.lado(),
                             T=self.dono.T)
            foto = ImageTk.PhotoImage(Image.open(destino))
        except Exception as erro:                   # noqa: BLE001
            self.previa.config(image="", text="?")
            self.estado.config(text=t("Não deu para abrir a imagem: %s") % erro)
            return
        self.previa.config(image=foto, text="")
        self.previa.imagem = foto
        self.estado.config(text="")

    def preparar(self):
        """
        Monta o pacote e deixa pronto -- sem tocar no cliente.

        Dois nomes tem de servir: o do icone e o do pacote. Um pacote original
        do jogo e recusado mais adiante, pelo l2icone: remontar o Icon.utx
        poria catorze mil icones em risco por causa de um.
        """
        if self.rodando:
            return
        nome = self.nome_do_icone.get().strip()
        pacote = self.pacote.get().strip()
        if not l2icone.nome_valido(nome) or not l2icone.nome_valido(pacote):
            messagebox.showerror(
                t("Nome inválido"),
                t("Use letras, números e sublinhado, começando por letra."),
                parent=self.winfo_toplevel())
            return
        if not self.arquivo.get().strip():
            messagebox.showerror(t("Falta a imagem"),
                                 t("Escolha a imagem primeiro."),
                                 parent=self.winfo_toplevel())
            return

        motor.gravar_opcao("icone", "pacote", pacote)
        self.rodando = True
        self.botao_preparar.config(state="disabled")
        self.estado.config(text=t("montando o pacote…"))
        threading.Thread(target=self._preparar_thread,
                         args=(pacote, nome, self.arquivo.get().strip(),
                               self.lado()),
                         daemon=True).start()

    def lado(self):
        """O tamanho escolhido para o ícone, em pixels."""
        try:
            return int(self.lado_do_icone.get())
        except (AttributeError, TypeError, ValueError):
            return l2icone.LADO

    def _preparar_thread(self, pacote, nome, arquivo, lado=None):
        trabalho = Path(self.dono.trabalho()) / "icone_proprio"
        try:
            referencia, feito = l2icone.montar_para_o_cliente(
                self.dono.T, self.dono.cliente.get(), pacote, nome, arquivo,
                trabalho, instalar_no_cliente=False,
                lado=lado or l2icone.LADO)
            erro = None
        except Exception as e:                      # noqa: BLE001
            referencia, feito, erro = None, None, e
        try:
            self.after(0, self._fim_preparo, referencia, feito, erro)
        except tk.TclError:
            pass

    def _fim_preparo(self, referencia, feito, erro):
        self.rodando = False
        self.botao_preparar.config(state="normal")
        if erro is not None:
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para criar o ícone"), str(erro),
                                 parent=self.winfo_toplevel())
            return
        self.referencia = referencia
        self.pendente = feito if feito and Path(feito).is_file() else None
        self._marcar()
        self.estado.config(
            text=t("%s pronto. Vai para o cliente junto com as tabelas.")
            % referencia)
        if self.ao_mudar:
            self.ao_mudar(referencia)


class EscolherIcone:
    """
    Devolve em `.resposta` a referencia escolhida, ou None se o usuario
    desistiu.

    `dono` e a aba que abriu a janela: dela vem o cache de imagens ja lidas, o
    caminho do cliente e a pasta de trabalho.
    """

    def __init__(self, raiz, dono, catalogo, atual=""):
        self.raiz = raiz
        self.dono = dono
        self.catalogo = list(catalogo)
        self.mostrados = []
        self.resposta = None
        self.rodando = False
        self.imagem_propria = None

        self.janela = tk.Toplevel(raiz)
        self.janela.title(t("Escolher o ícone"))
        self.janela.transient(raiz)
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        ajuda.por_icone(self.janela)

        abas = ttk.Notebook(self.janela)
        abas.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        abas.add(self._montar_do_cliente(abas), text=t(" Do cliente "))
        abas.add(self._montar_propria(abas), text=t(" Imagem própria "))

        baixo = ttk.Frame(self.janela)
        baixo.pack(fill="x", padx=10, pady=10)
        ttk.Button(baixo, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")

        if atual:
            self.filtro.set(atual.split(".")[-1][:12])
        self.preencher()
        if atual in self.mostrados:
            indice = self.mostrados.index(atual)
            self.lista.selection_set(indice)
            self.lista.see(indice)
            self.ao_marcar()

        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        raiz.wait_window(self.janela)

    # ---- aba: do cliente -------------------------------------------------
    def _montar_do_cliente(self, pai):
        aba = ttk.Frame(pai, padding=8)

        topo = ttk.Frame(aba)
        topo.pack(fill="x")
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(topo, textvariable=self.filtro, width=34)
        entrada.pack(side="left", padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self.preencher())
        self.conta = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        corpo = ttk.Frame(aba)
        corpo.pack(fill="both", expand=True, pady=(8, 0))

        self.lista = tk.Listbox(corpo, width=46, height=17,
                                exportselection=False)
        barra = ttk.Scrollbar(corpo, orient="vertical", command=self.lista.yview)
        self.lista.config(yscrollcommand=barra.set)
        barra.pack(side="left", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", self.ao_marcar)
        self.lista.bind("<Double-Button-1>", lambda _e: self.aceitar())

        lado = ttk.Frame(corpo, padding=(12, 0, 0, 0))
        lado.pack(side="left", fill="y")
        self.previa = self._moldura(lado)
        self.nome = ttk.Label(lado, text="", foreground=COR_TEXTO_FRACO,
                              wraplength=180, justify="left")
        self.nome.pack(anchor="w", pady=(6, 0))

        ttk.Button(aba, text=t("Usar este"),
                   command=self.aceitar).pack(anchor="w", pady=(8, 0))
        return aba

    # ---- aba: imagem propria ---------------------------------------------
    def _montar_propria(self, pai):
        aba = ttk.Frame(pai, padding=8)

        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Escolha uma imagem sua. Ela é ajustada para o "
                         "tamanho escolhido e vira um pacote de textura, que "
                         "entra no cliente junto com as tabelas, em Instalar "
                         "no cliente. O pacote é seu -- os do jogo não são "
                         "tocados.")
                  ).pack(anchor="w")

        linha = ttk.Frame(aba)
        linha.pack(fill="x", pady=(10, 0))
        ttk.Label(linha, text=t("Imagem:")).pack(side="left")
        self.arquivo = tk.StringVar()
        ttk.Entry(linha, textvariable=self.arquivo).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(linha, text=t("Escolher…"),
                   command=self.escolher_arquivo).pack(side="left", padx=(6, 0))
        ttk.Button(linha, text=t("Gerar com IA…"),
                   command=self.gerar_com_ia).pack(side="left", padx=(6, 0))
        ttk.Label(linha, text=t("tamanho:")).pack(side="left", padx=(10, 0))
        self.lado_do_icone = tk.StringVar(value="32")
        caixa_lado = ttk.Combobox(linha, textvariable=self.lado_do_icone,
                                  values=("32", "64"), state="readonly",
                                  width=4)
        caixa_lado.pack(side="left", padx=(4, 0))
        caixa_lado.bind("<<ComboboxSelected>>",
                        lambda _e: self.mostrar_previa_propria())

        corpo = ttk.Frame(aba)
        corpo.pack(fill="x", pady=(10, 0))

        lado = ttk.Frame(corpo)
        lado.pack(side="left")
        self.previa_propria = self._moldura(lado)
        ttk.Label(lado, text=t("como vai ficar"), foreground=COR_TEXTO_FRACO,
                  font=("Segoe UI", 8)).pack(anchor="center", pady=(4, 0))

        campos = ttk.Frame(corpo)
        campos.pack(side="left", fill="x", expand=True, padx=(14, 0))
        campos.columnconfigure(1, weight=1)

        ttk.Label(campos, text=t("nome do ícone:")).grid(row=0, column=0,
                                                         sticky="w")
        self.nome_do_icone = tk.StringVar()
        ttk.Entry(campos, textvariable=self.nome_do_icone).grid(
            row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(campos, text=t("pacote:")).grid(row=1, column=0, sticky="w",
                                                  pady=(6, 0))
        self.pacote = tk.StringVar(
            value=motor.ler_opcao("icone", "pacote", l2icone.PACOTE_PADRAO))
        ttk.Entry(campos, textvariable=self.pacote).grid(
            row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        self.rotulo_ref = ttk.Label(campos, text="", foreground=tema.TEXTO_FRACO,
                                    font=("Segoe UI", 8))
        self.rotulo_ref.grid(row=2, column=0, columnspan=2, sticky="w",
                             pady=(6, 0))
        for var in (self.nome_do_icone, self.pacote):
            var.trace_add("write", lambda *_a: self.mostrar_referencia())

        acao = ttk.Frame(aba)
        acao.pack(fill="x", pady=(12, 0))
        self.botao_criar = ttk.Button(acao, text=t("Criar e usar"),
                                      command=self.criar, state="disabled")
        self.botao_criar.pack(side="left")
        self.estado = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(side="left", padx=(10, 0))
        ajuda.ajuda(acao, lambda: t(
            "O pacote é criado com o nome que você escolher e vai para "
            "systextures em Instalar no cliente, com as tabelas. Acrescentar "
            "um segundo ícone ao mesmo pacote remonta o pacote inteiro, com "
            "os que já estavam lá.\n\n"
            "Um pacote original do jogo é recusado: reescrevê-lo poria "
            "milhares de ícones em risco por causa de um."), padx=(10, 0))

        reg = ttk.LabelFrame(aba, text=t("Andamento"), padding=4)
        reg.pack(fill="both", expand=True, pady=(10, 0))
        self.texto = tk.Text(reg, height=6, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)
        return aba

    @staticmethod
    def _moldura(pai):
        moldura = tk.Frame(pai, bg=COR_FUNDO_ICONE, width=LADO + 10,
                           height=LADO + 10, highlightthickness=1,
                           highlightbackground=tema.BORDA,
                           highlightcolor=tema.BORDA)
        moldura.pack()
        moldura.pack_propagate(False)
        rotulo = tk.Label(moldura, bg=COR_FUNDO_ICONE, fg=tema.TEXTO_APAGADO, text="—",
                          font=("Segoe UI", 8))
        rotulo.pack(expand=True)
        return rotulo

    # ---- a lista do cliente ----------------------------------------------
    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        self.mostrados = [r for r in self.catalogo
                          if not procurado or procurado in r.lower()]
        self.lista.delete(0, "end")
        for referencia in self.mostrados:
            self.lista.insert("end", referencia)
        self.conta.config(text=t("%d de %d") % (len(self.mostrados),
                                                len(self.catalogo)))

    def ao_marcar(self, _evento=None):
        escolhido = self.lista.curselection()
        if not escolhido:
            return
        referencia = self.mostrados[escolhido[0]]
        self.nome.config(text=referencia)
        if Image is None:
            return
        if referencia in self.dono.icones:
            self._desenhar(self.previa, self.dono.icones[referencia])
            return
        self.previa.config(image="", text="…")
        threading.Thread(target=self._carregar, args=(referencia,),
                         daemon=True).start()

    def _carregar(self, referencia):
        imagem = self.dono.carregar_icone(referencia)
        try:
            self.janela.after(0, self._guardar, referencia, imagem)
        except tk.TclError:
            pass                    # a janela foi fechada antes de chegar

    def _guardar(self, referencia, imagem):
        foto = ImageTk.PhotoImage(imagem) if imagem is not None else None
        self.dono.icones[referencia] = foto
        escolhido = self.lista.curselection()
        if escolhido and self.mostrados[escolhido[0]] == referencia:
            self._desenhar(self.previa, foto)

    @staticmethod
    def _desenhar(rotulo, foto):
        if foto is None:
            rotulo.config(image="", text="—")
        else:
            rotulo.config(image=foto, text="")
        rotulo.imagem = foto

    def aceitar(self):
        escolhido = self.lista.curselection()
        if escolhido:
            self.resposta = self.mostrados[escolhido[0]]
            self.janela.destroy()

    # ---- a imagem propria ------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def escolher_arquivo(self):
        caminho = filedialog.askopenfilename(
            parent=self.janela, title=t("Escolha a imagem do ícone"),
            filetypes=[(t(rotulo), padrao) for rotulo, padrao in TIPOS_DE_IMAGEM])
        if not caminho:
            return
        self.arquivo.set(caminho)
        if not self.nome_do_icone.get().strip():
            self.nome_do_icone.set(l2icone.limpar_nome(Path(caminho).stem))
        self.mostrar_previa_propria()
        self.mostrar_referencia()


    def gerar_com_ia(self):
        """
        Pede a arte à IA e traz o resultado para o campo de imagem própria.

        Mesma janela que o painel usa: o pedido é o mesmo venha de onde vier.
        """
        import gui_ia
        feito = gui_ia.JanelaDeArte(
            self.raiz, self.dono, sugestao=self.nome_do_icone.get(),
            pai=self.janela).resposta
        if not feito:
            return
        self.arquivo.set(str(feito["imagem"]))
        if feito.get("nome") and not self.nome_do_icone.get().strip():
            self.nome_do_icone.set(feito["nome"])
        if feito.get("lado"):
            self.lado_do_icone.set(str(feito["lado"]))
        self.quadros_da_ia = feito.get("quadros") or []
        try:
            self.mostrar_previa_propria()
            self.mostrar_referencia()
        except Exception:                           # noqa: BLE001
            pass
        if self.quadros_da_ia:
            self.log(t("\nA IA gerou %d quadros. Eles entram no mesmo pacote, "
                       "numerados, quando você criar.") % len(self.quadros_da_ia))

    def mostrar_previa_propria(self):
        """
        Mostra o desenho como ele vai ficar: no tamanho escolhido, encaixado
        no centro.
        """
        caminho = self.arquivo.get().strip()
        if Image is None or not caminho:
            return
        try:
            pronta = l2icone.preparar(
                caminho, Path(self.dono.trabalho()) / "previa_icone.png",
                lado=self.lado(), T=self.dono.T)
            imagem = motor.abrir_imagem(pronta, self.dono.T)
        except Exception as erro:                   # noqa: BLE001
            self.log(t("Não deu para ler a imagem: %s") % erro)
            self._desenhar(self.previa_propria, None)
            return
        foto = ImageTk.PhotoImage(imagem)
        self.imagem_propria = foto
        self._desenhar(self.previa_propria, foto)

    def mostrar_referencia(self):
        pacote = self.pacote.get().strip()
        nome = self.nome_do_icone.get().strip()
        pronto = (l2icone.nome_valido(pacote) and l2icone.nome_valido(nome)
                  and Path(self.arquivo.get().strip() or ".").is_file())
        self.rotulo_ref.config(
            text=(t("vai virar: %s.%s") % (pacote, nome)) if pronto else "")
        self.botao_criar.config(
            state="normal" if pronto and not self.rodando else "disabled")

    def criar(self):
        """Monta o pacote. O cliente so muda em Instalar no cliente."""
        if self.rodando:
            return
        pacote = self.pacote.get().strip()
        nome = self.nome_do_icone.get().strip()
        if not l2icone.nome_valido(nome) or not l2icone.nome_valido(pacote):
            messagebox.showerror(
                t("Nome inválido"),
                t("Use letras, números e sublinhado, começando por letra."),
                parent=self.janela)
            return

        motor.gravar_opcao("icone", "pacote", pacote)
        self.rodando = True
        self.botao_criar.config(state="disabled")
        self.estado.config(text=t("montando o pacote…"))
        self.log(t("\n=== criando %s.%s ===") % (pacote, nome))
        threading.Thread(target=self._criar_thread,
                         args=(pacote, nome, self.arquivo.get().strip(),
                               list(getattr(self, "quadros_da_ia", [])),
                               self.lado()),
                         daemon=True).start()

    def lado(self):
        """O tamanho escolhido para o ícone, em pixels."""
        try:
            return int(self.lado_do_icone.get())
        except (AttributeError, TypeError, ValueError):
            return l2icone.LADO

    def _criar_thread(self, pacote, nome, arquivo, quadros=(), lado=None):
        def anotar(texto):
            try:
                self.janela.after(0, self.log, "  " + texto)
            except tk.TclError:
                pass

        try:
            referencia, feito = l2icone.montar_para_o_cliente(
                self.dono.T, self.dono.cliente.get(), pacote, nome, arquivo,
                Path(self.dono.trabalho()) / "icone_proprio", aolog=anotar,
                instalar_no_cliente=False, quadros=quadros,
                lado=lado or l2icone.LADO)
            erro = None
        except Exception as e:                      # noqa: BLE001
            referencia, feito, erro = None, None, e
        try:
            self.janela.after(0, self._fim_criacao, referencia, feito, erro)
        except tk.TclError:
            pass

    def _fim_criacao(self, referencia, feito, erro):
        self.rodando = False
        self.estado.config(text="")
        self.mostrar_referencia()
        if erro is not None:
            self.log(t("Parou: %s") % erro)
            messagebox.showerror(t("Não deu para criar o ícone"), str(erro),
                                 parent=self.janela)
            return
        self.resposta = referencia
        # O pacote fica com a aba, que o poe no cliente junto com as tabelas.
        # O cliente muda num lugar so.
        if feito and Path(feito).is_file():
            self.dono.icone_pendente = Path(feito)
        self.log(t("pronto: %s") % referencia)
        messagebox.showinfo(
            t("Ícone criado"),
            t("%s está pronto. Ele vai para o cliente junto com as tabelas, "
              "em Instalar no cliente.") % referencia,
            parent=self.janela)
        self.janela.destroy()
