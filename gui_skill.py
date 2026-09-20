#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aba "Habilidades" -- criar uma habilidade nova copiando uma que ja existe.

Mesmo desenho da aba de Itens, com a diferenca que muda tudo: habilidade tem
NIVEL. A lista mostra uma linha por habilidade, e nao por nivel -- seriam
42.019 linhas com a mesma habilidade repetida quarenta vezes.

Copiar leva todos os niveis, nas duas tabelas, de uma vez. O corte "até o
nível" existe para as rotas de encantamento, que passam de seis mil niveis e
que ninguem quer clonar por engano.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import rolagem
import gui_icone
import l2conferir
import l2item
import l2skill
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
LADO_DO_ICONE = 32

CARTOES = (
    ("total", N_("habilidades"), tema.PAINEL, tema.TEXTO),
    ("niveis", N_("níveis somados"), tema.PAINEL, tema.TEXTO),
    ("ativas", N_("ativas"), tema.PAINEL, tema.TEXTO),
    ("passivas", N_("passivas"), tema.PAINEL, tema.TEXTO),
)

# (chave no XML, rotulo, opcoes ou None para campo livre)
CAMPOS = (
    ("skillType", N_("tipo de efeito"), l2skill.TIPOS),
    ("operateType", N_("modo"), l2skill.OPERACOES),
    ("target", N_("alvo"), l2skill.ALVOS),
    ("power", N_("poder"), None),
    ("magicLvl", N_("nível mágico"), None),
    ("mpConsume", N_("mana por uso"), None),
    ("mpInitialConsume", N_("mana ao começar"), None),
    ("hpConsume", N_("vida por uso"), None),
    ("castRange", N_("alcance"), None),
    ("effectRange", N_("alcance do efeito"), None),
    ("skillRadius", N_("raio"), None),
    ("hitTime", N_("tempo de uso (ms)"), None),
    ("coolTime", N_("tempo final (ms)"), None),
    ("reuseDelay", N_("recarga (ms)"), None),
    ("element", N_("elemento"), l2skill.ELEMENTOS),
    ("weaponsAllowed", N_("armas permitidas"), l2skill.ARMAS_PERMITIDAS),
    ("aggroPoints", N_("provocação"), None),
    ("abnormalTime", N_("duração (s)"), None),
    ("isMagic", N_("é magia"), l2skill.SIM_NAO),
    ("isDebuff", N_("é maldição"), l2skill.SIM_NAO),
    ("lvlDepend", N_("depende do nível"), None),
    ("overHit", N_("permite over-hit"), l2skill.SIM_NAO),
    ("staticReuse", N_("recarga fixa"), l2skill.SIM_NAO),
    ("ignoreShld", N_("ignora escudo"), l2skill.SIM_NAO),
)


class JanelaSkill:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.skills = None
        self.lista = []
        self.mostrados = []
        self.icones = {}
        self.gravados = []
        self.base = None
        self.campos = {}
        self.estados = []
        # "editar" ou "nova". A tela inteira depende disto, e o usuario le o
        # modo no alto do painel em vez de deduzi-lo dos campos.
        self.modo = "editar"
        self.estado_em_edicao = None
        # O .utx de um icone proprio, feito e ainda nao instalado. Ele entra no
        # cliente junto com as tabelas, no mesmo "Instalar no cliente".
        self.icone_pendente = None
        self.catalogo_de_icones = []

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Clique numa habilidade da lista para editá-la. "
                         "Para criar uma, use Nova habilidade — a cópia leva "
                         "todos os níveis, no skillgrp e no "
                         "skillname.")).pack(anchor="w")

        self._montar_cliente(quadro)
        self._montar_resumo(quadro)

        painel = ttk.Panedwindow(quadro, orient="horizontal")
        painel.pack(fill="both", expand=True, pady=(8, 0))
        painel.add(self._montar_lista(painel), weight=2)
        painel.add(self._montar_nova(painel), weight=3)

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
            "Abrir lê o skillgrp.dat e o skillname-e.dat do cliente.\n\n"
            "Antes de qualquer coisa ser gravada, cada tabela é remontada e "
            "comparada com o binário original. Se a volta não reproduz a ida "
            "byte a byte, a definição não descreve este cliente e nada é "
            "escrito."), padx=(8, 0))

    def _montar_resumo(self, pai):
        faixa = ttk.Frame(pai)
        faixa.pack(fill="x", pady=(10, 0))
        self.numeros = {}
        for i, (chave, rotulo, fundo, cor) in enumerate(CARTOES):
            cartao = tk.Frame(faixa, bg=fundo, padx=14, pady=10,
                              highlightthickness=1,
                              highlightbackground=tema.BORDA)
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
        caixa = ttk.LabelFrame(pai, text=t("Habilidade base"), padding=6)

        busca = ttk.Frame(caixa)
        busca.pack(fill="x")
        ttk.Label(busca, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(busca, textvariable=self.filtro)
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self.preencher())
        self.conta = ttk.Label(busca, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("nome"), N_("modo"), N_("níveis"), N_("ícone"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=16, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (64, 190, 76, 60, 170),
                                              ("e", "w", "w", "e", "w")):
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

    def _montar_nova(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Habilidade"), padding=6)

        # O modo primeiro, e em negrito: era a informacao que faltava.
        self.rotulo_modo = ttk.Label(
            caixa, text="", font=("Segoe UI", 10, "bold"), wraplength=380,
            justify="left")
        self.rotulo_modo.pack(anchor="w", pady=(0, 6))

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        self.moldura = tk.Frame(topo, bg=COR_FUNDO_ICONE,
                                width=LADO_DO_ICONE + 10,
                                height=LADO_DO_ICONE + 10,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA)
        self.moldura.pack(side="left")
        self.moldura.pack_propagate(False)
        self.tela_icone = tk.Label(self.moldura, bg=COR_FUNDO_ICONE,
                                   fg=tema.TEXTO_APAGADO, text="—",
                                   font=("Segoe UI", 8))
        self.tela_icone.pack(expand=True)

        resumo = ttk.Frame(topo)
        resumo.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.rotulo_base = ttk.Label(
            resumo, text=t("Escolha uma habilidade na lista."),
            foreground=COR_TEXTO_FRACO, wraplength=380, justify="left")
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
        self.botao_nova = ttk.Button(acao, text=t("Nova habilidade\u2026"),
                                     command=self.nova_habilidade)
        self.botao_nova.pack(side="left")
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
        # Editando, o id e o da habilidade marcada e nao se digita: mudar o
        # numero ali era, na verdade, criar outra -- e foi assim que a tela
        # trouxe uma coisa quando se pediu outra.
        self.entrada_id = ttk.Entry(aba, textvariable=self.novo_id, width=12)
        self.entrada_id.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.botao_sugerir = ttk.Button(aba, text=t("Sugerir"),
                                        command=self.sugerir_id)
        self.botao_sugerir.grid(row=0, column=2, sticky="w", padx=(6, 0))

        ttk.Label(aba, text=t("nome:")).grid(row=1, column=0, sticky="w",
                                             pady=(6, 0))
        self.novo_nome = tk.StringVar()
        ttk.Entry(aba, textvariable=self.novo_nome).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(aba, text=t("descrição:")).grid(row=2, column=0, sticky="w",
                                                  pady=(6, 0))
        self.nova_descricao = tk.StringVar()
        ttk.Entry(aba, textvariable=self.nova_descricao).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(aba, text=t("ícone:")).grid(row=3, column=0, sticky="w",
                                              pady=(6, 0))
        self.novo_icone = tk.StringVar()
        entrada = ttk.Entry(aba, textvariable=self.novo_icone)
        entrada.grid(row=3, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        entrada.bind("<FocusOut>",
                     lambda _e: self.mostrar_icone(self.novo_icone.get()))
        entrada.bind("<Return>",
                     lambda _e: self.mostrar_icone(self.novo_icone.get()))
        self.botao_icone = ttk.Button(aba, text=t("Escolher…"),
                                      command=self.escolher_icone)
        self.botao_icone.grid(row=3, column=2, sticky="w", padx=(6, 0),
                              pady=(6, 0))

        ttk.Label(aba, text=t("copiar até o nível:")).grid(
            row=4, column=0, sticky="w", pady=(6, 0))
        self.ate_o_nivel = tk.StringVar()
        ttk.Entry(aba, textvariable=self.ate_o_nivel, width=12).grid(
            row=4, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        self.substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(aba, variable=self.substituir,
                        text=t("substituir se o id já existir")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

        canto = ttk.Frame(aba)
        canto.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ajuda.ajuda(canto, lambda: t(
            "O id acima de 90000 fica longe da faixa do jogo e das rotas de "
            "encantamento, que ocupam os 50000.\n\n"
            "Copiar até o nível corta a cópia: em branco, leva todos os "
            "níveis da habilidade base."))
        return aba

    def _montar_xml(self, pai):
        aba = ttk.Frame(pai, padding=8)

        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Mana, alcance e tempo de uso vêm do cliente. Campo "
                         "em branco não é escrito: o servidor usa o padrão "
                         "dele.")).pack(anchor="w")
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
            "Traz do servidor a habilidade que est\u00e1 MARCADA NA LISTA -- e "
            "n\u00e3o a do campo \"id novo\".\n\n"
            "Poder, recarga e tipo de efeito n\u00e3o existem no cliente: "
            "s\u00f3 o servidor os tem. \u00c9 assim que se copia os "
            "n\u00fameros de uma habilidade que j\u00e1 funciona.\n\n"
            "Para reler uma que voc\u00ea criou, marque-a na lista: ela "
            "est\u00e1 l\u00e1 depois de gerar."), padx=(8, 0))

        self.situacao_servidor = ttk.Label(aba, text="",
                                           foreground=COR_TEXTO_FRACO,
                                           wraplength=420, justify="left")
        self.situacao_servidor.pack(anchor="w", pady=(4, 0))


        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(8, 0))
        grade.columnconfigure(1, weight=1)
        grade.columnconfigure(3, weight=1)
        for i, (chave, rotulo, opcoes) in enumerate(CAMPOS):
            coluna = (i % 2) * 2
            fila = i // 2
            ttk.Label(grade, text=t(rotulo) + ":").grid(
                row=fila, column=coluna, sticky="w", pady=2)
            variavel = tk.StringVar()
            self.campos[chave] = variavel
            if opcoes is None:
                widget = ttk.Entry(grade, textvariable=variavel, width=14)
            else:
                widget = ttk.Combobox(grade, textvariable=variavel,
                                      values=list(opcoes), width=14)
            widget.grid(row=fila, column=coluna + 1, sticky="ew",
                        padx=(6, 12), pady=2)

        caixa = ttk.LabelFrame(aba, text=t("Status que a habilidade dá"),
                               padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))

        escolha = ttk.Frame(caixa)
        escolha.pack(fill="x")
        escolha.columnconfigure(3, weight=1)

        ttk.Label(escolha, text=t("operação") + ":").grid(row=0, column=0,
                                                          sticky="w")
        self.operacao = tk.StringVar(value="add")
        ttk.Combobox(escolha, textvariable=self.operacao,
                     values=list(l2item.OPERACOES), state="readonly",
                     width=9).grid(row=1, column=0, sticky="w")

        ttk.Label(escolha, text=t("status") + ":").grid(row=0, column=3,
                                                        sticky="w",
                                                        padx=(8, 0))
        self.estado_escolhido = tk.StringVar()
        ttk.Combobox(escolha, textvariable=self.estado_escolhido,
                     values=self._rotulos_de_estado(),
                     state="readonly").grid(row=1, column=3, sticky="ew",
                                            padx=(8, 0))

        ttk.Label(escolha, text=t("valor") + ":").grid(row=0, column=4,
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
        colunas = (N_("operação"), N_("status"), N_("valor"))
        self.tabela_estados = ttk.Treeview(dentro, columns=colunas,
                                           show="headings", height=5,
                                           selectmode="extended")
        for nome, largura, alinhamento in zip(colunas, (90, 300, 80),
                                              ("w", "w", "e")):
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
        ttk.Label(baixo, text=t("Duplo clique numa linha para ajustá-la."),
                  foreground=COR_TEXTO_FRACO).pack(side="right")
        ttk.Button(baixo, text=t("Tirar"),
                   command=self.tirar_estado).pack(side="left")
        ttk.Button(baixo, text=t("Ver o XML"),
                   command=self.ver_xml).pack(side="left", padx=(6, 0))
        ajuda.ajuda(baixo, lambda: t(
            "O valor pode ser um só, que vale para todos os níveis, ou um por "
            "nível, separados por espaço:\n\n"
            "    1.15 1.20 1.25\n\n"
            "Nesse caso o programa escreve a <table> e faz o <set> apontar "
            "para ela, que é como o jogo guarda o \"Power 25\" que vira "
            "\"Power 27\".\n\n"
            "A conta tem de bater com o número de níveis. Se não bater, o "
            "programa avisa antes de gerar."), padx=(10, 0))
        return aba

    def _montar_rodape(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left")
        self.botao_xml = ttk.Button(linha, text=t("Salvar XML do servidor…"),
                                    command=self.salvar_xml)
        self.botao_xml.pack(side="left", padx=(6, 0))
        self.botao_restaurar = ttk.Button(linha, text=t("Restaurar originais"),
                                          command=self.restaurar)
        self.botao_restaurar.pack(side="left", padx=(6, 0))

        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=4, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

    def _rotulos_de_estado(self):
        saida = []
        for grupo, pares in l2item.ESTADOS:
            for nome, rotulo in pares:
                saida.append("%s — %s (%s)" % (t(grupo), t(rotulo), nome))
        return saida

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
        return Path(motor.BASE) / "trabalho" / "skills"

    def saida(self):
        return Path(motor.BASE) / "skills_geradas"

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
        pronto = parado and self.skills is not None and self.base is not None
        self.botao_gerar.config(state="normal" if pronto else "disabled")
        self.botao_nova.config(state="normal" if pronto else "disabled")
        self.botao_icone.config(
            state="normal" if parado and self.skills is not None else "disabled")
        self.botao_instalar.config(
            state="normal" if parado and self.gravados else "disabled")
        self.botao_xml.config(state="normal" if pronto else "disabled")
        self.botao_restaurar.config(
            state="normal" if parado and (self.system() /
                                          l2skill.PASTA_GUARDA).is_dir()
            else "disabled")

    # ---- escolhas --------------------------------------------------------
    def cronica_escolhida(self):
        """O nome da pasta da cronica que esta na caixa."""
        return l2item.cronica_do_rotulo(self.cronica_rotulo.get(),
                                        self.embutidas)

    def ao_trocar_cronica(self, _evento=None):
        motor.gravar_opcao("item", "cronica", self.cronica_escolhida())
        self.skills = None
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
        self.log(t("\n=== abrindo as tabelas de habilidade de %s ===") % system)
        threading.Thread(target=self._abrir_thread, args=(system,),
                         daemon=True).start()

    def _abrir_thread(self, system):
        try:
            skills = l2skill.Skills(self.T, system, self.trabalho(),
                                    self.cronica_escolhida(),
                                    aoprogresso=self.progresso)
            erro = None
        except Exception as e:                      # noqa: BLE001
            skills, erro = None, e
        self.raiz.after(0, self._fim_abertura, skills, erro)

    def _fim_abertura(self, skills, erro):
        self.rodando = False
        if erro is not None:
            self._desenhar_progresso(0, "")
            self.log(t("Não deu para abrir: %s") % erro)
            messagebox.showerror(t("Não deu para abrir as tabelas"), str(erro))
            self.atualizar_botoes()
            return

        self.skills = skills
        self.gravados = []
        for chave, (deu, motivo) in sorted(skills.provas.items()):
            self.log(t("  %s: %s") % (skills.tabelas[chave].origem.name,
                                      motivo))
        ruins = skills.conferir(so_alteradas=False)
        if ruins:
            messagebox.showwarning(
                t("Definição não confere"),
                t("Estas tabelas não voltam iguais ao original:\n\n%s\n\n"
                  "Elas podem ser lidas, mas gravar qualquer alteração nelas "
                  "está bloqueado.") % "\n".join("%s — %s" % p for p in ruins))

        self.lista = skills.listar()
        self.numeros["total"].config(text="%d" % len(self.lista))
        self.numeros["niveis"].config(
            text="%d" % sum(h["niveis"] for h in self.lista))
        self.numeros["ativas"].config(
            text="%d" % sum(1 for h in self.lista if h["tipo"] == "ACTIVE"))
        self.numeros["passivas"].config(
            text="%d" % sum(1 for h in self.lista if h["tipo"] == "PASSIVE"))

        self.preencher()
        self.sugerir_id()
        self._desenhar_progresso(1.0, t("tabelas abertas"))
        self.log(t("%d habilidades lidas.") % len(self.lista))
        self.atualizar_botoes()
        threading.Thread(target=self._catalogar_icones, daemon=True).start()

    def _catalogar_icones(self):
        try:
            import l2item as _item
            catalogo = _item.icones_do_cliente(
                self.cliente.get(), [h["icone"] for h in self.lista])
        except Exception:
            catalogo = sorted({h["icone"] for h in self.lista if h["icone"]})
        self.raiz.after(0, self._guardar_catalogo, catalogo)

    def _guardar_catalogo(self, catalogo):
        self.catalogo_de_icones = catalogo
        self.log(t("%d ícones disponíveis no cliente.") % len(catalogo))

    # ---- a lista ---------------------------------------------------------
    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        self.tabela.delete(*self.tabela.get_children())
        self.mostrados = [h for h in self.lista
                          if not procurado
                          or procurado in h["nome"].lower()
                          or procurado in h["id"]
                          or procurado in h["icone"].lower()]
        for i, h in enumerate(self.mostrados):
            self.tabela.insert("", "end", iid=str(i),
                               values=(h["id"], h["nome"], h["tipo"],
                                       h["niveis"], h["icone"]))
        self.conta.config(text=t("%d de %d") % (len(self.mostrados),
                                                len(self.lista)))

    def ao_escolher(self, _evento=None):
        """
        Marcar na lista: editando, e a habilidade; criando, e a copiada.

        Nos dois casos os campos do cliente sao preenchidos com os dela, que e
        o que o usuario ve no jogo. O que muda e o significado, e o significado
        esta escrito no alto do painel.
        """
        escolhido = self.tabela.selection()
        if not escolhido:
            return
        h = self.mostrados[int(escolhido[0])]
        self.base = h
        self.rotulo_base.config(
            text=t("Da lista: %s, id %s, %d níveis")
            % (h["nome"] or t("sem nome"), h["id"], h["niveis"]))
        if self.modo == "editar":
            self.novo_id.set(h["id"])
            self.novo_nome.set(h["nome"])
            self.novo_icone.set(h["icone"])
        self.mostrar_icone(self.novo_icone.get() or h["icone"])
        self.dizer_o_alvo(h["id"])

        try:
            prontos = l2skill.campos_do_servidor(self.skills, h["linha"])
        except Exception:
            prontos = {}
        for chave, variavel in self.campos.items():
            variavel.set(prontos.get(chave, ""))
        self._atualizar_modo()
        self.atualizar_botoes()

    def ao_dar_duplo_clique(self, _evento=None):
        """Duplo clique na lista: editar aquela habilidade, sem meio-termo."""
        if self.base is None:
            return
        self.modo = "editar"
        self.estados = []
        self._refazer_estados()
        self.ao_escolher()
        self.log(t("Editando a habilidade %s.") % self.base["id"])

    def _atualizar_modo(self):
        """
        Escreve o modo e ajusta o que pode ser mexido.

        Era a informacao que faltava: com "Habilidade nova" escrito no painel e
        os dados da habilidade marcada dentro dele, nao havia como saber o que
        o botao Gerar ia fazer.
        """
        rotulo = getattr(self, "rotulo_modo", None)
        if rotulo is None:
            return
        if self.base is None:
            rotulo.config(text=t("Escolha uma habilidade na lista."))
        elif self.modo == "editar":
            rotulo.config(text=t("Editando a habilidade %s — %s")
                          % (self.base["id"],
                             self.base["nome"] or t("sem nome")))
        else:
            rotulo.config(text=t("Nova habilidade %s, copiada da %s")
                          % (self.novo_id.get() or "?", self.base["id"]))

        editando = self.modo == "editar"
        self.entrada_id.config(state="readonly" if editando else "normal")
        self.botao_sugerir.config(state="disabled" if editando else "normal")
        self.botao_gerar.config(
            text=t("Regravar a habilidade") if editando else t("Gerar"))

    def nova_habilidade(self):
        """Abre a janela que pergunta o que e preciso para copiar."""
        if self.skills is None:
            messagebox.showinfo(t("Abra as tabelas primeiro"),
                                t("Abra as tabelas do cliente para começar."))
            return
        if self.base is None:
            messagebox.showinfo(t("Escolha a base"),
                                t("Marque na lista a habilidade a copiar."))
            return
        NovaHabilidade(self)

    def comecar_a_nova(self, dados):
        """Chamado pela janela quando o usuário confirma."""
        self.modo = "nova"
        self.icone_pendente = dados.get("pendente")
        self.novo_id.set(dados["id"])
        self.novo_nome.set(dados["nome"])
        self.nova_descricao.set(dados["descricao"])
        self.novo_icone.set(dados["icone"])
        self.ate_o_nivel.set(dados["ate_o_nivel"])
        self.substituir.set(dados["substituir"])
        self.mostrar_icone(dados["icone"])
        self._atualizar_modo()
        self.atualizar_botoes()
        self.log(t("Nova habilidade %s, copiada da %s.")
                 % (dados["id"], self.base["id"]))

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
        if self.skills is not None:
            self.novo_id.set(str(self.skills.proximo_id_livre()))

    def voltar_a_editar(self, ident):
        """
        Depois de gerar, a tela passa a EDITAR o que acabou de sair.

        E o que a pessoa faz em seguida: gerou, quer ver como ficou e ajustar.
        Antes a tela se limpava e sugeria o proximo id, o que empurrava para
        criar outra -- e deixava a recem-criada sem jeito obvio de reabrir.
        """
        self.modo = "editar"
        for i, h in enumerate(self.mostrados):
            if h["id"] == str(ident):
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
        if self.skills is None:
            return
        catalogo = self.catalogo_de_icones or sorted(
            {h["icone"] for h in self.lista if h["icone"]})
        escolhido = gui_icone.EscolherIcone(self.raiz, self, catalogo,
                                            self.novo_icone.get()).resposta
        if escolhido:
            self.novo_icone.set(escolhido)
            self.mostrar_icone(escolhido)


    # ---- trazer do servidor ----------------------------------------------
    def ler_do_servidor(self):
        """
        Traz do servidor a habilidade MARCADA NA LISTA.

        Poder, recarga e tipo de efeito NAO EXISTEM no cliente: so o servidor
        os tem. E assim que se copiam os numeros de uma habilidade que ja
        funciona.

        Le o id da lista, e nao o do campo "id novo": o campo diz para onde a
        habilidade vai, a lista diz de onde ela vem. Uma habilidade
        recem-criada esta na lista depois de gerar, entao releio dela e so
        marca-la.

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
                                t("Escolha uma habilidade na lista."))
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
            achado = l2servidor.achar_skill(pasta, alvo, perfil)
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
        self.estados = [dict(e) for e in (achado.get("estados") or [])]
        self._refazer_estados()

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

        entrada = {"operacao": self.operacao.get(), "estado": nome,
                   "valor": valor}
        if self.estado_em_edicao is not None:
            self.estados[self.estado_em_edicao] = entrada
            self.parar_de_editar_estado()
        else:
            self.estados.append(entrada)
            self.valor.set("")
        self._refazer_estados()

    def tirar_estado(self):
        for indice in sorted((int(i) for i in self.tabela_estados.selection()),
                             reverse=True):
            del self.estados[indice]
        self.parar_de_editar_estado()
        self._refazer_estados()

    def _refazer_estados(self):
        """
        Redesenha a tabela a partir da lista.

        A mesma dezena de linhas estava copiada em tres lugares, e a terceira
        copia ja tinha divergido das outras duas.
        """
        self.tabela_estados.delete(*self.tabela_estados.get_children())
        for i, entrada in enumerate(self.estados):
            self.tabela_estados.insert(
                "", "end", iid=str(i),
                values=(entrada["operacao"],
                        "%s (%s)" % (t(l2item.ESTADOS_POR_NOME.get(
                            entrada["estado"], entrada["estado"])),
                            entrada["estado"]),
                        entrada["valor"]))

    def editar_estado(self, _evento=None):
        """
        Duplo clique numa linha: os tres campos voltam para cima.

        Ajustar um valor exigia tirar a linha e escrever tudo de novo, e quem
        so queria trocar 1.30 por 1.25 refazia a operacao e o status junto --
        com chance de errar o que estava certo.
        """
        marcadas = self.tabela_estados.selection()
        if not marcadas:
            return
        indice = int(marcadas[0])
        if indice >= len(self.estados):
            return
        entrada = self.estados[indice]
        self.estado_em_edicao = indice
        self.operacao.set(entrada["operacao"])
        # A caixa e readonly: tem de receber um rotulo que esteja na lista
        # dela, e nao um montado a parte. O nome entre parenteses e a chave.
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

    # ---- o XML -----------------------------------------------------------
    def _quantos_niveis(self):
        if self.base is None:
            return 1
        corte = self.ate_o_nivel.get().strip()
        if corte.isdigit():
            return max(1, min(int(corte), self.base["niveis"]))
        return self.base["niveis"]

    def _xml_atual(self, avisos=None):
        try:
            ident = int(self.novo_id.get().strip())
        except ValueError:
            return None
        campos = dict((chave, var.get()) for chave, var in self.campos.items())
        return l2skill.xml_servidor(ident, self.novo_nome.get().strip(),
                                    self.base["id"], self._quantos_niveis(),
                                    campos=campos, estados=self.estados,
                                    avisos=avisos)

    def conferir_os_niveis(self):
        """
        Devolve os avisos de tabela com contagem errada.

        Uma tabela com menos numeros do que a habilidade tem niveis nao da
        erro nenhum na hora de gravar: o servidor e que derruba a habilidade,
        ou entrega o nivel errado, muito depois. Conferir aqui e o unico
        momento em que ainda da para consertar sabendo por que.
        """
        avisos = []
        self._xml_atual(avisos)
        return avisos

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
            initialfile="%s-skill.xml" % self.novo_id.get().strip(),
            filetypes=[("XML", "*.xml"), (t("Todos"), "*.*")])
        if not destino:
            return
        try:
            Path(destino).write_text(texto, encoding="utf-8", newline="")
        except OSError as erro:
            messagebox.showerror(t("Não deu para salvar"), str(erro))
            return
        self.log(t("XML salvo em %s") % destino)

    # ---- gerar -----------------------------------------------------------
    def gerar(self):
        if self.rodando or self.skills is None or self.base is None:
            return
        # Editando, o id e o da habilidade marcada e a gravacao passa por cima
        # dela. Ler o id do campo abriria a porta para "editar" a 1086 e
        # escrever na 90000 sem que nada dissesse isso.
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
        if self.modo == "editar" and not messagebox.askyesno(
                t("Regravar a habilidade %s") % novo_id,
                t("A habilidade %s vai ser regravada com o que está na tela.\n\n"
                  "As tabelas saem numa pasta à parte; o cliente só muda em "
                  "Instalar no cliente.\n\nRegravar?") % novo_id):
            return

        tortas = self.conferir_os_niveis()
        if tortas and not messagebox.askyesno(
                t("Valores por nível não batem"),
                t("%s.\n\nA tabela precisa ter um valor por nível, na ordem. "
                  "Com a conta errada o servidor derruba a habilidade ou "
                  "entrega o nível errado, e nada avisa.\n\nGerar assim mesmo?")
                % ";\n".join(t(x) for x in tortas)):
            return

        niveis = self._quantos_niveis()
        if niveis > l2skill.NIVEIS_DE_AVISO and not messagebox.askyesno(
                t("São muitos níveis"),
                t("Esta habilidade tem %d níveis, e a cópia leva todos. As "
                  "habilidades com milhares de níveis são as rotas de "
                  "encantamento.\n\nUse \"copiar até o nível\" para cortar.\n\n"
                  "Copiar os %d mesmo assim?") % (niveis, niveis)):
            return

        self.rodando = True
        self.atualizar_botoes()
        threading.Thread(target=self._gerar_thread, args=(novo_id,),
                         daemon=True).start()

    def _gerar_thread(self, novo_id):
        def anotar(texto):
            self.raiz.after(0, self.log, "  " + texto)

        corte = self.ate_o_nivel.get().strip()
        try:
            self.skills.clonar(self.base["id"], novo_id,
                               nome=self.novo_nome.get().strip(),
                               descricao=self.nova_descricao.get().strip(),
                               icone=self.novo_icone.get().strip(),
                               ate_o_nivel=int(corte) if corte.isdigit() else None,
                               substituir=self.substituir.get())
            try:
                gravados = self.skills.gravar(self.saida(), aolog=anotar)
            except Exception:
                self.skills.remover(novo_id)
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
        self.lista = self.skills.listar()
        self.preencher()
        self.log(t("Habilidade %d gerada em %s") % (novo_id, self.saida()))
        messagebox.showinfo(
            t("Habilidade gerada"),
            t("A habilidade %d foi gerada em:\n\n%s\n\nO XML do servidor saiu "
              "junto, em %s.\n\nNada foi alterado no cliente ainda.")
            % (novo_id, self.saida(), xml.name if xml else "—"))
        self.voltar_a_editar(novo_id)
        self.atualizar_botoes()

    def _salvar_xml_junto(self, novo_id):
        texto = self._xml_atual()
        if texto is None:
            return None
        destino = self.saida() / ("%d-skill.xml" % novo_id)
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
                % (len(self.gravados), system, l2skill.PASTA_GUARDA)):
            return
        try:
            postos = l2skill.instalar(self.gravados, system,
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

        Ele foi montado na hora de criar a habilidade e deixado de lado: o
        cliente so muda aqui, num lugar so, com as tabelas. Depois de posto, a
        marca sai -- instalar duas vezes copiaria o mesmo arquivo por cima de
        si mesmo sem motivo.
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
                  "desfazendo as habilidades criadas. Continuar?")
                % l2skill.PASTA_GUARDA):
            return
        voltaram = l2skill.restaurar(system,
                                     aolog=lambda s: self.log("  " + s))
        messagebox.showinfo(t("Pronto"),
                            t("%d tabelas restauradas.") % len(voltaram))

    # ---- o manual --------------------------------------------------------
    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "skills",
                        t("Manual — criar uma habilidade")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))


class NovaHabilidade(tk.Toplevel):
    """
    A janela que pergunta o que e preciso para copiar uma habilidade.

    Existe para separar dois assuntos que moravam no mesmo formulario: mexer
    numa habilidade que ja existe e fazer outra a partir dela. Enquanto os dois
    dividiam os mesmos campos, o id sugerido para a nova ficava a vista de quem
    so queria olhar a antiga -- e foi assim que a tela trouxe a 90000 quando se
    pediu a 1.

    O icone se escolhe VENDO, na grade a direita, ou se envia como imagem
    propria. O que sai daqui vai para o painel de tras, que passa ao modo
    "nova"; os campos continuam editaveis la, porque isto e um comeco guiado e
    nao uma cerca.
    """

    def __init__(self, dono):
        tk.Toplevel.__init__(self, dono.raiz)
        self.dono = dono
        self.title(t("Nova habilidade"))
        self.transient(dono.raiz)
        # Sem isto o Tk poe o icone dele -- a pena -- e a janela parece de
        # outro programa.
        ajuda.por_icone(self)

        base = dono.base
        # Dentro de uma area rolavel: o conteudo desta janela e mais alto do
        # que um monitor de notebook, e sem rolagem a metade de baixo -- onde
        # ficam os botoes -- sai por fora da area de trabalho.
        area = rolagem.Area(self)
        area.pack(fill="both", expand=True)
        quadro = ttk.Frame(area.dentro, padding=12)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, font=("Segoe UI", 10, "bold"),
                  text=t("Copiando a habilidade %s — %s")
                  % (base["id"], base["nome"] or t("sem nome"))).pack(
            anchor="w")
        # "os 1 níveis" era o que aparecia numa habilidade de nível único.
        niveis = int(base["niveis"] or 1)
        ttk.Label(quadro, foreground=COR_TEXTO_FRACO, wraplength=760,
                  justify="left",
                  text=(t("A cópia leva o nível único, no skillgrp e no "
                          "skillname. Modo, animação e tempo de uso vêm da "
                          "base.") if niveis == 1
                        else t("A cópia leva os %d níveis, no skillgrp e no "
                               "skillname. Modo, animação e tempo de uso vêm "
                               "da base.") % niveis)).pack(anchor="w",
                                                           pady=(2, 10))

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True)

        campos = ttk.Frame(corpo)
        campos.pack(side="left", fill="y")
        campos.columnconfigure(1, weight=1)

        ttk.Label(campos, text=t("id:")).grid(row=0, column=0, sticky="w")
        self.ident = tk.StringVar(
            value=str(dono.skills.proximo_id_livre()) if dono.skills else "")
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

        ttk.Label(campos, text=t("descrição:")).grid(row=2, column=0,
                                                     sticky="w", pady=(6, 0))
        self.descricao = tk.StringVar()
        ttk.Entry(campos, textvariable=self.descricao).grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))
        # Em branco de proposito: a descricao do jogo muda de nivel para
        # nivel -- e o "Power 25" que vira "Power 27" --, e deixando vazio
        # cada nivel herda a do mesmo nivel da base. Escrevendo uma, ela vale
        # igual em todos, o que quase nunca e o que se quer.
        ttk.Label(campos, foreground=COR_TEXTO_FRACO, wraplength=300,
                  justify="left",
                  text=t("Em branco, cada nível herda a descrição do mesmo "
                         "nível da base — que costuma ser o certo, porque ela "
                         "muda de nível para nível.")).grid(
            row=3, column=1, columnspan=2, sticky="w", padx=(6, 0),
            pady=(2, 0))

        ttk.Label(campos, text=t("copiar até o nível:")).grid(
            row=4, column=0, sticky="w", pady=(6, 0))
        self.ate = tk.StringVar()
        ttk.Entry(campos, textvariable=self.ate, width=12).grid(
            row=4, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        self.substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(campos, variable=self.substituir,
                        text=t("substituir se o id já existir")).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

        canto = ttk.Frame(campos)
        canto.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ajuda.ajuda(canto, lambda: t(
            "O id a partir de 90000 fica longe da faixa do jogo e das rotas "
            "de encantamento, que ocupam os 50000.\n\n"
            "Copiar até o nível corta a cópia: em branco, leva todos os "
            "níveis da habilidade base."))

        direita = ttk.LabelFrame(corpo, text=t("Ícone"), padding=6)
        direita.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.icone = gui_icone.PainelDeIcone(
            direita, dono, dono.catalogo_de_icones or sorted(
                {h["icone"] for h in dono.lista if h["icone"]}),
            atual=base["icone"])
        self.icone.pack(fill="both", expand=True)

        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(14, 0))
        ttk.Button(rodape, text=t("Cancelar"),
                   command=self.destroy).pack(side="right")
        ttk.Button(rodape, text=t("Criar"), command=self.criar).pack(
            side="right", padx=(0, 6))

        self.bind("<Escape>", lambda _e: self.destroy())
        ajuda.ajustar_a_tela(self, 980, 620)
        ajuda.centralizar(self)
        self.grab_set()
        self.focus_set()

    def sugerir(self):
        if self.dono.skills is not None:
            self.ident.set(str(self.dono.skills.proximo_id_livre()))

    def criar(self):
        texto = self.ident.get().strip()
        if not texto.isdigit() or int(texto) <= 0:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número maior que "
                                   "zero."), parent=self)
            return
        ident = int(texto)
        if (not self.substituir.get()
                and self.dono.skills is not None
                and self.dono.skills.existe(ident)):
            messagebox.showerror(
                t("Esse id já existe"),
                t("A habilidade %d já está no cliente.\n\nEscolha outro id, "
                  "ou marque \"substituir se o id já existir\".") % ident,
                parent=self)
            return
        if ident < l2skill.PRIMEIRO_ID_LIVRE and not messagebox.askyesno(
                t("Id baixo"),
                t("O %d está na faixa do jogo. Os ids a partir de %d ficam "
                  "longe dela e das rotas de encantamento.\n\nUsar o %d "
                  "assim mesmo?") % (ident, l2skill.PRIMEIRO_ID_LIVRE, ident),
                parent=self):
            return
        if not self.icone.referencia and not messagebox.askyesno(
                t("Sem ícone"),
                t("Nenhum ícone escolhido: a habilidade fica com o quadrado "
                  "vazio no lugar dele.\n\nContinuar assim?"), parent=self):
            return

        self.dono.comecar_a_nova({"id": str(ident),
                                  "nome": self.nome.get().strip(),
                                  "descricao": self.descricao.get().strip(),
                                  "icone": self.icone.referencia,
                                  "ate_o_nivel": self.ate.get().strip(),
                                  "substituir": self.substituir.get(),
                                  "pendente": self.icone.pendente})
        self.destroy()
