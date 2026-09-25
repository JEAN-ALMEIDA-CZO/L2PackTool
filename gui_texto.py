#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aba "Textos" -- o que o jogo escreve na tela.

Tres tabelas, uma lista so: a mensagem de sistema, o texto de interface e a fala
de NPC. Quem monta servidor mexe nisso para traduzir e para trocar o que o jogo
diz pelo que o servidor dele diz.

A lista tem onze mil linhas num cliente do High Five, e por isso a busca e o
centro da tela: procura-se pelo texto, do jeito que ele aparece no jogo, e nao
pelo numero.

**A marca vale mais que o texto.** `$s1` e `$c1` sao os buracos onde o servidor
encaixa numero, nome e item. Uma frase reescrita sem a marca que ela tinha
continua aparecendo -- so chega sem o dado que anunciava, e nada avisa. Por isso
a tela conta as marcas antes e depois, e pergunta quando alguma se perde.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import ajuda
import gui_projeto
import l2conferir
import l2item
import l2mensagem
import motor
import projeto
import tema
from idioma import t, N_

COR_TEXTO_FRACO = tema.TEXTO_FRACO

CARTOES = (
    ("total", N_("textos"), tema.PAINEL, tema.TEXTO),
    ("sistema", N_("mensagens do sistema"), tema.PAINEL, tema.TEXTO),
    ("interface", N_("textos de interface"), tema.PAINEL, tema.TEXTO),
    ("npc", N_("falas de NPC"), tema.PAINEL, tema.TEXTO),
)

# Quantos aparecem na lista de uma vez. Onze mil linhas num Treeview deixam a
# rolagem pesada e nao servem para nada: ninguem procura rolando.
LIMITE_DA_LISTA = 400


class JanelaTexto:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.textos = None
        self.lista = []
        self.mostrados = []
        self.gravados = []
        self.marcado = None

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("As frases que o jogo escreve na tela: mensagem de "
                         "sistema, texto de interface e fala de NPC. Procure "
                         "pelo texto como ele aparece no jogo, escreva o novo e "
                         "aplique.\n\nAs tabelas saem numa pasta à parte; o "
                         "cliente só muda em Instalar no cliente.")).pack(
                             anchor="w")

        self._montar_cliente(quadro)
        self._montar_resumo(quadro)
        self._montar_busca(quadro)
        self._montar_lista(quadro)
        self._montar_edicao(quadro)
        self._montar_rodape(quadro)
        self.atualizar_botoes()

    # ---- montagem --------------------------------------------------------
    def _montar_cliente(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))
        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))
        self.rotulo_cronica = ttk.Label(linha, style="Miudo.TLabel")
        self.rotulo_cronica.pack(side="left", padx=(12, 0))
        self.mostrar_cronica()
        projeto.ao_trocar(lambda *_a: self.ao_trocar_cronica())

        self.botao_abrir = ttk.Button(linha, text=t("Carregar"),
                                      style="Primario.TButton",
                                      command=self.abrir)
        self.botao_abrir.pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Carregar lê o systemmsg-e, o sysstring-e e o npcstring-e do "
            "cliente -- os que existirem nesta crônica.\n\n"
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

    def _montar_busca(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text=t("procurar") + ":").pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(linha, textvariable=self.filtro, width=40)
        entrada.pack(side="left", padx=(6, 0))
        entrada.bind("<Return>", self.ao_filtrar)
        self.filtro.trace_add("write", lambda *_a: self.ao_filtrar())

        ttk.Label(linha, text=t("tabela") + ":").pack(side="left", padx=(12, 0))
        self.qual = tk.StringVar(value=t("todas"))
        self.escolha_de_tabela = ttk.Combobox(
            linha, textvariable=self.qual, width=22, state="readonly",
            values=[t("todas")])
        self.escolha_de_tabela.pack(side="left", padx=(6, 0))
        self.escolha_de_tabela.bind("<<ComboboxSelected>>", self.ao_filtrar)

        self.so_com_marca = tk.BooleanVar(value=False)
        ttk.Checkbutton(linha, variable=self.so_com_marca,
                        text=t("só as que têm $s1"),
                        command=self.ao_filtrar).pack(side="left", padx=(12, 0))
        self.conta = ttk.Label(linha, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(12, 0))

    def _montar_lista(self, pai):
        dentro = ttk.Frame(pai)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("tabela"), N_("id"), N_("texto"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=14, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (150, 70, 700),
                                              ("w", "e", "w")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento)
        rolar = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=rolar.set)
        rolar.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_escolher)

    def _montar_edicao(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("O texto"), padding=6)
        caixa.pack(fill="x", pady=(8, 0))

        self.rotulo_alvo = ttk.Label(caixa, text=t("escolha um texto na lista"),
                                     foreground=COR_TEXTO_FRACO)
        self.rotulo_alvo.grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(caixa, text=t("texto") + ":").grid(row=1, column=0,
                                                     sticky="w", pady=(6, 0))
        self.texto_novo = tk.StringVar()
        self.campo = ttk.Entry(caixa, textvariable=self.texto_novo, width=96)
        self.campo.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))
        self.campo.bind("<Return>", lambda _e: self.aplicar())

        ttk.Label(caixa, text=t("segunda linha") + ":").grid(
            row=2, column=0, sticky="w", pady=(4, 0))
        self.extra_novo = tk.StringVar()
        self.campo_extra = ttk.Entry(caixa, textvariable=self.extra_novo,
                                     width=96)
        self.campo_extra.grid(row=2, column=1, sticky="ew", padx=(6, 0),
                              pady=(4, 0))
        caixa.columnconfigure(1, weight=1)
        ajuda.ajuda(caixa, lambda: t(
            "A segunda linha existe só na mensagem de sistema: é o que o jogo "
            "escreve embaixo da principal.\n\n"
            "As marcas $s1, $s2, $c1 são os buracos onde o servidor encaixa "
            "número, nome ou item. Tirar uma não dá erro -- a frase só chega "
            "sem o dado que anunciava."), grid=True, row=1, column=2,
            padx=(8, 0))

        acao = ttk.Frame(caixa)
        acao.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.botao_aplicar = ttk.Button(acao, text=t("Aplicar"),
                                        command=self.aplicar)
        self.botao_aplicar.pack(side="left")
        self.botao_voltar = ttk.Button(acao, text=t("Voltar ao original"),
                                       command=self.voltar_ao_original)
        self.botao_voltar.pack(side="left", padx=(6, 0))
        self.aviso = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.aviso.pack(side="left", padx=(12, 0))

    def _montar_rodape(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(8, 0))
        self.botao_gerar = ttk.Button(linha, text=t("Gerar as tabelas"),
                                      style="Primario.TButton",
                                      command=self.gerar)
        self.botao_gerar.pack(side="left")
        self.botao_instalar = ttk.Button(linha, text=t("Instalar no cliente"),
                                         command=self.instalar)
        self.botao_instalar.pack(side="left", padx=(6, 0))
        self.botao_restaurar = ttk.Button(linha, text=t("Restaurar originais"),
                                          command=self.restaurar)
        self.botao_restaurar.pack(side="left", padx=(6, 0))
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Gerar escreve as tabelas numa pasta à parte; instalar as põe no "
            "cliente. São separados de propósito: dá para olhar o resultado "
            "antes de o cliente depender dele.\n\n"
            "Na primeira instalação as tabelas originais são guardadas em "
            "system/%s, e é de lá que Restaurar as traz de volta.")
            % l2mensagem.PASTA_GUARDA, padx=(10, 0))

        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.registro = tk.Text(reg, height=4, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.registro.yview)
        self.registro.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.registro.pack(fill="both", expand=True)

    # ---- o basico --------------------------------------------------------
    def log(self, texto):
        self.registro.insert("end", texto + "\n")
        self.registro.see("end")

    def system(self):
        return l2conferir.raiz_do_cliente(self.cliente.get().strip()) / "system"

    def trabalho(self):
        return Path(motor.BASE) / "trabalho" / "textos"

    def saida(self):
        return l2mensagem.saida()

    def cronica_escolhida(self):
        return l2item.cronica_em_uso()

    def mostrar_cronica(self):
        try:
            self.rotulo_cronica.config(
                text=t("crônica: %s")
                % l2item.rotulo_da_cronica(self.cronica_escolhida()))
        except tk.TclError:
            pass

    def ao_trocar_cronica(self, _evento=None):
        """Trocou de projeto: o que estava lido era de outro cliente."""
        self.mostrar_cronica()
        if self.textos is None:
            return
        self.textos = None
        self.lista = []
        self.mostrados = []
        self.marcado = None
        self.gravados = []
        try:
            self.tabela.delete(*self.tabela.get_children())
        except tk.TclError:
            return
        self.log(t("\nCrônica: %s. Carregue as tabelas de novo.")
                 % l2item.rotulo_da_cronica(self.cronica_escolhida()))
        self.atualizar_botoes()

    def progresso(self, fracao, texto):
        self.raiz.after(0, self._desenhar_progresso, fracao, texto)

    def _desenhar_progresso(self, fracao, texto):
        if fracao is not None:
            self.andamento.config(value=int(max(0.0, min(1.0, fracao)) * 1000))
        self.estado.config(text=texto)

    def atualizar_botoes(self):
        parado = not self.rodando
        pronto = parado and self.textos is not None
        self.botao_abrir.config(state="normal" if parado else "disabled")
        self.botao_gerar.config(
            state="normal" if pronto and self.textos.alteradas else "disabled")
        self.botao_instalar.config(
            state="normal" if parado and self.gravados else "disabled")
        self.botao_aplicar.config(
            state="normal" if pronto and self.marcado else "disabled")
        self.botao_voltar.config(state=self.botao_aplicar.cget("state"))
        self.botao_restaurar.config(
            state="normal" if parado
            and (self.system() / l2mensagem.PASTA_GUARDA).is_dir()
            else "disabled")

    # ---- abrir -----------------------------------------------------------
    def abrir(self):
        if self.rodando:
            return
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas(precisa_servidor=False)
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        faltam = [n for n in ("l2encdec", "l2disasm", "l2asm")
                  if not Path(self.T.get(n, "")).exists()]
        if faltam:
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.")
                                 % (", ".join(faltam), motor.CONFIG))
            return

        system = self.system()
        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== abrindo as tabelas de texto de %s ===") % system)
        threading.Thread(target=self._abrir_thread, args=(system,),
                         daemon=True).start()

    def _abrir_thread(self, system):
        try:
            textos = l2mensagem.Mensagens(self.T, system, self.trabalho(),
                                          self.cronica_escolhida(),
                                          aoprogresso=self.progresso)
            erro = None
        except Exception as e:                      # noqa: BLE001
            textos, erro = None, e
        self.raiz.after(0, self._fim_abertura, textos, erro)

    def _fim_abertura(self, textos, erro):
        self.rodando = False
        if erro is not None:
            self._desenhar_progresso(0, "")
            self.log(t("Não deu para abrir: %s") % erro)
            messagebox.showerror(t("Não deu para abrir as tabelas"), str(erro))
            self.atualizar_botoes()
            return

        self.textos = textos
        self.gravados = []
        self.marcado = None
        ruins = textos.conferir(so_alteradas=False)
        if ruins:
            messagebox.showwarning(
                t("Definição não confere"),
                t("Estas tabelas não voltam iguais ao original:\n\n%s\n\n"
                  "Elas podem ser lidas, mas gravar qualquer alteração nelas "
                  "está bloqueado.") % "\n".join("%s — %s" % p for p in ruins))

        self.lista = textos.listar()
        por_grupo = {}
        for entrada in self.lista:
            por_grupo[entrada["grupo"]] = por_grupo.get(entrada["grupo"], 0) + 1
        self.numeros["total"].config(text="%d" % len(self.lista))
        for chave in ("sistema", "interface", "npc"):
            self.numeros[chave].config(
                text=("%d" % por_grupo[chave]) if chave in por_grupo else "—")

        rotulos = [t("todas")] + [textos.rotulo(c) for c in ("sistema",
                                                             "interface", "npc")
                                  if c in textos.tabelas]
        self.escolha_de_tabela.config(values=rotulos)
        self.qual.set(t("todas"))

        if textos.faltando:
            self.log(t("  esta crônica não tem: %s")
                     % ", ".join(a for _c, a, _r in textos.faltando))
        self.preencher()
        self.log(t("Carregados %d textos.") % len(self.lista))
        self.atualizar_botoes()

    # ---- a lista ---------------------------------------------------------
    def ao_filtrar(self, _evento=None):
        if self.textos is not None:
            self.preencher()

    def _grupo_escolhido(self):
        """A chave da tabela escolhida na caixa, ou None para todas."""
        escolhido = self.qual.get()
        if not escolhido or escolhido == t("todas"):
            return None
        for chave in ("sistema", "interface", "npc"):
            if self.textos.rotulo(chave) == escolhido:
                return chave
        return None

    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        grupo = self._grupo_escolhido()
        so_marca = self.so_com_marca.get()
        achados = []
        for entrada in self.lista:
            if grupo and entrada["grupo"] != grupo:
                continue
            if so_marca and not l2mensagem.MARCA.search(entrada["texto"]):
                continue
            if procurado and (procurado not in entrada["texto"].lower()
                              and procurado != entrada["id"]):
                continue
            achados.append(entrada)

        self.mostrados = achados[:LIMITE_DA_LISTA]
        self.tabela.delete(*self.tabela.get_children())
        for i, entrada in enumerate(self.mostrados):
            self.tabela.insert("", "end", iid=str(i),
                               values=(t(entrada["rotulo"]), entrada["id"],
                                       entrada["texto"] or t("(vazio)")))
        if len(achados) > len(self.mostrados):
            self.conta.config(
                text=t("%d de %d — refine a busca para ver o resto")
                % (len(self.mostrados), len(achados)))
        else:
            self.conta.config(text=t("%d de %d") % (len(achados),
                                                    len(self.lista)))
        self.marcado = None
        self.rotulo_alvo.config(text=t("escolha um texto na lista"))
        self.atualizar_botoes()

    def ao_escolher(self, _evento=None):
        escolhido = self.tabela.selection()
        if not escolhido:
            return
        entrada = self.mostrados[int(escolhido[0])]
        self.marcado = entrada
        self.texto_novo.set(entrada["texto"])
        self.extra_novo.set(entrada.get("extra", ""))
        # A segunda linha so existe na mensagem de sistema: mostrar o campo
        # sempre faria parecer que o texto de interface tem uma e nao tem.
        tem_extra = "extra" in entrada
        estado = "normal" if tem_extra else "disabled"
        self.campo_extra.config(state=estado)
        self.rotulo_alvo.config(
            text=t("%s, id %s%s")
            % (t(entrada["rotulo"]), entrada["id"],
               (" — " + t("tem %d marca(s): %s")
                % (len(l2mensagem.MARCA.findall(entrada["texto"])),
                   ", ".join(l2mensagem.MARCA.findall(entrada["texto"]))))
               if l2mensagem.MARCA.search(entrada["texto"]) else ""))
        self.aviso.config(text="")
        self.atualizar_botoes()

    # ---- editar ----------------------------------------------------------
    def aplicar(self):
        if self.textos is None or not self.marcado:
            return
        entrada = self.marcado
        novo = self.texto_novo.get()
        extra = (self.extra_novo.get() if "extra" in entrada else None)
        if novo == entrada["texto"] and extra == entrada.get("extra"):
            self.aviso.config(text=t("nada mudou"))
            return
        try:
            perdidas = self.textos.trocar(entrada["grupo"], entrada["id"],
                                          novo, extra)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu"), str(erro))
            return

        if perdidas and not messagebox.askyesno(
                t("Faltam marcas"),
                t("O texto original tinha %s e o novo não tem.\n\nA marca é o "
                  "lugar onde o servidor encaixa o número, o nome ou o item. "
                  "Sem ela a frase aparece, mas sem o dado -- e o jogo não "
                  "reclama.\n\nAplicar assim mesmo?")
                % ", ".join(perdidas)):
            # Desfaz: o texto volta a ser o que era.
            self.textos.trocar(entrada["grupo"], entrada["id"],
                               entrada["texto"], entrada.get("extra"))
            self.texto_novo.set(entrada["texto"])
            self.aviso.config(text=t("desfeito"))
            return

        entrada["texto"] = novo
        if extra is not None:
            entrada["extra"] = extra
        self.log(t("  %s %s: %r") % (t(entrada["rotulo"]), entrada["id"],
                                     novo[:60]))
        self.aviso.config(text=t("aplicado — use Gerar as tabelas"))
        self.preencher_mantendo(entrada)
        self.atualizar_botoes()

    def preencher_mantendo(self, entrada):
        """Refaz a lista e deixa marcado o mesmo texto."""
        alvo = (entrada["grupo"], entrada["id"])
        self.preencher()
        for i, mostrado in enumerate(self.mostrados):
            if (mostrado["grupo"], mostrado["id"]) == alvo:
                self.tabela.selection_set(str(i))
                self.tabela.see(str(i))
                self.ao_escolher()
                return

    def voltar_ao_original(self):
        """Devolve o texto que estava no cliente quando a tabela foi aberta."""
        if self.textos is None or not self.marcado:
            return
        entrada = self.marcado
        guardado = None
        for original in self.lista:
            if (original["grupo"], original["id"]) == (entrada["grupo"],
                                                       entrada["id"]):
                guardado = original
                break
        if guardado is None:
            return
        self.texto_novo.set(guardado["texto"])
        self.extra_novo.set(guardado.get("extra", ""))
        self.aviso.config(text=t("texto do cliente de volta no campo -- "
                                 "aplique para valer"))

    # ---- gerar e instalar ------------------------------------------------
    def gerar(self):
        if self.textos is None or not self.textos.alteradas:
            return
        quais = ", ".join(sorted(self.textos.alteradas))
        if not messagebox.askyesno(
                t("Gerar as tabelas"),
                t("As tabelas mexidas (%s) vão ser escritas em:\n\n%s\n\nO "
                  "cliente só muda em Instalar no cliente.\n\nGerar?")
                % (quais, self.saida())):
            return
        try:
            self.gravados = self.textos.gravar(
                self.saida(), aolog=lambda s: self.log("  " + s))
        except Exception as erro:                   # noqa: BLE001
            self.log(t("A geração parou: %s") % erro)
            messagebox.showerror(t("A geração parou"), str(erro))
            return
        self.log(t("Gerado em %s") % self.saida())
        messagebox.showinfo(
            t("Tabelas geradas"),
            t("%d tabela(s) em:\n\n%s\n\nNada foi alterado no cliente ainda.")
            % (len(self.gravados), self.saida()))
        self.atualizar_botoes()

    def instalar(self):
        if self.rodando or not self.gravados:
            return
        system = self.system()
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("%d tabela(s) vão ser copiadas para:\n\n%s\n\nOs originais "
                  "são guardados em %s na primeira vez. Continuar?")
                % (len(self.gravados), system, l2mensagem.PASTA_GUARDA)):
            return
        try:
            postos = l2mensagem.instalar(self.gravados, system,
                                         aolog=lambda s: self.log("  " + s))
        except Exception as erro:                   # noqa: BLE001
            self.log(t("A instalação parou: %s") % erro)
            messagebox.showerror(t("A instalação parou"), str(erro))
            return
        messagebox.showinfo(
            t("Instalação terminada"),
            t("%d tabela(s) instaladas. Feche o cliente antes de testar.")
            % len(postos))
        self.atualizar_botoes()

    def restaurar(self):
        system = self.system()
        guarda = system / l2mensagem.PASTA_GUARDA
        if not guarda.is_dir():
            messagebox.showinfo(
                t("Não há o que restaurar"),
                t("Não achei %s -- nenhuma tabela de texto foi instalada "
                  "ainda.") % guarda)
            return
        if not messagebox.askyesno(
                t("Restaurar originais"),
                t("As tabelas guardadas em %s voltam para o cliente, por cima "
                  "das que estão lá.\n\nRestaurar?") % guarda):
            return
        try:
            voltaram = l2mensagem.restaurar(
                system, aolog=lambda s: self.log("  " + s))
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para restaurar"), str(erro))
            return
        messagebox.showinfo(t("Restaurado"),
                            t("%d tabela(s) voltaram ao original.")
                            % len(voltaram))
        self.atualizar_botoes()

    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "textos",
                        t("Manual — os textos do cliente")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))
