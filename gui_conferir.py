#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aba "Conferir Cliente" -- o que as tabelas pedem contra o que esta instalado.

A tela responde tres perguntas, nesta ordem, porque e nesta ordem que elas
aparecem para quem monta um cliente:

    o que falta?            a conferencia, que so le
    onde eu acho isso?      a procura numa pasta com outros clientes
    instala pra mim.        a copia para dentro do cliente

O meio do caminho -- por que um item aparece sem modelo, qual arquivo o
cliente estava procurando -- e justamente o que nao da para ver jogando. O
cliente nao avisa que faltou textura: ele desenha o boneco branco e segue.
"""

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote_plus

import ajuda
import l2conferir
import motor
import tema
import gui_projeto
from idioma import t, N_

# A paleta dos cartoes de resumo. Numero grande em cima, palavra embaixo: o
# resumo tem de ser lido de longe, antes de qualquer lista.
CARTOES = (
    ("instalados", N_("pacotes instalados"), tema.PAINEL, tema.TEXTO),
    ("referencias", N_("referências nas tabelas"), tema.PAINEL, tema.TEXTO),
    ("resolvidas", N_("encontradas no cliente"), tema.FUNDO_BOM, tema.BOM),
    ("faltando", N_("pacotes que faltam"), tema.FUNDO_RUIM, tema.ATENCAO),
    ("incompletos", N_("pacotes incompletos"), tema.FUNDO_ATENCAO, tema.ATENCAO),
)

COR_TEXTO_FRACO = tema.TEXTO_FRACO


class JanelaConferir:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.resultado = None
        self.lista_de_problemas = []
        self.achados = {}
        self.candidatos = []

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Confere o que as tabelas do cliente pedem contra os "
                         "pacotes instalados e aponta o que falta. Só lê: "
                         "nada é alterado até você mandar instalar.")
                  ).pack(anchor="w")

        self._montar_cliente(quadro)
        self._montar_resumo(quadro)

        painel = ttk.Panedwindow(quadro, orient="vertical")
        painel.pack(fill="both", expand=True, pady=(8, 0))
        painel.add(self._montar_problemas(painel), weight=3)
        painel.add(self._montar_procura(painel), weight=2)
        painel.add(self._montar_servidor(painel), weight=2)

        self._montar_rodape(quadro)
        self.atualizar_botoes()

    # ---- montagem --------------------------------------------------------
    def _montar_cliente(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))

        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))

        self.botao_conferir = ttk.Button(linha, text=t("Conferir"),
                                         style="Primario.TButton",
                                         command=self.conferir)
        self.botao_conferir.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "A conferência lê as tabelas do cliente (npcgrp, weapongrp, "
            "armorgrp, etcitemgrp, skillgrp), junta todos os caminhos de "
            "modelo, textura, ícone e som que elas citam, e procura cada um "
            "nas pastas do cliente.\n\n"
            "Pacotes com Blowfish -- a maioria dos .usx e .ukx -- só abrem "
            "por inteiro. Desses a conferência confirma que o arquivo existe "
            "e diz no relatório que o conteúdo não foi aberto."),
            padx=(8, 0))

    def _montar_resumo(self, pai):
        faixa = ttk.Frame(pai)
        faixa.pack(fill="x", pady=(10, 0))

        self.numeros = {}
        for i, (chave, rotulo, fundo, cor) in enumerate(CARTOES):
            cartao = tk.Frame(faixa, bg=fundo, padx=14, pady=10,
                              highlightthickness=1,
                              highlightbackground=tema.BORDA)
            cartao.grid(row=0, column=i, sticky="nsew", padx=(0 if not i else 6, 0))
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

    def _montar_problemas(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("O que falta"), padding=6)

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True)
        colunas = (N_("situação"), N_("pacote"), N_("referências"), N_("tabelas"))
        self.problemas = ttk.Treeview(dentro, columns=colunas, show="headings",
                                      height=8, selectmode="browse")
        for nome, largura, alinhamento in zip(
                colunas, (150, 300, 100, 330), ("w", "w", "e", "w")):
            self.problemas.heading(nome, text=t(nome))
            self.problemas.column(nome, width=largura, anchor=alinhamento)
        self.problemas.tag_configure("pacote", foreground=tema.ATENCAO)
        self.problemas.tag_configure("objeto", foreground=tema.ATENCAO)
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.problemas.yview)
        self.problemas.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.problemas.pack(side="left", fill="both", expand=True)
        self.problemas.bind("<<TreeviewSelect>>", self.mostrar_detalhe)

        self.detalhe = tk.Text(caixa, height=4, wrap="none",
                               foreground=COR_TEXTO_FRACO)
        self.detalhe.pack(fill="x", pady=(6, 0))
        self.detalhe.insert("1.0", t("Selecione uma linha para ver exemplos."))
        self.detalhe.config(state="disabled")

        # Quando o pacote nao esta em nenhum dos clientes que o usuario tem, a
        # unica saida e ir buscar fora -- e o nome do pacote e justamente o que
        # se digita numa busca.
        sob = ttk.Frame(caixa)
        sob.pack(fill="x", pady=(6, 0))
        self.botao_internet = ttk.Button(
            sob, text=t("Procurar na internet"), state="disabled",
            command=self.procurar_na_internet)
        self.botao_internet.pack(side="left")
        ajuda.ajuda(sob, lambda: t(
            "Abre o navegador com o nome do pacote já pesquisado.\n\n"
            "Serve para o pacote que não está em nenhum cliente seu: quase "
            "todo pack de armadura ou de arma que circula tem o nome do "
            "arquivo no anúncio.\n\n"
            "Baixe só de onde você confia, e confira o arquivo antes de "
            "instalar."), padx=(8, 0))
        return caixa

    def _montar_procura(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Procurar em outros clientes"),
                               padding=6)

        linha = ttk.Frame(caixa)
        linha.pack(fill="x")
        ttk.Label(linha, text=t("Pasta:")).pack(side="left")
        self.biblioteca = tk.StringVar(
            value=motor.ler_opcao("conferir", "biblioteca", ""))
        ttk.Entry(linha, textvariable=self.biblioteca).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(linha, text=t("Escolher…"),
                   command=self.escolher_biblioteca).pack(side="left", padx=(6, 0))
        self.botao_procurar = ttk.Button(linha, text=t("Procurar"),
                                         command=self.procurar)
        self.botao_procurar.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Aponte a pasta onde ficam os seus outros clientes. A procura "
            "desce por todas as subpastas atrás dos pacotes que faltam, "
            "porque o mesmo arquivo muda de lugar de um cliente para outro.\n\n"
            "Nada é copiado por conta própria: o que for achado entra na "
            "lista, e a instalação só acontece no botão."),
            padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("pacote"), N_("arquivo"), N_("tamanho"), N_("veio de"),
                   N_("vai para"))
        self.encontrados = ttk.Treeview(dentro, columns=colunas,
                                        show="headings", height=6,
                                        selectmode="extended")
        for nome, largura, alinhamento in zip(
                colunas, (250, 250, 90, 200, 110),
                ("w", "w", "e", "w", "w")):
            self.encontrados.heading(nome, text=t(nome))
            self.encontrados.column(nome, width=largura, anchor=alinhamento)
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.encontrados.yview)
        self.encontrados.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.encontrados.pack(side="left", fill="both", expand=True)

        acao = ttk.Frame(caixa)
        acao.pack(fill="x", pady=(6, 0))
        ttk.Button(acao, text=t("Marcar tudo"),
                   command=self.marcar_tudo).pack(side="left")
        self.botao_instalar = ttk.Button(acao, text=t("Instalar no cliente"),
                                         command=self.instalar)
        self.botao_instalar.pack(side="left", padx=(6, 0))
        self.aviso_procura = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.aviso_procura.pack(side="left", padx=(12, 0))
        return caixa

    def _montar_servidor(self, pai):
        """
        A conferencia do PAR: o que existe num lado e nao no outro.

        E outra pergunta que a de cima. A de cima olha o cliente contra ele
        mesmo -- textura que falta. Esta olha o cliente contra o servidor, e
        pega o erro mais silencioso de servidor privado: item que so um dos
        dois lados conhece.
        """
        caixa = ttk.LabelFrame(pai, text=t("Conferir contra o servidor"),
                               padding=6)

        linha = ttk.Frame(caixa)
        linha.pack(fill="x")
        self.servidor = tk.StringVar(
            value=motor.ler_opcao("conferir", "servidor", ""))
        self.botao_par = ttk.Button(linha, text=t("Conferir o par"),
                                    command=self.conferir_par)
        self.botao_par.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Aponte a pasta de dados do servidor -- a que tem items, npcs e "
            "skills dentro, em XML ou em .sql.\n\n"
            "O programa lê os dois formatos: os cores em XML (aCis, "
            "L2jServer, Mobius) e os de banco (L2jFrozen), que guardam a mesma "
            "coisa em tabelas.\n\n"
            "Só lê. É a conferência que pega item que existe num lado e não no "
            "outro -- nenhum dos dois casos dá erro em jogo."), padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("situação"), N_("o quê"), N_("id"), N_("nome"))
        self.par = ttk.Treeview(dentro, columns=colunas, show="headings",
                                height=8, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (190, 110, 80, 320),
                                              ("w", "w", "e", "w")):
            self.par.heading(nome, text=t(nome))
            self.par.column(nome, width=largura, anchor=alinhamento)
        self.par.tag_configure("cliente", foreground=tema.ATENCAO)
        self.par.tag_configure("servidor", foreground=tema.ATENCAO)
        self.par.tag_configure("nivel", foreground=tema.TEXTO)
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.par.yview)
        self.par.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.par.pack(side="left", fill="both", expand=True)

        # O quadro fica escondido ate haver o que mostrar: uma grade vazia
        # com quatro cabecalhos so ocupa espaco e sugere que faltou alguma
        # coisa.
        self.quadro_par = ttk.Frame(caixa)
        self.celulas_par = {}
        titulos = ("", t("itens"), t("habilidades"), t("NPCs"))
        linhas = (("cliente", t("no cliente")),
                  ("servidor", t("no servidor")),
                  ("so_cliente", t("só no cliente")),
                  ("so_servidor", t("só no servidor")))
        for coluna, titulo in enumerate(titulos):
            ttk.Label(self.quadro_par, text=titulo,
                      font=("Segoe UI", 9, "bold")).grid(
                row=0, column=coluna, sticky="e" if coluna else "w",
                padx=(0 if coluna else 0, 14))
        for i, (chave, rotulo) in enumerate(linhas):
            ttk.Label(self.quadro_par, text=rotulo).grid(
                row=i + 1, column=0, sticky="w", padx=(0, 14))
            for coluna, assunto in enumerate(("itens", "skills", "npcs")):
                celula = ttk.Label(self.quadro_par, text="—")
                celula.grid(row=i + 1, column=coluna + 1, sticky="e",
                            padx=(0, 14))
                self.celulas_par[(chave, assunto)] = celula

        self.frase_par = ttk.Label(caixa, text="", foreground=COR_TEXTO_FRACO,
                                   wraplength=700, justify="left")

        baixo = ttk.Frame(caixa)
        baixo.pack(fill="x", pady=(6, 0))
        self.resumo_par = ttk.Label(baixo, text="", foreground=COR_TEXTO_FRACO)
        self.resumo_par.pack(side="left")
        self.botao_relatorio_par = ttk.Button(
            baixo, text=t("Salvar este relatório…"), state="disabled",
            command=self.salvar_relatorio_par)
        self.botao_relatorio_par.pack(side="right")
        return caixa

    def _montar_rodape(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(8, 0))
        self.botao_relatorio = ttk.Button(linha, text=t("Salvar relatório…"),
                                          command=self.salvar_relatorio)
        self.botao_relatorio.pack(side="left")

        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=5, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

    # ---- ajudantes -------------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def trabalho(self):
        return Path(motor.BASE) / "trabalho" / "conferir"

    def atualizar_botoes(self):
        parado = not self.rodando
        tem_cliente = Path(self.cliente.get().strip() or ".").is_dir()
        self.botao_conferir.config(
            state="normal" if parado and tem_cliente else "disabled")
        self.botao_procurar.config(
            state="normal" if parado and self.resultado
            and self.resultado["pacotes_ausentes"] else "disabled")
        self.botao_instalar.config(
            state="normal" if parado and self.candidatos else "disabled")
        self.botao_relatorio.config(
            state="normal" if parado and self.resultado else "disabled")
        self.botao_par.config(
            state="normal" if parado and Path(
                self.servidor.get().strip() or ".").is_dir() else "disabled")

    def progresso(self, fracao, texto):
        """Chamado de dentro da thread; so agenda o desenho."""
        self.raiz.after(0, self._desenhar_progresso, fracao, texto)

    def _desenhar_progresso(self, fracao, texto):
        if fracao is not None:
            self.andamento.config(value=int(max(0.0, min(1.0, fracao)) * 1000))
        self.estado.config(text=texto)

    @staticmethod
    def _tamanho(bytes_):
        for unidade, divisor in (("GB", 1073741824.0), ("MB", 1048576.0),
                                 ("KB", 1024.0)):
            if bytes_ >= divisor:
                return "%.1f %s" % (bytes_ / divisor, unidade)
        return "%d B" % bytes_

    # ---- escolhas --------------------------------------------------------
    def escolher_biblioteca(self):
        pasta = filedialog.askdirectory(
            title=t("Escolha a pasta onde ficam os outros clientes"))
        if pasta:
            self.biblioteca.set(pasta)
            motor.gravar_opcao("conferir", "biblioteca", pasta)

    # ---- a conferencia ---------------------------------------------------
    def conferir(self):
        if self.rodando:
            return
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas()
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        raiz = Path(self.cliente.get().strip())

        l2encdec = Path(self.T.get("l2encdec", ""))
        if not l2encdec.exists():
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.")
                                 % ("l2encdec", motor.CONFIG))
            return

        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== conferindo %s ===") % raiz)
        threading.Thread(target=self._conferir_thread, args=(raiz,),
                         daemon=True).start()

    def _conferir_thread(self, raiz):
        try:
            resultado = l2conferir.conferir(raiz, self.T, self.trabalho(),
                                            aoprogresso=self.progresso)
            erro = None
        except Exception as e:                      # noqa: BLE001
            resultado, erro = None, e
        self.raiz.after(0, self._fim_conferencia, resultado, erro)

    def _fim_conferencia(self, resultado, erro):
        self.rodando = False
        self._desenhar_progresso(0 if erro else 1.0, "")
        if erro is not None:
            self.log(t("A conferência parou: %s") % erro)
            messagebox.showerror(t("A conferência parou"), str(erro))
            self.atualizar_botoes()
            return

        self.resultado = resultado
        self.candidatos = []
        self.encontrados.delete(*self.encontrados.get_children())
        self.aviso_procura.config(text="")

        faltando = sum(len(e["referencias"])
                       for e in resultado["pacotes_ausentes"].values())
        self.numeros["instalados"].config(text="%d" % resultado["pacotes_instalados"])
        self.numeros["referencias"].config(text="%d" % resultado["total"])
        self.numeros["resolvidas"].config(text="%d" % resultado["resolvidas"])
        self.numeros["faltando"].config(text="%d" % len(resultado["pacotes_ausentes"]))
        self.numeros["incompletos"].config(text="%d" % len(resultado["objetos_ausentes"]))

        for tabela in resultado["tabelas"]:
            if tabela["erro"]:
                self.log(t("  %s não abriu: %s") % (tabela["nome"], tabela["erro"]))
            else:
                self.log(t("  %s: %d referências")
                         % (tabela["nome"], tabela["referencias"]))

        self.preencher_problemas()
        self.log(t("Conferido em %.1f s. %d referências, %d resolvidas, "
                   "%d sem o pacote, %d sem o objeto.")
                 % (resultado["segundos"], resultado["total"],
                    resultado["resolvidas"], faltando,
                    sum(len(e["referencias"])
                        for e in resultado["objetos_ausentes"].values())))
        if resultado["nao_conferidos"]:
            self.log(t("%d pacotes ficaram sem conferir por dentro "
                       "(Blowfish); a existência do arquivo foi confirmada.")
                     % len(resultado["nao_conferidos"]))
        self._desenhar_progresso(1.0, t("conferência terminada"))
        self.atualizar_botoes()

    def preencher_problemas(self):
        self.problemas.delete(*self.problemas.get_children())
        self.botao_internet.config(state="disabled")
        self.lista_de_problemas = l2conferir.problemas(self.resultado)
        for i, item in enumerate(self.lista_de_problemas):
            situacao = (t("falta o pacote") if item["gravidade"] == "pacote"
                        else t("falta dentro do pacote"))
            self.problemas.insert(
                "", "end", iid=str(i), tags=(item["gravidade"],),
                values=(situacao, item["pacote"], item["quantos"],
                        ", ".join(item["origens"])))
        if not self.lista_de_problemas:
            self._escrever_detalhe(
                t("Nenhuma referência sem destino. Todo modelo, textura e "
                  "ícone que as tabelas citam está instalado."))

    def mostrar_detalhe(self, _evento=None):
        escolhido = self.problemas.selection()
        if not escolhido:
            return
        item = self.lista_de_problemas[int(escolhido[0])]
        # Só faz sentido buscar fora o que não está em pasta nenhuma. Pacote
        # presente com objeto faltando é outro problema, e baixar outra cópia
        # não resolve.
        self.botao_internet.config(
            state="normal" if item["gravidade"] == "pacote" else "disabled")
        linhas = []
        if item["gravidade"] == "pacote":
            linhas.append(t("O cliente procura o pacote %s e ele não está em "
                            "pasta nenhuma.") % item["pacote"])
        else:
            linhas.append(t("O pacote está em %s, mas não tem dentro o que a "
                            "tabela pede.") % item["caminho"])
        linhas.append(t("%d referências. Exemplos:") % item["quantos"])
        linhas += ["    " + exemplo for exemplo in item["exemplos"]]
        self._escrever_detalhe("\n".join(linhas))

    # ---- o par cliente/servidor ------------------------------------------
    def conferir_par(self):
        if self.rodando:
            return
        raiz = Path(self.cliente.get().strip())
        pasta = Path(self.servidor.get().strip() or ".")
        if not (raiz / "system").is_dir():
            messagebox.showerror(t("Cliente inválido"),
                                 t("Não achei a pasta system dentro de:\n\n%s")
                                 % raiz)
            return
        if not pasta.is_dir():
            messagebox.showerror(t("Pasta inválida"),
                                 t("Não achei a pasta:\n\n%s") % pasta)
            return

        motor.gravar_opcao("conferir", "servidor", str(pasta))
        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== conferindo o cliente contra %s ===") % pasta)
        threading.Thread(target=self._par_thread, args=(raiz, pasta),
                         daemon=True).start()

    def _par_thread(self, raiz, pasta):
        import l2item
        import l2npc
        import l2servidor
        import l2skill

        try:
            trabalho = self.trabalho()
            self.progresso(0.03, t("vendo como este servidor é arrumado"))
            # Farejar primeiro diz em que pastas as coisas moram. Sem isso, a
            # varredura contava como item do jogo o <item id="1"> de
            # recipes.xml, que ali e ingrediente de receita.
            detectado = l2servidor.farejar(pasta)
            self.progresso(0.05, t("lendo o servidor"))
            servidor = l2servidor.ler_servidor(
                pasta, aoprogresso=self.progresso,
                pastas=detectado.get("pastas"))
            servidor["detectado"] = detectado.get("achados") or []

            self.progresso(0.5, t("lendo os itens do cliente"))
            itens = l2item.Itens(self.T, raiz / "system", trabalho)
            do_cliente_itens = dict((i["id"], i["nome"]) for i in itens.listar())

            self.progresso(0.7, t("lendo as habilidades do cliente"))
            skills = l2skill.Skills(self.T, raiz / "system", trabalho)
            do_cliente_skills = dict((h["id"], h["niveis"])
                                     for h in skills.listar())
            nomes_skills = dict((h["id"], h["nome"]) for h in skills.listar())

            self.progresso(0.9, t("lendo os NPCs do cliente"))
            grupo = l2npc.Npcgrp(raiz / "system", self.T, trabalho)
            nomes = l2npc.Npcname(raiz / "system", self.T, trabalho).nomes()
            do_cliente_npcs = dict((l[0], nomes.get(l[0], ""))
                                   for l in grupo.linhas)

            resultado = l2servidor.conferir(do_cliente_itens, do_cliente_skills,
                                            do_cliente_npcs, servidor)
            resultado["nomes_do_cliente"] = {"itens": do_cliente_itens,
                                             "skills": nomes_skills,
                                             "npcs": do_cliente_npcs}
            erro = None
        except Exception as e:                      # noqa: BLE001
            resultado, erro = None, e
        self.raiz.after(0, self._fim_par, resultado, erro)

    def _fim_par(self, resultado, erro):
        self.rodando = False
        self._desenhar_progresso(1.0 if not erro else 0, "")
        if erro is not None:
            self.log(t("A conferência do par parou: %s") % erro)
            messagebox.showerror(t("A conferência parou"), str(erro))
            self.atualizar_botoes()
            return

        self.resultado_par = resultado
        self.par.delete(*self.par.get_children())
        nomes = resultado["nomes_do_cliente"]
        servidor = resultado["servidor"]

        faixas = (
            ("itens_so_no_cliente", t("só no cliente"), t("item"), "cliente",
             nomes["itens"]),
            ("itens_so_no_servidor", t("só no servidor"), t("item"),
             "servidor", servidor["itens"]),
            ("skills_so_no_cliente", t("só no cliente"), t("habilidade"),
             "cliente", nomes["skills"]),
            ("skills_so_no_servidor", t("só no servidor"), t("habilidade"),
             "servidor", {}),
            ("npcs_so_no_cliente", t("só no cliente"), t("NPC"), "cliente",
             nomes["npcs"]),
            ("npcs_so_no_servidor", t("só no servidor"), t("NPC"), "servidor",
             servidor["npcs"]),
        )
        quantos = 0
        for chave, situacao, assunto, marca, catalogo in faixas:
            for ident in resultado[chave]:
                self.par.insert("", "end", tags=(marca,),
                                values=(situacao, assunto, ident,
                                        catalogo.get(ident, "")))
                quantos += 1
        for ident, no_cliente, no_servidor in resultado["niveis_a_mais"]:
            self.par.insert(
                "", "end", tags=("nivel",),
                values=(t("nível a mais no servidor"), t("habilidade"), ident,
                        t("cliente %s, servidor %d") % (no_cliente, no_servidor)))
            quantos += 1

        self._mostrar_quadro(resultado, servidor, quantos)
        self.log(t("%d diferenças entre o cliente e o servidor.") % quantos)
        self.botao_relatorio_par.config(state="normal")
        self._desenhar_progresso(1.0, t("conferência terminada"))
        self.atualizar_botoes()

    def _mostrar_quadro(self, resultado, servidor, quantos):
        """
        O resultado em grade, e uma frase dizendo o que ele significa.

        A linha corrida de antes punha "servidor: 9430, 2703, 6519" -- tres
        numeros sem rotulo, que so se entendiam contando a ordem da metade
        anterior da frase.
        """
        totais = resultado["totais"]
        so_cliente = {"itens": len(resultado["itens_so_no_cliente"]),
                      "skills": len(resultado["skills_so_no_cliente"]),
                      "npcs": len(resultado["npcs_so_no_cliente"])}
        so_servidor = {"itens": len(resultado["itens_so_no_servidor"]),
                       "skills": len(resultado["skills_so_no_servidor"]),
                       "npcs": len(resultado["npcs_so_no_servidor"])}
        por_linha = {"cliente": dict(zip(("itens", "skills", "npcs"),
                                         totais["cliente"])),
                     "servidor": dict(zip(("itens", "skills", "npcs"),
                                          totais["servidor"])),
                     "so_cliente": so_cliente,
                     "so_servidor": so_servidor}
        for (chave, assunto), celula in self.celulas_par.items():
            celula.config(text="{:,}".format(por_linha[chave][assunto])
                          .replace(",", "."))

        self.quadro_par.pack(anchor="w", pady=(8, 0))
        self.frase_par.pack(anchor="w", pady=(6, 0))

        partes = []
        if sum(so_cliente.values()):
            partes.append(t("O cliente mostra %d coisas que o servidor não "
                            "conhece: quem as vir no jogo não consegue usá-las.")
                          % sum(so_cliente.values()))
        if sum(so_servidor.values()):
            partes.append(t("O servidor tem %d que o cliente não sabe "
                            "desenhar: aparecem sem nome e sem ícone.")
                          % sum(so_servidor.values()))
        a_mais = len(resultado["niveis_a_mais"])
        if a_mais:
            partes.append(t("%d habilidades têm mais níveis no servidor do que "
                            "o cliente sabe mostrar.") % a_mais)
        if not partes:
            partes.append(t("Os dois lados batem: nada existe só de um lado."))
        partes.append(t("A lista acima tem as %d linhas, uma por diferença.")
                      % quantos)
        self.frase_par.config(text=" ".join(partes))

        detectado = servidor.get("detectado") or []
        self.resumo_par.config(
            text=(t("servidor em %s — %s") % (servidor["formato"],
                                              "; ".join(detectado)))
            if detectado else t("servidor em %s") % servidor["formato"])

    def salvar_relatorio_par(self):
        import l2servidor

        if not getattr(self, "resultado_par", None):
            return
        destino = filedialog.asksaveasfilename(
            title=t("Salvar o relatório"), defaultextension=".txt",
            initialfile="cliente_e_servidor.txt",
            filetypes=[(t("Texto"), "*.txt"), (t("Todos"), "*.*")])
        if not destino:
            return
        try:
            Path(destino).write_text(
                l2servidor.texto_da_conferencia(
                    self.resultado_par,
                    self.resultado_par["nomes_do_cliente"]),
                encoding="utf-8", newline="")
        except OSError as erro:
            messagebox.showerror(t("Não deu para salvar"), str(erro))
            return
        self.log(t("Relatório salvo em %s") % destino)

    def procurar_na_internet(self):
        """Abre o navegador com o nome do pacote já pesquisado."""
        escolhido = self.problemas.selection()
        if not escolhido:
            return
        item = self.lista_de_problemas[int(escolhido[0])]
        busca = "%s lineage 2 %s" % (item["pacote"], t("download"))
        endereco = "https://www.google.com/search?q=" + quote_plus(busca)
        try:
            webbrowser.open(endereco)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para abrir o navegador"), str(erro))
            return
        self.log(t("Procurando %s na internet.") % item["pacote"])

    def _escrever_detalhe(self, texto):
        self.detalhe.config(state="normal")
        self.detalhe.delete("1.0", "end")
        self.detalhe.insert("1.0", texto)
        self.detalhe.config(state="disabled")

    # ---- a procura -------------------------------------------------------
    def procurar(self):
        if self.rodando or not self.resultado:
            return
        pasta = Path(self.biblioteca.get().strip() or ".")
        if not pasta.is_dir():
            messagebox.showerror(t("Pasta inválida"),
                                 t("Não achei a pasta:\n\n%s") % pasta)
            return

        motor.gravar_opcao("conferir", "biblioteca", str(pasta))
        faltando = sorted(self.resultado["pacotes_ausentes"])
        self.rodando = True
        self.atualizar_botoes()
        self.encontrados.delete(*self.encontrados.get_children())
        self.candidatos = []
        self.log(t("\n=== procurando %d pacotes em %s ===")
                 % (len(faltando), pasta))
        threading.Thread(target=self._procurar_thread, args=(pasta, faltando),
                         daemon=True).start()

    def _procurar_thread(self, pasta, faltando):
        try:
            achados = l2conferir.procurar(pasta, faltando,
                                          aoprogresso=self.progresso)
            erro = None
        except Exception as e:                      # noqa: BLE001
            achados, erro = {}, e
        self.raiz.after(0, self._fim_procura, achados, faltando, erro)

    def _fim_procura(self, achados, faltando, erro):
        self.rodando = False
        self._desenhar_progresso(1.0 if not erro else 0, "")
        if erro is not None:
            self.log(t("A procura parou: %s") % erro)
            messagebox.showerror(t("A procura parou"), str(erro))
            self.atualizar_botoes()
            return

        self.achados = achados
        self.candidatos = []
        raiz = Path(self.cliente.get().strip())
        for chave in sorted(achados):
            for candidato in achados[chave]:
                destino = l2conferir.destino_no_cliente(raiz,
                                                        candidato["caminho"])
                self.candidatos.append(candidato["caminho"])
                self.encontrados.insert(
                    "", "end", iid=str(len(self.candidatos) - 1),
                    values=(self.resultado["pacotes_ausentes"][chave]["nome"],
                            candidato["caminho"].name,
                            self._tamanho(candidato["tamanho"]),
                            candidato["origem"], destino.parent.name))

        sem_achar = len(faltando) - len(achados)
        self.aviso_procura.config(
            text=t("%d de %d pacotes encontrados.") % (len(achados), len(faltando)))
        self.log(t("Procura terminada: %d de %d pacotes encontrados.")
                 % (len(achados), len(faltando)))
        if sem_achar:
            self.log(t("Continuam sem origem: %s")
                     % ", ".join(sorted(set(faltando) - set(achados))[:12]))
        self.marcar_tudo()
        self._desenhar_progresso(1.0, t("procura terminada"))
        self.atualizar_botoes()

    def marcar_tudo(self):
        itens = self.encontrados.get_children()
        if itens:
            self.encontrados.selection_set(itens)

    # ---- a instalacao ----------------------------------------------------
    def instalar(self):
        escolhidos = [self.candidatos[int(i)]
                      for i in self.encontrados.selection()]
        if not escolhidos:
            messagebox.showinfo(t("Nada marcado"),
                                t("Marque na lista o que deve ser instalado."))
            return

        raiz = Path(self.cliente.get().strip())
        # Dois arquivos com o mesmo nome instalariam um por cima do outro sem
        # o usuario escolher qual. Melhor recusar e deixar ele decidir.
        nomes = [c.name.lower() for c in escolhidos]
        repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
        if repetidos:
            messagebox.showerror(
                t("Escolha um de cada"),
                t("Estes pacotes estão marcados mais de uma vez, vindos de "
                  "clientes diferentes:\n\n%s\n\nDeixe marcado só o que você "
                  "quer instalar.") % "\n".join(repetidos))
            return

        total = sum(c.stat().st_size for c in escolhidos if c.is_file())
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("%d pacotes, %s, vão ser copiados para dentro de:\n\n%s\n\n"
                  "Nenhum arquivo existente é sobrescrito. Continuar?")
                % (len(escolhidos), self._tamanho(total), raiz)):
            return

        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== instalando %d pacotes ===") % len(escolhidos))
        threading.Thread(target=self._instalar_thread, args=(raiz, escolhidos),
                         daemon=True).start()

    def _instalar_thread(self, raiz, escolhidos):
        def anotar(texto):
            self.raiz.after(0, self.log, "  " + texto)

        try:
            feitos = l2conferir.instalar(raiz, escolhidos, aolog=anotar)
            erro = None
        except Exception as e:                      # noqa: BLE001
            feitos, erro = [], e
        self.raiz.after(0, self._fim_instalacao, feitos, erro)

    def _fim_instalacao(self, feitos, erro):
        self.rodando = False
        self.atualizar_botoes()
        if erro is not None:
            self.log(t("A instalação parou: %s") % erro)
            messagebox.showerror(t("A instalação parou"), str(erro))
            return

        bons = [f for f in feitos if f["ok"]]
        self.log(t("%d de %d pacotes instalados.") % (len(bons), len(feitos)))
        messagebox.showinfo(
            t("Instalação terminada"),
            t("%d de %d pacotes instalados.\n\nConfira de novo para ver o que "
              "isso resolveu.") % (len(bons), len(feitos)))

    # ---- o relatorio -----------------------------------------------------
    def salvar_relatorio(self):
        if not self.resultado:
            return
        destino = filedialog.asksaveasfilename(
            title=t("Salvar o relatório"), defaultextension=".txt",
            initialfile="conferencia_%s.txt" % self.resultado["raiz"].name,
            filetypes=[(t("Texto"), "*.txt"), (t("Todos"), "*.*")])
        if not destino:
            return
        try:
            Path(destino).write_text(
                l2conferir.texto_do_relatorio(self.resultado),
                encoding="utf-8", newline="")
        except OSError as erro:
            messagebox.showerror(t("Não deu para salvar"), str(erro))
            return
        self.log(t("Relatório salvo em %s") % destino)
