#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aba "Itens" -- criar um item novo copiando um que ja existe.

O item novo nasce como copia de um item que o cliente ja desenha. Uma linha do
armorgrp tem 332 colunas, e as que nao tem a ver com aparencia -- peso, som ao
equipar, malha de cada combinacao de raca e sexo -- precisam de valores
plausiveis. Herda-las e mais seguro do que inventa-las.

A tela mostra o icone porque e assim que se reconhece um item. Ele aparece no
tamanho em que o jogo o desenha, 32x32: ampliado, o mesmo desenho fica borrado,
e a ampliacao nao acrescenta informacao nenhuma.

O XML do servidor sai da mesma tela. Peso, material, grau e parte do corpo sao
lidos da tabela do cliente e ja vem preenchidos; o resto -- dano, defesa, preco
e os status que o item da ao jogador -- e escolhido aqui, sempre em lista. Nome
de status inventado nao e ignorado pelo servidor: ele derruba o carregamento da
tabela de itens inteira.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import gui_icone
import l2conferir
import l2item
import l2upscale as motor
import gui_projeto
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE

# O tamanho em que o cliente desenha o icone. Mostrar maior so borra.
LADO_DO_ICONE = 32

CARTOES = (
    ("total", N_("itens no cliente"), tema.PAINEL, tema.TEXTO),
    ("weapon", N_("armas"), tema.PAINEL, tema.TEXTO),
    ("armor", N_("armaduras"), tema.PAINEL, tema.TEXTO),
    ("etc", N_("outros"), tema.PAINEL, tema.TEXTO),
)

# Os campos do XML que a tela oferece por grupo, na ordem em que aparecem.
# (chave no XML, rotulo, lista de opcoes ou None para campo livre)
CAMPOS_COMUNS = (
    ("tipo", N_("tipo no servidor"), l2item.TIPOS_DE_ITEM),
    ("default_action", N_("ação ao clicar"), l2item.ACOES),
    ("bodypart", N_("parte do corpo"), l2item.PARTES_DO_CORPO),
    ("material", N_("material"), l2item.MATERIAIS),
    ("crystal_type", N_("grau"), l2item.GRAUS),
    ("weight", N_("peso"), None),
    ("price", N_("preço"), None),
    ("crystal_count", N_("cristais"), None),
)

CAMPOS_POR_GRUPO = {
    "weapon": (("weapon_type", N_("tipo de arma"), l2item.TIPOS_DE_ARMA),
               ("random_damage", N_("dano aleatório"), None),
               ("soulshots", N_("soulshots"), None),
               ("spiritshots", N_("spiritshots"), None),
               ("mp_consume", N_("consumo de mana"), None),
               ("reuse_delay", N_("recarga (ms)"), None),
               ("is_magical", N_("é mágica"), ("", "true", "false")),
               ("enchant4_skill", N_("skill a partir do +4"), None),
               ("oncrit_skill", N_("skill no crítico"), None),
               ("oncrit_chance", N_("chance no crítico"), None),
               ("oncast_skill", N_("skill ao castar"), None),
               ("oncast_chance", N_("chance ao castar"), None)),
    "armor": (("armor_type", N_("tipo de armadura"), l2item.TIPOS_DE_ARMADURA),),
    "etc": (("etcitem_type", N_("tipo"), l2item.TIPOS_DE_ETC),
            ("is_stackable", N_("empilhável"), ("", "true", "false")),
            ("handler", N_("handler"), None),
            ("reuse_delay", N_("recarga (ms)"), None)),
}

# Quais ficam disponíveis em qualquer item, no fim da lista.
CAMPOS_FINAIS = (
    ("item_skill", N_("skill enquanto equipado"), None),
    ("is_tradable", N_("negociável"), ("", "true", "false")),
    ("is_dropable", N_("largável"), ("", "true", "false")),
    ("is_sellable", N_("vendável"), ("", "true", "false")),
    ("is_destroyable", N_("destruível"), ("", "true", "false")),
    ("is_depositable", N_("guardável"), ("", "true", "false")),
    ("is_oly_restricted", N_("proibido na Olimpíada"), ("", "true", "false")),
)


class JanelaItem:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.itens = None
        self.lista = []
        self.mostrados = []
        self.icones = {}            # referencia -> PhotoImage
        self.gravados = []
        self.base = None
        # "editar" ou "nova". A tela inteira depende disto, e o usuario le o
        # modo no alto do painel em vez de deduzi-lo dos campos.
        self.modo = "editar"
        self.estado_em_edicao = None
        # O .utx de um icone proprio, feito e ainda nao instalado. Entra no
        # cliente junto com as tabelas.
        self.icone_pendente = None
        self.campos = {}            # chave do XML -> StringVar
        self.linhas_de_campo = {}   # chave -> (rotulo, widget)
        self.estados = []           # [{operacao, ordem, estado, valor}]
        self.numeros_do_cliente = {}    # colunas do weapongrp, vindas da modal
        self.estados_aceitos = None     # os status deste servidor, se sabidos
        self.estados_de_onde = ""       # "core" ou "datapack"
        self.catalogo_de_icones = []

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Cria um item novo copiando um que já existe. O item "
                         "base entrega aparência, peso, som e tudo o mais; "
                         "você troca o id, o nome e o ícone.")).pack(anchor="w")

        self._montar_cliente(quadro)
        self._montar_resumo(quadro)

        painel = ttk.Panedwindow(quadro, orient="horizontal")
        painel.pack(fill="both", expand=True, pady=(8, 0))
        painel.add(self._montar_lista(painel), weight=2)
        painel.add(self._montar_novo(painel), weight=3)

        self._montar_rodape(quadro)
        self._atualizar_modo()
        self.atualizar_botoes()

    # ---- montagem --------------------------------------------------------
    def _montar_cliente(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))

        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))

        ttk.Label(linha, text=t("Crônica:")).pack(side="left", padx=(12, 0))
        # A caixa mostra o rotulo; o resto do programa continua falando em
        # nome de pasta, que e o que a configuracao e o executavel guardam.
        self.embutidas = l2item.cronicas() or [l2item.CRONICA_PADRAO]
        guardada = motor.ler_opcao("item", "cronica", self.embutidas[0])
        if guardada not in self.embutidas:
            guardada = self.embutidas[0]
        rotulos = [l2item.rotulo_da_cronica(c) for c in self.embutidas]
        self.cronica_rotulo = tk.StringVar(
            value=l2item.rotulo_da_cronica(guardada))
        caixa = ttk.Combobox(linha, textvariable=self.cronica_rotulo,
                             values=rotulos, state="readonly", width=16)
        caixa.pack(side="left", padx=(6, 0))
        caixa.bind("<<ComboboxSelected>>", self.ao_trocar_cronica)

        self.botao_abrir = ttk.Button(linha, text=t("Carregar"),
                                      command=self.abrir)
        self.botao_abrir.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Abrir lê as quatro tabelas de item do cliente: as três de "
            "aparência e a de nomes.\n\n"
            "Antes de qualquer coisa ser gravada, cada tabela é remontada e "
            "comparada com o binário original. Se a volta não reproduz a ida "
            "byte a byte, a definição não descreve este cliente e nada é "
            "escrito -- campo deslocado não dá erro, dá item errado."),
            padx=(8, 0))

    def _montar_resumo(self, pai):
        faixa = ttk.Frame(pai)
        faixa.pack(fill="x", pady=(10, 0))
        self.numeros = {}
        for i, (chave, rotulo, fundo, cor) in enumerate(CARTOES):
            cartao = tk.Frame(faixa, bg=fundo, padx=14, pady=10,
                              highlightthickness=1,
                              highlightbackground=tema.BORDA,
                              highlightcolor=tema.BORDA)
            cartao.grid(row=0, column=i, sticky="nsew",
                        padx=(0 if not i else 6, 0))
            faixa.columnconfigure(i, weight=1)
            numero = tk.Label(cartao, text="—", bg=fundo, fg=cor,
                              font=("Segoe UI", 18, "bold"))
            numero.pack(anchor="w")
            tk.Label(cartao, text=t(rotulo), bg=fundo, fg=COR_TEXTO_FRACO,
                     font=("Segoe UI", 8)).pack(anchor="w")
            self.numeros[chave] = numero

        self.andamento = ttk.Progressbar(pai, mode="determinate", maximum=1000)
        self.andamento.pack(fill="x", pady=(8, 0))
        self.estado = ttk.Label(pai, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(anchor="w")

    def _montar_lista(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Item base"), padding=6)

        busca = ttk.Frame(caixa)
        busca.pack(fill="x")
        ttk.Label(busca, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(busca, textvariable=self.filtro)
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", self.ao_filtrar)
        self.conta = ttk.Label(busca, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("tipo"), N_("nome"), N_("ícone"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=16, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (64, 84, 210, 210),
                                              ("e", "w", "w", "w")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento)
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_escolher)
        self.tabela.bind("<Double-1>", self.ao_dar_duplo_clique)
        return caixa

    def _montar_novo(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Item"), padding=6)

        # O modo primeiro, e em negrito: era a informacao que faltava.
        self.rotulo_modo = ttk.Label(
            caixa, text="", font=("Segoe UI", 10, "bold"), wraplength=380,
            justify="left")
        self.rotulo_modo.pack(anchor="w", pady=(0, 6))

        # ---- cabeca: o icone e de onde o item vem ----
        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        self.moldura = tk.Frame(topo, bg=COR_FUNDO_ICONE,
                                width=LADO_DO_ICONE + 10,
                                height=LADO_DO_ICONE + 10,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                highlightcolor=tema.BORDA)
        self.moldura.pack(side="left")
        self.moldura.pack_propagate(False)
        self.tela_icone = tk.Label(self.moldura, bg=COR_FUNDO_ICONE,
                                   fg=tema.TEXTO_APAGADO, text="—",
                                   font=("Segoe UI", 8))
        self.tela_icone.pack(expand=True)

        resumo = ttk.Frame(topo)
        resumo.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.rotulo_base = ttk.Label(resumo,
                                     text=t("Escolha um item na lista."),
                                     foreground=COR_TEXTO_FRACO,
                                     wraplength=380, justify="left")
        self.rotulo_base.pack(anchor="w")
        self.rotulo_icone = ttk.Label(resumo, text="", foreground=tema.TEXTO_FRACO,
                                      font=("Segoe UI", 8))
        self.rotulo_icone.pack(anchor="w")

        abas = ttk.Notebook(caixa)
        abas.pack(fill="both", expand=True, pady=(8, 0))
        abas.add(self._montar_identificacao(abas), text=t(" Identificação "))
        abas.add(self._montar_xml(abas), text=t(" XML do servidor "))

        acao = ttk.Frame(caixa)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_novo = ttk.Button(acao, text=t("Novo item\u2026"),
                                     command=self.novo_item)
        self.botao_novo.pack(side="left")
        self.botao_gerar = ttk.Button(acao, text=t("Gerar"), command=self.gerar)
        self.botao_gerar.pack(side="left", padx=(6, 0))
        self.botao_instalar = ttk.Button(acao, text=t("Instalar no cliente"),
                                         command=self.instalar)
        self.botao_instalar.pack(side="left", padx=(6, 0))
        return caixa

    def _montar_identificacao(self, pai):
        aba = ttk.Frame(pai, padding=8)
        aba.columnconfigure(1, weight=1)

        ttk.Label(aba, text=t("id:")).grid(row=0, column=0, sticky="w")
        self.novo_id = tk.StringVar()
        # Editando, o id e o do item marcado e nao se digita: mudar o numero
        # ali era, na verdade, criar outro.
        self.entrada_id = ttk.Entry(aba, textvariable=self.novo_id, width=12)
        self.entrada_id.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.botao_sugerir = ttk.Button(aba, text=t("Sugerir"),
                                        command=self.sugerir_id)
        self.botao_sugerir.grid(row=0, column=2, sticky="w", padx=(6, 0))

        ttk.Label(aba, text=t("nome:")).grid(row=1, column=0, sticky="w",
                                             pady=(6, 0))
        self.novo_nome = tk.StringVar()
        ttk.Entry(aba, textvariable=self.novo_nome).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(aba, text=t("destaque:")).grid(row=2, column=0, sticky="w",
                                                 pady=(6, 0))
        self.novo_destaque = tk.StringVar()
        ttk.Entry(aba, textvariable=self.novo_destaque).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(aba, text=t("descrição:")).grid(row=3, column=0, sticky="w",
                                                  pady=(6, 0))
        self.nova_descricao = tk.StringVar()
        ttk.Entry(aba, textvariable=self.nova_descricao).grid(
            row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(aba, text=t("ícone:")).grid(row=4, column=0, sticky="w",
                                              pady=(6, 0))
        self.novo_icone = tk.StringVar()
        entrada = ttk.Entry(aba, textvariable=self.novo_icone)
        entrada.grid(row=4, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        entrada.bind("<FocusOut>",
                     lambda _e: self.mostrar_icone(self.novo_icone.get()))
        entrada.bind("<Return>",
                     lambda _e: self.mostrar_icone(self.novo_icone.get()))
        self.botao_icone = ttk.Button(aba, text=t("Escolher…"),
                                      command=self.escolher_icone)
        self.botao_icone.grid(row=4, column=2, sticky="w", padx=(6, 0),
                              pady=(6, 0))

        self.substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(aba, variable=self.substituir,
                        text=t("substituir se o id já existir")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # O `?` se coloca sozinho com pack, e aqui o pai usa grid -- daí o
        # quadro intermediário.
        canto = ttk.Frame(aba)
        canto.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ajuda.ajuda(canto, lambda: t(
            "O id é o que amarra o cliente ao servidor. Use um acima de "
            "30000, longe da faixa do jogo original -- escrever por cima de "
            "um item que existe é o erro mais caro aqui.\n\n"
            "O ícone é uma referência do tipo pacote.objeto, e pode ser "
            "qualquer um que já esteja instalado no cliente."))
        return aba

    def _montar_xml(self, pai):
        aba = ttk.Frame(pai, padding=8)

        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("O que vem da tabela do cliente já está preenchido. "
                         "Campo em branco não é escrito: o servidor usa o "
                         "padrão dele.")).pack(anchor="w")
        # A mesma opcao da aba de conferencia e da de NPC: quem apontou o
        # servidor uma vez nao deve ter de apontar de novo em cada tela.
        de_onde = ttk.Frame(aba)
        de_onde.pack(fill="x", pady=(8, 0))
        self.pasta_do_servidor = tk.StringVar(
            value=motor.ler_opcao("conferir", "servidor", ""))
        self.botao_ler_servidor = ttk.Button(
            de_onde, text=t("Ler do servidor"), command=self.ler_do_servidor)
        self.botao_ler_servidor.pack(side="left", padx=(6, 0))
        ajuda.ajuda(de_onde, lambda: t(
            "Traz do servidor o item que est\u00e1 MARCADO NA LISTA -- e n\u00e3o "
            "o do campo \"id novo\".\n\n"
            "Dano, defesa e pre\u00e7o n\u00e3o existem no cliente: s\u00f3 o "
            "servidor os tem. \u00c9 assim que se copia os n\u00fameros de um "
            "item que j\u00e1 funciona.\n\n"
            "Para reler um item que voc\u00ea criou, marque-o na lista: ele "
            "est\u00e1 l\u00e1 depois de gerar."), padx=(8, 0))

        self.situacao_servidor = ttk.Label(aba, text="",
                                           foreground=COR_TEXTO_FRACO,
                                           wraplength=420, justify="left")
        self.situacao_servidor.pack(anchor="w", pady=(4, 0))


        # ---- os <set name="..."> ----
        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(8, 0))
        grade.columnconfigure(1, weight=1)
        grade.columnconfigure(3, weight=1)
        self.grade_de_campos = grade
        self.montar_campos("weapon")

        # ---- os status ----
        caixa = ttk.LabelFrame(aba, text=t("Status que o item dá ao jogador"),
                               padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(caixa, foreground=COR_TEXTO_FRACO, wraplength=900,
                  justify="left",
                  text=t("Uma linha de cada vez: o que a conta FAZ, em que "
                         "MOMENTO ela entra, QUAL número do jogador ela mexe e "
                         "QUANTO. Duplo clique numa linha da tabela traz os "
                         "campos de volta para cima.")).pack(anchor="w",
                                                             pady=(0, 6))

        # Em grade, e nao em linha: com `pack(side="left")` o botão era o
        # último a receber espaço e saía da tela numa janela estreita. Aqui só
        # a coluna do status estica, e os rótulos dizem o que é cada caixa.
        escolha = ttk.Frame(caixa)
        escolha.pack(fill="x")
        # Piso de largura na coluna que estica: e ela que leva o rotulo mais
        # longo da linha E a caixa de status. Sem o piso, numa janela estreita
        # a grade a espremia e `3. que numero do jogador:` saia aparado.
        escolha.columnconfigure(3, weight=1, minsize=230)

        ttk.Label(escolha, text=t("1. a conta faz:")).grid(row=0, column=0,
                                                           sticky="w")
        self.operacao = tk.StringVar()
        caixa_op = ttk.Combobox(escolha, textvariable=self.operacao,
                                values=l2item.com_explicacao(
                                    l2item.O_QUE_A_OPERACAO_FAZ),
                                state="readonly", width=28)
        caixa_op.grid(row=1, column=0, sticky="w")
        caixa_op.bind("<<ComboboxSelected>>", lambda _e: self._ordem_padrao())

        # A ordem e obrigatoria no XML deste core: `DocumentBase` le o atributo
        # sem checar se existe, e sem ele a tabela de itens inteira deixa de
        # carregar. Fica a vista, ja preenchida com o que o jogo usa, e escrita
        # por extenso -- `0x08` sozinho nao diz nada a quem nao leu o core.
        ttk.Label(escolha, text=t("2. em que momento:")).grid(
            row=0, column=1, sticky="w", padx=(8, 0))
        self.ordem = tk.StringVar()
        ttk.Combobox(escolha, textvariable=self.ordem,
                     values=l2item.com_explicacao(l2item.O_QUE_A_ORDEM_FAZ),
                     state="readonly", width=24).grid(row=1, column=1,
                                                      sticky="w", padx=(8, 0))
        self.operacao.set(l2item.com_explicacao(
            l2item.O_QUE_A_OPERACAO_FAZ)[0])
        self._ordem_padrao()

        ttk.Label(escolha, text=t("3. que número do jogador:")).grid(
            row=0, column=3, sticky="w", padx=(8, 0))
        self.estado_escolhido = tk.StringVar()
        self.caixa_estado = ttk.Combobox(escolha,
                                         textvariable=self.estado_escolhido,
                                         values=self._rotulos_de_estado(),
                                         state="readonly")
        self.caixa_estado.grid(row=1, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(escolha, text=t("4. quanto:")).grid(row=0, column=4,
                                                      sticky="w", padx=(8, 0))
        self.valor = tk.StringVar()
        entrada = ttk.Entry(escolha, textvariable=self.valor, width=8)
        entrada.grid(row=1, column=4, sticky="w", padx=(8, 0))
        entrada.bind("<Return>", lambda _e: self.acrescentar_estado())

        self.botao_estado = ttk.Button(escolha, text=t("Acrescentar"),
                                       command=self.acrescentar_estado)
        self.botao_estado.grid(row=1, column=5, sticky="w", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("operação"), N_("ordem"), N_("status"), N_("valor"))
        self.tabela_estados = ttk.Treeview(dentro, columns=colunas,
                                           show="headings", height=6,
                                           selectmode="extended")
        for nome, largura, alinhamento in zip(colunas, (90, 70, 300, 80),
                                              ("w", "w", "w", "e")):
            self.tabela_estados.heading(nome, text=t(nome))
            self.tabela_estados.column(nome, width=largura, anchor=alinhamento)
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.tabela_estados.yview)
        self.tabela_estados.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela_estados.pack(side="left", fill="both", expand=True)
        self.tabela_estados.bind("<Double-1>", self.editar_estado)

        baixo = ttk.Frame(caixa)
        baixo.pack(fill="x", pady=(6, 0))
        ttk.Button(baixo, text=t("Tirar"),
                   command=self.tirar_estado).pack(side="left")
        ttk.Button(baixo, text=t("Ver o XML"),
                   command=self.ver_xml).pack(side="left", padx=(6, 0))
        ttk.Button(baixo, text=t("Conferir com o servidor"),
                   command=self.conferir_estados_do_servidor).pack(
            side="left", padx=(6, 0))
        ajuda.ajuda(baixo, lambda: t(
            "A operação diz como o valor entra na conta. `add` soma ao total; "
            "`baseadd` soma à base, antes dos multiplicadores; `set` fixa; "
            "`enchant` é a parcela que cresce a cada encantamento.\n\n"
            "Os nomes de status são os que o seu servidor aceita, lidos do "
            "código dele. Um nome fora da lista não é ignorado: derruba o "
            "carregamento da tabela de itens inteira."), padx=(10, 0))
        return aba

    def _montar_rodape(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left")
        self.botao_aparencia = ttk.Button(linha, text=t("Trocar apar\u00eancia\u2026"),
                                          command=self.trocar_aparencia)
        self.botao_aparencia.pack(side="left", padx=(6, 0))
        self.botao_xml = ttk.Button(linha, text=t("Salvar XML do servidor…"),
                                    command=self.salvar_xml)
        self.botao_xml.pack(side="left", padx=(6, 0))
        self.botao_restaurar = ttk.Button(linha, text=t("Restaurar originais"),
                                          command=self.restaurar)
        self.botao_restaurar.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Gerar escreve as tabelas numa pasta à parte; instalar as põe no "
            "cliente. São separados de propósito: dá para olhar o resultado "
            "antes de o cliente depender dele.\n\n"
            "Na primeira instalação as tabelas originais são guardadas em "
            "system/backup_itens, e é de lá que Restaurar as traz de volta."),
            padx=(10, 0))

        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=4, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

    # ---- os campos do XML, que mudam com o grupo -------------------------
    def montar_campos(self, grupo):
        """Refaz a grade de campos para o tipo do item base."""
        for filho in self.grade_de_campos.winfo_children():
            filho.destroy()
        self.campos = {}

        lista = (CAMPOS_COMUNS + CAMPOS_POR_GRUPO.get(grupo, ())
                 + CAMPOS_FINAIS)
        for i, (chave, rotulo, opcoes) in enumerate(lista):
            coluna = (i % 2) * 2
            fila = i // 2
            ttk.Label(self.grade_de_campos, text=t(rotulo) + ":").grid(
                row=fila, column=coluna, sticky="w", pady=2)
            variavel = tk.StringVar()
            self.campos[chave] = variavel
            if opcoes is None:
                widget = ttk.Entry(self.grade_de_campos, textvariable=variavel,
                                   width=14)
            else:
                widget = ttk.Combobox(self.grade_de_campos,
                                      textvariable=variavel,
                                      values=list(opcoes), width=14)
            widget.grid(row=fila, column=coluna + 1, sticky="ew",
                        padx=(6, 12), pady=2)

    MARCA = "\u26a0 "        # o triangulo de aviso, na frente do rotulo

    def _rotulos_de_estado(self):
        """
        'grupo — rótulo (nome)', que é como se acha um status na lista.

        Depois de conferir com o servidor, os que ele não tem ganham um
        triângulo na frente. A chave continua entre parênteses no fim, que é de
        onde `_nome_do_rotulo` a tira -- a marca não atrapalha.
        """
        saida = []
        for grupo, pares in l2item.ESTADOS:
            for nome, rotulo in pares:
                marca = ("" if self.estados_aceitos is None
                         or nome in self.estados_aceitos else self.MARCA)
                saida.append("%s%s — %s (%s)" % (marca, t(grupo), t(rotulo),
                                                 nome))
        return saida

    def conferir_estados_do_servidor(self, calado=False):
        """
        Pergunta ao servidor quais status ele conhece, e marca os que faltam.

        Leva alguns segundos: lê a pasta inteira. Por isso é um botão, e não
        algo que acontece sozinho ao abrir a tela.
        """
        pasta = self.pasta_do_servidor.get().strip()
        if not pasta:
            if not calado:
                messagebox.showinfo(
                    t("Falta a pasta do servidor"),
                    t("Aponte a pasta de dados do servidor para eu poder "
                      "conferir os status."))
            return

        def olhar():
            import l2servidor
            try:
                perfil = l2servidor.farejar(pasta)
                aceitos = perfil.get("estados_aceitos") or []
                de_onde = perfil.get("estados_de_onde") or ""
                erro = None
            except Exception as e:                  # noqa: BLE001
                aceitos, de_onde, erro = [], "", e
            self.raiz.after(0, self._estados_conferidos, aceitos, de_onde,
                            erro, calado)

        self.log(t("\nConferindo os status com %s…") % pasta)
        threading.Thread(target=olhar, daemon=True).start()

    def _estados_conferidos(self, aceitos, de_onde, erro, calado):
        if erro is not None:
            self.log(t("Não deu para conferir: %s") % erro)
            if not calado:
                messagebox.showerror(t("Não deu para conferir"), str(erro))
            return
        if not aceitos:
            self.log(t("  o servidor não disse quais status aceita."))
            return

        self.estados_aceitos = set(aceitos)
        self.estados_de_onde = de_onde
        faltando = [n for _g, pares in l2item.ESTADOS for n, _r in pares
                    if n not in self.estados_aceitos]

        marcado = self.estado_escolhido.get()
        self.caixa_estado.config(values=self._rotulos_de_estado())
        # A caixa e readonly: um texto que nao esta mais na lista dela ficaria
        # visivel e nao poderia ser reescolhido.
        for rotulo in self._rotulos_de_estado():
            if self._nome_do_rotulo(rotulo) == self._nome_do_rotulo(marcado):
                self.estado_escolhido.set(rotulo)
                break

        self.log(t("  %d status aceitos, lidos %s.")
                 % (len(aceitos),
                    t("do código do servidor") if de_onde == "core"
                    else t("dos arquivos do servidor")))
        if faltando:
            self.log(t("  %d da lista este servidor não tem: %s")
                     % (len(faltando), ", ".join(faltando)))
        if not calado:
            messagebox.showinfo(
                t("Status conferidos"),
                t("Este servidor aceita %d status.\n\n%d da lista ele não "
                  "tem, e aparecem marcados com ⚠. Usar um deles derruba a "
                  "tabela de itens inteira no arranque.")
                % (len(aceitos), len(faltando)))

    @staticmethod
    def _nome_do_rotulo(rotulo):
        if "(" in rotulo and rotulo.endswith(")"):
            return rotulo[rotulo.rindex("(") + 1:-1]
        return rotulo.strip()

    # ---- ajudantes -------------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def _avisar_do_icone(self, recado):
        """
        O ícone veio de outro pacote -- dizer isso, da thread para o registro.

        A leitura do ícone roda fora da thread do Tk, e escrever no widget de
        lá trava a interface de um jeito que só aparece em máquina lenta.
        """
        try:
            self.raiz.after(0, self.log, recado)
        except Exception:                           # noqa: BLE001
            pass

    def system(self):
        return l2conferir.raiz_do_cliente(self.cliente.get().strip()) / "system"

    def trabalho(self):
        return Path(motor.BASE) / "trabalho" / "itens"

    def saida(self):
        return Path(motor.BASE) / "itens_gerados"

    def progresso(self, fracao, texto):
        self.raiz.after(0, self._desenhar_progresso, fracao, texto)

    def _desenhar_progresso(self, fracao, texto):
        if fracao is not None:
            self.andamento.config(value=int(max(0.0, min(1.0, fracao)) * 1000))
        self.estado.config(text=texto)

    def atualizar_botoes(self):
        parado = not self.rodando
        # Cinza so enquanto algo roda; faltando pasta ele diz o que falta.
        self.botao_abrir.config(state="normal" if parado else "disabled")
        pronto = parado and self.itens is not None and self.base is not None
        self.botao_gerar.config(state="normal" if pronto else "disabled")
        self.botao_icone.config(
            state="normal" if parado and self.itens is not None else "disabled")
        self.botao_instalar.config(
            state="normal" if parado and self.gravados else "disabled")
        self.botao_xml.config(state="normal" if pronto else "disabled")
        self.botao_aparencia.config(state="normal" if pronto else "disabled")
        self.botao_restaurar.config(
            state="normal" if parado and (self.system() /
                                          l2item.PASTA_GUARDA).is_dir()
            else "disabled")
        self.botao_novo.config(
            state=self.botao_gerar.cget("state"))

    # ---- escolhas --------------------------------------------------------
    def cronica_escolhida(self):
        """O nome da pasta da cronica que esta na caixa."""
        return l2item.cronica_do_rotulo(self.cronica_rotulo.get(),
                                        self.embutidas)

    def ao_trocar_cronica(self, _evento=None):
        motor.gravar_opcao("item", "cronica", self.cronica_escolhida())
        self.itens = None
        self.base = None
        self.tabela.delete(*self.tabela.get_children())
        self.log(t("Crônica: %s. Abra as tabelas de novo.") % self.cronica_escolhida())
        self.atualizar_botoes()

    # ---- abrir -----------------------------------------------------------
    def abrir(self):
        if self.rodando:
            return
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas(precisa_servidor=False)
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        system = self.system()
        faltam = [n for n in ("l2encdec", "l2disasm", "l2asm")
                  if not Path(self.T.get(n, "")).exists()]
        if faltam:
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.")
                                 % (", ".join(faltam), motor.CONFIG))
            return

        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== abrindo as tabelas de item de %s ===") % system)
        threading.Thread(target=self._abrir_thread, args=(system,),
                         daemon=True).start()

    def _abrir_thread(self, system):
        try:
            itens = l2item.Itens(self.T, system, self.trabalho(),
                                 self.cronica_escolhida(), aoprogresso=self.progresso)
            erro = None
        except Exception as e:                      # noqa: BLE001
            itens, erro = None, e
        self.raiz.after(0, self._fim_abertura, itens, erro)

    def _fim_abertura(self, itens, erro):
        self.rodando = False
        if erro is not None:
            self._desenhar_progresso(0, "")
            self.log(t("Não deu para abrir: %s") % erro)
            messagebox.showerror(t("Não deu para abrir as tabelas"), str(erro))
            self.atualizar_botoes()
            return

        self.itens = itens
        self.gravados = []
        for chave, (deu, motivo) in sorted(itens.provas.items()):
            self.log(t("  %s: %s") % (itens.tabelas[chave].origem.name, motivo))
        ruins = itens.conferir(so_alteradas=False)
        if ruins:
            messagebox.showwarning(
                t("Definição não confere"),
                t("Estas tabelas não voltam iguais ao original:\n\n%s\n\n"
                  "Elas podem ser lidas, mas gravar qualquer alteração nelas "
                  "está bloqueado.") % "\n".join("%s — %s" % p for p in ruins))

        self.lista = itens.listar()
        contas = {"total": len(self.lista)}
        for chave, _arquivo, _rotulo in l2item.GRUPOS:
            contas[chave] = sum(1 for i in self.lista if i["grupo"] == chave)
        for chave, rotulo in self.numeros.items():
            rotulo.config(text="%d" % contas.get(chave, 0))

        self.preencher()
        self.sugerir_id()
        self._desenhar_progresso(1.0, t("tabelas abertas"))
        self.log(t("%d itens lidos.") % len(self.lista))
        self.atualizar_botoes()
        threading.Thread(target=self._catalogar_icones, daemon=True).start()

    def _catalogar_icones(self):
        try:
            catalogo = l2item.icones_do_cliente(
                self.cliente.get(), [i["icone"] for i in self.lista])
        except Exception:
            catalogo = sorted({i["icone"] for i in self.lista if i["icone"]})
        self.raiz.after(0, self._guardar_catalogo, catalogo)

    def _guardar_catalogo(self, catalogo):
        self.catalogo_de_icones = catalogo
        self.log(t("%d ícones disponíveis no cliente.") % len(catalogo))

    # ---- a lista ---------------------------------------------------------
    def ao_filtrar(self, _evento=None):
        self.preencher()

    def preencher(self):
        """
        Refaz a lista com o filtro em vigor.

        Sem limite de linhas: as 9.534 entram em 0,16 s, e cortar a lista
        escondia justamente o item que o usuário estava procurando.
        """
        procurado = self.filtro.get().strip().lower()
        self.tabela.delete(*self.tabela.get_children())
        self.mostrados = [item for item in self.lista
                          if not procurado
                          or procurado in item["nome"].lower()
                          or procurado in item["id"]
                          or procurado in item["icone"].lower()]
        for i, item in enumerate(self.mostrados):
            self.tabela.insert("", "end", iid=str(i),
                               values=(item["id"], t(item["rotulo"]),
                                       item["nome"], item["icone"]))
        self.conta.config(text=t("%d de %d") % (len(self.mostrados),
                                                len(self.lista)))

    def ao_escolher(self, _evento=None):
        escolhido = self.tabela.selection()
        if not escolhido:
            return
        item = self.mostrados[int(escolhido[0])]
        # Trocar de item apaga o que a janela tinha recolhido: aqueles numeros
        # eram daquela arma, e aplica-los a esta seria escrever o dano de uma
        # na outra sem avisar.
        if self.base is not item:
            self.numeros_do_cliente = {}
        self.base = item
        self.rotulo_base.config(
            text=t("Da lista: %s (%s), id %s")
            % (item["nome"] or t("sem nome"), t(item["rotulo"]), item["id"]))
        if self.modo == "editar":
            self.novo_id.set(item["id"])
            self.novo_nome.set(item["nome"])
            self.novo_destaque.set(item.get("destaque", ""))
            self.novo_icone.set(item["icone"])
        self.mostrar_icone(self.novo_icone.get() or item["icone"])
        self.dizer_o_alvo(item["id"])

        # Os campos do XML mudam com o tipo, e o que dá para ler da tabela do
        # cliente é preenchido agora -- é o momento em que se sabe qual item é.
        self.montar_campos(item["grupo"])
        try:
            prontos = l2item.campos_do_servidor(self.itens, item["grupo"],
                                                item["linha"])
        except Exception:
            prontos = {}
        for chave, valor in prontos.items():
            if chave in self.campos:
                self.campos[chave].set(valor)
        self._atualizar_modo()
        self.atualizar_botoes()

    def ao_dar_duplo_clique(self, _evento=None):
        """Duplo clique na lista: editar aquele item, sem meio-termo."""
        if self.base is None:
            return
        self.modo = "editar"
        self.estados = []
        self._refazer_estados()
        self.ao_escolher()
        self.log(t("Editando o item %s.") % self.base["id"])

    def _atualizar_modo(self):
        """
        Escreve o modo e ajusta o que pode ser mexido.

        Era a informacao que faltava: com "Item novo" escrito no painel e os
        dados do item marcado dentro dele, nao havia como saber o que o botao
        Gerar ia fazer.
        """
        rotulo = getattr(self, "rotulo_modo", None)
        if rotulo is None:
            return
        if self.base is None:
            rotulo.config(text=t("Escolha um item na lista."))
        elif self.modo == "editar":
            rotulo.config(text=t("Editando o item %s \u2014 %s")
                          % (self.base["id"],
                             self.base["nome"] or t("sem nome")))
        else:
            rotulo.config(text=t("Item novo %s, copiado do %s")
                          % (self.novo_id.get() or "?", self.base["id"]))

        editando = self.modo == "editar"
        self.entrada_id.config(state="readonly" if editando else "normal")
        self.botao_sugerir.config(state="disabled" if editando else "normal")
        self.botao_gerar.config(
            text=t("Regravar o item") if editando else t("Gerar"))

    def novo_item(self):
        """Abre a janela que pergunta o que e preciso para copiar."""
        if self.itens is None:
            messagebox.showinfo(t("Abra as tabelas primeiro"),
                                t("Abra as tabelas do cliente para começar."))
            return
        if self.base is None:
            messagebox.showinfo(t("Escolha a base"),
                                t("Marque na lista o item a copiar."))
            return
        NovoItem(self)

    def comecar_o_novo(self, dados):
        """Chamado pela janela quando o usuário confirma."""
        self.modo = "nova"
        self.icone_pendente = dados.get("pendente")
        self.novo_id.set(dados["id"])
        self.novo_nome.set(dados["nome"])
        self.nova_descricao.set(dados["descricao"])
        self.novo_destaque.set(dados.get("destaque", ""))
        self.novo_icone.set(dados["icone"])
        self.substituir.set(dados["substituir"])
        self.mostrar_icone(dados["icone"])

        # Os números do cliente ficam guardados como estão: quem os grava é o
        # `clonar`, junto com o resto da linha.
        self.numeros_do_cliente = dict(dados.get("numeros") or {})

        vindos = dados.get("estados") or []
        if vindos:
            self.estados = [dict(e) for e in vindos]
            self._refazer_estados()

        for campo, valor in (dados.get("skills") or {}).items():
            if campo in self.campos:
                self.campos[campo].set(valor)

        self._atualizar_modo()
        self.atualizar_botoes()
        self.log(t("Item novo %s, copiado do %s.")
                 % (dados["id"], self.base["id"]))
        if self.numeros_do_cliente:
            self.log(t("  %d números do cliente vieram da janela.")
                     % len(self.numeros_do_cliente))
        if vindos:
            self.log(t("  %d status vieram da janela.") % len(vindos))

    def dizer_o_alvo(self, ident):
        """
        Escreve no botao o id que ele vai ler.

        "Ler do servidor" nao dizia de quem, e com o campo "id novo" logo
        acima mostrando o 90000 sugerido era natural ler aquele numero como o
        alvo. Com o id no proprio botao nao sobra duvida.
        """
        botao = getattr(self, "botao_ler_servidor", None)
        if botao is not None:
            botao.config(text=t("Ler o %s do servidor") % ident)

    def sugerir_id(self):
        if self.itens is not None:
            self.novo_id.set(str(self.itens.proximo_id_livre()))

    def voltar_a_editar(self, ident):
        """
        Depois de gerar, a tela passa a EDITAR o que acabou de sair.

        E o que a pessoa faz em seguida: gerou, quer ver como ficou e ajustar.
        Antes a tela se limpava e sugeria o proximo id, o que empurrava para
        criar outro e deixava o recem-criado sem jeito obvio de reabrir.
        """
        self.modo = "editar"
        for i, item in enumerate(self.mostrados):
            if str(item["id"]) == str(ident):
                self.tabela.selection_set(str(i))
                self.tabela.see(str(i))
                self.ao_escolher()
                return
        self._atualizar_modo()

    # ---- o icone ---------------------------------------------------------
    def mostrar_icone(self, referencia):
        self.rotulo_icone.config(text=referencia or "")
        if Image is None or not referencia:
            self._desenhar_icone(None)
            return
        if referencia in self.icones:
            self._desenhar_icone(self.icones[referencia])
            return
        threading.Thread(target=self._icone_thread, args=(referencia,),
                         daemon=True).start()

    def _icone_thread(self, referencia):
        imagem = self.carregar_icone(referencia)
        self.raiz.after(0, self._guardar_icone, referencia, imagem)

    def carregar_icone(self, referencia):
        """
        A imagem do ícone no tamanho em que o jogo a desenha.

        Só redimensiona quando o objeto não é 32x32 -- redimensionar de 32 para
        32 passaria por um reamostrador à toa e borraria a arte.
        """
        try:
            arquivo = l2item.extrair_icone(self.T, self.cliente.get(),
                                           referencia,
                                           self.trabalho() / "icones",
                                           dizer=self._avisar_do_icone)
            if not arquivo:
                return None
            bruta = motor.abrir_imagem(arquivo, self.T)
            if bruta.size != (LADO_DO_ICONE, LADO_DO_ICONE):
                bruta = bruta.resize((LADO_DO_ICONE, LADO_DO_ICONE),
                                     Image.LANCZOS)
            return bruta
        except Exception:
            return None

    def _guardar_icone(self, referencia, imagem):
        # O PhotoImage tem de nascer na thread do Tk, e precisa de referencia
        # viva: sem guardar, o Tk o recolhe e o rotulo fica em branco.
        foto = ImageTk.PhotoImage(imagem) if imagem is not None else None
        self.icones[referencia] = foto
        if referencia == self.novo_icone.get():
            self._desenhar_icone(foto)

    def _desenhar_icone(self, foto):
        if foto is None:
            self.tela_icone.config(image="", text="—")
        else:
            self.tela_icone.config(image=foto, text="")
        self.tela_icone.imagem = foto

    def escolher_icone(self):
        if self.itens is None:
            return
        catalogo = self.catalogo_de_icones or sorted(
            {i["icone"] for i in self.lista if i["icone"]})
        escolhido = gui_icone.EscolherIcone(self.raiz, self, catalogo,
                                            self.novo_icone.get()).resposta
        if escolhido:
            self.novo_icone.set(escolhido)
            self.mostrar_icone(escolhido)


    # ---- trazer do servidor ----------------------------------------------
    def ler_do_servidor(self):
        """
        Traz do servidor o item MARCADO NA LISTA.

        Dano, defesa e preco NAO EXISTEM no cliente: so o servidor os tem. E
        assim que se copiam os numeros de um item que ja funciona.

        Le o id da lista, e nao o do campo "id novo": o campo diz para onde o
        item vai, a lista diz de onde ele vem. Um item recem-criado esta na
        lista depois de gerar, entao releio dele e so marca-lo.

        Nao achando, diz isso -- "ainda nao existe do lado do servidor" e
        resposta util, e nao erro.
        """
        import l2servidor

        pasta = self.pasta_do_servidor.get().strip()
        if not pasta or not Path(pasta).is_dir():
            messagebox.showerror(t("Pasta inválida"),
                                 t("Aponte a pasta de dados do servidor."))
            return
        if self.base is None:
            messagebox.showinfo(t("Escolha primeiro"),
                                t("Escolha um item na lista."))
            return

        perfil = l2servidor.perfil_escolhido(
            motor.ler_opcao("servidor", "perfil",
                            l2servidor.DETECTAR), pasta)
        # O id lido e o da LISTA, e nao o do campo "id novo". O campo diz para
        # onde o item vai; a lista diz de onde ele vem. Misturar os dois fez a
        # tela trazer outro item sem explicar.
        alvo = str(self.base["id"])
        motor.gravar_opcao("conferir", "servidor", pasta)
        self.situacao_servidor.config(
            text=t("procurando o %s…") % alvo)
        self.raiz.update_idletasks()

        try:
            achado = l2servidor.achar_item(pasta, alvo, perfil)
        except Exception as erro:                   # noqa: BLE001
            self.situacao_servidor.config(text="")
            messagebox.showerror(t("Não deu para ler o servidor"), str(erro))
            return

        if achado is None:
            self.situacao_servidor.config(
                text=t("%s não está no servidor. Preencha e gere.") % alvo)
            self.log(t("  %s não esta no servidor; preencha e gere.") % alvo)
            messagebox.showinfo(
                t("Ainda não existe no servidor"),
                t("Não achei %s na pasta do servidor.\n\nPreencha os campos "
                  "e gere -- o arquivo sai junto com as tabelas do cliente.")
                % alvo)
            return

        self.aplicar_do_servidor(achado)
        aviso = achado.get("aviso") or ""
        self.situacao_servidor.config(
            text=t("Trazido o %s, de %s. %d campos, %d status.%s")
            % (alvo, achado["arquivo"].name, len(achado["campos"]),
               len(achado["estados"]),
               (" " + t("Atenção: %s.") % aviso) if aviso else ""))
        self.log(t("  lido %s de %s") % (alvo, achado["arquivo"].name))

    def aplicar_do_servidor(self, achado):
        """Poe no formulario o que veio do servidor."""
        for chave, valor in (achado.get("campos") or {}).items():
            if chave in self.campos:
                self.campos[chave].set(valor)
        if achado.get("tipo") and "tipo" in self.campos:
            self.campos["tipo"].set(achado["tipo"])

        self.estados = [dict(e) for e in (achado.get("estados") or [])]
        self._refazer_estados()

        # A pasta ja esta apontada e a espera ja foi aceita: aproveita para
        # saber quais status este servidor conhece, calado.
        if self.estados_aceitos is None:
            self.conferir_estados_do_servidor(calado=True)

    # ---- os status -------------------------------------------------------
    def acrescentar_estado(self):
        nome = self._nome_do_rotulo(self.estado_escolhido.get())
        if not nome or nome not in l2item.ESTADOS_POR_NOME:
            messagebox.showinfo(t("Escolha um status"),
                                t("Escolha um status na lista."))
            return
        valor = self.valor.get().strip()
        if not valor:
            messagebox.showinfo(t("Falta o valor"),
                                t("Escreva o valor do status."))
            return
        try:
            float(valor)
        except ValueError:
            messagebox.showerror(t("Valor inválido"),
                                 t("O valor tem de ser um número."))
            return

        if (self.estados_aceitos is not None
                and nome not in self.estados_aceitos):
            if not messagebox.askyesno(
                    t("O servidor não tem esse status"),
                    t("`%s` não existe no seu servidor.\n\nUsá-lo derruba a "
                      "carga da tabela de itens inteira -- os %s, e não só "
                      "este.\n\nAcrescentar assim mesmo?")
                    % (nome, "9.000+"), parent=self.raiz):
                return

        entrada = {"operacao": l2item.so_a_chave(self.operacao.get()),
                   "estado": nome,
                   "ordem": l2item.so_a_chave(self.ordem.get()),
                   "valor": valor}
        if self.estado_em_edicao is not None:
            self.estados[self.estado_em_edicao] = entrada
            self.parar_de_editar_estado()
        else:
            self.estados.append(entrada)
            self.valor.set("")
        self._refazer_estados()

    def _ordem_padrao(self):
        """
        A ordem que o jogo usa para aquela operação.

        Trocada junto com a operação porque é o que o datapack faz sem exceção:
        `set` sempre 0x08, `enchant` 0x0C, `add` e `sub` 0x10, `mul` 0x30. Quem
        precisa de outra ainda pode escolher.
        """
        operacao = l2item.so_a_chave(self.operacao.get())
        alvo = l2item.ORDEM_DA_OPERACAO.get(operacao, "0x10")
        for rotulo in l2item.com_explicacao(l2item.O_QUE_A_ORDEM_FAZ):
            if l2item.so_a_chave(rotulo) == alvo:
                self.ordem.set(rotulo)
                return
        self.ordem.set(alvo)

    def _por_a_operacao(self, chave):
        """Deixa a caixa mostrando aquela operação, com a explicação dela."""
        for rotulo in l2item.com_explicacao(l2item.O_QUE_A_OPERACAO_FAZ):
            if l2item.so_a_chave(rotulo) == chave:
                self.operacao.set(rotulo)
                return
        self.operacao.set(chave)

    def _por_a_ordem(self, chave):
        for rotulo in l2item.com_explicacao(l2item.O_QUE_A_ORDEM_FAZ):
            if l2item.so_a_chave(rotulo) == chave:
                self.ordem.set(rotulo)
                return
        self.ordem.set(chave)

    def tirar_estado(self):
        escolhidos = sorted((int(i) for i in self.tabela_estados.selection()),
                            reverse=True)
        for indice in escolhidos:
            del self.estados[indice]
        self.parar_de_editar_estado()
        self._refazer_estados()

    def _refazer_estados(self):
        """
        Redesenha a tabela a partir da lista.

        A mesma dezena de linhas estava copiada em tres lugares.
        """
        self.tabela_estados.delete(*self.tabela_estados.get_children())
        for i, entrada in enumerate(self.estados):
            self.tabela_estados.insert(
                "", "end", iid=str(i),
                values=(entrada["operacao"],
                        entrada.get("ordem", "") or l2item.ORDEM_DA_OPERACAO
                        .get(entrada["operacao"], "0x10"),
                        "%s (%s)" % (t(l2item.ESTADOS_POR_NOME.get(
                            entrada["estado"], entrada["estado"])),
                            entrada["estado"]),
                        entrada["valor"]))

    def editar_estado(self, _evento=None):
        """
        Duplo clique numa linha: os tres campos voltam para cima.

        Ajustar um valor exigia tirar a linha e escrever tudo de novo, e quem
        so queria trocar 1.30 por 1.25 refazia a operacao e o status junto.
        """
        marcadas = self.tabela_estados.selection()
        if not marcadas:
            return
        indice = int(marcadas[0])
        if indice >= len(self.estados):
            return
        entrada = self.estados[indice]
        self.estado_em_edicao = indice
        self._por_a_operacao(entrada["operacao"])
        self._por_a_ordem(entrada.get("ordem", "")
                          or l2item.ORDEM_DA_OPERACAO.get(entrada["operacao"],
                                                          "0x10"))
        # A caixa e readonly: tem de receber um rotulo que esteja na lista
        # dela. O nome entre parenteses e a chave.
        nome = entrada["estado"]
        for rotulo in self._rotulos_de_estado():
            if self._nome_do_rotulo(rotulo) == nome:
                self.estado_escolhido.set(rotulo)
                break
        self.valor.set(entrada["valor"])
        self.botao_estado.config(text=t("Guardar"))

    def parar_de_editar_estado(self):
        self.estado_em_edicao = None
        self.valor.set("")
        botao = getattr(self, "botao_estado", None)
        if botao is not None:
            botao.config(text=t("Acrescentar"))

    def _xml_atual(self):
        try:
            ident = int(self.novo_id.get().strip())
        except ValueError:
            return None
        campos = dict((chave, var.get()) for chave, var in self.campos.items())
        return l2item.xml_servidor(ident, self.novo_nome.get().strip(),
                                   self.base["grupo"], self.base["id"],
                                   campos=campos, estados=self.estados)

    def ver_xml(self):
        if self.base is None:
            return
        texto = self._xml_atual()
        if texto is None:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número."))
            return
        janela = tk.Toplevel(self.raiz)
        janela.title(t("XML do servidor"))
        janela.transient(self.raiz)
        ajuda.por_icone(janela)
        caixa = tk.Text(janela, width=76, height=26, wrap="none")
        caixa.pack(fill="both", expand=True, padx=8, pady=8)
        caixa.insert("1.0", texto)
        caixa.config(state="disabled")
        ttk.Button(janela, text=t("Fechar"),
                   command=janela.destroy).pack(pady=(0, 8))

    # ---- gerar -----------------------------------------------------------
    def gerar(self):
        if self.rodando or self.itens is None or self.base is None:
            return
        # Editando, o id e o do item marcado e a gravacao passa por cima dele.
        # Ler o id do campo abriria a porta para "editar" um e escrever noutro.
        if self.modo == "editar":
            self.novo_id.set(self.base["id"])
            self.substituir.set(True)
        try:
            novo_id = int(self.novo_id.get().strip())
        except ValueError:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número."))
            return
        if novo_id <= 0:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser maior que zero."))
            return

        if self.modo == "editar":
            if not messagebox.askyesno(
                    t("Regravar o item %s") % novo_id,
                    t("O item %s vai ser regravado com o que está na "
                      "tela.\n\nAs tabelas saem numa pasta à parte; o cliente "
                      "só muda em Instalar no cliente.\n\nRegravar?")
                    % novo_id):
                return
        elif novo_id < l2item.PRIMEIRO_ID_LIVRE and not messagebox.askyesno(
                t("id na faixa do jogo"),
                t("O id %d fica na faixa dos itens originais. Se ele já "
                  "existir, o item de verdade é substituído.\n\nUsar mesmo "
                  "assim?") % novo_id):
            return

        self.rodando = True
        self.atualizar_botoes()
        threading.Thread(target=self._gerar_thread, args=(novo_id,),
                         daemon=True).start()

    def _gerar_thread(self, novo_id):
        def anotar(texto):
            self.raiz.after(0, self.log, "  " + texto)

        try:
            trocas = {}
            icone = self.novo_icone.get().strip()
            if icone and icone != self.base["icone"]:
                trocas["icon[0]"] = icone
            # Os números do cliente entram pela mesma porta do ícone: são
            # colunas da linha nova, e `clonar` é quem a escreve.
            for coluna, valor in (self.numeros_do_cliente or {}).items():
                if coluna in self.itens.tabelas[self.base["grupo"]].cabecalho:
                    trocas[coluna] = valor
            self.itens.clonar(self.base["grupo"], self.base["id"], novo_id,
                              nome=self.novo_nome.get().strip(),
                              descricao=self.nova_descricao.get().strip(),
                              destaque=self.novo_destaque.get().strip(),
                              trocas=trocas,
                              substituir=self.substituir.get())
            try:
                gravados = self.itens.gravar(self.saida(), aolog=anotar)
            except Exception:
                # O item ja estava na memoria quando a gravacao falhou. Deixa-lo
                # la faria a proxima tentativa esbarrar num "id ja existe" que
                # o usuario nao criou.
                self.itens.remover(novo_id)
                raise
            erro = None
        except Exception as e:                      # noqa: BLE001
            gravados, erro = [], e
        self.raiz.after(0, self._fim_geracao, novo_id, gravados, erro)

    def _fim_geracao(self, novo_id, gravados, erro):
        self.rodando = False
        if erro is not None:
            self.log(t("A geração parou: %s") % erro)
            messagebox.showerror(t("A geração parou"), str(erro))
            self.atualizar_botoes()
            return

        self.gravados = gravados
        xml = self._salvar_xml_junto(novo_id)
        self.lista = self.itens.listar()
        self.preencher()
        self.log(t("Item %d gerado em %s") % (novo_id, self.saida()))
        messagebox.showinfo(
            t("Item gerado"),
            t("O item %d foi gerado em:\n\n%s\n\nO XML do servidor saiu "
              "junto, em %s.\n\nNada foi alterado no cliente ainda.")
            % (novo_id, self.saida(), xml.name if xml else "—"))
        self.voltar_a_editar(novo_id)
        self.atualizar_botoes()

    def _salvar_xml_junto(self, novo_id):
        """Grava o XML ao lado das tabelas, com o nome que o servidor espera."""
        texto = self._xml_atual()
        if texto is None:
            return None
        destino = self.saida() / ("%d-item.xml" % novo_id)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8", newline="")
        except OSError as erro:
            self.log(t("Não deu para salvar o XML: %s") % erro)
            return None
        self.log(t("  gravado %s") % destino.name)
        return destino

    # ---- instalar --------------------------------------------------------
    def instalar(self):
        if self.rodando or not self.gravados:
            return
        system = self.system()
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("%d tabelas vão ser copiadas para:\n\n%s\n\nOs originais "
                  "são guardados em %s na primeira vez. Continuar?")
                % (len(self.gravados), system, l2item.PASTA_GUARDA)):
            return
        try:
            postos = l2item.instalar(self.gravados, system,
                                     aolog=lambda s: self.log("  " + s))
            icone = self.instalar_icone_pendente()
        except Exception as e:                      # noqa: BLE001
            self.log(t("A instalação parou: %s") % e)
            messagebox.showerror(t("A instalação parou"), str(e))
            return
        messagebox.showinfo(
            t("Instalação terminada"),
            (t("%d tabelas instaladas, e o pacote de ícone %s. Feche o cliente "
               "antes de testar.") % (len(postos), icone.name) if icone
             else t("%d tabelas instaladas. Feche o cliente antes de "
                    "testar.") % len(postos)))
        self.atualizar_botoes()

    def instalar_icone_pendente(self):
        """
        Poe no cliente o pacote do icone proprio, se houver um esperando.

        Ele foi montado na hora de criar o item e deixado de lado: o cliente
        so muda aqui, num lugar so, com as tabelas. Depois de posto, a marca
        sai -- instalar duas vezes copiaria o mesmo arquivo sobre si mesmo.
        """
        pendente = getattr(self, "icone_pendente", None)
        if not pendente or not Path(pendente).is_file():
            return None
        import l2icone

        posto = l2icone.instalar(pendente, self.cliente.get(),
                                 aolog=lambda s: self.log("  " + s))
        self.icone_pendente = None
        return Path(posto) if posto else Path(pendente)

    def restaurar(self):
        system = self.system()
        if not messagebox.askyesno(
                t("Restaurar originais"),
                t("As tabelas guardadas em %s voltam para o cliente, "
                  "desfazendo os itens criados. Continuar?")
                % l2item.PASTA_GUARDA):
            return
        voltaram = l2item.restaurar(system, aolog=lambda s: self.log("  " + s))
        messagebox.showinfo(t("Pronto"),
                            t("%d tabelas restauradas.") % len(voltaram))

    # ---- trocar a aparencia ----------------------------------------------
    def trocar_aparencia(self):
        """Muda para onde um item que ja existe aponta, sem criar outro."""
        if self.itens is None or self.base is None:
            messagebox.showinfo(t("Escolha um item"),
                                t("Escolha na lista o item a mudar."))
            return
        janela = TrocarAparencia(self.raiz, self, self.base)
        if janela.mudou:
            self.gravados = []
            self.lista = self.itens.listar()
            self.preencher()
            self.atualizar_botoes()
            messagebox.showinfo(
                t("Apar\u00eancia trocada"),
                t("A troca est\u00e1 na mem\u00f3ria. Use Gerar para escrever "
                  "as tabelas, e depois Instalar no cliente."))

    # ---- o manual --------------------------------------------------------
    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "itens", t("Manual — criar um item")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))

    # ---- o XML -----------------------------------------------------------
    def salvar_xml(self):
        if self.base is None:
            return
        texto = self._xml_atual()
        if texto is None:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número."))
            return
        destino = filedialog.asksaveasfilename(
            title=t("Salvar o XML do servidor"), defaultextension=".xml",
            initialfile="%s-item.xml" % self.novo_id.get().strip(),
            filetypes=[("XML", "*.xml"), (t("Todos"), "*.*")])
        if not destino:
            return
        try:
            Path(destino).write_text(texto, encoding="utf-8", newline="")
        except OSError as erro:
            messagebox.showerror(t("Não deu para salvar"), str(erro))
            return
        self.log(t("XML salvo em %s") % destino)


class TrocarAparencia:
    """
    Troca para onde um item que JA EXISTE aponta, sem criar item novo.

    Nao ha lista fixa de colunas: a arma tem duas malhas e tres texturas, a
    armadura tem um par por combinacao de raca e sexo -- 38 referencias numa
    peca comum. A janela mostra toda coluna cujo valor tem a forma
    `pacote.objeto`, que e o formato de referencia, e deixa trocar qualquer uma.

    A troca de pacote em bloco existe porque e assim que um pack de retextura
    chega: os mesmos nomes de objeto, noutro pacote. Trocar 38 referencias a
    mao seria o caminho para errar uma.
    """

    def __init__(self, raiz, dono, item):
        self.dono = dono
        self.item = item
        self.mudou = False
        self.referencias = l2item.referencias_da_linha(
            dono.itens, item["grupo"], item["linha"])

        self.janela = tk.Toplevel(raiz)
        self.janela.title(t("Trocar a apar\u00eancia"))
        self.janela.transient(raiz)
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        ajuda.por_icone(self.janela)

        quadro = ttk.Frame(self.janela, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=560,
                  foreground=COR_TEXTO_FRACO,
                  text=t("%s (id %s) aponta para %d objetos. Troque para onde "
                         "quiser que ele aponte -- o id e o nome n\u00e3o mudam.")
                  % (item["nome"] or t("sem nome"), item["id"],
                     len(self.referencias))).pack(anchor="w")

        dentro = ttk.Frame(quadro)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("campo"), N_("aponta para"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=14, selectmode="browse")
        for nome, largura in zip(colunas, (190, 360)):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor="w")
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.tabela.yview)
        self.tabela.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_marcar)
        self.preencher()

        edicao = ttk.Frame(quadro)
        edicao.pack(fill="x", pady=(8, 0))
        ttk.Label(edicao, text=t("aponta para") + ":").pack(side="left")
        self.valor = tk.StringVar()
        ttk.Entry(edicao, textvariable=self.valor).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(edicao, text=t("Escolher \u00edcone\u2026"),
                   command=self.escolher_icone).pack(side="left", padx=(6, 0))
        ttk.Button(edicao, text=t("Aplicar neste"),
                   command=self.aplicar_um).pack(side="left", padx=(6, 0))

        bloco = ttk.LabelFrame(quadro, text=t("Trocar o pacote em bloco"),
                               padding=6)
        bloco.pack(fill="x", pady=(10, 0))
        ttk.Label(bloco, text=t("de") + ":").pack(side="left")
        self.de = tk.StringVar()
        ttk.Entry(bloco, textvariable=self.de, width=22).pack(side="left",
                                                              padx=(6, 0))
        ttk.Label(bloco, text=t("para") + ":").pack(side="left", padx=(10, 0))
        self.para = tk.StringVar()
        ttk.Entry(bloco, textvariable=self.para, width=22).pack(side="left",
                                                                padx=(6, 0))
        ttk.Button(bloco, text=t("Trocar"),
                   command=self.trocar_bloco).pack(side="left", padx=(10, 0))

        acao = ttk.Frame(quadro)
        acao.pack(fill="x", pady=(10, 0))
        ttk.Button(acao, text=t("Fechar"),
                   command=self.janela.destroy).pack(side="right")
        self.aviso = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.aviso.pack(side="left")

        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        raiz.wait_window(self.janela)

    def preencher(self):
        self.tabela.delete(*self.tabela.get_children())
        for i, entrada in enumerate(self.referencias):
            self.tabela.insert("", "end", iid=str(i),
                               values=(entrada["coluna"], entrada["valor"]))

    def ao_marcar(self, _evento=None):
        escolhido = self.tabela.selection()
        if escolhido:
            self.valor.set(self.referencias[int(escolhido[0])]["valor"])

    def escolher_icone(self):
        catalogo = self.dono.catalogo_de_icones or sorted(
            {i["icone"] for i in self.dono.lista if i["icone"]})
        escolhido = gui_icone.EscolherIcone(self.janela, self.dono, catalogo,
                                            self.valor.get()).resposta
        if escolhido:
            self.valor.set(escolhido)

    def _aplicar(self, trocas):
        if not trocas:
            self.aviso.config(text=t("nada a trocar"))
            return
        try:
            quantas = l2item.trocar_aparencia(self.dono.itens,
                                              self.item["grupo"],
                                              self.item["id"], trocas)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("N\u00e3o deu"), str(erro),
                                 parent=self.janela)
            return
        if quantas:
            self.mudou = True
        for entrada in self.referencias:
            if entrada["coluna"] in trocas:
                entrada["valor"] = trocas[entrada["coluna"]]
        self.preencher()
        self.aviso.config(text=t("%d campo(s) trocado(s)") % quantas)
        self.dono.log(t("  %s: %d campo(s) de apar\u00eancia trocado(s)")
                      % (self.item["id"], quantas))

    def aplicar_um(self):
        escolhido = self.tabela.selection()
        if not escolhido:
            messagebox.showinfo(t("Escolha um campo"),
                                t("Marque na lista o campo a trocar."),
                                parent=self.janela)
            return
        entrada = self.referencias[int(escolhido[0])]
        self._aplicar({entrada["coluna"]: self.valor.get().strip()})

    def trocar_bloco(self):
        self._aplicar(l2item.trocar_pacote(self.referencias, self.de.get(),
                                           self.para.get()))


class NovoItem(tk.Toplevel):
    """
    A janela que pergunta o que e preciso para copiar um item.

    Gemea da de habilidade, e pelo mesmo motivo: mexer num item que existe e
    fazer outro a partir dele sao dois assuntos, e dividir os mesmos campos
    punha o id sugerido a vista de quem so queria olhar o antigo.

    O icone se escolhe VENDO, na grade a direita, ou se envia como imagem
    propria -- que sai preparada e entra no cliente junto com as tabelas.
    """

    def __init__(self, dono):
        tk.Toplevel.__init__(self, dono.raiz)
        self.dono = dono
        self.title(t("Novo item"))
        self.transient(dono.raiz)
        ajuda.por_icone(self)

        base = dono.base
        self.e_arma = base["grupo"] == "weapon"
        self.estados = []
        self.numeros = {}
        self.skills = {}

        quadro = ttk.Frame(self, padding=12)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, font=("Segoe UI", 10, "bold"),
                  text=t("Copiando o item %s — %s")
                  % (base["id"], base["nome"] or t("sem nome"))).pack(
            anchor="w")
        ttk.Label(quadro, foreground=COR_TEXTO_FRACO, wraplength=760,
                  justify="left",
                  text=t("A cópia leva a linha inteira de %s: aparência, peso "
                         "e material vêm da base. O que você mudar aqui entra "
                         "por cima dela.")
                  % t(base["rotulo"])).pack(anchor="w", pady=(2, 10))

        self.abas = ttk.Notebook(quadro)
        self.abas.pack(fill="both", expand=True)

        corpo = ttk.Frame(self.abas, padding=8)
        self.abas.add(corpo, text=t("  Identificação  "))
        if self.e_arma:
            self.abas.add(self._pagina_numeros(), text=t("  Números  "))
        self.abas.add(self._pagina_status(), text=t("  Status  "))
        self.abas.add(self._pagina_skills(), text=t("  Skills  "))

        campos = ttk.Frame(corpo)
        campos.pack(side="left", fill="y")
        campos.columnconfigure(1, weight=1)

        ttk.Label(campos, text=t("id:")).grid(row=0, column=0, sticky="w")
        self.ident = tk.StringVar(
            value=str(dono.itens.proximo_id_livre()) if dono.itens else "")
        ttk.Entry(campos, textvariable=self.ident, width=12).grid(
            row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Button(campos, text=t("Sugerir"), command=self.sugerir).grid(
            row=0, column=2, sticky="w", padx=(6, 0))

        ttk.Label(campos, text=t("nome:")).grid(row=1, column=0, sticky="w",
                                                pady=(6, 0))
        self.nome = tk.StringVar(value=base["nome"])
        ttk.Entry(campos, textvariable=self.nome, width=34).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(campos, text=t("destaque:")).grid(row=2, column=0,
                                                    sticky="w", pady=(6, 0))
        # Vem preenchido com o do item base: a copia herda a linha inteira, e
        # esta e a palavra que o jogo desenha ao lado do nome. Apagar aqui
        # tira a palavra da copia, sem tocar no original.
        self.destaque = tk.StringVar(value=base.get("destaque", ""))
        ttk.Entry(campos, textvariable=self.destaque, width=34).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(campos, text=t("descrição:")).grid(row=3, column=0,
                                                     sticky="w", pady=(6, 0))
        self.descricao = tk.StringVar()
        ttk.Entry(campos, textvariable=self.descricao).grid(
            row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        self.substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(campos, variable=self.substituir,
                        text=t("substituir se o id já existir")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        canto = ttk.Frame(campos)
        canto.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ajuda.ajuda(canto, lambda: t(
            "O id é o que amarra o cliente ao servidor. Use um acima de "
            "30000, longe da faixa do jogo original -- escrever por cima de "
            "um item que existe é o erro mais caro aqui."))

        direita = ttk.LabelFrame(corpo, text=t("Ícone"), padding=6)
        direita.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.icone = gui_icone.PainelDeIcone(
            direita, dono, dono.catalogo_de_icones or sorted(
                {i["icone"] for i in dono.lista if i["icone"]}),
            atual=base["icone"])
        self.icone.pack(fill="both", expand=True)

        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(14, 0))
        ttk.Button(rodape, text=t("Cancelar"),
                   command=self.destroy).pack(side="right")
        ttk.Button(rodape, text=t("Criar"), command=self.criar).pack(
            side="right", padx=(0, 6))
        self.recado = ttk.Label(rodape, text="", foreground=tema.ATENCAO,
                                wraplength=560, justify="left")
        self.recado.pack(side="left")

        if self.e_arma:
            self._ler_a_base()

        self.bind("<Escape>", lambda _e: self.destroy())
        ajuda.centralizar(self)
        self.grab_set()
        self.focus_set()
        self._fixar_tamanho()

    def _fixar_tamanho(self):
        """
        Trava o tamanho da janela depois de medida.

        Um caderno pede a largura da página mais larga, e a janela seguia essa
        medida: trocar de página, ou escolher um ícone de nome comprido,
        redimensionava tudo e a tela parecia piscar. Medida uma vez, ela para
        de se mexer sozinha -- e continua redimensionável pela borda.
        """
        try:
            self.update_idletasks()
            # Pelo conteudo, mas nunca maior do que a tela: o que passa do
            # monitor nao fica so escondido, fica inalcancavel.
            ajuda.ajustar_a_tela(self, 900, 520)
        except tk.TclError:
            pass

    # ---- página dos números do cliente -----------------------------------
    def _pagina_numeros(self):
        """
        As colunas do `weapongrp.dat` -- o que a tooltip do inventário mostra.

        Não é o mesmo que o status do servidor, e é por isso que estão em
        páginas separadas: um é o que o jogador lê, o outro é o que o golpe
        faz. Divergir não dá erro em lugar nenhum.
        """
        aba = ttk.Frame(self.abas, padding=8)
        ttk.Label(aba, foreground=COR_TEXTO_FRACO, wraplength=740,
                  justify="left",
                  text=t("Estes são os números do CLIENTE: o que aparece na "
                         "tooltip do inventário. Quem manda no golpe é o "
                         "servidor, na aba Status.")).pack(anchor="w")

        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(8, 0))
        self.campos_numeros = {}
        for i, (coluna, rotulo, alvo, _op) in enumerate(l2item.NUMEROS_DA_ARMA):
            linha, lado = divmod(i, 3)
            celula = ttk.Frame(grade)
            celula.grid(row=linha, column=lado, sticky="w", padx=(0, 18),
                        pady=(0, 6))
            ttk.Label(celula, text=t(rotulo) + ":").pack(anchor="w")
            baixo = ttk.Frame(celula)
            baixo.pack(anchor="w")
            variavel = tk.StringVar()
            self.campos_numeros[coluna] = variavel
            ttk.Entry(baixo, textvariable=variavel, width=9).pack(side="left")
            ttk.Label(baixo, text=alvo, foreground=COR_TEXTO_FRACO,
                      font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))

        baixo = ttk.Frame(aba)
        baixo.pack(fill="x", pady=(10, 0))
        ttk.Button(baixo, text=t("Copiar para os Status"),
                   command=self.numeros_para_status).pack(side="left")
        ttk.Button(baixo, text=t("Voltar aos da base"),
                   command=self._ler_a_base).pack(side="left", padx=(6, 0))
        ajuda.ajuda(baixo, lambda: t(
            "O nome cinza ao lado de cada caixa é o status do servidor "
            "correspondente. A correspondência foi conferida contra o "
            "datapack, item a item.@@"
            "`Copiar para os Status` escreve os mesmos números na aba Status, "
            "para os dois lados não discordarem. Precisão e evasão viram `sub` "
            "quando o número é negativo, que é como o servidor escreve.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))
        return aba

    def _ler_a_base(self):
        """Enche os números com os da arma copiada."""
        try:
            self.numeros = l2item.numeros_da_arma(self.dono.itens,
                                                  self.dono.base["id"])
        except Exception:                           # noqa: BLE001
            self.numeros = {}
        for coluna, variavel in self.campos_numeros.items():
            variavel.set(self.numeros.get(coluna, ""))

    def numeros_para_status(self):
        """Os números do cliente viram o <for> do servidor."""
        vindos = l2item.estados_dos_numeros(
            dict((c, v.get()) for c, v in self.campos_numeros.items()))
        if not vindos:
            self.recado.config(text=t("Nenhum número para copiar."))
            return
        # Substitui o status do mesmo nome em vez de duplicar: dois <set> para
        # o mesmo stat é o servidor aplicando o último e o usuário lendo o
        # primeiro.
        de_fora = set(e["estado"] for e in vindos)
        self.estados = [e for e in self.estados
                        if e.get("estado") not in de_fora] + vindos
        self._refazer_estados()
        self.abas.select(2 if self.e_arma else 1)
        self.recado.config(text=t("%d status vieram dos números.")
                           % len(vindos))

    # ---- página dos status do servidor -----------------------------------
    def _pagina_status(self):
        aba = ttk.Frame(self.abas, padding=8)
        ttk.Label(aba, wraplength=740, justify="left",
                  font=("Segoe UI", 9, "bold"),
                  text=t("É esta página que faz o item valer alguma coisa. "
                         "Sem ela, a espada nova tem a aparência certa e dano "
                         "nenhum.")).pack(anchor="w")
        ttk.Label(aba, foreground=COR_TEXTO_FRACO, wraplength=740,
                  justify="left",
                  text=t("Monte uma linha de cada vez: escolha o que a conta "
                         "FAZ, depois QUAL número do jogador ela mexe, "
                         "escreva o valor e clique em Acrescentar.\n"
                         "Numa arma comum são quatro linhas: `fixa` para dano "
                         "físico, dano mágico, crítico e velocidade de "
                         "ataque.")).pack(anchor="w", pady=(2, 0))

        escolha = ttk.Frame(aba)
        escolha.pack(fill="x", pady=(10, 0))
        # Piso de largura na coluna que estica: e ela que leva o rotulo mais
        # longo da linha E a caixa de status. Sem o piso, numa janela estreita
        # a grade a espremia e `3. que numero do jogador:` saia aparado.
        escolha.columnconfigure(3, weight=1, minsize=230)

        ttk.Label(escolha, text=t("1. a conta faz:")).grid(row=0, column=0,
                                                           sticky="w")
        self.operacao = tk.StringVar()
        caixa = ttk.Combobox(escolha, textvariable=self.operacao,
                             values=l2item.com_explicacao(
                                 l2item.O_QUE_A_OPERACAO_FAZ),
                             state="readonly", width=30)
        caixa.grid(row=1, column=0, columnspan=2, sticky="w")
        caixa.bind("<<ComboboxSelected>>", lambda _e: self._ordem_padrao())

        ttk.Label(escolha, text=t("2. em que momento:")).grid(
            row=0, column=2, sticky="w", padx=(10, 0))
        self.ordem = tk.StringVar()
        ttk.Combobox(escolha, textvariable=self.ordem,
                     values=l2item.com_explicacao(l2item.O_QUE_A_ORDEM_FAZ),
                     state="readonly", width=26).grid(
            row=1, column=2, sticky="w", padx=(10, 0))
        self.operacao.set(l2item.com_explicacao(
            l2item.O_QUE_A_OPERACAO_FAZ)[0])
        self._ordem_padrao()

        ttk.Label(escolha, text=t("3. que número do jogador:")).grid(
            row=0, column=3, sticky="w", padx=(10, 0))
        self.estado_escolhido = tk.StringVar()
        self.caixa_estado = ttk.Combobox(
            escolha, textvariable=self.estado_escolhido,
            values=self.dono._rotulos_de_estado(), state="readonly")
        self.caixa_estado.grid(row=1, column=3, sticky="ew", padx=(10, 0))

        ttk.Label(escolha, text=t("4. quanto:")).grid(row=0, column=4,
                                                      sticky="w", padx=(10, 0))
        self.valor = tk.StringVar()
        entrada = ttk.Entry(escolha, textvariable=self.valor, width=8)
        entrada.grid(row=1, column=4, sticky="w", padx=(10, 0))
        entrada.bind("<Return>", lambda _e: self.acrescentar_estado())

        ttk.Button(escolha, text=t("Acrescentar"),
                   command=self.acrescentar_estado).grid(row=1, column=5,
                                                         sticky="w",
                                                         padx=(10, 0))

        dentro = ttk.Frame(aba)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("operação"), N_("ordem"), N_("status"), N_("valor"))
        self.tabela_estados = ttk.Treeview(dentro, columns=colunas,
                                           show="headings", height=8,
                                           selectmode="extended")
        for nome, largura, alinhamento in zip(colunas, (90, 70, 300, 80),
                                              ("w", "w", "w", "e")):
            self.tabela_estados.heading(nome, text=t(nome))
            self.tabela_estados.column(nome, width=largura, anchor=alinhamento)
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela_estados.yview)
        self.tabela_estados.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela_estados.pack(side="left", fill="both", expand=True)
        self.tabela_estados.bind("<Double-1>", lambda _e: self.tirar_estado())

        baixo = ttk.Frame(aba)
        baixo.pack(fill="x", pady=(6, 0))
        ttk.Button(baixo, text=t("Tirar"),
                   command=self.tirar_estado).pack(side="left")
        ajuda.ajuda(baixo, lambda: t(
            "A operação diz como o valor entra na conta: `set` fixa a base, "
            "`add` e `sub` somam antes dos multiplicadores, `mul` multiplica, "
            "`enchant` é a parcela que cresce a cada +1.@@"
            "A ordem é o momento da conta, e o servidor NÃO tem padrão para "
            "ela: falta o atributo, a tabela de itens inteira deixa de "
            "carregar. Ela é preenchida sozinha com o que o jogo usa para "
            "cada operação.@@"
            "Um nome de status que o seu servidor não conheça também derruba "
            "a carga. Aponte a pasta do servidor na aba e os que ele não tem "
            "aparecem marcados.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))
        return aba

    def _ordem_padrao(self):
        """
        Escolhe sozinha o momento que o jogo usa para aquela conta.

        Quem não sabe o que é `0x08` não deveria precisar escolher: o padrão de
        cada operação é o que o datapack faz sem uma exceção.
        """
        operacao = l2item.so_a_chave(self.operacao.get())
        alvo = l2item.ORDEM_DA_OPERACAO.get(operacao, "0x10")
        for rotulo in l2item.com_explicacao(l2item.O_QUE_A_ORDEM_FAZ):
            if l2item.so_a_chave(rotulo) == alvo:
                self.ordem.set(rotulo)
                return
        self.ordem.set(alvo)

    def acrescentar_estado(self):
        nome = self.dono._nome_do_rotulo(self.estado_escolhido.get())
        valor = self.valor.get().strip()
        if not nome or not valor:
            self.recado.config(text=t("Escolha o status e escreva o valor."))
            return
        self.estados = [e for e in self.estados if e.get("estado") != nome]
        self.estados.append({"operacao": l2item.so_a_chave(self.operacao.get()),
                             "ordem": l2item.so_a_chave(self.ordem.get()),
                             "estado": nome, "valor": valor})
        self.valor.set("")
        self._refazer_estados()
        self.recado.config(text="")

    def tirar_estado(self):
        fora = sorted((int(i) for i in self.tabela_estados.selection()),
                      reverse=True)
        for indice in fora:
            if indice < len(self.estados):
                del self.estados[indice]
        self._refazer_estados()

    def _refazer_estados(self):
        tabela = getattr(self, "tabela_estados", None)
        if tabela is None:
            return
        tabela.delete(*tabela.get_children())
        for i, entrada in enumerate(self.estados):
            nome = entrada.get("estado", "")
            rotulo = l2item.ESTADOS_POR_NOME.get(nome, nome)
            tabela.insert("", "end", iid=str(i),
                          values=(entrada.get("operacao", "add"),
                                  entrada.get("ordem", "")
                                  or l2item.ORDEM_DA_OPERACAO.get(
                                      entrada.get("operacao", "add"), "0x10"),
                                  "%s (%s)" % (t(rotulo), nome),
                                  entrada.get("valor", "")))

    # ---- página das skills -----------------------------------------------
    def _pagina_skills(self):
        aba = ttk.Frame(self.abas, padding=8)
        ttk.Label(aba, foreground=COR_TEXTO_FRACO, wraplength=740,
                  justify="left",
                  text=t("Skills que o item carrega. O valor é o id e o nível "
                         "escritos juntos: 3599-1.")).pack(anchor="w")

        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(10, 0))
        grade.columnconfigure(1, weight=1)
        self.campos_skill = {}

        linha = 0
        for campo, rotulo, chance in l2item.SKILLS_DO_ITEM:
            # `item_skill` vale para qualquer item; as outras três só o core lê
            # em arma, e escrevê-las noutro tipo é enfeite que não faz nada.
            if chance is not None or campo == "enchant4_skill":
                if not self.e_arma:
                    continue
            ttk.Label(grade, text=t(rotulo) + ":").grid(row=linha, column=0,
                                                        sticky="w",
                                                        pady=(0, 6))
            caixa = ttk.Frame(grade)
            caixa.grid(row=linha, column=1, sticky="w", padx=(8, 0),
                       pady=(0, 6))
            variavel = tk.StringVar()
            self.campos_skill[campo] = variavel
            ttk.Entry(caixa, textvariable=variavel, width=22).pack(side="left")
            ttk.Label(caixa, text=campo, foreground=COR_TEXTO_FRACO,
                      font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))
            if chance:
                ttk.Label(caixa, text=t("chance") + ":").pack(side="left",
                                                              padx=(12, 0))
                quanto = tk.StringVar()
                self.campos_skill[chance] = quanto
                ttk.Entry(caixa, textvariable=quanto, width=6).pack(
                    side="left", padx=(4, 0))
                ttk.Label(caixa, text="%", foreground=COR_TEXTO_FRACO).pack(
                    side="left")
            linha += 1

        ttk.Button(aba, text=t("Conferir"), command=self.conferir_skills).pack(
            anchor="w", pady=(6, 0))
        self.recado_skill = ttk.Label(aba, text="", foreground=tema.ATENCAO,
                                      wraplength=720, justify="left")
        self.recado_skill.pack(anchor="w", pady=(6, 0))

        ajuda.ajuda(aba, lambda: t(
            "`enquanto equipado` aceita várias, separadas por `;`. As outras "
            "três, só uma.@@"
            "Cuidado com a chance: o servidor descarta a skill EM SILÊNCIO se "
            "ela faltar ou for zero. Não dá erro, não vai para o log -- a arma "
            "simplesmente não faz nada, e quem for testar vai culpar a skill.@@"
            "O id é o da habilidade no servidor. A aba Habilidades lista "
            "todas as que existem neste cliente.")
            .replace("@@", chr(10) + chr(10)), padx=(0, 0), pady=(8, 0),
            side="top", anchor="w")
        return aba

    def skills_escritas(self):
        return dict((campo, variavel.get().strip())
                    for campo, variavel in self.campos_skill.items()
                    if variavel.get().strip())

    def conferir_skills(self):
        problemas = l2item.conferir_skills(self.skills_escritas())
        self.recado_skill.config(
            text="\n".join("• " + p for p in problemas) if problemas
            else t("Nada a corrigir."),
            foreground=tema.ATENCAO if problemas else tema.BOM)
        return problemas

    def sugerir(self):
        if self.dono.itens is not None:
            self.ident.set(str(self.dono.itens.proximo_id_livre()))

    def criar(self):
        texto = self.ident.get().strip()
        if not texto.isdigit() or int(texto) <= 0:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número maior que "
                                   "zero."), parent=self)
            return
        ident = int(texto)
        # A lista da aba ja tem todos os itens do cliente: perguntar a ela e
        # mais honesto do que abrir a tabela outra vez so para saber isto.
        existe = any(str(i["id"]) == texto for i in self.dono.lista)
        if existe and not self.substituir.get():
            messagebox.showerror(
                t("Esse id já existe"),
                t("O item %d já está no cliente.\n\nEscolha outro id, ou "
                  "marque \"substituir se o id já existir\".") % ident,
                parent=self)
            return
        if ident < l2item.PRIMEIRO_ID_LIVRE and not messagebox.askyesno(
                t("Id baixo"),
                t("O %d está na faixa do jogo. Os ids a partir de %d ficam "
                  "longe dela.\n\nUsar o %d assim mesmo?")
                % (ident, l2item.PRIMEIRO_ID_LIVRE, ident), parent=self):
            return
        if not self.icone.referencia and not messagebox.askyesno(
                t("Sem ícone"),
                t("Nenhum ícone escolhido: o item fica com o quadrado vazio "
                  "no lugar dele.\n\nContinuar assim?"), parent=self):
            return

        skills = self.skills_escritas()
        problemas = l2item.conferir_skills(skills)
        if problemas:
            self.abas.select(self.abas.index("end") - 1)
            self.conferir_skills()
            if not messagebox.askyesno(
                    t("As skills têm problema"),
                    t("%s\n\nCriar assim mesmo?")
                    % "\n".join("• " + p for p in problemas), parent=self):
                return

        numeros = dict((coluna, variavel.get().strip())
                       for coluna, variavel in
                       getattr(self, "campos_numeros", {}).items()
                       if variavel.get().strip() != "")

        self.dono.comecar_o_novo({"id": str(ident),
                                  "nome": self.nome.get().strip(),
                                  "destaque": self.destaque.get().strip(),
                                  "descricao": self.descricao.get().strip(),
                                  "icone": self.icone.referencia,
                                  "substituir": self.substituir.get(),
                                  "pendente": self.icone.pendente,
                                  "numeros": numeros,
                                  "estados": list(self.estados),
                                  "skills": skills})
        self.destroy()
