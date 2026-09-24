#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A aba de Multisell: a lista de trocas que um NPC oferece.

O formato e uma tabela de trocas -- paga isto, recebe aquilo --, e editar isso
num XML de dez mil linhas e o que faz a maioria desistir. Aqui ela e montada
como um **checkout**: os itens com icone e nome dos dois lados, a quantidade a
vista, e a conta escrita por extenso.

O que a tela mostra sai de duas fontes, e nenhuma e escrita a mao:

- **O servidor** da as multisells que ja existem e a pasta onde elas moram.
- **O cliente** da o nome, o icone e a descricao de cada item. Um id que o
  cliente nao conhece aparece marcado, porque em jogo ele sairia como uma linha
  sem nome e sem desenho -- e ninguem saberia por que.

## Do lado do cliente nao ha arquivo

Multisell e inteiramente do servidor: o cliente so desenha o que o pacote
manda. Por isso nao ha "instalar no cliente" aqui. O que o cliente precisa e
conhecer os ITENS usados, e para isso existe o botao de conferir -- que cruza a
lista com as tabelas dele antes de instalar.
"""

import bisect
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

import ajuda
import l2conferir
import l2item
import l2multisell
import motor
import gui_mundo
import gui_projeto
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_TEXTO = tema.TEXTO
COR_LINHA = tema.PAINEL
COR_LINHA_ALT = tema.FUNDO
COR_MARCADA = tema.OURO_FUNDO
COR_TEXTO_MARCADO = tema.TEXTO
COR_BORDA = tema.BORDA
COR_CABECALHO = tema.ELEVADO
ALTURA_DA_LINHA = 38
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE
COR_PAGA = tema.ATENCAO
COR_RECEBE = tema.BOM
LADO_DO_ICONE = 32

PAGA, RECEBE = "paga", "recebe"


class JanelaMultisell:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.itens = None
        self.nomes = {}
        self.descricoes = {}
        self.icones = {}
        self.icones_de_item = {}        # {id: referencia do icone no cliente}
        self.perfil_servidor = None
        self.listas = []
        self.mostradas = []
        self.lista = l2multisell.vazia()
        self.troca = {"paga": [], "recebe": []}
        self.em_edicao = None           # indice da troca sendo mexida
        self.marcada_cesta = None       # indice da troca marcada no checkout
        self.abertas_cesta = set()      # indices das trocas com a gaveta aberta
        self._tops = []                 # onde cada troca comeca, em pixels
        self._redesenho_pedido = False

        # Linha alta o bastante para o icone de 32 pixels. Sem isto o Tk corta
        # o desenho pela metade, e parece defeito da imagem.
        try:
            estilo = ttk.Style()
            if estilo.configure("Multisell.Treeview") is None:
                estilo.configure("Multisell.Treeview", rowheight=36)
            estilo.configure("Multisell.Treeview", rowheight=36)
        except tk.TclError:
            pass

        quadro = ttk.Frame(pai, padding=10)
        self.quadro = quadro    # a ancora dos `after` desta aba
        quadro.bind("<Destroy>", self._ao_morrer)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Multisell é a lista de trocas de um NPC: o jogador "
                         "paga uma coisa e recebe outra. Monte a troca dos "
                         "dois lados e ela entra na lista.")).pack(anchor="w")

        self._montar_pastas(quadro)

        painel = ttk.Panedwindow(quadro, orient="horizontal")
        painel.pack(fill="both", expand=True, pady=(8, 0))
        painel.add(self._montar_listas(painel), weight=1)
        painel.add(self._montar_checkout(painel), weight=3)

        self._montar_rodape(quadro)
        self.atualizar_botoes()

    # ---- as pastas -------------------------------------------------------
    def _montar_pastas(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))
        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))
        self.botao_abrir = ttk.Button(linha, text=t("Carregar"),
                                      style="Primario.TButton",
                                      command=self.carregar_tudo)
        self.botao_abrir.pack(side="left")
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Carrega tudo o que esta aba usa: as tabelas do cliente e as "
            "multisells que já existem no servidor.@@"
            "Do cliente vêm o nome, o ícone e a descrição de cada item — é o "
            "que faz a lista parecer o que o jogador vai ver, e é o que "
            "permite a conferência avisar quando um id não existe lá. Do "
            "servidor vem a lista do que já está feito.")
            .replace("@@", chr(10) + chr(10)), padx=(8, 0))

        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(6, 0))
        self.pasta_do_servidor = tk.StringVar(
            value=gui_mundo._servidor_do_projeto())
        self.onde_ficam = ttk.Label(linha, text="",
                                    foreground=COR_TEXTO_FRACO)
        self.onde_ficam.pack(side="left", padx=(10, 0))

    def perfil(self):
        """O perfil deste servidor, se já foi lido. Nunca lê aqui."""
        return self.perfil_servidor or {}

    def pasta_das_multisells(self):
        import l2servidor
        return l2servidor.raiz_de(self.pasta_do_servidor.get().strip(),
                                  self.perfil(), "multisell")

    # ---- a lista de multisells -------------------------------------------
    def _montar_listas(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Multisells do servidor"),
                               padding=6)

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(topo, textvariable=self.filtro)
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self.preencher())
        self.conta = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("nome"), N_("trocas"), N_("NPCs"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=16, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (140, 60, 56),
                                              ("w", "e", "e")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento,
                               stretch=(nome == N_("nome")))
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<Double-1>", lambda _e: self.abrir_marcada())

        baixo = ttk.Frame(caixa)
        baixo.pack(fill="x", pady=(6, 0))
        ttk.Button(baixo, text=t("Abrir"),
                   command=self.abrir_marcada).pack(side="left")
        ttk.Button(baixo, text=t("Nova"),
                   command=self.nova_lista).pack(side="left", padx=(6, 0))
        ttk.Button(baixo, text=t("Excluir"),
                   command=self.excluir_marcada).pack(side="left",
                                                      padx=(16, 0))
        ajuda.ajuda(baixo, lambda: t(
            "O nome do arquivo é o identificador da lista — não há campo de id "
            "dentro da XML. É por ele que o NPC a abre:@@"
            "    multisell <nome>@@"
            "Por isso renomear troca a lista de identidade, e duas com o mesmo "
            "nome são a MESMA lista: a segunda a carregar apaga a primeira.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))
        return caixa

    # ---- o checkout ------------------------------------------------------
    def _montar_checkout(self, pai):
        caixa = ttk.Frame(pai, padding=(8, 0, 0, 0))

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        ttk.Label(topo, text=t("nome do arquivo:")).pack(side="left")
        self.nome = tk.StringVar()
        ttk.Entry(topo, textvariable=self.nome, width=16).pack(side="left",
                                                               padx=(6, 0))
        self.rotulo_bypass = ttk.Label(topo, text="",
                                       foreground=COR_TEXTO_FRACO,
                                       font=("Consolas", 9))
        self.rotulo_bypass.pack(side="left", padx=(10, 0))
        self.nome.trace_add("write", lambda *_a: self._dizer_bypass())

        opcoes = ttk.Frame(caixa)
        opcoes.pack(fill="x", pady=(6, 0))
        self.opcoes = {}
        for chave, rotulo in l2multisell.OPCOES:
            variavel = tk.BooleanVar(value=False)
            self.opcoes[chave] = variavel
            ttk.Checkbutton(opcoes, variable=variavel,
                            text=t(rotulo)).pack(side="left", padx=(0, 16))
        ttk.Label(opcoes, text=t("NPCs:")).pack(side="left")
        self.npcs = tk.StringVar()
        ttk.Entry(opcoes, textvariable=self.npcs, width=26).pack(side="left",
                                                                 padx=(6, 0))
        ajuda.ajuda(opcoes, lambda: t(
            "Os ids dos NPCs que podem abrir esta lista, separados por "
            "espaço ou vírgula.@@"
            "**Deixando em branco, QUALQUER NPC abre.** É assim no core: a "
            "lista só fica restrita quando tem pelo menos um NPC. E, estando "
            "restrita, ela deixa de poder ser aberta sem NPC — de um painel da "
            "comunidade, por exemplo.@@"
            "`cobrar a taxa do castelo` desconta a taxa da região. `manter o "
            "encantamento` faz o item recebido sair com o mesmo +N do item "
            "dado — serve para troca de arma por arma.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))

        # ---- a troca sendo montada ----
        montar = ttk.LabelFrame(caixa, text=t("A troca"), padding=8)
        montar.pack(fill="x", pady=(8, 0))

        lados = ttk.Frame(montar)
        lados.pack(fill="x")
        self.listas_do_lado = {}
        self.descricao_do_lado = {}
        for lado, rotulo, cor in ((PAGA, N_("o jogador PAGA"), COR_PAGA),
                                  (RECEBE, N_("e RECEBE"), COR_RECEBE)):
            self.listas_do_lado[lado] = self._montar_lado(lados, lado,
                                                          t(rotulo), cor)

        acao = ttk.Frame(montar)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_por = ttk.Button(acao, text=t("Pôr na lista"),
                                    command=self.por_na_lista)
        self.botao_por.pack(side="left")
        ttk.Button(acao, text=t("Limpar a troca"),
                   command=self.limpar_troca).pack(side="left", padx=(6, 0))
        self.recado = ttk.Label(acao, text="", foreground=COR_PAGA,
                                wraplength=520, justify="left")
        self.recado.pack(side="left", padx=(12, 0))

        # ---- o checkout propriamente ----
        cesta = ttk.LabelFrame(caixa, text=t("Trocas desta lista"), padding=6)
        cesta.pack(fill="both", expand=True, pady=(8, 0))

        # A fonte da lista e a do sistema: o checkout e desenhado a mao, e
        # medir o texto com a mesma fonte que o desenha e o que permite cortar
        # um nome comprido na letra certa.
        self.fonte_cesta = tkfont.nametofont("TkDefaultFont")
        self.fonte_cabecalho = self.fonte_cesta.copy()
        self.fonte_cabecalho.config(weight="bold")

        dentro = ttk.Frame(cesta)
        dentro.pack(fill="both", expand=True)

        self.cabeca_cesta = tk.Canvas(dentro, height=22, highlightthickness=0,
                                      background=COR_CABECALHO)
        self.cabeca_cesta.pack(fill="x")
        self.cabeca_cesta.bind("<Configure>", self._pintar_cabecalho)

        corpo = ttk.Frame(dentro)
        corpo.pack(fill="both", expand=True)
        self.cesta = tk.Canvas(corpo, background=COR_LINHA,
                               highlightthickness=1,
                               highlightbackground=COR_BORDA,
                               yscrollincrement=ALTURA_DA_LINHA, height=260)
        self.barra_cesta = ttk.Scrollbar(corpo, orient="vertical",
                                         command=self.cesta.yview)
        self.cesta.config(yscrollcommand=self._cesta_rolou)
        self.barra_cesta.pack(side="right", fill="y")
        self.cesta.pack(side="left", fill="both", expand=True)

        self.cesta.bind("<Configure>", lambda _e: self._pintar_cesta())
        self.cesta.bind("<Button-1>", self._clicar_na_cesta)
        self.cesta.bind("<Double-Button-1>", lambda _e: self.editar_troca())
        self.cesta.bind("<Up>", lambda _e: self._andar_na_cesta(-1))
        self.cesta.bind("<Down>", lambda _e: self._andar_na_cesta(1))
        # A roda anda tres linhas, nao uma. O tratador global do `rolagem` so
        # entrega uma por giro, e numa lista de 3.176 trocas isso e uma
        # eternidade; prender aqui e devolver "break" tira o global do caminho.
        self.cesta.bind("<MouseWheel>",
                        lambda e: self._rolar_cesta(-1 if e.delta > 0 else 1))
        self.cesta.bind("<Button-4>", lambda _e: self._rolar_cesta(-1))
        self.cesta.bind("<Button-5>", lambda _e: self._rolar_cesta(1))

        baixo = ttk.Frame(cesta)
        baixo.pack(fill="x", pady=(6, 0))
        ttk.Button(baixo, text=t("Editar"),
                   command=self.editar_troca).pack(side="left")
        ttk.Button(baixo, text=t("Tirar"),
                   command=self.tirar_troca).pack(side="left", padx=(6, 0))
        ttk.Button(baixo, text=t("Subir"),
                   command=lambda: self.mover_troca(-1)).pack(side="left",
                                                              padx=(16, 0))
        ttk.Button(baixo, text=t("Descer"),
                   command=lambda: self.mover_troca(1)).pack(side="left",
                                                             padx=(4, 0))
        self.total = ttk.Label(baixo, text="", foreground=COR_TEXTO_FRACO)
        self.total.pack(side="right")

        acao = ttk.Frame(caixa)
        acao.pack(fill="x", pady=(8, 0))
        ttk.Button(acao, text=t("Conferir"),
                   command=self.conferir).pack(side="left")
        ttk.Button(acao, text=t("Ver a XML"),
                   command=self.ver_xml).pack(side="left", padx=(6, 0))
        self.botao_instalar = ttk.Button(
            acao, text=t("Instalar no servidor"), command=self.instalar)
        self.botao_instalar.pack(side="left", padx=(6, 0))
        self.estado = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))
        return caixa

    def _montar_lado(self, pai, lado, rotulo, cor):
        """Uma das duas metades da troca: a lista e os botões dela."""
        caixa = ttk.Frame(pai)
        caixa.pack(side="left", fill="both", expand=True,
                   padx=(0, 10) if lado == PAGA else (10, 0))
        ttk.Label(caixa, text=rotulo, foreground=cor,
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(4, 0))
        colunas = (N_("id"), N_("qtd"), N_("+"))
        # A coluna da arvore leva o desenho E o nome, na mesma celula: e o
        # unico lugar do Treeview onde imagem e texto ficam lado a lado.
        tabela = ttk.Treeview(dentro, columns=colunas, show="tree headings",
                              height=4, selectmode="browse",
                              style="Multisell.Treeview")
        tabela.heading("#0", text=t("item"))
        tabela.column("#0", width=220, minwidth=150, stretch=True)
        for nome, largura, alinhamento, estica in zip(
                colunas, (52, 72, 30), ("e", "e", "e"),
                (False, False, False)):
            tabela.heading(nome, text=t(nome))
            tabela.column(nome, width=largura, anchor=alinhamento,
                          stretch=estica)
        tabela.pack(fill="both", expand=True)
        tabela.bind("<Double-1>", lambda _e, l=lado: self.mudar_quantidade(l))
        tabela.bind("<<TreeviewSelect>>",
                    lambda _e, l=lado: self._dizer_a_descricao(l))

        # A descricao do item marcado. Ela e longa demais para uma coluna, e
        # curta demais para uma janela: uma linha embaixo resolve.
        descricao = ttk.Label(caixa, text="", foreground=COR_TEXTO_FRACO,
                              wraplength=330, justify="left",
                              font=("Segoe UI", 8))
        descricao.pack(anchor="w", pady=(2, 0))
        self.descricao_do_lado[lado] = descricao

        botoes = ttk.Frame(caixa)
        botoes.pack(fill="x", pady=(4, 0))
        ttk.Button(botoes, text=t("+ item"),
                   command=lambda l=lado: self.por_item(l)).pack(side="left")
        ttk.Button(botoes, text=t("Quantidade…"),
                   command=lambda l=lado: self.mudar_quantidade(l)).pack(
            side="left", padx=(4, 0))
        ttk.Button(botoes, text=t("Tirar"),
                   command=lambda l=lado: self.tirar_item(l)).pack(
            side="left", padx=(4, 0))
        return tabela

    def _montar_rodape(self, pai):
        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="both", expand=True, pady=(8, 0))
        self.texto = tk.Text(reg, height=5, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

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
        pasta = Path(motor.BASE) / "trabalho" / "multisell"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def saida(self):
        return Path(motor.BASE) / "multisell_gerada"

    def atualizar_botoes(self):
        parado = not self.rodando
        # So fica cinza enquanto algo roda. Faltando pasta ele continua
        # clicavel e DIZ o que falta -- botao cinza nao ensina nada.
        self.botao_abrir.config(state="normal" if parado else "disabled")
        tem = bool(self.lista.get("trocas"))
        self.botao_instalar.config(state="normal" if parado and tem
                                   else "disabled")

    def nome_do_item(self, ident):
        return self.nomes.get(str(ident), "")

    def _dizer_bypass(self):
        nome = self.nome.get().strip()
        self.rotulo_bypass.config(
            text=t("no NPC:  %s") % l2multisell.bypass(nome) if nome else "")

    # ---- abrir o cliente -------------------------------------------------
    def carregar_tudo(self):
        """
        Carrega o que esta aba usa: as tabelas do cliente e as multisells.

        Nessa ordem, porque é o cliente que dá nome e desenho aos itens: com
        ele antes, a lista do servidor já nasce legível em vez de ser
        preenchida na frente de quem olha.
        """
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas()
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        self._depois_das_tabelas = self.ler_do_servidor
        self.abrir()

    def abrir(self):
        if self.rodando:
            return
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("lendo…"))
        self.log(t("\n=== abrindo as tabelas de %s ===") % self.system())
        threading.Thread(target=self._abrir_thread, daemon=True).start()

    def _abrir_thread(self):
        try:
            itens = l2item.Itens(self.T, self.system(), self.trabalho())
            catalogo = itens.listar()
            erro = None
        except Exception as e:                      # noqa: BLE001
            itens, catalogo, erro = None, [], e
        self.raiz.after(0, self._fim_abertura, itens, catalogo, erro)

    def _fim_abertura(self, itens, catalogo, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            self.log(t("Não deu para abrir: %s") % erro)
            messagebox.showerror(t("Não deu para abrir"), str(erro))
            self.atualizar_botoes()
            return
        self.itens = itens
        self.nomes = dict((i["id"], i["nome"]) for i in catalogo if i["nome"])
        self.descricoes = dict((i["id"], i.get("descricao") or "")
                               for i in catalogo)
        self.icones_de_item = dict((i["id"], i.get("icone") or "")
                                   for i in catalogo)
        self.log(t("%d itens no cliente.") % len(catalogo))
        self._refazer_lados()
        self._refazer_cesta()
        self.atualizar_botoes()
        # O `Carregar` encadeia: terminadas as tabelas, vêm as multisells.
        seguinte = getattr(self, "_depois_das_tabelas", None)
        self._depois_das_tabelas = None
        if seguinte is not None:
            seguinte()

    # ---- o servidor ------------------------------------------------------
    def ler_do_servidor(self):
        pasta = self.pasta_do_servidor.get().strip()
        if not pasta:
            return
        self.log(t("\nLendo as multisells de %s…") % pasta)

        def olhar():
            import l2servidor
            try:
                perfil = l2servidor.perfil_escolhido(
                    motor.ler_opcao("servidor", "perfil", l2servidor.DETECTAR),
                    pasta)
                onde = l2servidor.raiz_de(pasta, perfil, "multisell")
                achadas = l2multisell.listar(onde) if onde else []
                erro = None
            except Exception as e:                  # noqa: BLE001
                perfil, onde, achadas, erro = {}, None, [], e
            self.raiz.after(0, self._servidor_chegou, perfil, onde, achadas,
                            erro)

        threading.Thread(target=olhar, daemon=True).start()

    def _servidor_chegou(self, perfil, onde, achadas, erro):
        self.perfil_servidor = perfil or {}
        if erro is not None:
            self.log(t("Não deu para ler: %s") % erro)
            return
        if onde is None:
            self.onde_ficam.config(text=t("não descobri onde as multisells "
                                          "moram"))
            self.log(t("Não descobri onde as multisells moram nessa pasta."))
            return
        self.onde_ficam.config(text=str(onde))
        self.listas = achadas
        self.preencher()
        quebradas = [a for a in achadas if a["erro"]]
        self.log(t("%d multisells, %d trocas no total.")
                 % (len(achadas), sum(a["trocas"] for a in achadas)))
        for a in quebradas:
            self.log(t("  %s não abriu: %s") % (a["nome"], a["erro"]))
        self.atualizar_botoes()

    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        self.mostradas = [a for a in self.listas
                          if not procurado or procurado in a["nome"].lower()]
        self.tabela.delete(*self.tabela.get_children())
        for i, a in enumerate(self.mostradas):
            self.tabela.insert("", "end", iid=str(i),
                               values=(a["nome"],
                                       a["erro"] or a["trocas"],
                                       a["npcs"] or t("todos")))
        self.conta.config(text=t("%d de %d") % (len(self.mostradas),
                                                len(self.listas)))

    def marcada(self):
        escolhida = self.tabela.selection()
        if not escolhida:
            return None
        indice = int(escolhida[0])
        return self.mostradas[indice] if indice < len(self.mostradas) else None

    def abrir_marcada(self):
        alvo = self.marcada()
        if alvo is None:
            return
        try:
            lista = l2multisell.ler(alvo["caminho"])
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para abrir"), str(erro))
            return
        self.usar(lista)
        self.log(t("\nAberta a multisell %s: %d trocas.")
                 % (lista["nome"], len(lista["trocas"])))

    def usar(self, lista):
        """Põe na tela a multisell inteira."""
        self.lista = lista
        self.nome.set(lista["nome"])
        self.npcs.set(" ".join(lista["npcs"]))
        for chave, variavel in self.opcoes.items():
            variavel.set(bool(lista.get("opcoes", {}).get(chave)))
        self.limpar_troca()
        self._refazer_cesta()
        self.atualizar_botoes()

    def nova_lista(self):
        self.usar(l2multisell.vazia())
        self.nome.set("")
        self.log(t("\nMultisell nova. Dê um nome ao arquivo — é ele que o NPC "
                   "chama."))

    def excluir_marcada(self):
        alvo = self.marcada()
        if alvo is None:
            return
        if not messagebox.askyesno(
                t("Excluir a multisell %s") % alvo["nome"],
                t("O arquivo %s é apagado do servidor.\n\nIsto não tem "
                  "volta.\n\nContinuar?") % alvo["caminho"].name):
            return
        try:
            alvo["caminho"].unlink()
        except OSError as erro:
            messagebox.showerror(t("Não deu para apagar"), str(erro))
            return
        self.log(t("\nApagada: %s") % alvo["caminho"])
        self.ler_do_servidor()

    # ---- montar a troca --------------------------------------------------
    def por_item(self, lado):
        """Escolhe um item do cliente e põe naquele lado da troca."""
        if self.itens is None:
            messagebox.showinfo(
                t("Abra as tabelas primeiro"),
                t("Abra as tabelas do cliente para escolher pelo nome e pelo "
                  "ícone."))
            return
        import gui_arma

        escolha = gui_arma.EscolherArma(
            self.raiz, self, grupos=("weapon", "armor", "etc"),
            titulo=(t("O que o jogador paga") if lado == PAGA
                    else t("O que o jogador recebe")))
        item = escolha.resposta
        if not item or not str(item.get("id", "")).isdigit():
            return

        quanto = self._perguntar_quantidade(item)
        if quanto is None:
            return
        conta, encanto = quanto
        self.troca[lado].append({"id": str(item["id"]), "count": conta,
                                 "enchant": encanto})
        self._refazer_lados()

    def _perguntar_quantidade(self, item, conta="1", encanto="0"):
        """Uma janelinha com a quantidade e o encantamento. None = cancelou."""
        janela = ajuda.por_icone(tk.Toplevel(self.raiz))
        janela.title(t("Quantidade"))
        janela.transient(self.raiz)
        janela.resizable(False, False)

        quadro = ttk.Frame(janela, padding=14)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, font=("Segoe UI", 10, "bold"),
                  text="%s" % (self.nome_do_item(item["id"])
                               or t("item %s") % item["id"])).pack(anchor="w")
        ttk.Label(quadro, foreground=COR_TEXTO_FRACO,
                  text=t("id %s") % item["id"]).pack(anchor="w")

        campos = ttk.Frame(quadro)
        campos.pack(anchor="w", pady=(10, 0))
        ttk.Label(campos, text=t("quantidade:")).grid(row=0, column=0,
                                                      sticky="w")
        v_conta = tk.StringVar(value=str(conta))
        entrada = ttk.Entry(campos, textvariable=v_conta, width=12)
        entrada.grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(campos, text=t("encantamento:")).grid(row=1, column=0,
                                                        sticky="w",
                                                        pady=(6, 0))
        v_encanto = tk.StringVar(value=str(encanto))
        ttk.Spinbox(campos, textvariable=v_encanto, from_=0, to=60,
                    width=5).grid(row=1, column=1, sticky="w", padx=(6, 0),
                                  pady=(6, 0))
        ajuda.ajuda(quadro, lambda: t(
            "A quantidade é por troca: `1000` de Adena quer dizer que cada "
            "clique custa mil.@@"
            "O encantamento em zero não é escrito no arquivo — é o padrão do "
            "servidor. Num item que o jogador RECEBE, ele sai já refinado; "
            "num que ele PAGA, só serve o item naquele +N exato."),
            padx=(0, 0), pady=(10, 0), side="top", anchor="w")

        resposta = {}

        def aceitar():
            c, e = v_conta.get().strip(), v_encanto.get().strip() or "0"
            if not c.isdigit() or int(c) <= 0:
                messagebox.showerror(t("Quantidade inválida"),
                                     t("A quantidade tem de ser um número "
                                       "maior que zero."), parent=janela)
                return
            resposta["conta"], resposta["encanto"] = c, e
            janela.destroy()

        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(14, 0))
        ttk.Button(baixo, text=t("Cancelar"),
                   command=janela.destroy).pack(side="right")
        ttk.Button(baixo, text=t("Usar"), command=aceitar).pack(
            side="right", padx=(0, 6))
        janela.bind("<Return>", lambda _e: aceitar())
        janela.bind("<Escape>", lambda _e: janela.destroy())
        entrada.focus_set()
        entrada.selection_range(0, "end")
        ajuda.centralizar(janela)
        janela.grab_set()
        self.raiz.wait_window(janela)

        if "conta" not in resposta:
            return None
        return resposta["conta"], resposta["encanto"]

    def _marcado_no_lado(self, lado):
        tabela = self.listas_do_lado[lado]
        escolhido = tabela.selection()
        if not escolhido:
            return None
        indice = int(escolhido[0])
        return indice if indice < len(self.troca[lado]) else None

    def mudar_quantidade(self, lado):
        indice = self._marcado_no_lado(lado)
        if indice is None:
            return
        parte = self.troca[lado][indice]
        quanto = self._perguntar_quantidade(parte, parte.get("count", "1"),
                                            parte.get("enchant", "0"))
        if quanto is None:
            return
        parte["count"], parte["enchant"] = quanto
        self._refazer_lados()

    def tirar_item(self, lado):
        indice = self._marcado_no_lado(lado)
        if indice is None:
            return
        del self.troca[lado][indice]
        self._refazer_lados()

    def limpar_troca(self):
        self.troca = {PAGA: [], RECEBE: []}
        self.em_edicao = None
        self.recado.config(text="")
        self.botao_por.config(text=t("Pôr na lista"))
        self._refazer_lados()

    def _refazer_lados(self):
        for lado, tabela in self.listas_do_lado.items():
            tabela.delete(*tabela.get_children())
            for i, parte in enumerate(self.troca[lado]):
                encanto = str(parte.get("enchant", "0") or "0")
                tabela.insert("", "end", iid=str(i),
                              image=self.icone_de(parte["id"]),
                              text=" " + (self.nome_do_item(parte["id"])
                                          or t("(não está no cliente)")),
                              values=(parte["id"],
                                      self._quanto(parte),
                                      encanto if encanto != "0" else ""))
            self._dizer_a_descricao(lado)

    def _dizer_a_descricao(self, lado):
        """A descrição do item marcado naquele lado."""
        rotulo = self.descricao_do_lado.get(lado)
        if rotulo is None:
            return
        indice = self._marcado_no_lado(lado)
        if indice is None:
            rotulo.config(text="")
            return
        ident = str(self.troca[lado][indice].get("id", ""))
        rotulo.config(text=(self.descricoes.get(ident) or "").strip())

    # ---- os icones -------------------------------------------------------
    def icone_de(self, ident):
        """
        O desenho daquele item, ou "" enquanto ele não chegou.

        Pedir 9.412 ícones seria absurdo; os que a tela usa são dezenas. Cada
        um é extraído uma vez, numa thread, e fica guardado.
        """
        ident = str(ident)
        if ident in self.icones:
            return self.icones[ident] or ""
        referencia = (getattr(self, "icones_de_item", {}) or {}).get(ident)
        if not referencia or Image is None:
            self.icones[ident] = None
            return ""
        self.icones[ident] = None       # marca como pedido, para não repetir
        threading.Thread(target=self._icone_thread,
                         args=(ident, referencia), daemon=True).start()
        return ""

    def _icone_thread(self, ident, referencia):
        imagem = self.carregar_icone(referencia)
        try:
            self.raiz.after(0, self._icone_chegou, ident, imagem)
        except tk.TclError:
            pass                        # a janela fechou

    def _icone_chegou(self, ident, imagem):
        if imagem is None:
            return
        self.icones[ident] = ImageTk.PhotoImage(imagem)
        self._pedir_redesenho()

    def _pedir_redesenho(self):
        """
        Um redesenho só, por mais ícones que cheguem juntos.

        Eles chegam em rajada quando a lista abre -- dezenas em menos de um
        segundo --, e redesenhar a cada um faria a tela piscar por todo o
        tempo da rajada.
        """
        if self._redesenho_pedido:
            return
        self._redesenho_pedido = True
        try:
            self._redesenho_marcado = self.quadro.after(
                120, self._redesenhar_agora)
        except tk.TclError:
            self._redesenho_pedido = False

    def _ao_morrer(self, evento):
        # Em `<Destroy>` o Tkinter as vezes entrega o NOME do widget, e nao
        # o objeto. A conferencia existe para nao fechar a aba quando quem
        # morreu foi um filho do quadro.
        if str(evento.widget) == str(self.quadro):
            self.fechar()

    def fechar(self):
        """
        Chamado antes de destruir a aba, ao trocar o idioma.

        Cancela o que estava marcado. Sem isto o tempo vence depois da
        aba, e o Tcl reclama de um comando que ja nao existe.
        """
        for atributo in ("_marcado", "_redesenho_marcado"):
            bilhete = getattr(self, atributo, None)
            if bilhete is None:
                continue
            try:
                self.quadro.after_cancel(bilhete)
            except tk.TclError:
                pass                    # ja venceu, ou o quadro se foi
            setattr(self, atributo, None)

    def _redesenhar_agora(self):
        self._redesenho_pedido = False
        self._redesenho_marcado = None
        self._refazer_lados()
        self._pintar_cesta()

    # ---- a cesta ---------------------------------------------------------
    def por_na_lista(self):
        """A troca montada entra na lista -- ou substitui a que está sendo
        editada."""
        if not self.troca[PAGA] or not self.troca[RECEBE]:
            self.recado.config(text=t("A troca precisa dos dois lados: o que "
                                      "o jogador paga e o que ele recebe."))
            return
        nova = {"paga": [dict(p) for p in self.troca[PAGA]],
                "recebe": [dict(p) for p in self.troca[RECEBE]],
                "comentario": ""}
        if self.em_edicao is not None and self.em_edicao < len(self.lista["trocas"]):
            self.lista["trocas"][self.em_edicao] = nova
        else:
            self.lista["trocas"].append(nova)
        self.limpar_troca()
        self._refazer_cesta()
        self.atualizar_botoes()

    def _quanto(self, parte):
        """`30.000`, com o ponto do milhar que o olho usa para conferir."""
        try:
            return "{:,}".format(int(parte.get("count", 1))).replace(",", ".")
        except (TypeError, ValueError):
            return str(parte.get("count", ""))

    def _refazer_cesta(self):
        """A lista mudou: refaz a régua de rolagem e repinta."""
        trocas = self.lista.get("trocas") or []
        if self.marcada_cesta is not None and self.marcada_cesta >= len(trocas):
            self.marcada_cesta = None
        self.abertas_cesta = set(i for i in self.abertas_cesta
                                 if i < len(trocas))
        self._medir_cesta()
        self._pintar_cesta()
        self.total.config(text=t("%d trocas") % len(trocas))

    def _pode_abrir(self, troca):
        """Só vale abrir quando há mais de um item para mostrar."""
        return (len(troca.get("paga") or [])
                + len(troca.get("recebe") or [])) > 2

    def _linhas_da_troca(self, i, troca):
        if i not in self.abertas_cesta or not self._pode_abrir(troca):
            return 1
        return 1 + max(len(troca.get("paga") or []),
                       len(troca.get("recebe") or []))

    def _medir_cesta(self):
        """
        A régua: em que pixel cada troca começa.

        Com a gaveta a linha deixou de ter altura fixa, então "o que está à
        vista" não é mais uma divisão. É uma busca binária nesta lista, que se
        refaz só quando a lista muda ou uma gaveta abre.
        """
        trocas = self.lista.get("trocas") or []
        self._tops = []
        y = 0
        for i, troca in enumerate(trocas):
            self._tops.append(y)
            y += self._linhas_da_troca(i, troca) * ALTURA_DA_LINHA
        self.cesta.config(scrollregion=(0, 0, 1, max(1, y)))

    def _altura_da_cesta(self):
        return (self.cesta.bbox("all") or (0, 0, 1, 1))[3] or 1

    # ---- o checkout e desenhado, nao montado -----------------------------
    def _colunas_da_cesta(self, largura):
        """
        Onde cada coluna começa e acaba. A mesma conta serve o cabeçalho e as
        linhas -- é o que mantém os dois alinhados quando a janela muda.
        """
        numero = 8
        paga = 44
        meio = max(paga + 140, largura // 2)
        return numero, paga, meio - 24, meio + 8, max(meio + 40, largura - 8)

    def _pintar_cabecalho(self, _evento=None):
        tela = self.cabeca_cesta
        tela.delete("all")
        largura = tela.winfo_width()
        if largura <= 1:
            return
        numero, paga, _fim, recebe, _ = self._colunas_da_cesta(largura)
        for x, texto, cor in ((numero, t("#"), COR_TEXTO_FRACO),
                              (paga, t("o jogador paga"), COR_PAGA),
                              (recebe, t("e recebe"), COR_RECEBE)):
            tela.create_text(x, 11, text=texto, anchor="w", fill=cor,
                             font=self.fonte_cabecalho)

    def _pintar_cesta(self):
        """
        Desenha só as linhas à vista.

        A maior multisell deste servidor tem 3.176 trocas. Um widget por linha
        seriam dezenas de milhares, e o Tk engasga muito antes disso. Item de
        canvas é barato, e aqui só existe o que cabe na tela -- umas quinze.
        """
        tela = self.cesta
        tela.delete("all")
        self._pintar_cabecalho()
        trocas = self.lista.get("trocas") or []
        largura = tela.winfo_width()
        if largura <= 1:
            return
        if not trocas:
            tela.create_text(largura // 2, 30, text=t("Nenhuma troca ainda."),
                             fill=COR_TEXTO_FRACO, font=self.fonte_cesta)
            return
        topo = tela.canvasy(0)
        fundo = topo + tela.winfo_height()
        i = max(0, bisect.bisect_right(self._tops, topo) - 1)
        while i < len(trocas) and self._tops[i] < fundo:
            self._pintar_troca(i, trocas[i], largura)
            i += 1

    def _pintar_troca(self, i, troca, largura):
        tela = self.cesta
        alto = self._tops[i]
        linhas = self._linhas_da_troca(i, troca)
        marcada = (i == self.marcada_cesta)
        fundo = (COR_MARCADA if marcada
                 else (COR_LINHA if i % 2 == 0 else COR_LINHA_ALT))
        tela.create_rectangle(0, alto, largura,
                              alto + linhas * ALTURA_DA_LINHA,
                              fill=fundo, outline=fundo)
        cor = COR_TEXTO_MARCADO if marcada else COR_TEXTO
        fraca = COR_TEXTO_MARCADO if marcada else COR_TEXTO_FRACO
        numero, paga, fim_paga, recebe, fim_recebe = \
            self._colunas_da_cesta(largura)
        meio = alto + ALTURA_DA_LINHA // 2
        pagos = troca.get("paga") or []
        recebidos = troca.get("recebe") or []

        tela.create_text(numero, meio, text=str(i + 1), anchor="w",
                         fill=fraca, font=self.fonte_cesta)
        if self._pode_abrir(troca):
            tela.create_text(numero + 18, meio,
                             text="\u25be" if linhas > 1 else "\u25b8",
                             anchor="w", fill=fraca, font=self.fonte_cesta)
        tela.create_text((fim_paga + recebe) // 2, meio, text="\u2192",
                         fill=fraca, font=self.fonte_cesta)

        if linhas == 1:
            self._pintar_lado(pagos, paga, fim_paga, meio, cor)
            self._pintar_lado(recebidos, recebe, fim_recebe, meio, cor)
            return

        # Aberta: o topo conta, e cada item ganha a sua linha.
        tela.create_text(paga, meio, text=self._conta_de_itens(len(pagos)),
                         anchor="w", fill=fraca, font=self.fonte_cabecalho)
        tela.create_text(recebe, meio,
                         text=self._conta_de_itens(len(recebidos)),
                         anchor="w", fill=fraca, font=self.fonte_cabecalho)
        for k in range(linhas - 1):
            meio += ALTURA_DA_LINHA
            if k < len(pagos):
                self._pintar_item(pagos[k], paga + 14, fim_paga, meio, cor)
            if k < len(recebidos):
                self._pintar_item(recebidos[k], recebe + 14, fim_recebe,
                                  meio, cor)

    def _conta_de_itens(self, quantos):
        return t("1 item") if quantos == 1 else t("%d itens") % quantos

    def _pintar_item(self, parte, x, limite, meio, cor):
        """
        Um item: o desenho e, ao lado, o nome com a quantidade.

        Item sem ícone ganha um quadrado tracejado -- o espaço fica reservado,
        então as linhas não dançam conforme os ícones vão chegando.
        """
        desenho = self.icone_de(parte["id"])
        if desenho:
            self.cesta.create_image(x, meio, image=desenho, anchor="w")
        else:
            self.cesta.create_rectangle(x + 8, meio - 8, x + 24, meio + 8,
                                        outline=COR_TEXTO_FRACO, dash=(2, 2))
        x += LADO_DO_ICONE + 5
        encanto = str(parte.get("enchant", "0") or "0")
        rotulo = "%s x %s%s" % (
            self.nome_do_item(parte["id"]) or (t("item %s") % parte["id"]),
            self._quanto(parte),
            (" +%s" % encanto) if encanto != "0" else "")
        return self._escrever_ate(rotulo, x, limite, meio, cor)

    def _pintar_lado(self, partes, x, limite, meio, cor):
        """Um lado inteiro numa linha só, os itens ligados por `+`."""
        tela = self.cesta
        for n, parte in enumerate(partes):
            if x >= limite:
                tela.create_text(limite, meio, text="\u2026", anchor="e",
                                 fill=cor, font=self.fonte_cesta)
                return
            if n:
                tela.create_text(x, meio, text="+", anchor="w", fill=cor,
                                 font=self.fonte_cesta)
                x += 13
            x = self._pintar_item(parte, x, limite, meio, cor) + 10

    def _escrever_ate(self, texto, x, limite, meio, cor):
        """Escreve o que couber até `limite`, cortando com reticência."""
        if x + self.fonte_cesta.measure(texto) > limite:
            while texto and (x + self.fonte_cesta.measure(texto + "\u2026")
                             > limite):
                texto = texto[:-1]
            texto += "\u2026"
        self.cesta.create_text(x, meio, text=texto, anchor="w", fill=cor,
                               font=self.fonte_cesta)
        return x + self.fonte_cesta.measure(texto)

    # ---- rolar, marcar, andar --------------------------------------------
    def _cesta_rolou(self, inicio, fim):
        self.barra_cesta.set(inicio, fim)
        self._pintar_cesta()

    def _rolar_cesta(self, passos):
        self.cesta.yview_scroll(passos * 3, "units")
        return "break"

    def _troca_em(self, y):
        """Qual troca ocupa aquele pixel, ou None."""
        trocas = self.lista.get("trocas") or []
        if not trocas or not self._tops:
            return None
        i = bisect.bisect_right(self._tops, y) - 1
        if i < 0 or i >= len(trocas):
            return None
        fim = self._tops[i] + self._linhas_da_troca(i, trocas[i]) * ALTURA_DA_LINHA
        return i if y < fim else None

    def _clicar_na_cesta(self, evento):
        trocas = self.lista.get("trocas") or []
        y = self.cesta.canvasy(evento.y)
        i = self._troca_em(y)
        self.cesta.focus_set()
        # O triângulo abre e fecha; o resto da linha só marca. Ele só responde
        # na linha de cima -- dentro da gaveta aquele x é do item, não dela.
        if (i is not None and self._pode_abrir(trocas[i])
                and y - self._tops[i] < ALTURA_DA_LINHA
                and 22 <= evento.x <= 40):
            self.abertas_cesta.symmetric_difference_update({i})
            self.marcada_cesta = i
            self._medir_cesta()
            self._pintar_cesta()
            return
        self.marcada_cesta = i
        self._pintar_cesta()

    def _andar_na_cesta(self, passo):
        trocas = self.lista.get("trocas") or []
        if not trocas:
            return "break"
        atual = self.marcada_cesta
        destino = 0 if atual is None else max(0, min(len(trocas) - 1,
                                                     atual + passo))
        self.marcada_cesta = destino
        self._ver_troca(destino)
        self._pintar_cesta()
        return "break"

    def _ver_troca(self, i):
        """Rola o bastante para a troca ficar à vista, e nem um passo além."""
        trocas = self.lista.get("trocas") or []
        if not self._tops or i >= len(self._tops):
            return
        tela = self.cesta
        ultimo = self._tops[-1] + (self._linhas_da_troca(len(trocas) - 1,
                                                         trocas[-1])
                                   * ALTURA_DA_LINHA)
        total = float(max(1, ultimo))
        topo = tela.canvasy(0)
        visivel = tela.winfo_height()
        alto = self._tops[i]
        fundo = alto + self._linhas_da_troca(i, trocas[i]) * ALTURA_DA_LINHA
        if alto < topo:
            tela.yview_moveto(alto / total)
        elif fundo > topo + visivel:
            tela.yview_moveto((fundo - visivel) / total)

    def _troca_marcada(self):
        """Qual troca está marcada no checkout, ou None."""
        i = self.marcada_cesta
        trocas = self.lista.get("trocas") or []
        return i if i is not None and 0 <= i < len(trocas) else None

    def editar_troca(self):
        indice = self._troca_marcada()
        if indice is None:
            return
        troca = self.lista["trocas"][indice]
        self.troca = {PAGA: [dict(p) for p in troca.get("paga") or []],
                      RECEBE: [dict(p) for p in troca.get("recebe") or []]}
        self.em_edicao = indice
        self.botao_por.config(text=t("Guardar a troca %d") % (indice + 1))
        self.recado.config(text="")
        self._refazer_lados()

    def tirar_troca(self):
        indice = self._troca_marcada()
        if indice is None:
            return
        del self.lista["trocas"][indice]
        # As gavetas sao guardadas por indice, e tirar uma troca desloca todas
        # as de baixo: sem isto abriria a linha errada.
        self.abertas_cesta = set((j - 1) if j > indice else j
                                 for j in self.abertas_cesta if j != indice)
        if self.marcada_cesta is not None and self.marcada_cesta > indice:
            self.marcada_cesta -= 1
        if self.em_edicao == indice:
            self.limpar_troca()
        self._refazer_cesta()
        self.atualizar_botoes()

    def mover_troca(self, passo):
        indice = self._troca_marcada()
        if indice is None:
            return
        destino = indice + passo
        trocas = self.lista["trocas"]
        if not 0 <= destino < len(trocas):
            return
        trocas[indice], trocas[destino] = trocas[destino], trocas[indice]
        de_um = indice in self.abertas_cesta
        do_outro = destino in self.abertas_cesta
        self.abertas_cesta.discard(indice)
        self.abertas_cesta.discard(destino)
        if de_um:
            self.abertas_cesta.add(destino)
        if do_outro:
            self.abertas_cesta.add(indice)
        self.marcada_cesta = destino
        self._refazer_cesta()
        self._ver_troca(destino)
        self._pintar_cesta()

    # ---- gerar e instalar ------------------------------------------------
    def _da_tela(self):
        """A multisell como está na tela."""
        lista = dict(self.lista)
        lista["nome"] = self.nome.get().strip()
        lista["npcs"] = [p for p in self.npcs.get().replace(",", " ").split()
                         if p.isdigit()]
        lista["opcoes"] = dict((c, v.get()) for c, v in self.opcoes.items()
                               if v.get())
        return lista

    def conferir(self, calado=False):
        lista = self._da_tela()
        outros = set(a["nome"] for a in self.listas
                     if a["nome"] != (self.lista.get("nome") or ""))
        problemas = l2multisell.conferir(lista, self.itens, outros)
        if problemas:
            self.log(t("\nA conferência achou %d coisas:") % len(problemas))
            for p in problemas:
                self.log("  • " + p)
            if not calado:
                messagebox.showwarning(
                    t("A conferência achou problemas"),
                    "\n\n".join("• " + p for p in problemas[:8]))
        elif not calado:
            messagebox.showinfo(
                t("Está tudo certo"),
                t("%d trocas, e todos os itens existem no cliente.")
                % len(lista.get("trocas") or []))
            self.log(t("\nConferência: nada a corrigir."))
        return problemas

    def ver_xml(self):
        lista = self._da_tela()
        janela = ajuda.por_icone(tk.Toplevel(self.raiz))
        janela.title(t("XML da multisell %s") % (lista["nome"] or "?"))
        janela.transient(self.raiz)
        caixa = tk.Text(janela, width=84, height=28, wrap="none",
                        font=("Consolas", 9))
        caixa.pack(fill="both", expand=True, padx=8, pady=8)
        caixa.insert("1.0", l2multisell.xml(lista, self.nomes))
        caixa.config(state="disabled")
        ttk.Button(janela, text=t("Fechar"),
                   command=janela.destroy).pack(pady=(0, 8))
        janela.bind("<Escape>", lambda _e: janela.destroy())

    def instalar(self):
        lista = self._da_tela()
        problemas = self.conferir(calado=True)
        if problemas and not messagebox.askyesno(
                t("A conferência achou problemas"),
                t("%s\n\nInstalar assim mesmo?")
                % "\n\n".join("• " + p for p in problemas[:6])):
            return

        pasta = self.pasta_das_multisells()
        if pasta is None:
            messagebox.showinfo(
                t("Não sei onde gravar"),
                t("Aponte a pasta de dados do servidor e use Ler as "
                  "multisells.\n\nSe ela já está apontada, o programa não "
                  "conseguiu descobrir onde as multisells moram dentro "
                  "dela."))
            return

        alvo = pasta / ("%s.xml" % lista["nome"])
        if alvo.exists() and not messagebox.askyesno(
                t("Já existe"),
                t("%s já existe.\n\nEscrever por cima?") % alvo.name):
            return

        texto = l2multisell.xml(lista, self.nomes)
        try:
            # A cópia na pasta de saída fica sempre: é dela que se recupera o
            # arquivo quando alguém mexe no do servidor a mão.
            l2multisell.gravar(texto, self.saida(), lista["nome"])
            posto = l2multisell.gravar(texto, pasta, lista["nome"])
        except Exception as erro:                   # noqa: BLE001
            self.log(t("A instalação parou: %s") % erro)
            messagebox.showerror(t("A instalação parou"), str(erro))
            return

        self.lista["nome"] = lista["nome"]
        self.log(t("\nInstalada em %s") % posto)
        self.ler_do_servidor()
        messagebox.showinfo(
            t("Multisell instalada"),
            t("%s\n\n%d trocas.\n\nFalta recarregar no jogo:\n"
              "    //reload multisell\n\nE pôr o bypass no HTML do NPC:\n"
              "    %s")
            % (posto, len(lista.get("trocas") or []),
               l2multisell.bypass(lista["nome"])))

    # ---- o manual --------------------------------------------------------
    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "multisell",
                        t("Manual — multisell")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))

    # ---- o painel de ícone pede isto ao dono -----------------------------
    def carregar_icone(self, referencia):
        """A imagem do ícone, para a janela de escolher item."""
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
        except Exception:                           # noqa: BLE001
            return None
