#!/usr/bin/env python3
"""
Aba "NPC com efeito" -- a interface.

O trabalho pesado esta no l2npc.py; aqui so ha a tela. A divisao e a mesma do
resto do programa: nada que demore roda na thread da interface, porque uma
janela congelada e indistinguivel de uma travada, e o Windows ainda a marca
como "nao responde".

A tela tem tres partes, na ordem em que se usa:

  1. os NPCs que o cliente ja tem, para escolher de quem copiar a aparencia
  2. os efeitos que o cliente ja tem, para escolher o que vai brilhar
  3. o formulario do NPC novo, e os dois botoes -- gerar e instalar

Gerar e instalar sao passos separados de proposito. Gerar escreve tudo numa
pasta de saida e nao toca no cliente; o usuario ve o que saiu e so entao
autoriza a copia. Quem instala por engano num cliente que usa para jogar
descobre o problema na hora de entrar no jogo, que e tarde.
"""

import threading
import time
import tkinter as tk
import shutil
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

import tema
import l2npc
import idioma
import ajuda
import gui_mundo
import gui_projeto
from idioma import t, N_
import motor

# A regua. Largura e altura do desenho, em pixels.
LARGURA_REGUA = 330
ALTURA_REGUA = 250

# Onde o efeito cai no corpo, por fracao da altura da malha. Serve para trocar
# um numero solto ("Z = 20") por uma referencia que se entende de imediato.
FAIXAS_DO_CORPO = (
    (0.10, N_("nos pes")),
    (0.30, N_("na altura das pernas")),
    (0.52, N_("na altura da cintura")),
    (0.80, N_("na altura do peito")),
    (1.00, N_("na altura da cabeca")),
)

# As marcas desenhadas na regua, como fracao da altura da malha. Sao poucas de
# proposito: servem para situar o Z de relance, e uma regua cheia de rotulos
# deixa de ser lida.
# As marcas sao fracoes da altura CONTADAS DO CHAO, e o chao nao e o zero da
# malha -- ver `desenhar_regua`.
MARCAS_DO_CORPO = (
    (0.00, N_("pes")),
    (0.52, N_("cintura")),
    (0.88, N_("cabeca")),
    (1.08, N_("acima da cabeca")),
)

# Onde o cliente costuma estar, para a primeira vez doer menos.
PALPITES = (
    r"C:\Lineage II",
    r"C:\Lineage 2",
    r"C:\L2",
    r"C:\Games\Lineage II",
    r"D:\Lineage II",
)


def achar_cliente():
    """O primeiro palpite que tiver um npcgrp.dat dentro. Vazio se nenhum."""
    guardado = motor.ler_opcao("cliente", "system", "")
    if guardado and (Path(guardado) / "npcgrp.dat").exists():
        return guardado

    for raiz in PALPITES:
        system = Path(raiz) / "system"
        if (system / "npcgrp.dat").exists():
            return str(system)

    return ""


class JanelaNpc:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()

        self.npcs = []              # resumo do npcgrp
        self.nomes = {}             # id -> nome, do npcname-e.dat
        self.titulos = {}           # id -> titulo, da mesma linha
        self.efeitos = []           # catalogo
        self.recusados = []
        self.escolhidos = []        # efeitos que vao para o NPC novo
        self.ultimo_relatorio = None
        self.vigiando = False       # ha uma thread esperando o jogo fechar?
        self.tentou_substituir = False   # ja perguntei "substituir?" nesta geracao
        self.base_da_ultima = None       # NPC base da geracao em curso

        # Altura da malha do NPC base, medida dos vertices. None enquanto nao
        # se sabe; a regua se desenha assim mesmo, so sem a referencia.
        self.dados_da_malha_atual = {}
        self.altura_malha = None
        self.chao_malha = 0.0
        self.topo_malha = None
        self.ossos_malha = []
        self.malha_atual = ""
        self.desenho_regua = None       # referencia viva do PhotoImage

        # Cada abertura recomeca o arquivo: interessa o que aconteceu AGORA, e
        # um registro que so cresce vira lixo que ninguem le.
        self.diario = motor.BASE / "npc.log"
        try:
            self.diario.write_text(
                "L2PackTool - aba NPC com efeito\n%s\n\n"
                % time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        except OSError:
            import tempfile
            self.diario = Path(tempfile.gettempdir()) / "L2PackTool-npc.log"

        # Os passos. O NPC e um assunto so -- aparencia, efeito e atributos do
        # servidor sao partes do mesmo bicho -- mas cabem mal na mesma tela, e
        # a ordem em que se preenche e sempre esta.
        self.passos = ttk.Notebook(pai)
        self.passos.pack(fill="both", expand=True)

        primeiro = ttk.Frame(self.passos)
        self.passos.add(primeiro, text=t(" 1 - Cliente e efeitos "))

        quadro = ttk.Frame(primeiro, padding=10)
        quadro.pack(fill="both", expand=True)

        # ---- cliente ----
        topo = ttk.LabelFrame(quadro, text=t("Cliente"), padding=8)
        topo.pack(fill="x")
        self.cliente = tk.StringVar(value=achar_cliente())
        self.botao_ler = ttk.Button(topo, text=t("Carregar"), command=self.ler_cliente)
        self.botao_ler.pack(side="left", padx=(8, 0))
        self.botao_editar_npc = ttk.Button(
            topo, text=t("Editar este NPC…"), command=self.editar_existente,
            state="disabled")
        self.botao_editar_npc.pack(side="left", padx=(8, 0))
        ajuda.Dica(self.botao_editar_npc, lambda: t(
            "Traz o NPC marcado na lista da esquerda para o formulário, para "
            "você acrescentar efeito a um NPC que JÁ EXISTE.\n\n"
            "O id, o nome e o título vêm dele. Se ele foi criado por este "
            "programa, os efeitos que já tem voltam também, e você acrescenta "
            "aos que estão lá.\n\n"
            "Ao gerar, o programa pergunta se pode substituir: a linha antiga "
            "sai e a nova entra no lugar, com o mesmo id.\n\n"
            "Duplo clique na lista faz o mesmo."))

        ttk.Button(topo, text=t("NPCs criados…"),
                   command=self.abrir_criados).pack(side="left", padx=(8, 0))
        ajuda.ajuda(topo, lambda: t(
            "Ler o cliente carrega os NPCs e os efeitos que ele já tem. A "
            "primeira leitura demora, porque varre todos os pacotes atrás de "
            "emissores; depois fica em cache.\n\n"
            "NPCs criados lista o que este programa já pôs neste cliente, com "
            "duplo clique para editar e botão para remover."))

        # ---- as duas listas ----
        meio = ttk.Frame(quadro)
        meio.pack(fill="both", expand=True, pady=(8, 0))
        meio.columnconfigure(0, weight=1, uniform="listas")
        meio.columnconfigure(1, weight=1, uniform="listas")
        meio.rowconfigure(0, weight=1)

        self.lista_npc, self.busca_npc = self._lista(
            meio, 0, N_("NPCs do cliente"),
            (N_("id"), N_("nome"), N_("classe"), N_("efeito")),
            (60, 170, 210, 150), self.filtrar_npcs)
        self.lista_fx, self.busca_fx = self._lista(
            meio, 1, N_("Efeitos instalados"),
            (N_("caminho"), N_("emissores")),
            (330, 150), self.filtrar_efeitos)
        # Varios de uma vez: um NPC pode acender mais de um emissor.
        self.lista_fx.config(selectmode="extended")
        self.lista_fx.bind("<Double-1>", lambda _e: self.adicionar_efeito())
        self.lista_npc.bind("<<TreeviewSelect>>", lambda _e: self.npc_selecionado())
        # Duplo clique num NPC do cliente: traz ele para o formulario, do mesmo
        # jeito que o duplo clique na lista dos criados.
        self.lista_npc.bind("<Double-1>", lambda _e: self.editar_existente())

        # ---- formulario ----
        baixo = ttk.LabelFrame(quadro, text=t("NPC"), padding=8)

        # Qual NPC este formulario esta montando, dito em letras grandes. Sem
        # isto, editar o 60000 punha o 20001 marcado na lista da esquerda --
        # que e a base, e esta certo -- e parecia que o 60000 se perdeu.
        self.rotulo_alvo = ttk.Label(baixo, text="",
                                     font=("Segoe UI", 10, "bold"),
                                     wraplength=900, justify="left")
        self.rotulo_alvo.pack(anchor="w", pady=(0, 6))
        baixo.pack(fill="x", pady=(8, 0))

        # A regua fica a direita dos campos, e nao embaixo: quem mexe na altura
        # precisa ver as duas coisas ao mesmo tempo.
        previa = ttk.Frame(baixo)
        previa.pack(side="right", fill="y", padx=(12, 0))
        self.rotulo_regua = ttk.Label(previa)
        self.rotulo_regua.pack()
        self.botao_ver = ttk.Button(previa, text=t("Ver a malha em 3D"),
                                    command=self.ver_malha, state="disabled")
        self.botao_ver.pack(fill="x", pady=(6, 0))
        ajuda.Dica(self.botao_ver, lambda: t(
            "Abre a malha do NPC base no visualizador do umodel, para girar e "
            "ver as animações.\n\n"
            "O EFEITO não aparece ali: partícula do Unreal Engine 2 só o "
            "próprio jogo desenha. Para ver o efeito, use o DevMode."))

        botao_dev = ttk.Button(previa, text=t("Abrir o jogo em DevMode"),
                               command=self.abrir_devmode)
        botao_dev.pack(fill="x", pady=(4, 0))
        ajuda.Dica(botao_dev, lambda: t(
            "Abre o cliente sem servidor, num mapa local, com o console de "
            "desenvolvimento ligado -- o único jeito de ver o efeito de "
            "verdade.\n\n"
            "No jogo: Tab abre o console; o comando para chamar o NPC já fica "
            "na área de transferência.\n\n"
            "O l2.ini e o user.ini do cliente são copiados antes e devolvidos "
            "quando o jogo fecha: sem isso o jogo normal não abriria depois."))

        esquerda = ttk.Frame(baixo)
        esquerda.pack(side="left", fill="both", expand=True)
        baixo = esquerda      # o resto do formulario continua igual, aqui dentro

        linha1 = ttk.Frame(baixo)
        linha1.pack(fill="x")
        # O id que foi aberto para EDICAO. Enquanto o campo continuar com
        # ele, a tela diz "editando"; mudando o numero, vira NPC novo -- que e
        # exatamente o que mudar o id significa.
        self.editando_tag = None
        self.id_novo = tk.StringVar(value="50100")
        self.nome_novo = tk.StringVar(value="")
        # O rotulo acompanha os campos sozinho: e uma linha de
        # leitura, e mante-la por chamada em cada lugar que mexe
        # nos campos seria esquecer um deles mais cedo ou mais
        # tarde.
        for _v in (self.id_novo, self.nome_novo):
            _v.trace_add("write", lambda *_a: self.dizer_o_alvo())
        self.titulo_novo = tk.StringVar(value="")
        self._campo(linha1, N_("Id novo:"), self.id_novo, 8, dica=lambda: t(
            "O número do NPC novo, do lado do cliente e do servidor.\n\n"
            "Precisa estar livre: o programa sugere o próximo depois do maior "
            "que achou no npcgrp.dat do seu cliente.\n\n"
            "Se o id já existir, ele pergunta se você quer gerar por cima -- a "
            "linha antiga sai e a nova entra no lugar."))
        self._campo(linha1, N_("Nome:"), self.nome_novo, 22, dica=lambda: t(
            "O nome que aparece sobre a cabeça do NPC no jogo.\n\n"
            "Vai para o npcname-e.dat do cliente e para o XML do servidor, "
            "com usingServerSideName ligado.\n\n"
            "Pode ficar vazio: aí o NPC nasce sem nome."))
        self._campo(linha1, N_("Título:"), self.titulo_novo, 18, dica=lambda: t(
            "A linha menor acima do nome -- \"Mercador\", \"Guardião\", o que "
            "você quiser.\n\n"
            "Também é opcional."))

        # Cada grupo na sua linha, e nao tudo numa so. Os mesmos rotulos em
        # ingles e espanhol sao bem mais largos que em portugues: enfileirados,
        # passavam da largura da coluna e o ultimo controle saia cortado.
        modos = ttk.Frame(baixo)
        modos.pack(fill="x", pady=(6, 0))
        self.modo = tk.StringVar(value="script")
        ttk.Radiobutton(modos, text=t("Script (compila)"), value="script",
                        variable=self.modo, command=self.trocar_modo
                        ).pack(side="left")
        ttk.Radiobutton(modos, text=t("Rapido (so o .dat)"), value="rapido",
                        variable=self.modo, command=self.trocar_modo
                        ).pack(side="left", padx=(12, 0))
        ajuda.ajuda(modos, lambda: t(
            "SCRIPT: vários efeitos no mesmo NPC, com controle de altura, "
            "escala e osso. É o modo completo.\n\n"
            "RÁPIDO: um efeito só, sem ajuste de altura nem de osso. Em "
            "compensação é imediato."))

        linha2 = ttk.Frame(baixo)
        linha2.pack(fill="x", pady=(6, 0))
        # Preenchido com os ossos da malha assim que um NPC base e escolhido.
        self._escrevendo_campos = False
        # O tamanho do BONECO, e nao do efeito. Vai em DrawScale, do
        # lado do cliente: o servidor nao tem campo para isso.
        self.tamanho = tk.StringVar(value="1.00")
        self.obedece = tk.BooleanVar(value=True)
        self.osso = tk.StringVar(value="")
        self.altura = tk.StringVar(value="20")
        self.escala = tk.StringVar(value="1.00")
        # Animacao que o NPC toca quando o jogador clica nele. 1 e o slot
        # SpWait01, o unico que praticamente toda malha do jogo possui; 0
        # devolve o NPC ao sorteio padrao do servidor.
        self.social = tk.StringVar(value="1")
        # O osso vira lista, e nao texto: os nomes vem do esqueleto da malha, e
        # digitar um que nao existe faz o AttachToBone nao achar onde prender.
        ttk.Label(linha2, text=t("Osso:")).pack(side="left", padx=(0, 4))
        self.entrada_osso = ttk.Combobox(linha2, textvariable=self.osso, width=20,
                                         state="readonly", values=())
        self.entrada_osso.pack(side="left", padx=(0, 2))
        ajuda.ajuda(linha2, lambda: t(
            "Onde o efeito fica preso no corpo do NPC.\n\n"
            "A lista vem do esqueleto da malha escolhida, não de uma lista "
            "fixa: cada modelo tem os ossos dele. O Bip01 é a raiz, e serve "
            "para quase tudo.\n\n"
            "Preso a um osso, o efeito acompanha o movimento daquela parte do "
            "corpo."), padx=(0, 12))
        self.entrada_altura = self._campo(
            linha2, N_("Altura (Z):"), self.altura, 7, dica=lambda: t(
                "A que altura o efeito fica, em unidades do jogo, contadas "
                "do CHÃO do boneco -- é o que a régua ao lado mostra: pés, "
                "cintura, peito, cabeça, ou acima dela.\n\n"
                "O osso decide o X e o Y: o efeito acompanha aquela parte do "
                "corpo. A altura decide o Z, e vale sozinha.\n\n"
                "Com altura 0 o efeito fica preso ao osso, sem ajuste -- que "
                "é o que se quer para um brilho na mão.\n\n"
                "Aceita número negativo, para descer abaixo do chão."))
        ttk.Checkbutton(
            linha2, variable=self.obedece,
            text=t("obedecer à altura")).pack(side="left", padx=(10, 0))
        ajuda.ajuda(linha2, lambda: t(
            "Muitos efeitos trazem a posição dentro de si e ignoram onde o "
            "programa os põe -- um marcador de quest já vem feito para pairar "
            "sobre a cabeça, e vai continuar lá por mais que você mude a "
            "altura.\n\n"
            "Marcado, o programa põe cada emissor de partícula do efeito em "
            "PTCS_Relative e zera o deslocamento próprio dele. Aí quem manda "
            "na posição é a altura desta tela.\n\n"
            "Desmarque para deixar o efeito exatamente como o autor dele "
            "fez."), padx=(4, 0))

        self._campo(linha2, N_("Escala:"), self.escala, 7, dica=lambda: t(
            "O tamanho do efeito.\n\n"
            "1.00 é o tamanho com que ele foi feito. 0.50 é metade; 2.00 é o "
            "dobro.\n\n"
            "Efeito pensado para um dragão costuma engolir um humano: é aqui "
            "que se ajusta."))
        self._campo(linha2, N_("Tamanho do NPC:"), self.tamanho, 7,
                    dica=lambda: t(
            "O tamanho do boneco, e não do efeito. 1,00 é o tamanho "
            "original; 2,00 dobra.@@"
            "Vai em DrawScale, do lado do cliente -- o servidor não tem "
            "campo para isso, e o tamanho é desenho.@@"
            "A colisão acompanha sozinha: o motor desenha a malha "
            "centrada no ponto do NPC, então a altura de colisão tem de "
            "ser a METADE da altura desenhada. Dobrar o boneco sem dobrar "
            "o cilindro o enterra até o peito -- por isso mudar este "
            "campo refaz raio e altura na aba 2.@@"
            "No visualizador do cliente (DevMode) a colisão vem do campo "
            "ColliH da própria janela dele, e não do XML: para ver o "
            "tamanho novo ali, digite a altura de colisão e clique em "
            "Apply.")
                    .replace("@@", chr(10) + chr(10)))
        self._campo(linha2, N_("Social ao clicar:"), self.social, 5, dica=lambda: t(
            "A animação que o NPC faz quando o jogador clica nele, para ficar "
            "claro que ele percebeu o clique.\n\n"
            "1 é o SpWait01, que praticamente toda malha do jogo tem. 2 e 3 "
            "existem em parte delas.\n\n"
            "0 desliga: o NPC volta ao sorteio normal do servidor.\n\n"
            "Depende do servidor ler socialAction no XML do NPC."))

        linha3 = ttk.Frame(baixo)
        linha3.pack(fill="x", pady=(6, 0))
        ttk.Button(linha3, text=t("Adicionar o efeito selecionado"),
                   command=self.adicionar_efeito).pack(side="left")
        ttk.Button(linha3, text=t("Aplicar ao marcado"),
                   command=self.aplicar_ao_escolhido).pack(side="left", padx=(6, 0))
        ttk.Button(linha3, text=t("Tirar"),
                   command=self.tirar_efeito).pack(side="left", padx=(6, 0))

        self.lista_escolhidos = tk.Listbox(baixo, height=3,
                                           exportselection=False)
        self.lista_escolhidos.bind("<<ListboxSelect>>",
                                   self.efeito_escolhido_marcado)
        self.lista_escolhidos.pack(fill="x", pady=(6, 0))

        acao = ttk.Frame(baixo)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_gerar = ttk.Button(acao, text=t("Gerar"), command=self.gerar,
                                      state="disabled")
        self.botao_gerar.pack(side="left")
        self.botao_instalar = ttk.Button(acao, text=t("Instalar no cliente"),
                                         command=self.instalar, state="disabled")
        self.botao_instalar.pack(side="left", padx=(8, 0))
        ajuda.ajuda(acao, lambda: t(
            "Gerar monta tudo numa pasta de trabalho e não toca no cliente: "
            "sai dali o npcgrp.dat e o npcname-e.dat com a linha nova, o "
            "pacote do NPC e o XML do servidor.\n\n"
            "Instalar copia isso para dentro do cliente, guardando o que "
            "estava lá em system/backup_npc antes.\n\n"
            "São dois passos de propósito: dá para conferir o que saiu antes "
            "de mexer num cliente que você usa para jogar."), padx=(10, 0))
        self.estado = ttk.Label(acao, text="", foreground=tema.TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

        # ---- registro ----
        reg = ttk.LabelFrame(quadro, text=t("Andamento"), padding=4)
        reg.pack(fill="both", expand=True, pady=(8, 0))
        self.texto = tk.Text(reg, height=8, wrap="word", font=("Consolas", 9))
        rolagem = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

        # Os campos valem para o efeito JA escolhido, e nao so para o
        # proximo a ser acrescentado.
        for variavel in (self.osso, self.altura, self.escala, self.obedece):
            variavel.trace_add("write", self.campos_do_efeito_mudaram)
        # Mudar o tamanho refaz a colisao na hora: um boneco dobrado com o
        # cilindro antigo nasce enterrado ate o peito, e ninguem tem de
        # lembrar de apertar um botao para isso nao acontecer.
        self.tamanho.trace_add("write", self.tamanho_mudou)

        for variavel in (self.altura, self.escala):
            variavel.trace_add("write", lambda *_a: self.desenhar_regua())

        segundo = ttk.Frame(self.passos)
        self.passos.add(segundo, text=t(" 2 - Servidor "))
        self.servidor = gui_mundo.PainelServidor(segundo, self)

        self.trocar_modo()
        self.desenhar_regua()
        if self.cliente.get():
            self.log(t("Cliente encontrado em %s") % self.cliente.get())
            self.log(t("Clique em \"Ler o cliente\" para carregar NPCs e efeitos."))
            # Se a sessao passada terminou com o jogo aberto, as copias dos
            # .ini ficaram para tras e o cliente esta com eles em texto puro.
            self.conferir_inis_pendentes()
        else:
            self.log(t("Aponte a pasta system do cliente para comecar."))

    # ---- o que o painel do servidor pergunta ------------------------------
    def id_do_npc(self):
        return self.id_novo.get().strip()

    def tamanho_mudou(self, *_a):
        """
        Refaz a colisao quando o tamanho muda.

        So quando a malha ja foi medida: sem ela nao ha o que calcular, e
        escrever um numero inventado nos dois campos seria pior do que deixar
        os que estao la.
        """
        painel = getattr(self, "servidor", None)
        if painel is None or not (self.dados_da_malha_atual or {}).get("altura"):
            return
        try:
            painel.medir_colisao(calado=True)
        except Exception:                           # noqa: BLE001
            pass            # campo pela metade enquanto se digita: sem drama

    def tamanho_do_npc(self):
        """O tamanho digitado, ou 1.0 se o campo estiver ilegivel."""
        try:
            return float(self.tamanho.get().replace(",", "."))
        except ValueError:
            return 1.0

    def nome_do_npc(self):
        """
        O nome do NPC, resolvido -- nunca vazio.

        O .dat do cliente e o XML do servidor leem daqui, entao os dois recebem
        a mesma coisa. Quando cada um resolvia o vazio por conta propria, o
        servidor ficava com `NPC 90006` e o cliente com nada, e o jogador via
        **NoNameNPC** em cima da cabeca do monstro.
        """
        digitado = self.nome_novo.get().strip()
        if digitado:
            return digitado
        base = self.base_selecionado()
        do_base = (self.nomes.get(base, "") or "").strip() if base else ""
        return do_base or (t("NPC %s") % (self.id_do_npc() or "?"))

    def titulo_do_npc(self):
        return self.titulo_novo.get().strip()

    def base_do_npc(self):
        selecao = self.lista_npc.selection()
        if not selecao:
            return ""
        valor = self.lista_npc.item(selecao[0], "values")[0]
        return "" if valor == "\u2026" else valor

    def proximo_id_livre(self, a_partir_de=90000):
        """
        O primeiro id que nao esta no npcgrp deste cliente.

        Antes o campo vinha com um numero fixo, e quem gerasse dois NPCs
        seguidos sem reparar sobrescrevia o primeiro.
        """
        usados = set()
        for npc in self.npcs:
            try:
                usados.add(int(npc["tag"]))
            except (ValueError, KeyError, TypeError):
                pass
        ident = int(a_partir_de)
        while ident in usados:
            ident += 1
        return ident

    # ---- pecas repetidas -------------------------------------------------
    def _lista(self, pai, coluna, titulo, colunas, larguras, aofiltrar):
        caixa = ttk.LabelFrame(pai, text=t(titulo), padding=6)
        caixa.grid(row=0, column=coluna, sticky="nsew",
                   padx=(0, 6) if coluna == 0 else (6, 0))

        barra = ttk.Frame(caixa)
        barra.pack(fill="x")
        ttk.Label(barra, text=t("filtrar:")).pack(side="left")
        busca = tk.StringVar()
        entrada = ttk.Entry(barra, textvariable=busca)
        entrada.pack(side="left", fill="x", expand=True, padx=(4, 0))
        busca.trace_add("write", lambda *_a: aofiltrar())

        corpo = ttk.Frame(caixa)
        corpo.pack(fill="both", expand=True, pady=(4, 0))
        tabela = ttk.Treeview(corpo, columns=colunas, show="headings", height=9)
        for nome, largura in zip(colunas, larguras):
            # O nome da coluna e a identidade dela no Treeview; so o cabecalho
            # visivel muda de idioma.
            tabela.heading(nome, text=t(nome))
            tabela.column(nome, width=largura, anchor="w")
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=tabela.yview)
        tabela.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        tabela.pack(side="left", fill="both", expand=True)
        return tabela, busca

    @staticmethod
    def _campo(pai, rotulo, variavel, largura, dica=None):
        ttk.Label(pai, text=t(rotulo)).pack(side="left", padx=(0, 4))
        entrada = ttk.Entry(pai, textvariable=variavel, width=largura)
        entrada.pack(side="left", padx=(0, 2 if dica else 12))
        if dica:
            # A dica fica no `?`, e nao no campo: assim ela nao abre sozinha
            # enquanto o usuario esta digitando ali dentro.
            ajuda.ajuda(pai, dica, padx=(0, 12))
        return entrada

    def _social_escolhido(self):
        """O id da animacao de clique. Texto invalido vira 1, nunca um erro."""
        try:
            valor = int(self.social.get().strip())
        except ValueError:
            return 1
        return valor if 0 <= valor <= 7 else 1

    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")
        self._gravar(texto)

    def _gravar(self, texto):
        """
        Repete a linha num arquivo, com hora.

        A janela mostra o andamento, mas se o programa fechar no meio a janela
        vai junto. O arquivo fica -- e a ultima linha dele diz onde parou.
        """
        try:
            with open(self.diario, "a", encoding="utf-8", errors="replace") as f:
                f.write("%s  %s\n" % (time.strftime("%H:%M:%S"), texto))
        except OSError:
            pass        # nao poder registrar nao pode impedir de trabalhar

    def trabalho(self):
        """Arquivos intermediarios, descartaveis."""
        pasta = motor.BASE / "trabalho" / "npc"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def cache(self):
        """
        O catalogo de efeitos, que NAO pode viver em trabalho/.

        A aba de texturas apaga aquela pasta inteira no arranque, e com razao:
        sao PNG e DDS de execucoes interrompidas. Mas varrer os pacotes do
        cliente leva segundos, e refazer isso a cada abertura porque o arquivo
        estava na pasta errada seria um custo cobrado do usuario por nada.
        """
        return motor.BASE / "efeitos.json"

    def saida(self):
        pasta = motor.BASE / "saida" / "npc"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    # ---- cliente ---------------------------------------------------------
    def ler_cliente(self):
        if self.rodando:
            return

        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas(precisa_servidor=False)
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        system = Path(self.cliente.get())
        if not (system / "npcgrp.dat").exists():
            # A pasta do projeto existe, mas nao e um cliente: o npcgrp.dat e
            # o que prova que e. Vale um recado proprio, porque o problema
            # aqui nao e configuracao faltando -- e pasta errada.
            gui_projeto.avisar_falta(self, [
                t("Não achei npcgrp.dat em %s. A pasta do cliente do projeto "
                  "aponta para o lugar errado.") % system])
            return

        faltando = [k for k in ("l2encdec", "l2asm", "l2disasm", "umodel")
                    if not Path(self.T.get(k, "")).exists()]
        if faltando:
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.")
                                 % (", ".join(faltando), motor.CONFIG))
            return

        motor.gravar_opcao("cliente", "system", str(system))
        self.rodando = True
        self.botao_ler.config(state="disabled")
        self.estado.config(text=t("lendo…"))
        threading.Thread(target=self._ler_thread, args=(system,), daemon=True).start()

    def _ler_thread(self, system):
        def diga(texto):
            self.raiz.after(0, self.log, texto)

        try:
            diga(t("\nLendo npcgrp.dat…"))
            grp = l2npc.Npcgrp(system, self.T, self.trabalho())
            npcs = grp.resumo()
            diga(t("  %d NPCs.") % len(npcs))

            # O efeito de um NPC feito em modo script nao esta no .dat: esta
            # dentro do pacote dele. Sem esta leitura a coluna "efeito" sai
            # vazia justamente para os NPCs que este programa criou.
            dos_pacotes = l2npc.efeitos_dos_gerados(
                system, npcs, aolog=lambda m: diga("  " + m))
            for n in npcs:
                if not n["efeito"] and n["tag"] in dos_pacotes:
                    n["efeito"] = dos_pacotes[n["tag"]]
            if dos_pacotes:
                diga(t("  %d NPCs com efeito no pacote próprio.") % len(dos_pacotes))

            nomes, titulos = {}, {}
            try:
                tabela = l2npc.Npcname(system, self.T, self.trabalho())
                nomes = tabela.nomes()
                titulos = tabela.titulos()
                diga(t("  %d nomes em npcname-e.dat.") % len(nomes))
            except l2npc.ErroDat as e:
                diga(t("  sem nomes (%s)") % e)

            diga(t("Varrendo os pacotes atras de efeitos. Da primeira vez demora; "
                 "depois fica em cache."))

            def andando(i, total, nome):
                if nome:
                    self.raiz.after(0, self.estado.config,
                                    {"text": t("efeitos: %d/%d  %s") % (i, total, nome)})

            efeitos, recusados = l2npc.catalogar_efeitos(
                system, self.T, self.trabalho(),
                cache=self.cache(), aoprogresso=andando)

            diga(t("  %d efeitos em %d pacotes.")
                 % (len(efeitos), len(set(e["pacote"] for e in efeitos))))
            if recusados:
                diga(t("  %d pacotes não abriram:") % len(recusados))
                for nome, motivo in recusados[:6]:
                    diga(t("     %-30s %s") % (nome, motivo))
                if len(recusados) > 6:
                    diga(t("     e mais %d.") % (len(recusados) - 6))

            self.raiz.after(0, self._fim_leitura, npcs, nomes, titulos,
                            efeitos, recusados)
        except Exception as e:
            diga(t("ERRO: %s") % e)
            self.raiz.after(0, self._fim_leitura, [], {}, {}, [], [])

    def _fim_leitura(self, npcs, nomes, titulos, efeitos, recusados):
        self.rodando = False
        self.botao_ler.config(state="normal")
        self.npcs, self.nomes, self.titulos = npcs, nomes, titulos
        self.efeitos, self.recusados = efeitos, recusados
        self.estado.config(text="")

        # O primeiro id LIVRE a partir de 90000, e nao o maior mais um: num
        # cliente com um id solto la em cima -- e quase todo cliente
        # modificado tem -- o maior mais um joga o NPC novo para uma faixa que
        # o proprio cliente trata mal.
        if npcs:
            livre = self.proximo_id_livre()
            self.id_novo.set(str(livre))
            self.log(t("  proximo id livre no npcgrp: %d.") % livre)
        self.filtrar_npcs()
        self.filtrar_efeitos()
        self.atualizar_botoes()

    # ---- filtros ---------------------------------------------------------
    def sugerir_id(self):
        """Poe no campo o primeiro id livre, se o usuario ainda nao escolheu."""
        if not self.npcs:
            return
        atual = self.id_novo.get().strip()
        if atual and atual not in [n["tag"] for n in self.npcs]:
            return
        self.id_novo.set(str(self.proximo_id_livre()))

    def filtrar_npcs(self):
        alvo = self.busca_npc.get().strip().lower()
        self.lista_npc.delete(*self.lista_npc.get_children())

        # Todos, sem corte. Encher a Treeview com os 6539 NPCs de um cliente
        # custa 0,08 s -- medido --, entao o limite que havia aqui so escondia
        # NPCs de quem estava procurando.
        for n in self.npcs:
            nome = self.nomes.get(n["tag"], "")
            if alvo and alvo not in ("%s %s %s %s" % (n["tag"], nome, n["classe"],
                                                      n["malha"])).lower():
                continue
            self.lista_npc.insert("", "end", values=(n["tag"], nome, n["classe"],
                                                     n["efeito"]))

    def marcar_efeitos_usados(self):
        """
        Deixa marcados, na lista da direita, os efeitos que este NPC usa.

        Filtrar so estreitava a lista; qual deles estava em uso continuava
        sendo adivinhacao.
        """
        usados = set(e["caminho"] for e in self.escolhidos)
        if not usados:
            return
        marcar = [item for item in self.lista_fx.get_children()
                  if self.lista_fx.item(item, "values")[0] in usados]
        if marcar:
            self.lista_fx.selection_set(marcar)
            self.lista_fx.see(marcar[0])

    def filtrar_efeitos(self):
        alvo = self.busca_fx.get().strip().lower()
        self.lista_fx.delete(*self.lista_fx.get_children())

        for e in self.efeitos:
            if alvo and alvo not in e["caminho"].lower():
                continue
            emissores = ", ".join("%s x%d" % (k.replace("Emitter", ""), v)
                                  for k, v in sorted(e["emissores"].items()))
            self.lista_fx.insert("", "end", values=(e["caminho"], emissores))

    # ---- efeitos escolhidos ---------------------------------------------
    def adicionar_efeito(self):
        """Manda para o NPC todos os efeitos marcados, com os valores atuais."""
        selecao = self.lista_fx.selection()
        if not selecao:
            messagebox.showinfo(t("Nada selecionado"),
                                t("Selecione um ou mais efeitos na lista da direita.\n\n"
                                "Ctrl ou Shift marcam vários."))
            return

        try:
            altura = float(self.altura.get().replace(",", "."))
            escala = float(self.escala.get().replace(",", "."))
        except ValueError:
            messagebox.showerror(t("Número invalido"),
                                 t("Altura e escala precisam ser números."))
            return

        osso = self.osso.get().strip() or (self.ossos_malha[0] if self.ossos_malha else "Bip01")
        novos = 0
        for item in selecao:
            caminho = self.lista_fx.item(item, "values")[0]
            if not caminho or caminho == "…":
                continue
            if any(e["caminho"] == caminho for e in self.escolhidos):
                continue        # ja esta na lista: acender duas vezes o mesmo
            self.escolhidos.append({"caminho": caminho, "osso": osso,
                                    "altura": altura, "escala": escala,
                                    "obedece": self.obedece.get()})
            novos += 1

        if novos == 0:
            messagebox.showinfo(t("Nada a acrescentar"),
                                t("Os efeitos marcados já estao na lista."))
            return

        self.redesenhar_escolhidos()

    def campos_do_efeito_mudaram(self, *_a):
        """
        Escreve osso, altura e escala no efeito a que eles se referem.

        Sem isto os campos eram um formulario de PROXIMO efeito, e nao do
        efeito atual: mexer neles e clicar em Gerar produzia o arquivo
        anterior, igualzinho, sem erro nenhum.
        """
        if getattr(self, "_escrevendo_campos", False) or not self.escolhidos:
            return
        marcados = list(self.lista_escolhidos.curselection())
        if not marcados:
            if len(self.escolhidos) != 1:
                return          # varios efeitos e nenhum marcado: nao adivinho
            marcados = [0]
        try:
            altura = float(self.altura.get().replace(",", "."))
            escala = float(self.escala.get().replace(",", "."))
        except ValueError:
            return              # numero pela metade enquanto se digita
        osso = self.osso.get().strip() or "Bip01"
        for i in marcados:
            if 0 <= i < len(self.escolhidos):
                self.escolhidos[i].update({"osso": osso, "altura": altura,
                                           "escala": escala,
                                           "obedece": self.obedece.get()})
        guardados = marcados
        self.redesenhar_escolhidos()
        for i in guardados:
            self.lista_escolhidos.selection_set(i)

    def efeito_escolhido_marcado(self, _evento=None):
        """Marcar um efeito na lista traz os valores dele para os campos."""
        marcados = list(self.lista_escolhidos.curselection())
        if len(marcados) != 1 or marcados[0] >= len(self.escolhidos):
            return
        self._sincronizar_campos(self.escolhidos[marcados[0]])

    def _sincronizar_campos(self, e):
        """Poe nos campos os valores deste efeito, sem disparar a escrita."""
        self._escrevendo_campos = True
        try:
            self.osso.set(e.get("osso") or "Bip01")
            self.altura.set("%g" % float(e.get("altura", 0)))
            self.escala.set("%.2f" % float(e.get("escala", 1)))
            self.obedece.set(bool(e.get("obedece", True)))
        finally:
            self._escrevendo_campos = False

    def redesenhar_escolhidos(self):
        """A lista da tela sai da lista de verdade, nunca o contrario."""
        # E os campos saem do efeito, quando nao ha duvida de qual e. Sem isto,
        # um campo desatualizado -- o valor de partida da tela, por exemplo --
        # era escrito no efeito junto com o que o usuario acabou de mudar.
        if len(self.escolhidos) == 1:
            self._sincronizar_campos(self.escolhidos[0])
        self.desenhar_regua()
        self.lista_escolhidos.delete(0, "end")
        for e in self.escolhidos:
            self.lista_escolhidos.insert(
                "end", t("%s   osso=%s  z=%.1f  escala=%.2f%s")
                % (e["caminho"], e.get("osso") or "Bip01",
                   float(e.get("altura", 0)), float(e.get("escala", 1)),
                   "" if e.get("obedece", True) else t("   (posição do efeito)")))
        self.atualizar_botoes()

    def aplicar_ao_escolhido(self):
        """
        Troca osso, altura e escala dos efeitos marcados na lista de baixo.

        Sem isto, mudar a altura de um efeito ja escolhido exigia tira-lo e
        por de novo -- e com varios efeitos no mesmo NPC, cada um com a sua
        altura, isso vira um vaivem.
        """
        marcados = list(self.lista_escolhidos.curselection())
        if not marcados:
            messagebox.showinfo(t("Nada marcado"),
                                t("Marque na lista de baixo o efeito a ajustar."))
            return

        try:
            altura = float(self.altura.get().replace(",", "."))
            escala = float(self.escala.get().replace(",", "."))
        except ValueError:
            messagebox.showerror(t("Número invalido"),
                                 t("Altura e escala precisam ser números."))
            return

        osso = self.osso.get().strip() or (self.ossos_malha[0] if self.ossos_malha else "Bip01")
        for i in marcados:
            self.escolhidos[i].update({"osso": osso, "altura": altura, "escala": escala})

        self.redesenhar_escolhidos()
        for i in marcados:
            self.lista_escolhidos.selection_set(i)

    def tirar_efeito(self):
        for i in reversed(list(self.lista_escolhidos.curselection())):
            del self.escolhidos[i]
        self.redesenhar_escolhidos()

    def trocar_modo(self):
        """
        O modo rapido desliga o que ele nao sabe fazer.

        As tres colunas do npcgrp guardam uma classe de efeito e uma escala, e
        nada mais -- nao ha onde por osso, altura nem um segundo emissor.
        Deixar os campos ativos sugeriria que sao levados em conta, e o usuario
        so descobriria que nao ao entrar no jogo e ver o efeito no lugar
        errado.
        """
        rapido = self.modo.get() == "rapido"
        estado = "disabled" if rapido else "normal"
        self.entrada_osso.config(state=estado)
        self.entrada_altura.config(state=estado)
        self.estado.config(
            text=t("modo rapido: um efeito, so a escala; sem compilar nada")
            if rapido else "")
        self.atualizar_botoes()

    def atualizar_botoes(self):
        self.dizer_o_alvo()
        pronto = bool(self.npcs and self.escolhidos and not self.rodando)
        self.botao_gerar.config(state="normal" if pronto else "disabled")
        self.botao_editar_npc.config(
            state="normal" if (self.lista_npc.selection() and not self.rodando)
            else "disabled")

    # ---- regua de altura -------------------------------------------------
    def base_selecionado(self):
        """O NPC base marcado na lista, ou None."""
        selecao = self.lista_npc.selection()
        if not selecao:
            return None
        valores = self.lista_npc.item(selecao[0], "values")
        return None if not valores or valores[0] == "…" else valores[0]

    def npc_selecionado(self):
        """
        Trocou o NPC marcado na lista.

        A regua so refaz a medicao quando a malha muda -- e ela sai cedo quando
        nao mudou --, entao os botoes precisam ser atualizados aqui, e nao la
        dentro.
        """
        self.base_mudou()
        self.dizer_o_alvo()
        self.atualizar_botoes()

    def dizer_o_alvo(self, editando=False):
        """
        Escreve qual NPC o formulario esta montando, e de quem ele copia.

        A lista da esquerda e do NPC BASE, e nao do NPC que esta sendo feito.
        Os dois numeros aparecendo juntos e o que faz a tela parar de parecer
        que trocou de assunto sozinha.
        """
        rotulo = getattr(self, "rotulo_alvo", None)
        if rotulo is None:
            return
        ident = self.id_novo.get().strip()
        editando = editando or (ident and ident == self.editando_tag)
        base = self.base_selecionado() or ""
        nome = self.nome_novo.get().strip()
        if not ident:
            rotulo.config(text=t("Escolha o NPC base na lista e dê um id novo."))
            return
        quem = "%s%s" % (ident, (" \u2014 %s" % nome) if nome else "")
        rotulo.config(
            text=(t("Editando o NPC %s   (cópia de %s)") % (quem, base or "?")
                  if editando else
                  t("NPC novo %s   (cópia de %s)") % (quem, base or "?")))

    def editar_existente(self):
        """
        O NPC marcado na lista vira o NPC do formulario.

        E o caminho para acrescentar efeito a um NPC que ja existe, em vez de
        criar um novo: o id continua o mesmo, e "Gerar" oferece substituir.

        Tres casos, e cada um precisa de um tratamento diferente:

          - NPC criado por este programa, com o pacote inteiro: as escolhas
            voltam do fonte guardado no .u -- base, efeitos, osso, altura,
            escala -- e o usuario ACRESCENTA ao que ja estava la;
          - NPC criado por este programa, mas sem o pacote: nao da para saber
            de quem ele copiou a aparencia, e gerar por cima estenderia uma
            classe que nao existe mais. Ai so avisando;
          - NPC do cliente: ele mesmo vira a base, que e o que preserva
            aparencia e comportamento.
        """
        if self.rodando:
            return

        selecao = self.lista_npc.selection()
        if not selecao:
            messagebox.showinfo(t("Escolha um"),
                                t("Selecione na lista da esquerda o NPC que você "
                                  "quer editar."))
            return

        tag = self.lista_npc.item(selecao[0], "values")[0]
        self.carregar_para_editar(tag, exigir_receita=False)

    def preencher_do_base(self, tag):
        """
        O que da para aproveitar do NPC base ao escolhe-lo.

        O cliente guarda pouco do que o servidor precisa -- nome, titulo e a
        malha. Isso ja poupa digitacao, e o resto o painel do servidor deixa em
        valores de partida plausiveis.
        """
        if not tag or tag == "\u2026":
            return
        if not self.nome_novo.get().strip():
            self.nome_novo.set(self.nomes.get(tag, ""))
        if not self.titulo_novo.get().strip():
            self.titulo_novo.set(self.titulos.get(tag, ""))
        if getattr(self, "servidor", None) is not None:
            self.servidor.atualizar_previa()

    def base_mudou(self):
        """Mede a malha do NPC recem-escolhido, fora da thread da interface."""
        self.preencher_do_base(self.base_selecionado())
        tag = self.base_selecionado()
        if tag is None:
            return

        npc = next((n for n in self.npcs if n["tag"] == tag), None)
        malha = npc["malha"] if npc else ""
        if malha == self.malha_atual:
            return

        self.malha_atual = malha
        self.dados_da_malha_atual = {}
        self.altura_malha = None
        self.chao_malha, self.topo_malha = 0.0, None
        self.botao_ver.config(state="normal" if malha else "disabled")
        self.desenhar_regua()

        def medir():
            try:
                dados = l2npc.dados_da_malha(
                    self.T, self.cliente.get(), malha, self.trabalho(),
                    cache=motor.BASE / "malhas.json")
            except Exception:
                dados = None
            self.raiz.after(0, self.malha_lida, malha, dados)

        threading.Thread(target=medir, daemon=True).start()

    def malha_lida(self, malha, dados):
        """Chega a altura e a lista de ossos da malha escolhida."""
        # So aceita se o usuario nao tiver trocado de NPC no meio.
        if malha != self.malha_atual:
            return

        # A medida inteira fica guardada: o painel do servidor usa a altura
        # E o raio para preencher o cilindro de colisao.
        self.dados_da_malha_atual = dados or {}
        self.altura_malha = (dados or {}).get("altura")
        # A origem da malha nao fica nos pes: e preciso saber onde eles estao
        # para que "acima da cabeca" queira dizer acima da cabeca.
        self.chao_malha = (dados or {}).get("chao")
        self.topo_malha = (dados or {}).get("topo")
        if self.chao_malha is None:
            self.chao_malha = 0.0
        if self.topo_malha is None and self.altura_malha:
            self.topo_malha = self.chao_malha + self.altura_malha
        self.ossos_malha = (dados or {}).get("ossos") or []

        # O primeiro osso do .psk e a raiz do esqueleto -- "Bip01" em toda
        # malha humanoide deste cliente. E o padrao seguro: prender na raiz faz
        # o efeito acompanhar o boneco inteiro.
        self.entrada_osso.config(values=self.ossos_malha)
        if self.ossos_malha and self.osso.get() not in self.ossos_malha:
            self.osso.set(self.ossos_malha[0])

        # Um Z que faz sentido nesta malha. So quando o campo ainda esta no
        # valor de fabrica: mexeu, e escolha do usuario e nao se toca.
        if self.topo_malha and self.altura.get().strip() in ("", "80", "0"):
            self.altura.set("%g" % round(self.topo_malha
                                         + (self.altura_malha or 0) * 0.08, 1))

        self.desenhar_regua()

    def _numero(self, variavel, padrao):
        try:
            return float(variavel.get().strip().replace(",", "."))
        except ValueError:
            return padrao

    def desenhar_regua(self):
        """
        Desenha a altura da malha com uma marca no Z escolhido.

        E um diagrama, nao um render: o efeito e um sistema de particulas do
        Unreal Engine 2, e nada fora do motor do jogo desenha aquilo. O que
        esta aqui responde a pergunta que da para responder -- em que altura do
        boneco o efeito vai ficar preso, e quanto a escala o aumenta.
        """
        z = self._numero(self.altura, 0.0)
        escala = self._numero(self.escala, 1.0)
        altura = self.altura_malha

        imagem = Image.new("RGB", (LARGURA_REGUA, ALTURA_REGUA), (250, 250, 250))
        d = ImageDraw.Draw(imagem)
        d.rectangle((0, 0, LARGURA_REGUA - 1, ALTURA_REGUA - 1), outline=(200, 205, 210))

        base_y, topo_y = ALTURA_REGUA - 30, 34
        eixo_x = 52

        # O desenho trabalha em altura ABSOLUTA da malha, com o chao embaixo.
        # A origem da malha costuma ficar na cintura, entao contar do zero
        # poria os pes no meio da regua.
        chao = self.chao_malha or 0.0
        topo = self.topo_malha or ((chao + altura) if altura else chao + 40.0)
        limite = max(topo, z * 1.12, chao + 10.0)

        def para_y(valor):
            faixa = max(1e-6, limite - chao)
            return int(base_y - ((valor - chao) / faixa) * (base_y - topo_y))

        legendas = []          # (y, texto) das partes do corpo

        if altura is None:
            d.text((10, 10), t("medindo a malha…"), fill=(120, 130, 140))
        else:
            d.text((10, 10), "%s" % (self.malha_atual.split(".")[-1][:30]),
                   fill=(60, 70, 80))
            d.text((10, 22), t("altura da malha: %.1f unidades") % altura,
                   fill=(60, 70, 80))

        # O boneco, como uma barra simples. Nao e a silhueta dele: desenhar uma
        # figura humana para um dragao seria mentir.
        if altura:
            d.rectangle((eixo_x - 11, para_y(topo), eixo_x + 11, base_y),
                        fill=(214, 222, 230), outline=(150, 165, 180))
            for marca in range(int(chao // 10) * 10, int(limite) + 1, 10):
                y = para_y(marca)
                if y < topo_y - 2 or y > base_y + 2:
                    continue
                d.line((eixo_x - 17, y, eixo_x - 13, y), fill=(150, 165, 180))
                d.text((eixo_x - 40, y - 5), "%3d" % marca, fill=(130, 140, 150))

            # As partes do corpo, na altura que ESTA malha tem. Sao as
            # referencias que se usa para escolher o Z -- "na cintura" diz mais
            # do que "vinte unidades". So os tracinhos aqui: o texto vai depois
            # da linha do Z, senao ela o risca no meio.
            for fracao, rotulo in MARCAS_DO_CORPO:
                valor = chao + altura * fracao
                y = para_y(valor)
                if not (topo_y - 6 <= y <= base_y + 6):
                    continue
                d.line((eixo_x + 13, y, eixo_x + 22, y), fill=(120, 150, 175))
                legendas.append((y, "%s  (%.0f)" % (t(rotulo), valor)))

        # A marca do efeito, desenhada por ultimo para ficar por cima das
        # legendas quando cair em cima de uma delas.
        y = para_y(z)
        if topo_y - 12 <= y <= base_y + 12:
            for x in range(eixo_x - 22, LARGURA_REGUA - 14, 7):
                d.line((x, y, x + 4, y), fill=(200, 90, 40))
            raio = max(3, min(22, int(6 * max(escala, 0.05))))
            d.ellipse((eixo_x - raio, y - raio, eixo_x + raio, y + raio),
                      outline=(200, 90, 40), width=2)
            # O rotulo do Z fica na coluna da direita, e nao junto das
            # legendas do corpo: quando o Z cai em cima de uma delas -- que e
            # justamente o caso interessante -- os dois textos se escreviam por
            # cima um do outro.
            # O rotulo do Z na coluna da direita, longe das legendas do corpo,
            # e com o mesmo fundo claro para a linha nao passar nas letras.
            texto_z = "Z = %g" % z
            caixa = d.textbbox((LARGURA_REGUA - 74, y - 6), texto_z)
            d.rectangle((caixa[0] - 2, caixa[1] - 1, caixa[2] + 2, caixa[3] + 1),
                        fill=(250, 250, 250))
            d.text((LARGURA_REGUA - 74, y - 6), texto_z, fill=(200, 90, 40))

        # As legendas por ultimo, com um fundo claro para a linha tracejada nao
        # passar por dentro das letras.
        for y_legenda, texto in legendas:
            caixa = d.textbbox((eixo_x + 26, y_legenda - 5), texto)
            d.rectangle((caixa[0] - 2, caixa[1] - 1, caixa[2] + 2, caixa[3] + 1),
                        fill=(250, 250, 250))
            d.text((eixo_x + 26, y_legenda - 5), texto, fill=(110, 140, 165))

        # A leitura em palavras, que e o que se quer saber de fato.
        if altura:
            fracao = (z - chao) / altura if altura else 0
            if fracao > 1.0:
                onde = t(N_("acima da cabeca"))
            elif fracao < 0:
                onde = t(N_("abaixo dos pes"))
            else:
                onde = t(next(rotulo for teto, rotulo in FAIXAS_DO_CORPO
                              if fracao <= teto))
            d.text((10, ALTURA_REGUA - 22), t("o efeito fica %s") % onde,
                   fill=(40, 90, 60))
        d.text((LARGURA_REGUA - 96, ALTURA_REGUA - 22), t("escala %.2f") % escala,
               fill=(60, 70, 80))

        self.desenho_regua = ImageTk.PhotoImage(imagem)
        self.rotulo_regua.config(image=self.desenho_regua)

    def ver_malha(self):
        """
        Abre o visualizador 3D do umodel na malha do NPC base.

        Ele mostra o boneco com textura e animacao -- nao o efeito. Emissor de
        particula nao esta entre os recursos que o umodel abre, e nenhum
        visualizador de Lineage 2 desenha particula do Unreal Engine 2.
        """
        if not self.malha_atual:
            messagebox.showinfo(t("Escolha o NPC base"),
                                t("Selecione na lista da esquerda o NPC que vai "
                                "servir de base."))
            return

        try:
            pacote = l2npc.abrir_visualizador(self.T, self.cliente.get(),
                                              self.malha_atual)
        except Exception as e:
            messagebox.showerror(t("Não deu"), str(e))
            return

        self.log(t("\nAbrindo a malha %s (%s) no visualizador do umodel.")
                 % (self.malha_atual, Path(pacote).name))
        self.log(t("  ele mostra o boneco e as animações; o efeito, não -- "
                 "partícula so o jogo desenha."))

    def comando_do_npc(self, tag=None):
        """O comando que faz nascer o NPC do formulario (ou o indicado)."""
        tag = str(tag or self.id_novo.get().strip() or "<id>")
        return "SPAWNACTOR Class=FX_%s.Npc_%s_FX" % (tag, tag)

    def ver_no_jogo(self, tag, janela=None):
        """
        Abre o DevMode com o comando daquele NPC pronto para colar.

        O console do jogo nao recebe nada de fora -- e uma janela do proprio
        cliente, sem nenhuma porta de entrada. Entao o que da para fazer e
        deixar o comando na area de transferencia: no jogo e Tab, Ctrl+V,
        Enter.
        """
        comando = self.comando_do_npc(tag)
        try:
            self.raiz.clipboard_clear()
            self.raiz.clipboard_append(comando)
            self.raiz.update()
            copiou = True
        except Exception:
            copiou = False

        if not self.abrir_devmode(pergunta=(
                t("Vou abrir o cliente em DevMode para você ver o NPC %s.\n\n"
                  "O comando já vai estar na área de transferencia:\n"
                  "    %s\n\n"
                  "No jogo: Tab abre o console, Ctrl+V cola, Enter executa.\n"
                  "Se preferir o visualizador de NPC, o comando e  nv .\n\n"
                  "Continuar?") % (tag, comando))):
            return

        self.log(t("  comando do NPC %s %s:") % (tag, t("copiado") if copiou
                                              else t("(não consegui copiar)")))
        self.log("     %s" % comando)
        if janela is not None:
            janela.destroy()

    def abrir_devmode(self, pergunta=None):
        """
        Abre o proprio cliente sem servidor, para ver o NPC COM o efeito.

        E a unica forma de ver o efeito de fato: particula do Unreal Engine 2
        so o motor do jogo desenha. O cliente tem esse modo embutido e ja vem
        com o devmode.ini pronto; os comandos sao digitados no console do jogo.
        """
        if not messagebox.askyesno(
                t("Abrir o jogo em DevMode"),
                pergunta if pergunta else
                t("Vou abrir o cliente sem servidor, num mapa local, com o "
                  "console de desenvolvimento ligado.\n\n"
                  "E o único jeito de ver o EFEITO: nenhum programa fora do jogo "
                  "desenha partícula do Unreal Engine 2.\n\n"
                  "Vai aparecer um aviso dizendo que o AGP esta desativado: "
                  "clique OK. E uma checagem de hardware do D3DDrv que "
                  "nenhuma maquina moderna passa, e o jogo fica parado nela "
                  "ate o clique.\n\n"
                  "Feche o jogo normalmente quando terminar.\n\n"
                  "No jogo, para ver o NPC do formulario:\n"
                  "    Tab   e depois   %s\n\n"
                  "Continuar?") % self.comando_do_npc()):
            return False

        try:
            exe = l2npc.abrir_devmode(self.cliente.get(),
                                      aolog=lambda m: self.log(m))
        except Exception as e:
            messagebox.showerror(t("Não deu"), str(e))
            return False

        self.vigiar_jogo()

        tag = self.id_novo.get().strip()
        self.log(t("\n=== cliente aberto em DevMode ==="))
        self.log(t("  %s -INI=devmode.ini -ng") % exe)
        self.log(t("  se aparecer o aviso de AGP, clique OK: o jogo fica parado"))
        self.log(t("  nele ate o clique, sem mostrar janela de mundo nenhuma."))
        self.log(t("  o console do jogo abre com a tecla Tab. Comandos que o"))
        self.log(t("  Engine.dll deste cliente reconhece:"))
        for comando, para_que in l2npc.COMANDOS_DEVMODE:
            self.log(t("     %-42s %s") % (comando.replace("<id>", tag or "<id>"),
                                        para_que))
        self.log(t("  a sintaxe dos argumentos foi lida do binario, não de"))
        self.log(t("  documentacao -- pode ser preciso tentar variacoes."))
        self.log(t("  os .ini estao guardados; devolvo assim que o jogo fechar."))
        return True

    def vigiar_jogo(self):
        """
        Espera o jogo fechar e devolve os .ini guardados.

        Tem de ser DEPOIS que ele fecha: e ao sair que o Unreal grava a
        configuracao, entao devolver com o jogo aberto seria escrever para ser
        sobrescrito no instante seguinte.

        A espera e por nome de processo, e nao por um identificador: o L2.exe
        sobe elevado, e um programa comum nao consegue nem segurar um
        descritor dele.
        """
        if self.vigiando:
            return
        self.vigiando = True

        def esperar():
            # Ate o jogo aparecer -- ele demora a subir, ainda mais com a
            # janela de elevacao no caminho.
            for _ in range(60):
                if l2npc.jogo_aberto():
                    break
                time.sleep(2)

            while l2npc.jogo_aberto():
                time.sleep(3)

            self.raiz.after(0, self.jogo_fechou)

        threading.Thread(target=esperar, daemon=True).start()

    def jogo_fechou(self):
        self.vigiando = False
        self.log(t("\n=== o jogo fechou ==="))
        try:
            feitos = l2npc.restaurar_inis(self.cliente.get(),
                                          aolog=lambda m: self.log(m))
        except Exception as e:
            self.log(t("  ERRO ao devolver os .ini: %s") % e)
            messagebox.showerror(
                t("Os .ini não voltaram"),
                t("Não consegui devolver os .ini do cliente:\n\n%s\n\n"
                "As copias estao em system\\%s. Sem elas de volta, o jogo "
                "normal pode não abrir.") % (e, l2npc.PASTA_GUARDA))
            return

        if feitos:
            self.log(t("  devolvidos: %s") % ", ".join(feitos))
        else:
            self.log(t("  não havia nada guardado para devolver."))

    def conferir_inis_pendentes(self):
        """
        Na abertura, devolve o que tiver ficado para tras.

        Se o programa foi fechado com o jogo aberto -- ou se travou --, as
        copias ficam la e o cliente segue com os .ini em texto puro. Devolver
        na abertura seguinte evita que o usuario descubra isso na hora de
        jogar.
        """
        try:
            if not l2npc.tem_inis_guardados(self.cliente.get()):
                return
            if l2npc.jogo_aberto():
                self.log(t("Ha .ini guardados de uma sessão anterior, mas o jogo "
                         "esta aberto; devolvo quando ele fechar."))
                self.vigiar_jogo()
                return
            feitos = l2npc.restaurar_inis(self.cliente.get(),
                                          aolog=lambda m: self.log(m))
            if feitos:
                self.log(t("Devolvi os .ini que ficaram de uma sessão anterior: %s")
                         % ", ".join(feitos))
        except Exception as e:
            self.log(t("Aviso: não consegui conferir os .ini guardados (%s).") % e)

    # ---- o que ja foi criado --------------------------------------------
    def abrir_criados(self):
        """
        Lista os NPCs que este programa criou NESTE cliente, e permite tirar
        um deles.

        A lista sai do npcgrp.dat, nao de um registro a parte: e o cliente que
        manda. Um registro proprio ficaria desatualizado na primeira vez que o
        usuario trocasse de cliente ou restaurasse um backup, e entao a tela
        mostraria NPCs que nao existem e esconderia os que existem.
        """
        if self.rodando:
            return

        system = Path(self.cliente.get())
        if not (system / "npcgrp.dat").exists():
            messagebox.showerror(t("Pasta errada"), t("Aponte a pasta system do cliente."))
            return

        janela = ajuda.por_icone(tk.Toplevel(self.raiz))
        janela.title(t("NPCs criados neste cliente"))

        def no_tk(funcao, *argumentos):
            """
            Volta da thread para a interface -- e desiste se a janela fechou.

            A leitura do cliente roda fora da thread do Tk e volta por aqui.
            Fechar esta janela antes de ela terminar deixava o callback batendo
            em widget destruido: `invalid command name ...treeview`.
            """
            def entregar():
                try:
                    if not janela.winfo_exists():
                        return
                except tk.TclError:
                    return
                funcao(*argumentos)

            try:
                self.raiz.after(0, entregar)
            except (tk.TclError, RuntimeError):
                pass
        janela.geometry("760x380")
        janela.transient(self.raiz)

        quadro = ttk.Frame(janela, padding=10)
        quadro.pack(fill="both", expand=True)

        aviso = ttk.Label(quadro, foreground=tema.TEXTO_FRACO, justify="left",
                          text=t("Lendo o cliente…"))
        aviso.pack(anchor="w")

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("nome"), N_("classe"), N_("malha"),
                   N_("pacote"))
        tabela = ttk.Treeview(corpo, columns=colunas, show="headings", height=10)
        for nome, largura in zip(colunas, (60, 150, 190, 210, 110)):
            tabela.heading(nome, text=t(nome))
            tabela.column(nome, width=largura, anchor="w")
        rolagem = ttk.Scrollbar(corpo, orient="vertical", command=tabela.yview)
        tabela.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        tabela.pack(side="left", fill="both", expand=True)

        ttk.Label(quadro, foreground=tema.TEXTO_FRACO,
                  text=t("Duplo clique num NPC para trazer as escolhas dele de volta "
                       "ao formulario.")).pack(anchor="w", pady=(6, 0))

        barra = ttk.Frame(quadro)
        barra.pack(fill="x", pady=(8, 0))
        botao_editar = ttk.Button(barra, text=t("Editar"), state="disabled")
        botao_editar.pack(side="left")
        botao_jogo = ttk.Button(barra, text=t("Ver no jogo"), state="disabled")
        botao_jogo.pack(side="left", padx=(8, 0))
        botao_remover = ttk.Button(barra, text=t("Remover do cliente"), state="disabled")
        botao_remover.pack(side="left", padx=(8, 0))
        botao_atualizar = ttk.Button(barra, text=t("Reler"), state="disabled")
        botao_atualizar.pack(side="left", padx=(8, 0))
        ttk.Button(barra, text=t("Fechar"), command=janela.destroy).pack(side="right")

        estado = {"itens": []}

        def encher(itens):
            # Guarda dupla: o `after` pode ter sido agendado antes do
            # fechamento e so disparar depois dele.
            try:
                if not tabela.winfo_exists():
                    return
            except tk.TclError:
                return
            estado["itens"] = itens
            tabela.delete(*tabela.get_children())
            for n in itens:
                tabela.insert("", "end", values=(
                    n["tag"], n["nome"] or t("(sem nome)"), n["classe"],
                    n["malha"],
                    t("instalado") if n["pacote_existe"] else t("SEM O .u")))
            aviso.config(
                text=(t("%d NPC(s) criados por este programa.") % len(itens))
                if itens else
                t("Nenhum NPC criado por este programa foi encontrado "
                  "neste cliente."))
            botao_remover.config(state="normal" if itens else "disabled")
            botao_editar.config(state="normal" if itens else "disabled")
            botao_jogo.config(state="normal" if itens else "disabled")
            botao_atualizar.config(state="normal")

        def ler():
            aviso.config(text=t("Lendo o cliente…"))
            botao_remover.config(state="disabled")
            botao_editar.config(state="disabled")
            botao_atualizar.config(state="disabled")

            def trabalho():
                try:
                    itens = l2npc.listar_criados(self.T, system, self.trabalho())
                    no_tk(encher, itens)
                except Exception as e:
                    no_tk(aviso.config, {"text": t("Não deu: %s") % e})
                    no_tk(botao_atualizar.config, {"state": "normal"})

            threading.Thread(target=trabalho, daemon=True).start()

        def remover():
            selecao = tabela.selection()
            if not selecao:
                messagebox.showinfo(t("Escolha um"), t("Selecione o NPC a remover."),
                                    parent=janela)
                return

            tag = tabela.item(selecao[0], "values")[0]
            if not messagebox.askyesno(
                    t("Remover o NPC %s") % tag,
                    t("Vou tirar do cliente:\n\n"
                    "  - a linha do %s no npcgrp.dat\n"
                    "  - o nome dele no npcname-e.dat\n"
                    "  - o pacote FX_%s.u\n\n"
                    "O que estiver la vai para system\\backup_npc antes.\n\n"
                    "Do lado do servidor você ainda vai precisar apagar\n"
                    "data/xml/npcs/custom/npc_%s.xml e dar //reload npc.\n\n"
                    "Continuar?") % (tag, tag, tag), parent=janela):
                return

            aviso.config(text=t("Removendo…"))
            botao_remover.config(state="disabled")
            botao_editar.config(state="disabled")
            botao_atualizar.config(state="disabled")

            def trabalho():
                try:
                    l2npc.remover_npc(self.T, system, self.trabalho(), tag,
                                      saida=self.saida(),
                                      aolog=lambda m: self.raiz.after(0, self.log, "  " + m))
                    no_tk(ler)
                except Exception as e:
                    no_tk(self.log, t("  ERRO ao remover: %s") % e)
                    no_tk(messagebox.showerror, t("Não deu"), str(e))
                    self.raiz.after(0, ler)

            self.log(t("\n=== removendo o NPC %s ===") % tag)
            threading.Thread(target=trabalho, daemon=True).start()

        def ver(_evento=None):
            selecao = tabela.selection()
            if not selecao:
                messagebox.showinfo(t("Escolha um"), t("Selecione o NPC a ver."),
                                    parent=janela)
                return
            self.ver_no_jogo(tabela.item(selecao[0], "values")[0], janela)

        def editar(_evento=None):
            selecao = tabela.selection()
            if not selecao:
                messagebox.showinfo(t("Escolha um"), t("Selecione o NPC a editar."),
                                    parent=janela)
                return
            self.carregar_para_editar(tabela.item(selecao[0], "values")[0], janela)

        botao_editar.config(command=editar)
        botao_jogo.config(command=ver)
        botao_remover.config(command=remover)
        botao_atualizar.config(command=ler)
        tabela.bind("<Double-1>", editar)
        ler()

    def carregar_para_editar(self, tag, janela=None, exigir_receita=True):
        """
        Traz de volta as escolhas que criaram este NPC.

        O que se recupera vem do fonte guardado dentro do proprio pacote
        instalado -- NPC base, efeitos, osso, altura e escala -- mais o nome e
        o titulo, que saem do cliente. Depois disso, "Gerar" refaz o NPC por
        cima com o que voce mudar.
        """
        if not self.npcs or not self.efeitos:
            messagebox.showinfo(
                t("Leia o cliente primeiro"),
                t("Para editar eu preciso da lista de NPCs e de efeitos.\n\n"
                "Clique em \"Ler o cliente\" e tente de novo."),
                parent=janela or self.raiz)
            return

        atual_npc = next((n for n in self.npcs if n["tag"] == str(tag)), None)
        nosso = bool(atual_npc and l2npc.MARCA.match(atual_npc["classe"] or ""))

        receita = l2npc.ler_receita(self.cliente.get(), tag)
        if receita is None and (exigir_receita or nosso):
            # Sem o fonte nao da para saber de quem este NPC copiou a
            # aparencia, e gerar por cima faria a classe nova estender a antiga
            # -- que e ele mesmo, ou nada. Melhor parar aqui.
            messagebox.showwarning(
                t("Não consegui recuperar"),
                t("O pacote FX_%s.u não esta no cliente, ou não guarda mais o "
                "fonte.\n\nDa para recriar o NPC do zero com o mesmo id: o "
                "programa oferece substituir.") % tag,
                parent=janela or self.raiz)
            return

        if receita is None:
            # NPC do proprio cliente: ele e a base de si mesmo. E o que
            # preserva a aparencia e o comportamento que ele ja tem.
            receita = {"base": str(tag), "efeitos": [], "fonte": ""}

        self.id_novo.set(tag)
        self.editando_tag = str(tag)
        # Nome e titulo saem da MESMA linha do npcname-e.dat: o titulo e a
        # coluna `description`. Zerar o titulo aqui, como se fazia, apagava
        # metade da identificacao do NPC a cada edicao.
        self.nome_novo.set(self.nomes.get(str(tag), ""))
        self.titulo_novo.set(self.titulos.get(str(tag), ""))

        atual = atual_npc

        # O NPC base, selecionado na lista da esquerda como se tivesse sido
        # clicado -- e dele que a proxima geracao vai copiar a aparencia.
        base = receita["base"]
        achou_base = False
        if base:
            self.busca_npc.set(base)
            self.filtrar_npcs()
            for item in self.lista_npc.get_children():
                if self.lista_npc.item(item, "values")[0] == base:
                    self.lista_npc.selection_set(item)
                    self.lista_npc.see(item)
                    achou_base = True
                    break

        self.tamanho.set("%.2f" % float(receita.get("tamanho") or 1.0))
        self.escolhidos = list(receita["efeitos"])
        self.redesenhar_escolhidos()

        if self.escolhidos:
            primeiro = self.escolhidos[0]
            self.osso.set(primeiro.get("osso") or "Bip01")
            self.altura.set("%g" % float(primeiro.get("altura", 0)))
            self.escala.set("%.2f" % float(primeiro.get("escala", 1)))
            self.busca_fx.set(primeiro["caminho"].split(".")[-1])
            self.filtrar_efeitos()
            self.marcar_efeitos_usados()

        self.modo.set("script")
        self.trocar_modo()
        self.base_mudou()

        self.log(t("\n=== NPC %s carregado para edicao ===") % tag)
        self.log(t("  nome: %s   título: %s")
                 % (self.nome_novo.get() or t("(sem nome)"),
                    self.titulo_novo.get() or t("(sem título)")))
        self.log(t("  base: %s%s") % (base or t("(não registrado no pacote)"),
                                   "" if achou_base or not base
                                   else t("  [não esta na lista deste cliente]")))
        for e in self.escolhidos:
            self.log(t("  efeito: %s  osso=%s  z=%g  escala=%.2f")
                     % (e["caminho"], e.get("osso"), float(e.get("altura", 0)),
                        float(e.get("escala", 1))))
        if not self.escolhidos:
            self.log(t("  escolha um efeito na lista da direita e clique em "
                       "Adicionar."))
        if atual is not None and atual.get("efeito") and not self.escolhidos:
            self.log(t("  este NPC já tem efeito pela coluna do .dat: %s")
                     % atual["efeito"])
        self.log(t("  mude o que quiser e clique em Gerar: ele oferece substituir."))
        if atual is None:
            self.log(t("  aviso: este id não esta na lista carregada do cliente."))

        self.estado.config(text=t("editando o NPC %s") % tag)
        if janela is not None:
            janela.destroy()

    # ---- gerar -----------------------------------------------------------
    def gerar(self):
        if self.rodando:
            return

        selecao = self.lista_npc.selection()
        if not selecao:
            messagebox.showinfo(t("Escolha o NPC base"),
                                t("Selecione na lista da esquerda o NPC cuja aparencia "
                                "o novo vai copiar."))
            return

        base = self.lista_npc.item(selecao[0], "values")[0]
        if base == "…":
            return

        novo = self.id_novo.get().strip()
        if not novo.isdigit():
            messagebox.showerror(t("Id invalido"), t("O id novo tem de ser um número."))
            return

        # Cada geracao parte do npcgrp.dat DO CLIENTE, nao da anterior. E o
        # certo -- assim uma tentativa que deu errado nao contamina a proxima
        # -- mas significa que gerar duas vezes seguidas sem instalar joga fora
        # a primeira. Melhor dizer isso agora do que deixar alguem descobrir
        # que metade dos NPCs que ele criou nao esta no arquivo.
        if self.ultimo_relatorio and not self.ultimo_relatorio.get("instalado"):
            if not messagebox.askyesno(
                    t("O anterior não foi instalado"),
                    t("O NPC %s foi gerado mas não instalado.\n\n"
                    "Gerar de novo parte do cliente outra vez, e o anterior se "
                    "perde.\n\nContinuar mesmo assim?")
                    % self.ultimo_relatorio["tag"]):
                return

        # Se o id ja existe no cliente, refazer por cima e o caso comum --
        # e o que se faz para corrigir um NPC que saiu errado.
        substituir = any(n["tag"] == novo for n in self.npcs)
        if substituir and not messagebox.askyesno(
                t("O id %s já existe") % novo,
                t("Já existe um NPC %s neste cliente.\n\n"
                "Posso gerar por cima dele: a linha antiga sai e a nova entra "
                "no lugar.\n\nSubstituir?") % novo):
            return

        self.rodando = True
        self.botao_gerar.config(state="disabled")
        self.botao_instalar.config(state="disabled")
        self.estado.config(text=t("gerando…"))
        threading.Thread(target=self._gerar_thread, args=(base, novo, substituir),
                         daemon=True).start()

    def _gerar_thread(self, base, novo, substituir=False):
        self.base_da_ultima = base
        def diga(texto):
            self.raiz.after(0, self.log, "  " + texto)

        try:
            self.raiz.after(0, self.log, "\n=== NPC %s (base %s) ===" % (novo, base))

            # O lado do servidor sai do passo 2, ja no formato do emulador
            # escolhido. Antes o l2npc escrevia um molde fixo aqui e a outra
            # aba escrevia o de verdade: dois arquivos para o mesmo id, e o
            # servidor lia o que viesse por ultimo.
            try:
                servidor_pronto = self.servidor.principal()
            except Exception as erro:               # noqa: BLE001
                diga(t("o lado do servidor não saiu (%s); vai o molde padrão")
                     % erro)
                servidor_pronto = None

            relatorio = l2npc.criar_npc(
                self.T, self.cliente.get(), self.trabalho(), self.saida(),
                base_tag=base, novo_tag=novo, efeitos=list(self.escolhidos),
                modo=self.modo.get(),
                pacote="FX_%s" % novo, classe="Npc_%s_FX" % novo,
                nome=self.nome_novo.get().strip(),
                titulo=self.titulo_novo.get().strip(),
                escala_rapida=self.escolhidos[0]["escala"],
                substituir=substituir, social=self._social_escolhido(),
                aolog=diga, servidor_pronto=servidor_pronto,
                tamanho=self.tamanho_do_npc())

            # Spawn e loja nao acompanham o arquivo do NPC, mas saem na mesma
            # pasta: instalar so metade do conjunto e o erro que isso evita.
            try:
                self.servidor.gravar_extras(self.saida(), aolog=diga)
            except Exception as erro:               # noqa: BLE001
                diga(t("spawn e loja não sairam: %s") % erro)

            self.raiz.after(0, self._fim_geracao, relatorio, None)
        except Exception as e:
            self.raiz.after(0, self._fim_geracao, None, e)

    def gravar_xml_no_servidor(self, relatorio):
        """
        Copia a XML gerada para a pasta de NPCs do servidor.

        O cliente e o servidor sao dois lados do mesmo NPC, e ate agora so um
        deles era entregue no lugar certo: a XML ficava na pasta de trabalho
        esperando ser copiada a mao.

        Falhar aqui nao derruba a geracao. O NPC foi gerado; o que nao deu foi
        a entrega, e isso se diz e se refaz.
        """
        origem = (relatorio.get("arquivos") or {}).get("xml")
        destino = self.servidor.pasta_do_npc_no_servidor()
        if not origem or destino is None:
            return
        try:
            destino.mkdir(parents=True, exist_ok=True)
            alvo = destino / Path(origem).name
            shutil.copy2(origem, alvo)
        except OSError as erro:
            self.log(t("  não consegui gravar na pasta do servidor: %s") % erro)
            return
        relatorio["xml_no_servidor"] = alvo
        self.log(t("  XML gravada em %s") % alvo)

    def _fim_geracao(self, relatorio, erro):
        self.rodando = False
        self.botao_gerar.config(state="normal")

        if erro is not None:
            # "o id ja existe" nao e um beco sem saida: e o caso comum de
            # refazer um NPC. A checagem previa olha a lista carregada do
            # cliente, que envelhece assim que um NPC e instalado -- entao e
            # aqui, na recusa de verdade, que a pergunta tem de estar.
            if "ja existe no npcgrp" in str(erro) and not self.tentou_substituir:
                self.log("  %s" % erro)
                if messagebox.askyesno(
                        t("O id já existe"),
                        t("%s\n\nPosso gerar por cima: a linha antiga sai e a "
                        "nova entra no lugar.\n\nSubstituir?") % erro):
                    self.tentou_substituir = True
                    self.estado.config(text=t("substituindo…"))
                    self.rodando = True
                    self.botao_gerar.config(state="disabled")
                    threading.Thread(
                        target=self._gerar_thread,
                        args=(self.base_da_ultima, self.id_novo.get().strip(), True),
                        daemon=True).start()
                    return
                self.estado.config(text="")
                return

            self.tentou_substituir = False
            self.log(t("  ERRO: %s") % erro)
            self.estado.config(text=t("falhou"))
            messagebox.showerror(t("Não deu"), str(erro))
            return

        self.tentou_substituir = False

        self.ultimo_relatorio = relatorio
        self.gravar_xml_no_servidor(relatorio)
        self.botao_instalar.config(state="normal")
        self.estado.config(text=t("gerado em %s") % self.saida())
        self.log(t("  pronto. Arquivos em %s") % self.saida())
        self.log(t("  nada foi copiado para o cliente ainda -- use \"Instalar no cliente\"."))

    # ---- instalar --------------------------------------------------------
    def recado_do_fim(self, feitos, xml):
        """O titulo e o texto do aviso final, sem mostrar nada."""
        # A XML pode ja estar na pasta do servidor -- e esta, quando a
        # caixa da aba 2 fica marcada. Mandar copiar de novo o que ja foi
        # copiado e pior do que nao dizer nada: quem obedece copia por
        # cima do proprio arquivo, e quem desconfia perde tempo conferindo.
        no_servidor = self.ultimo_relatorio.get("xml_no_servidor")
        tag = self.ultimo_relatorio["tag"]
        if no_servidor:
            texto = t("Cliente atualizado: %s\n\n"
                      "A XML já está no servidor:\n     %s\n\n"
                      "Faltam dois passos, no jogo:\n\n"
                      "1. //reload npc\n"
                      "2. //spawn %s\n\n"
                      "Feche e abra o cliente também: o npcgrp.dat "
                      "só é lido no arranque.")
            texto = texto % (", ".join(feitos), no_servidor, tag)
        else:
            texto = t("Cliente atualizado: %s\n\n"
                      "O NPC ainda NÃO existe para o jogo. O cliente "
                      "só desenha o que o servidor manda nascer -- "
                      "faltam três passos:\n\n"
                      "1. copie este arquivo para a pasta de NPCs do "
                      "servidor:\n     %s\n"
                      "2. no jogo: //reload npc\n"
                      "3. no jogo: //spawn %s\n\n"
                      "Feche e abra o cliente também: o npcgrp.dat "
                      "só é lido no arranque.\n\n"
                      "Para o programa gravar lá sozinho, marque "
                      "\"gravar a XML na pasta do servidor\""
                      " na aba 2.")
            texto = texto % (", ".join(feitos), xml, tag)
        return ((t("Pronto -- falta recarregar") if no_servidor
                 else t("Falta o servidor")), texto)

    def instalar(self):
        if self.rodando or not self.ultimo_relatorio:
            return

        arquivos = [Path(p).name for c, p in self.ultimo_relatorio["arquivos"].items()
                    if c not in ("xml", "uc")]
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("Vou sobrescrever no cliente:\n\n  %s\n\n"
                "O que estiver la vai para system\\backup_npc antes.\n\nContinuar?")
                % "\n  ".join(arquivos)):
            return

        try:
            feitos = l2npc.instalar(self.ultimo_relatorio, self.cliente.get(),
                                    aolog=lambda linha: self.log("  " + linha))
        except Exception as e:
            self.log(t("  ERRO ao instalar: %s") % e)
            messagebox.showerror(t("Não deu"), str(e))
            return

        self.ultimo_relatorio["instalado"] = True
        self.log(t("  instalados: %s") % ", ".join(feitos))
        xml = self.ultimo_relatorio["arquivos"].get("xml")
        titulo, texto = self.recado_do_fim(feitos, xml)
        messagebox.showinfo(titulo, texto)
