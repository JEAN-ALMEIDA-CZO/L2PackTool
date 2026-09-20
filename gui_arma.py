#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Escolher um item do cliente, pelo nome e pelo desenho.

Nasceu para a arma da mao do NPC -- o `rHand` do XML leva um ID DE ITEM, e
`1472` nao diz nada a ninguem -- e hoje serve toda tela que precisa apontar um
item: a multisell, o glow, o mundo. Quem chama diz em `grupos` o que quer ver,
e a janela se descreve de acordo: so `weapon` e uma lista de armas, mais de um
grupo e uma lista de itens.

Tudo sai do `weapongrp.dat`, `armorgrp.dat`, `etcitemgrp.dat` e
`itemname-e.dat` -- as mesmas tabelas da aba de Itens, lidas pelo mesmo
`l2item`. Nao ha catalogo a parte para envelhecer: o que o cliente tem e o que
aparece aqui.

Abrir as tabelas custa alguns segundos, entao so acontece quando esta janela e
aberta pela primeira vez, e o resultado fica guardado na aba que a chamou.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

import ajuda
import l2conferir
import l2item
import l2skill
import motor
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

# O valor do combo quando ele nao filtra nada. Guardado em portugues e
# traduzido so na hora de mostrar, para a comparacao nao depender do idioma.
TODOS = N_("todos")

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE
LADO_DO_ICONE = 32


class EscolherArma:
    """
    Devolve em `.resposta` o dicionario da arma escolhida, ou None.

    `dono` e a aba que abriu a janela: dela vem o caminho do cliente, a pasta de
    trabalho, o cache de imagens e -- depois da primeira vez -- a lista de armas
    ja lida.
    """

    def __init__(self, raiz, dono, atual="", grupos=("weapon",), titulo=None):
        self.raiz = raiz
        self.dono = dono
        self.resposta = None
        self.grupos = tuple(grupos or ("weapon",))
        # Uma gaveta de cache por conjunto de grupos: guardar a lista de armas
        # e a do catalogo inteiro no mesmo lugar faria a segunda janela mostrar
        # o resultado da primeira.
        self.gaveta = "itens_do_cliente_" + "_".join(sorted(self.grupos))
        self.armas = list(getattr(dono, self.gaveta, []) or [])
        self.mostradas = []
        self.atual = str(atual or "").strip()

        self.janela = tk.Toplevel(raiz)
        # So armas, ou item no geral? Muda o titulo, a descricao, o recado de
        # leitura e ate a existencia do filtro de tipo.
        self.so_armas = (self.grupos == ("weapon",))
        self.janela.title(titulo or (t("Escolher a arma") if self.so_armas
                                     else t("Escolher o item")))
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)

        quadro = ttk.Frame(self.janela, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, foreground=COR_TEXTO_FRACO, wraplength=560,
                  justify="left",
                  text=t("A arma na mão é um id de item. A lista sai do "
                         "weapongrp.dat deste cliente.") if self.so_armas else
                  t("Todos os itens deste cliente — armas, armaduras e os "
                    "demais. A lista sai das tabelas dele.")).pack(anchor="w")

        topo = ttk.Frame(quadro)
        topo.pack(fill="x", pady=(8, 0))
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(topo, textvariable=self.filtro, width=24)
        entrada.pack(side="left", padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self._filtrar_daqui_a_pouco())
        ajuda.ajuda(topo, lambda: t(
            "Procura no nome e no id ao mesmo tempo.@@"
            "Digitar `dragon` acha pelo nome; digitar `9501` acha pelo id. "
            "Não precisa ser o começo: `slayer` acha `Dragon Slayer`."))

        self.tipo = tk.StringVar(value=TODOS)
        if not self.so_armas:
            ttk.Label(topo, text=t("Tipo:")).pack(side="left", padx=(12, 0))
            self.caixa_tipo = ttk.Combobox(topo, textvariable=self.tipo,
                                           state="readonly", width=12,
                                           values=(t(TODOS),))
            self.caixa_tipo.pack(side="left", padx=(6, 0))
            self.caixa_tipo.bind("<<ComboboxSelected>>",
                                 lambda _e: self.preencher())

        ttk.Label(topo, text=t("id de")).pack(side="left", padx=(12, 0))
        self.de = tk.StringVar()
        self.ate = tk.StringVar()
        for variavel in (self.de, self.ate):
            campo = ttk.Entry(topo, textvariable=variavel, width=7)
            campo.pack(side="left", padx=(4, 0))
            campo.bind("<KeyRelease>", lambda _e: self._filtrar_daqui_a_pouco())
            if variavel is self.de:
                ttk.Label(topo, text=t("até")).pack(side="left", padx=(4, 0))
        ajuda.ajuda(topo, lambda: t(
            "A faixa de ids, para quando você sabe onde os seus itens moram.@@"
            "Pack custom costuma reservar uma faixa — `9000` a `9999`, por "
            "exemplo. Preencher só um dos dois campos vale: `de 9000` mostra "
            "do 9000 para cima."))

        ttk.Button(topo, text=t("Limpar"),
                   command=self.limpar_filtros).pack(side="left", padx=(12, 0))
        self.conta = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True, pady=(8, 0))

        colunas = (N_("id"), N_("nome"), N_("tipo"))
        self.tabela = ttk.Treeview(corpo, columns=colunas, show="headings",
                                   height=16, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (70, 300, 60),
                                              ("e", "w", "w")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento)
        barra = ttk.Scrollbar(corpo, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_marcar)
        self.tabela.bind("<Double-Button-1>", lambda _e: self.aceitar())

        lado = ttk.Frame(corpo, padding=(12, 0, 0, 0))
        lado.pack(side="left", fill="y")
        self.moldura = tk.Frame(lado, bg=COR_FUNDO_ICONE,
                                width=LADO_DO_ICONE + 10,
                                height=LADO_DO_ICONE + 10,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                highlightcolor=tema.BORDA)
        self.moldura.pack()
        self.moldura.pack_propagate(False)
        self.tela = tk.Label(self.moldura, bg=COR_FUNDO_ICONE, fg=tema.TEXTO_APAGADO,
                             text="—", font=("Segoe UI", 8))
        self.tela.pack(expand=True)
        self.detalhe = ttk.Label(lado, text="", foreground=COR_TEXTO_FRACO,
                                 wraplength=170, justify="left")
        self.detalhe.pack(anchor="w", pady=(6, 0))

        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(10, 0))
        self.botao_usar = ttk.Button(baixo, text=t("Usar esta"),
                                     command=self.aceitar, state="disabled")
        self.botao_usar.pack(side="left")
        if self.grupos == ("weapon",):
            ttk.Button(baixo, text=t("Mão vazia"),
                       command=self.esvaziar).pack(side="left", padx=(6, 0))
        ttk.Button(baixo, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")
        self.estado = ttk.Label(baixo, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()

        if self.armas:
            self.preencher()
        else:
            self.estado.config(
                text=t("lendo as armas do cliente…") if self.so_armas
                else t("lendo os itens do cliente…"))
            threading.Thread(target=self._ler_thread, daemon=True).start()

        raiz.wait_window(self.janela)

    # ---- a lista ---------------------------------------------------------
    def _ler_thread(self):
        """
        Le o weapongrp do cliente fora da thread da interface.

        Alguns segundos numa tabela de milhares de linhas; fazer isso na thread
        da tela congelaria a janela recem-aberta.
        """
        try:
            raiz = l2conferir.raiz_do_cliente(self.dono.cliente.get().strip())
            itens = l2item.Itens(self.dono.T, raiz / "system",
                                 self.dono.trabalho() / "armas")
            armas = [i for i in itens.listar() if i["grupo"] in self.grupos]
            erro = None
        except Exception as e:                      # noqa: BLE001
            armas, erro = [], e
        try:
            self.janela.after(0, self._fim_leitura, armas, erro)
        except tk.TclError:
            pass                                    # a janela fechou antes

    def _fim_leitura(self, armas, erro):
        if erro is not None:
            self.estado.config(text="")
            messagebox.showerror(
                t("Não deu para ler as armas") if self.so_armas
                else t("Não deu para ler os itens"), str(erro),
                parent=self.janela)
            return
        self.armas = armas
        # Fica com a aba: a segunda vez que esta janela abrir e instantanea.
        setattr(self.dono, self.gaveta, armas)
        self.estado.config(text="")
        self._encher_os_tipos()
        self.preencher()

    def _encher_os_tipos(self):
        """
        O combo de tipo sai do que a lista TEM, nao de uma lista fixa.

        Cliente sem etcitemgrp legivel nao deve oferecer `Outros` -- escolher
        aquilo daria zero linhas sem dizer por que.
        """
        caixa = getattr(self, "caixa_tipo", None)
        if caixa is None:
            return
        vistos = []
        for a in self.armas:
            rotulo = a.get("rotulo") or ""
            if rotulo and rotulo not in vistos:
                vistos.append(rotulo)
        caixa.config(values=tuple([t(TODOS)] + [t(v) for v in vistos]))
        self._rotulos = vistos

    def _filtrar_daqui_a_pouco(self):
        """
        Espera a digitacao parar antes de refazer a lista.

        Refazer uma tabela de 9.432 linhas a cada tecla faz a digitacao
        engasgar: quem digita `dragon` pagaria seis vezes por um resultado que
        so interessa no fim.
        """
        marcado = getattr(self, "_marcado", None)
        if marcado is not None:
            try:
                self.janela.after_cancel(marcado)
            except tk.TclError:
                pass
        self._marcado = self.janela.after(220, self.preencher)

    def limpar_filtros(self):
        self.filtro.set("")
        self.tipo.set(t(TODOS))
        self.de.set("")
        self.ate.set("")
        self.preencher()

    def _faixa(self):
        """Os dois extremos da faixa de id, aceitando só um deles preenchido."""
        def numero(variavel, padrao):
            texto = variavel.get().strip()
            try:
                return int(texto)
            except ValueError:
                return padrao
        return numero(self.de, None), numero(self.ate, None)

    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        tipo = self.tipo.get()
        # O combo mostra o rotulo traduzido; a comparacao volta ao original.
        if tipo and tipo != t(TODOS):
            for bruto in getattr(self, "_rotulos", []):
                if t(bruto) == tipo:
                    tipo = bruto
                    break
        else:
            tipo = None
        de, ate = self._faixa()

        self.mostradas = []
        for a in self.armas:
            if procurado and (procurado not in a["nome"].lower()
                              and procurado not in str(a["id"])):
                continue
            if tipo and (a.get("rotulo") or "") != tipo:
                continue
            if de is not None or ate is not None:
                try:
                    ident = int(a["id"])
                except (TypeError, ValueError):
                    continue
                if de is not None and ident < de:
                    continue
                if ate is not None and ident > ate:
                    continue
            self.mostradas.append(a)
        self.tabela.delete(*self.tabela.get_children())
        for i, a in enumerate(self.mostradas):
            self.tabela.insert("", "end", iid=str(i),
                               values=(a["id"], a["nome"],
                                       t(a.get("rotulo", "")) or ""))
        self.conta.config(text=t("%d de %d") % (len(self.mostradas),
                                                len(self.armas)))
        self._marcar_a_atual()

    def _marcar_a_atual(self):
        """Deixa marcada a arma que ja estava no campo, se ela estiver aqui."""
        if not self.atual or self.atual == "0":
            return
        for i, a in enumerate(self.mostradas):
            if str(a["id"]) == self.atual:
                self.tabela.selection_set(str(i))
                self.tabela.see(str(i))
                self.ao_marcar()
                return

    # ---- a previa --------------------------------------------------------
    def ao_marcar(self, _evento=None):
        arma = self.marcada()
        self.botao_usar.config(state="normal" if arma else "disabled")
        if not arma:
            return
        self.detalhe.config(text=t("%s\nid %s\n%s")
                            % (arma["nome"] or t("sem nome"), arma["id"],
                               arma.get("icone") or ""))
        self.mostrar_icone(arma.get("icone") or "")

    def marcada(self):
        escolhida = self.tabela.selection()
        if not escolhida:
            return None
        indice = int(escolhida[0])
        return self.mostradas[indice] if indice < len(self.mostradas) else None

    def mostrar_icone(self, referencia):
        if Image is None or not referencia:
            self._desenhar(None)
            return
        cache = getattr(self.dono, "icones", None)
        if cache is None:
            cache = self.dono.icones = {}
        if referencia in cache:
            self._desenhar(cache[referencia])
            return
        threading.Thread(target=self._icone_thread, args=(referencia,),
                         daemon=True).start()

    def _icone_thread(self, referencia):
        try:
            arquivo = l2item.extrair_icone(
                self.dono.T, self.dono.cliente.get(), referencia,
                self.dono.trabalho() / "icones",
                dizer=getattr(self.dono, "_avisar_do_icone", None))
            imagem = motor.abrir_imagem(arquivo, self.dono.T) if arquivo else None
        except Exception:                           # noqa: BLE001
            imagem = None
        try:
            self.janela.after(0, self._guardar_icone, referencia, imagem)
        except tk.TclError:
            pass

    def _guardar_icone(self, referencia, imagem):
        foto = ImageTk.PhotoImage(imagem) if imagem is not None else None
        self.dono.icones[referencia] = foto
        arma = self.marcada()
        if arma and (arma.get("icone") or "") == referencia:
            self._desenhar(foto)

    def _desenhar(self, foto):
        if foto is None:
            self.tela.config(image="", text="—")
        else:
            self.tela.config(image=foto, text="")
        self.tela.imagem = foto

    # ---- respostas -------------------------------------------------------
    def aceitar(self):
        arma = self.marcada()
        if arma:
            self.resposta = arma
            self.janela.destroy()

    def esvaziar(self):
        """Mao vazia e `0`, que e o que o servidor entende por 'nada'."""
        self.resposta = {"id": "0", "nome": t("mão vazia"), "icone": ""}
        self.janela.destroy()


class DicaDaLinha:
    """
    Um balão com a descrição da linha sob o ponteiro.

    O `ajuda.Dica` prende-se a um widget inteiro; aqui o texto muda conforme a
    LINHA, então o balão segue o ponteiro e se refaz quando a linha troca.
    Refazer a cada pixel piscaria, então ele só se mexe quando a linha muda.
    """

    def __init__(self, tabela, texto_de, largura=380):
        self.tabela = tabela
        self.texto_de = texto_de
        self.largura = largura
        self.balao = None
        self.linha = None
        tabela.bind("<Motion>", self._mover, add="+")
        tabela.bind("<Leave>", lambda _e: self.fechar(), add="+")

    def _mover(self, evento):
        linha = self.tabela.identify_row(evento.y)
        if linha != self.linha:
            self.linha = linha
            self.fechar()
            texto = self.texto_de(linha) if linha else ""
            if texto:
                self._abrir(texto, evento)

    def _abrir(self, texto, evento):
        try:
            self.balao = tk.Toplevel(self.tabela)
            self.balao.wm_overrideredirect(True)
            self.balao.attributes("-topmost", True)
            tk.Label(self.balao, text=texto, justify="left",
                     wraplength=self.largura, background=tema.ELEVADO,
                     foreground=tema.TEXTO, relief="solid", borderwidth=1,
                     padx=8, pady=6, font=tema.CORPO).pack()
            self.balao.update_idletasks()
            x = self.tabela.winfo_rootx() + evento.x + 18
            y = self.tabela.winfo_rooty() + evento.y + 18
            # Nunca para fora da tela: um balão cortado não se lê.
            x = min(x, self.balao.winfo_screenwidth()
                    - self.balao.winfo_width() - 8)
            y = min(y, self.balao.winfo_screenheight()
                    - self.balao.winfo_height() - 8)
            self.balao.geometry("+%d+%d" % (max(0, x), max(0, y)))
        except tk.TclError:
            self.balao = None

    def fechar(self):
        if self.balao is not None:
            try:
                self.balao.destroy()
            except tk.TclError:
                pass
            self.balao = None


class EscolherSkill:
    """
    Devolve em `.resposta` o dicionário da skill escolhida, ou None.

    `dono` é a aba que abriu: dela vêm o caminho do cliente, a pasta de
    trabalho e -- depois da primeira vez -- a lista já lida.
    """

    GAVETA = "skills_do_cliente"

    def __init__(self, raiz, dono, atual="", titulo=None, sugeridas=None):
        self.raiz = raiz
        self.dono = dono
        self.resposta = None
        self.atual = str(atual or "").strip()
        # [(id, quantos mobs parecidos usam)] -- quem abriu já contou.
        self.sugeridas = list(sugeridas or [])
        self.skills = list(getattr(dono, self.GAVETA, []) or [])
        self.mostradas = []

        self.janela = tk.Toplevel(raiz)
        self.janela.title(titulo or t("Escolher a skill"))
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)

        quadro = ttk.Frame(self.janela, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, style="Fraco.TLabel", wraplength=560, justify="left",
                  text=t("As skills deste cliente. Passe o mouse numa linha "
                         "para ler o que ela faz.")).pack(anchor="w")

        topo = ttk.Frame(quadro)
        topo.pack(fill="x", pady=(8, 0))
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        campo = ttk.Entry(topo, textvariable=self.filtro, width=24)
        campo.pack(side="left", padx=(6, 0))
        campo.bind("<KeyRelease>", lambda _e: self._daqui_a_pouco())

        self.so_sugeridas = tk.BooleanVar(value=bool(self.sugeridas))
        if self.sugeridas:
            ttk.Checkbutton(topo, variable=self.so_sugeridas,
                            text=t("só as sugeridas (%d)") % len(self.sugeridas),
                            command=self.preencher).pack(side="left",
                                                         padx=(12, 0))
            ajuda.ajuda(topo, lambda: t(
                "As skills que os mobs PARECIDOS com este usam.@@"
                "Parecido é do mesmo tipo e de nível próximo, contado no seu "
                "próprio pack — não é uma lista escrita à mão. O número ao "
                "lado é quantos mobs parecidos usam aquela skill, e é o que "
                "separa o golpe padrão da família do que um mob só tem."))

        ttk.Button(topo, text=t("Limpar"),
                   command=self.limpar).pack(side="left", padx=(12, 0))
        self.conta = ttk.Label(topo, style="Miudo.TLabel")
        self.conta.pack(side="left", padx=(8, 0))

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("id"), N_("níveis"), N_("tipo"), N_("mobs"))
        self.tabela = ttk.Treeview(corpo, columns=colunas,
                                   show="tree headings", height=16,
                                   selectmode="browse", style="Icone.Treeview")
        self.tabela.heading("#0", text=t("skill"))
        self.tabela.column("#0", width=260, minwidth=160, stretch=True)
        for nome, largura in zip(colunas, (64, 54, 110, 54)):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor="e", stretch=False)
        barra = ttk.Scrollbar(corpo, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_marcar)
        self.tabela.bind("<Double-Button-1>", lambda _e: self.aceitar())
        DicaDaLinha(self.tabela, self._descricao_da_linha)

        self.nivel = tk.StringVar(value="1")
        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(10, 0))
        ttk.Label(baixo, text=t("nível")).pack(side="left")
        self.caixa_nivel = ttk.Combobox(baixo, textvariable=self.nivel,
                                        width=6, values=("1",))
        self.caixa_nivel.pack(side="left", padx=(6, 0))
        self.botao_usar = ttk.Button(baixo, text=t("Usar esta"),
                                     style="Primario.TButton",
                                     command=self.aceitar, state="disabled")
        self.botao_usar.pack(side="left", padx=(12, 0))
        ttk.Button(baixo, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")
        self.estado = ttk.Label(baixo, style="Miudo.TLabel")
        self.estado.pack(side="left", padx=(12, 0))

        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()

        if self.skills:
            self.preencher()
        else:
            self.estado.config(text=t("lendo as skills do cliente…"))
            threading.Thread(target=self._ler_thread, daemon=True).start()

        raiz.wait_window(self.janela)

    # ---- a lista ------------------------------------------------------
    def _ler_thread(self):
        try:
            raiz = l2conferir.raiz_do_cliente(self.dono.cliente.get().strip())
            skills = l2skill.Skills(self.dono.T, raiz / "system",
                                    self.dono.trabalho() / "skills").listar()
            erro = None
        except Exception as e:                      # noqa: BLE001
            skills, erro = [], e
        try:
            self.janela.after(0, self._fim_leitura, skills, erro)
        except tk.TclError:
            pass

    def _fim_leitura(self, skills, erro):
        self.estado.config(text="")
        if erro is not None:
            messagebox.showerror(t("Não deu para ler as skills"), str(erro),
                                 parent=self.janela)
            return
        self.skills = skills
        setattr(self.dono, self.GAVETA, skills)
        self.preencher()

    def _daqui_a_pouco(self):
        marcado = getattr(self, "_marcado", None)
        if marcado is not None:
            try:
                self.janela.after_cancel(marcado)
            except tk.TclError:
                pass
        self._marcado = self.janela.after(220, self.preencher)

    def limpar(self):
        self.filtro.set("")
        self.so_sugeridas.set(False)
        self.preencher()

    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        quantos_por_id = dict((str(i), n) for i, n in self.sugeridas)
        so_sugeridas = bool(self.so_sugeridas.get()) and bool(self.sugeridas)

        self.mostradas = []
        for s in self.skills:
            ident = str(s["id"])
            if so_sugeridas and ident not in quantos_por_id:
                continue
            if procurado and (procurado not in (s["nome"] or "").lower()
                              and procurado not in ident):
                continue
            self.mostradas.append(s)
        if so_sugeridas:
            # Na ordem da sugestão: a mais usada primeiro.
            self.mostradas.sort(key=lambda s: -quantos_por_id.get(str(s["id"]), 0))

        self.tabela.delete(*self.tabela.get_children())
        for i, s in enumerate(self.mostradas[:2000]):
            ident = str(s["id"])
            self.tabela.insert(
                "", "end", iid=str(i), image=self.icone_de(s.get("icone") or ""),
                text=" " + (s["nome"] or t("sem nome")),
                values=(ident, s.get("niveis", 1), t(s.get("tipo", "") or ""),
                        quantos_por_id.get(ident, "")))
        self.conta.config(text=t("%d de %d") % (len(self.mostradas),
                                                len(self.skills)))
        self._marcar_a_atual()

    def _marcar_a_atual(self):
        if not self.atual:
            return
        for i, s in enumerate(self.mostradas[:2000]):
            if str(s["id"]) == self.atual:
                self.tabela.selection_set(str(i))
                self.tabela.see(str(i))
                self.ao_marcar()
                return

    def _descricao_da_linha(self, linha):
        try:
            s = self.mostradas[int(linha)]
        except (ValueError, IndexError):
            return ""
        partes = ["%s   (id %s)" % (s["nome"] or t("sem nome"), s["id"])]
        if s.get("tipo"):
            partes.append(t("tipo: %s") % t(s["tipo"]))
        partes.append(t("%d nível(is)") % s.get("niveis", 1))
        if (s.get("descricao") or "").strip():
            partes.append("")
            partes.append(s["descricao"].strip())
        return "\n".join(partes)

    def marcada(self):
        escolhida = self.tabela.selection()
        if not escolhida:
            return None
        indice = int(escolhida[0])
        return self.mostradas[indice] if indice < len(self.mostradas) else None

    def ao_marcar(self, _evento=None):
        s = self.marcada()
        self.botao_usar.config(state="normal" if s else "disabled")
        if not s:
            return
        quantos = max(1, int(s.get("niveis", 1) or 1))
        self.caixa_nivel.config(values=tuple(str(n) for n in
                                             range(1, quantos + 1)))
        if not self.nivel.get().isdigit() or int(self.nivel.get()) > quantos:
            self.nivel.set("1")

    # ---- o desenho ----------------------------------------------------
    def icone_de(self, referencia):
        """O ícone da skill, pedido uma vez e guardado com a aba que chamou."""
        if not referencia or Image is None:
            return ""
        cache = getattr(self.dono, "icones", None)
        if cache is None:
            cache = self.dono.icones = {}
        if referencia in cache:
            return cache[referencia] or ""
        cache[referencia] = None
        threading.Thread(target=self._icone_thread, args=(referencia,),
                         daemon=True).start()
        return ""

    def _icone_thread(self, referencia):
        try:
            arquivo = l2item.extrair_icone(
                self.dono.T, self.dono.cliente.get(), referencia,
                self.dono.trabalho() / "icones",
                dizer=getattr(self.dono, "_avisar_do_icone", None))
            imagem = motor.abrir_imagem(arquivo, self.dono.T) if arquivo else None
            if imagem is not None and imagem.size != (LADO_DO_ICONE,
                                                      LADO_DO_ICONE):
                imagem = imagem.resize((LADO_DO_ICONE, LADO_DO_ICONE),
                                       Image.LANCZOS)
        except Exception:                           # noqa: BLE001
            imagem = None
        try:
            self.janela.after(0, self._icone_chegou, referencia, imagem)
        except tk.TclError:
            pass

    def _icone_chegou(self, referencia, imagem):
        if imagem is None:
            return
        self.dono.icones[referencia] = ImageTk.PhotoImage(imagem)
        if getattr(self, "_redesenho", False):
            return
        self._redesenho = True
        try:
            self.janela.after(120, self._redesenhar)
        except tk.TclError:
            self._redesenho = False

    def _redesenhar(self):
        self._redesenho = False
        try:
            self.preencher()
        except tk.TclError:
            pass

    def aceitar(self):
        s = self.marcada()
        if not s:
            return
        nivel = self.nivel.get().strip() or "1"
        self.resposta = {"id": str(s["id"]), "level": nivel,
                         "nome": s.get("nome", ""),
                         "icone": s.get("icone", "")}
        self.janela.destroy()


class MudarDrop:
    """
    Quantos caem e com que chance. Serve a aba de Mob e a de NPC.

    A chance aparece nas DUAS unidades ao mesmo tempo, e mexer numa acerta a
    outra. É onde mais se erra numa lista de drop: no XML do servidor o número
    é por milhão, então escrever `5` querendo 5% dá 0,0005% e o item nunca
    cai.

    `percentual=True` inverte quem manda: a tela do NPC guarda a chance em
    porcento, e ali o campo do milhão é que é o espelho.

    `gavetas` liga a caixa de categoria -- a aba de NPC chama de gaveta, e o
    Mob resolve isso por categoria na própria árvore.
    """

    CHEIA = 1000000

    def __init__(self, raiz, nome, ident, minimo="1", maximo="1", chance="1",
                 percentual=False, gavetas=None, gaveta=""):
        self.resposta = None
        self.percentual = percentual
        self.janela = tk.Toplevel(raiz)
        self.janela.title(t("O drop"))
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)

        quadro = ttk.Frame(self.janela, padding=tema.FOLGA)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, style="Subtitulo.TLabel",
                  text="%s  (id %s)" % (nome or t("item"), ident)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, tema.PERTO))

        self.minimo = tk.StringVar(value=str(minimo))
        self.maximo = tk.StringVar(value=str(maximo))
        if percentual:
            self.por_cento = tk.StringVar(value=str(chance))
            self.chance = tk.StringVar(value=str(self._do_por_cento(chance)))
        else:
            self.chance = tk.StringVar(value=str(chance))
            self.por_cento = tk.StringVar(value="%.4f" % self._em_por_cento(chance))

        for linha, (rotulo, variavel) in enumerate(
                ((t("quantidade mínima"), self.minimo),
                 (t("quantidade máxima"), self.maximo)), start=1):
            ttk.Label(quadro, text=rotulo).grid(row=linha, column=0, sticky="e",
                                                padx=(0, 6), pady=3)
            ttk.Entry(quadro, textvariable=variavel, width=14).grid(
                row=linha, column=1, sticky="w", pady=3)

        ttk.Label(quadro, text=t("chance (por milhão)")).grid(
            row=3, column=0, sticky="e", padx=(0, 6), pady=3)
        campo = ttk.Entry(quadro, textvariable=self.chance, width=14)
        campo.grid(row=3, column=1, sticky="w", pady=3)
        campo.bind("<KeyRelease>", lambda _e: self._da_chance())

        ttk.Label(quadro, text=t("o mesmo em %")).grid(
            row=4, column=0, sticky="e", padx=(0, 6), pady=3)
        campo = ttk.Entry(quadro, textvariable=self.por_cento, width=14)
        campo.grid(row=4, column=1, sticky="w", pady=3)
        campo.bind("<KeyRelease>", lambda _e: self._da_porcentagem())

        self.gaveta = tk.StringVar(value=gaveta or "")
        if gavetas:
            ttk.Label(quadro, text=t("gaveta")).grid(row=5, column=0,
                                                     sticky="e", padx=(0, 6),
                                                     pady=3)
            ttk.Combobox(quadro, textvariable=self.gaveta, values=list(gavetas),
                         state="readonly", width=12).grid(row=5, column=1,
                                                          sticky="w", pady=3)

        ajuda.ajuda(quadro, lambda: t(
            "Os dois campos são o mesmo número, em unidades diferentes.@@"
            "O XML do servidor guarda a chance por milhão: 1.000.000 é 100%. "
            "É o erro mais comum da lista de drop — escrever `5` querendo 5%: "
            "dá 0,0005%, e o item nunca cai. Mexer num campo acerta o outro."),
            grid=True, row=3, column=2, padx=(8, 0))

        botoes = ttk.Frame(quadro)
        botoes.grid(row=6, column=0, columnspan=3, sticky="ew",
                    pady=(tema.FOLGA, 0))
        ttk.Button(botoes, text=t("Usar"), style="Primario.TButton",
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")
        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        raiz.wait_window(self.janela)

    def _em_por_cento(self, chance):
        try:
            return 100.0 * float(chance) / self.CHEIA
        except (TypeError, ValueError):
            return 0.0

    def _do_por_cento(self, por_cento):
        try:
            return max(1, min(self.CHEIA,
                              int(round(float(por_cento) * self.CHEIA / 100.0))))
        except (TypeError, ValueError):
            return 1

    def _da_chance(self):
        self.por_cento.set("%.4f" % self._em_por_cento(self.chance.get()))

    def _da_porcentagem(self):
        self.chance.set(str(self._do_por_cento(self.por_cento.get())))

    def aceitar(self):
        # A tela do NPC guarda a chance em porcento; a do Mob, por milhao.
        chance = (self.por_cento.get().strip() if self.percentual
                  else self.chance.get().strip())
        self.resposta = {"minimo": self.minimo.get().strip() or "1",
                         "maximo": self.maximo.get().strip() or "1",
                         "chance": chance,
                         "gaveta": self.gaveta.get()}
        self.janela.destroy()
