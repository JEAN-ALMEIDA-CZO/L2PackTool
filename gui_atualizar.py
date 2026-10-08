#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A janela de atualização: o que mudou, o download e a instalação.

Três momentos na mesma janela, um depois do outro:

  1. a consulta -- a versão instalada, a do GitHub e as notas de cada versão
     nova (quem pula duas versões lê as duas);
  2. o download -- barra, quanto já veio, quanto falta, a velocidade e o
     tempo estimado, com Cancelar;
  3. a instalação -- o programa fecha, o instalador roda sem perguntas e abre
     a versão nova no fim.

E um modo silencioso para a abertura do programa: uma vez por dia ele
pergunta ao GitHub se há versão nova. Havendo, o botão do cabeçalho fica
dourado, e a janela aparece UMA vez por versão -- quem disse "depois" não é
perguntado de novo a cada abertura.
"""

import os
import re
import threading
import tkinter as tk
import webbrowser
from datetime import date
from tkinter import messagebox, ttk

import ajuda
import l2atualizar
import motor
import tema
from idioma import t

SECAO = "atualizacao"


def _automatica():
    return motor.ler_opcao(SECAO, "automatica", "sim") != "nao"


# ---------------------------------------------------------------------------
# a busca de abertura
# ---------------------------------------------------------------------------
def procurar_ao_abrir(raiz, botao):
    """Uma consulta por dia, em segundo plano, alguns segundos depois de abrir."""
    try:
        l2atualizar.limpar_baixados()
    except Exception:                               # noqa: BLE001
        pass
    if not _automatica():
        return
    hoje = date.today().isoformat()
    if motor.ler_opcao(SECAO, "ultima_busca", "") == hoje:
        # Ja perguntou hoje; mas se ja sabia de uma versao nova, o botao
        # continua avisando.
        conhecida = motor.ler_opcao(SECAO, "conhecida", "")
        if conhecida and l2atualizar.numero(conhecida) > l2atualizar.versao_atual():
            _marcar_botao(botao, conhecida)
        return

    def trabalho():
        try:
            achado = l2atualizar.procurar(timeout=10)
        except Exception:                           # noqa: BLE001
            return          # sem rede na abertura nao e assunto para janela
        try:
            raiz.after(0, depois, achado)
        except (tk.TclError, RuntimeError):
            pass

    def depois(achado):
        motor.gravar_opcao(SECAO, "ultima_busca", hoje)
        alvo = achado.get("alvo")
        if not alvo:
            motor.gravar_opcao(SECAO, "conhecida", "")
            return
        motor.gravar_opcao(SECAO, "conhecida", alvo["texto"])
        _marcar_botao(botao, alvo["texto"])
        if motor.ler_opcao(SECAO, "avisada", "") != alvo["texto"]:
            motor.gravar_opcao(SECAO, "avisada", alvo["texto"])
            abrir(raiz, botao, achado)

    raiz.after(4000, lambda: threading.Thread(target=trabalho,
                                              daemon=True).start())


def _marcar_botao(botao, texto_da_versao):
    try:
        botao.configure(text=t("Nova versão %s") % texto_da_versao,
                        style="Primario.TButton")
    except tk.TclError:
        pass


def texto_do_botao():
    return t("Atualizações")


def _celulas(linha):
    """As celulas de uma linha de tabela Markdown, sem as barras das pontas."""
    miolo = linha.strip()
    if miolo.startswith("|"):
        miolo = miolo[1:]
    if miolo.endswith("|"):
        miolo = miolo[:-1]
    return [c.strip() for c in miolo.split("|")]


def _blocos(texto):
    """
    O Markdown em blocos, na ordem: o que o GitHub desenha, so que contado.

    ("titulo", nivel, texto) | ("par", texto) | ("item", nivel, marca, texto)
    ("codigo", texto) | ("tabela", cabecalho, alinhamentos, linhas)
    ("citacao", texto) | ("regra",)

    Linhas seguidas de paragrafo viram um paragrafo so -- o texto da release
    e quebrado a mao a cada 80 colunas, como o CHANGELOG, e o GitHub junta.
    O mesmo vale para a continuacao recuada de um item de lista.
    """
    linhas = texto.replace("\r\n", "\n").split("\n")
    blocos = []
    i = 0
    while i < len(linhas):
        crua = linhas[i].rstrip()
        tira = crua.strip()
        if not tira:
            i += 1
            continue
        if tira.startswith("```"):
            corpo = []
            i += 1
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                corpo.append(linhas[i].rstrip())
                i += 1
            blocos.append(("codigo", "\n".join(corpo)))
            i += 1
            continue
        if tira.startswith("|") and i + 1 < len(linhas) and \
                re.match(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$", linhas[i + 1].strip()):
            cabecalho = _celulas(tira)
            alinhamentos = []
            for c in _celulas(linhas[i + 1]):
                alinhamentos.append("e" if c.endswith(":") and not c.startswith(":")
                                    else "center" if c.startswith(":") and c.endswith(":")
                                    else "w")
            corpo = []
            i += 2
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                corpo.append(_celulas(linhas[i]))
                i += 1
            blocos.append(("tabela", cabecalho, alinhamentos, corpo))
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", tira):
            blocos.append(("regra",))
            i += 1
            continue
        titulo = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", tira)
        if titulo:
            blocos.append(("titulo", len(titulo.group(1)), titulo.group(2)))
            i += 1
            continue
        item = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", crua)
        if item:
            recuo = len(item.group(1).expandtabs(4))
            texto_item = item.group(3).strip()
            i += 1
            # continuacao do item: linha recuada que nao e outro item
            while i < len(linhas) and linhas[i].strip() and \
                    linhas[i][:1] in (" ", "\t") and \
                    not re.match(r"^\s*([-*+]|\d+[.)])\s+", linhas[i]):
                texto_item += " " + linhas[i].strip()
                i += 1
            blocos.append(("item", recuo // 2, item.group(2), texto_item))
            continue
        if tira.startswith(">"):
            partes = []
            while i < len(linhas) and linhas[i].strip().startswith(">"):
                partes.append(linhas[i].strip()[1:].strip())
                i += 1
            blocos.append(("citacao", " ".join(p for p in partes if p)))
            continue
        # paragrafo: junta ate a proxima linha em branco ou bloco especial
        partes = [tira]
        i += 1
        while i < len(linhas):
            prox = linhas[i].strip()
            if not prox or re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||```|>|(-{3,}|\*{3,}|_{3,})$)", prox):
                break
            partes.append(prox)
            i += 1
        blocos.append(("par", " ".join(partes)))
    return blocos


def _sem_marcas(texto):
    """O texto de uma celula sem as marcas de Markdown."""
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    return re.sub(r"\*\*|`|(?<![\w*])\*(?=\S)|(?<=\S)\*(?!\w)", "", texto)


# ---------------------------------------------------------------------------
# a janela
# ---------------------------------------------------------------------------
_ABERTA = []


def abrir(raiz, botao=None, achado=None):
    """Abre (ou traz para a frente) a janela de atualização."""
    for janela in list(_ABERTA):
        try:
            janela.topo.deiconify()
            janela.topo.lift()
            janela.topo.focus_force()
            if achado is not None and not janela.baixando:
                janela.mostrar(achado)
            return janela
        except tk.TclError:
            _ABERTA.remove(janela)
    janela = JanelaDeAtualizacao(raiz, botao)
    _ABERTA.append(janela)
    if achado is None:
        janela.procurar()
    else:
        janela.mostrar(achado)
    return janela


class JanelaDeAtualizacao:
    def __init__(self, raiz, botao=None):
        self.raiz = raiz
        self.botao = botao
        self.achado = None
        self.baixando = False
        self.cancelar = threading.Event()
        self.instalador = None

        topo = self.topo = ajuda.por_icone(tk.Toplevel(raiz))
        topo.title(t("Atualizações"))
        topo.transient(raiz)
        topo.geometry("640x560")
        topo.minsize(520, 420)
        topo.protocol("WM_DELETE_WINDOW", self.fechar)

        quadro = ttk.Frame(topo, padding=16)
        quadro.pack(fill="both", expand=True)

        self.titulo = ttk.Label(quadro, style="Titulo.TLabel",
                                text=t("Procurando atualizações…"))
        self.titulo.pack(anchor="w")
        self.subtitulo = ttk.Label(quadro, style="Fraco.TLabel", justify="left",
                                   text=t("Versão instalada: %s")
                                   % l2atualizar.texto_da_versao(
                                       l2atualizar.versao_atual()))
        self.subtitulo.pack(anchor="w", pady=(2, 10))

        notas = ttk.LabelFrame(quadro, text=t("O que mudou"), padding=6)
        notas.pack(fill="both", expand=True)
        self.notas = tk.Text(notas, wrap="word", height=14, relief="flat",
                             background=tema.PAINEL, foreground=tema.TEXTO,
                             insertbackground=tema.TEXTO, padx=10, pady=8,
                             font=tema.CORPO, borderwidth=0,
                             highlightthickness=0)
        barra = ttk.Scrollbar(notas, orient="vertical", command=self.notas.yview)
        self.notas.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.notas.pack(side="left", fill="both", expand=True)
        n = self.notas
        n.tag_configure("versao", font=tema.TITULO, foreground=tema.OURO,
                        spacing1=6, spacing3=2)
        n.tag_configure("data", font=tema.MIUDO, foreground=tema.TEXTO_FRACO,
                        spacing3=8)
        n.tag_configure("h1", font=(tema.FAMILIA, 11, "bold"),
                        foreground=tema.TEXTO, spacing1=12, spacing3=4)
        n.tag_configure("h", font=tema.SUBTITULO, foreground=tema.TEXTO,
                        spacing1=10, spacing3=3)
        n.tag_configure("par", spacing1=2, spacing3=8, lmargin1=2, lmargin2=2)
        for nivel in range(4):
            recuo = 10 + 20 * nivel
            n.tag_configure("item%d" % nivel, lmargin1=recuo, lmargin2=recuo + 16,
                            spacing1=1, spacing3=3)
        n.tag_configure("marca", foreground=tema.OURO)
        n.tag_configure("forte", font=tema.CORPO_FORTE)
        n.tag_configure("italico", font=(tema.FAMILIA, 9, "italic"))
        n.tag_configure("codigo", font=tema.FIXA, foreground=tema.OURO_CLARO,
                        background=tema.FUNDO)
        n.tag_configure("bloco", font=tema.FIXA, foreground=tema.TEXTO,
                        background=tema.ABISSO, lmargin1=14, lmargin2=14,
                        rmargin=14, spacing1=1, spacing3=1)
        n.tag_configure("bloco_borda", background=tema.ABISSO, font=(tema.FAMILIA, 3),
                        lmargin1=14, rmargin=14)
        n.tag_configure("citacao", foreground=tema.TEXTO_FRACO, lmargin1=10,
                        lmargin2=22, spacing1=2, spacing3=8)
        n.tag_configure("marca_citacao", foreground=tema.BORDA_FORTE)
        n.bind("<Configure>", self._redesenhar_se_mudou, add="+")
        self.notas.configure(state="disabled")

        # ---- o andamento do download --------------------------------------
        self.quadro_download = ttk.Frame(quadro)
        self.barra = ttk.Progressbar(self.quadro_download, mode="determinate",
                                     maximum=1000)
        self.barra.pack(fill="x")
        linha = ttk.Frame(self.quadro_download)
        linha.pack(fill="x", pady=(4, 0))
        self.quanto = ttk.Label(linha, text="")
        self.quanto.pack(side="left")
        self.ritmo = ttk.Label(linha, text="", style="Fraco.TLabel")
        self.ritmo.pack(side="right")

        # ---- rodape ---------------------------------------------------------
        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(12, 0))
        self.auto = tk.BooleanVar(value=_automatica())
        ttk.Checkbutton(rodape, variable=self.auto,
                        text=t("Procurar sozinho ao abrir o programa"),
                        command=self._mudou_auto).pack(side="left")
        self.botao_fechar = ttk.Button(rodape, text=t("Fechar"),
                                       command=self.fechar)
        self.botao_fechar.pack(side="right")
        self.botao_pagina = ttk.Button(rodape, text=t("Ver no GitHub"),
                                       command=self.ver_pagina)
        self.botao_pagina.pack(side="right", padx=(0, 6))
        self.botao_acao = ttk.Button(rodape, text=t("Procurar de novo"),
                                     style="Primario.TButton",
                                     command=self.procurar)
        self.botao_acao.pack(side="right", padx=(0, 6))

    # ---- estados ----------------------------------------------------------
    def _mudou_auto(self):
        motor.gravar_opcao(SECAO, "automatica",
                           "sim" if self.auto.get() else "nao")

    def procurar(self):
        self.titulo.configure(text=t("Procurando atualizações…"))
        self.botao_acao.configure(state="disabled")
        self._escrever_notas([])

        def trabalho():
            try:
                achado, erro = l2atualizar.procurar(), None
            except Exception as e:                  # noqa: BLE001
                achado, erro = None, e
            try:
                self.topo.after(0, self._fim_da_busca, achado, erro)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=trabalho, daemon=True).start()

    def _fim_da_busca(self, achado, erro):
        if erro is not None:
            self.titulo.configure(text=t("Não deu para consultar o GitHub"))
            self.subtitulo.configure(text=str(erro))
            self.botao_acao.configure(text=t("Tentar de novo"), state="normal",
                                      command=self.procurar)
            return
        motor.gravar_opcao(SECAO, "ultima_busca", date.today().isoformat())
        self.mostrar(achado)

    def mostrar(self, achado):
        self.achado = achado
        atual = l2atualizar.texto_da_versao(achado["atual"])
        alvo = achado.get("alvo")
        if alvo:
            anexo = alvo["instalador"]
            self.titulo.configure(text=t("Nova versão %s disponível")
                                  % alvo["texto"])
            self.subtitulo.configure(
                text=t("Versão instalada: %s  ·  publicada em %s  ·  "
                       "download de %s")
                % (atual, alvo["data"] or "?",
                   l2atualizar.tamanho(anexo["tamanho"])))
            self.botao_acao.configure(text=t("Baixar e instalar"),
                                      state="normal", command=self.baixar)
            self._escrever_notas(achado["novas"])
            if self.botao is not None:
                _marcar_botao(self.botao, alvo["texto"])
            return
        ultima = achado.get("ultima")
        self.titulo.configure(text=t("Você está na versão mais recente"))
        self.subtitulo.configure(text=t("Versão instalada: %s") % atual)
        self.botao_acao.configure(text=t("Procurar de novo"), state="normal",
                                  command=self.procurar)
        self._escrever_notas([ultima] if ultima else [])
        if self.botao is not None:
            try:
                self.botao.configure(text=texto_do_botao(), style="TButton")
            except tk.TclError:
                pass

    # ---- as notas ---------------------------------------------------------
    def _escrever_notas(self, releases):
        """
        O texto da release, que é Markdown, desenhado como o GitHub mostra.

        Sem biblioteca de Markdown: as notas usam título, parágrafo, lista
        (com ou sem número), negrito, itálico, `código`, bloco de código,
        tabela, citação e linha divisória -- e é isso que se desenha. A
        tabela vira uma grade de verdade, embutida no texto, com cabeçalho,
        bordas e quebra de linha dentro da célula.
        """
        self._releases = list(releases)
        caixa = self.notas
        largura = max(caixa.winfo_width(), 560)
        self._largura_desenhada = largura
        for embutido in getattr(self, "_embutidos", []):
            try:
                embutido.destroy()
            except tk.TclError:
                pass
        self._embutidos = []
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        for n, release in enumerate(self._releases):
            if n:
                self._regra(largura)
            caixa.insert("end", t("Versão %s") % release["texto"] + "\n", "versao")
            if release.get("data"):
                caixa.insert("end", t("publicada em %s") % release["data"] + "\n", "data")
            for bloco in _blocos(release.get("notas") or t("(sem notas)")):
                self._bloco(bloco, largura)
        caixa.configure(state="disabled")
        caixa.yview_moveto(0)

    def _bloco(self, bloco, largura):
        caixa = self.notas
        tipo = bloco[0]
        if tipo == "titulo":
            nivel, texto = bloco[1], bloco[2]
            self._inline(texto, ("h1" if nivel <= 2 else "h",))
            caixa.insert("end", "\n", ("h1" if nivel <= 2 else "h",))
        elif tipo == "par":
            self._inline(bloco[1], ("par",))
            caixa.insert("end", "\n", ("par",))
        elif tipo == "item":
            nivel, marca, texto = bloco[1], bloco[2], bloco[3]
            tag = "item%d" % min(nivel, 3)
            simbolo = marca if marca[0].isdigit() else ("•", "◦", "▪", "▪")[min(nivel, 3)]
            caixa.insert("end", simbolo + "  ", (tag, "marca"))
            self._inline(texto, (tag,))
            caixa.insert("end", "\n", (tag,))
        elif tipo == "codigo":
            caixa.insert("end", "\n", ("bloco_borda",))
            caixa.insert("end", bloco[1] + "\n", ("bloco",))
            caixa.insert("end", "\n", ("bloco_borda",))
        elif tipo == "citacao":
            caixa.insert("end", "▎ ", ("citacao", "marca_citacao"))
            self._inline(bloco[1], ("citacao",))
            caixa.insert("end", "\n", ("citacao",))
        elif tipo == "regra":
            self._regra(largura)
        elif tipo == "tabela":
            self._tabela(bloco[1], bloco[2], bloco[3], largura)

    def _regra(self, largura):
        linha = tk.Frame(self.notas, height=1, width=largura - 40,
                         background=tema.BORDA_FORTE)
        self._embutidos.append(linha)
        self.notas.window_create("end", window=linha, pady=8)
        self.notas.insert("end", "\n")

    def _tabela(self, cabecalho, alinhamentos, linhas, largura):
        """
        A tabela como uma grade de rótulos, embutida no Text.

        A largura de cada coluna parte do texto mais comprido dela; se a
        soma passa da janela, as colunas largas encolhem e o texto quebra
        dentro da célula -- como o GitHub faz.
        """
        import tkinter.font as tkfont
        fonte = tkfont.Font(font=tema.CORPO)
        forte = tkfont.Font(font=tema.CORPO_FORTE)
        fixa = tkfont.Font(font=tema.FIXA)
        n = max([len(cabecalho)] + [len(l) for l in linhas])
        cab = (cabecalho + [""] * n)[:n]
        corpo = [(l + [""] * n)[:n] for l in linhas]

        def medida(texto, cabeca=False):
            # cada celula medida na fonte em que vai ser desenhada
            if re.fullmatch(r"`[^`]+`", texto.strip()):
                return fixa.measure(_sem_marcas(texto))
            if cabeca or re.fullmatch(r"\*\*.+\*\*", texto.strip()):
                return forte.measure(_sem_marcas(texto))
            return fonte.measure(_sem_marcas(texto))

        natural = []
        for c in range(n):
            medidas = [medida(cab[c], True)] + [medida(l[c]) for l in corpo]
            natural.append(max(medidas + [30]) + 20)
        disponivel = largura - 60
        larguras = list(natural)
        while sum(larguras) > disponivel:
            maior = max(range(n), key=lambda k: larguras[k])
            if larguras[maior] <= 90:
                break
            larguras[maior] -= 10

        grade = tk.Frame(self.notas, background=tema.BORDA)
        self._embutidos.append(grade)
        rolar = lambda e: self.notas.yview_scroll(int(-e.delta / 120), "units")
        for r, valores in enumerate([cab] + corpo):
            for c in range(n):
                texto = valores[c]
                inteiro_codigo = bool(re.fullmatch(r"`[^`]+`", texto.strip()))
                fundo = tema.ELEVADO if r == 0 else (tema.PAINEL if r % 2 else tema.FUNDO)
                rotulo = tk.Label(
                    grade, text=_sem_marcas(texto), justify="left",
                    anchor={"e": "e", "center": "center"}.get(
                        alinhamentos[c] if c < len(alinhamentos) else "w", "w"),
                    wraplength=larguras[c] - 16, background=fundo,
                    foreground=(tema.OURO_CLARO if inteiro_codigo else tema.TEXTO),
                    font=(tema.CORPO_FORTE if r == 0 or re.fullmatch(r"\*\*.+\*\*", texto.strip())
                          else tema.FIXA if inteiro_codigo else tema.CORPO),
                    padx=8, pady=4)
                rotulo.grid(row=r, column=c, sticky="nsew",
                            padx=(1 if c == 0 else 0, 1), pady=(1 if r == 0 else 0, 1))
                rotulo.bind("<MouseWheel>", rolar)
        for c in range(n):
            grade.grid_columnconfigure(c, minsize=larguras[c])
        grade.bind("<MouseWheel>", rolar)
        self.notas.window_create("end", window=grade, padx=4, pady=6)
        self.notas.insert("end", "\n")

    def _redesenhar_se_mudou(self, _evento=None):
        """A janela mudou de largura: as tabelas acompanham."""
        if not getattr(self, "_releases", None):
            return
        largura = self.notas.winfo_width()
        if abs(largura - getattr(self, "_largura_desenhada", largura)) < 40:
            return
        marcado = getattr(self, "_redesenho", None)
        if marcado:
            self.topo.after_cancel(marcado)

        def refazer():
            onde = self.notas.yview()[0]
            self._escrever_notas(self._releases)
            self.notas.yview_moveto(onde)
        self._redesenho = self.topo.after(250, refazer)

    def _inline(self, texto, base):
        """**negrito**, *itálico*, `código` e [rótulo](link) -> só o rótulo."""
        texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
        for pedaco in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|(?<![\w*])\*[^*\s][^*]*\*(?!\w))",
                               texto):
            if not pedaco:
                continue
            if pedaco.startswith("**") and pedaco.endswith("**"):
                # o negrito pode ter `codigo` dentro, como o GitHub aceita
                for parte in re.split(r"(`[^`]+`)", pedaco[2:-2]):
                    if parte.startswith("`") and parte.endswith("`") and len(parte) > 2:
                        self.notas.insert("end", parte[1:-1], base + ("codigo",))
                    elif parte:
                        self.notas.insert("end", parte, base + ("forte",))
            elif pedaco.startswith("*") and pedaco.endswith("*") and len(pedaco) > 2:
                self.notas.insert("end", pedaco[1:-1], base + ("italico",))
            elif pedaco.startswith("`") and pedaco.endswith("`"):
                self.notas.insert("end", pedaco[1:-1], base + ("codigo",))
            else:
                self.notas.insert("end", pedaco, base)

    # ---- o download ---------------------------------------------------------
    def baixar(self):
        alvo = (self.achado or {}).get("alvo")
        if not alvo:
            return
        self.baixando = True
        self.cancelar.clear()
        self.quadro_download.pack(fill="x", pady=(10, 0),
                                  before=self.botao_acao.master)
        self.barra.configure(value=0)
        self.quanto.configure(text=t("começando…"))
        self.ritmo.configure(text="")
        self.botao_acao.configure(text=t("Cancelar"), style="Perigo.TButton",
                                  command=self._pedir_cancelamento)
        self.titulo.configure(text=t("Baixando a versão %s…") % alvo["texto"])

        def progresso(baixados, total, velocidade):
            try:
                self.topo.after(0, self._andou, baixados, total, velocidade)
            except (tk.TclError, RuntimeError):
                pass

        def trabalho():
            try:
                caminho, erro = l2atualizar.baixar(
                    alvo["instalador"], progresso, self.cancelar), None
            except Exception as e:                  # noqa: BLE001
                caminho, erro = None, e
            try:
                self.topo.after(0, self._fim_do_download, caminho, erro)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=trabalho, daemon=True).start()

    def _andou(self, baixados, total, velocidade):
        if total:
            self.barra.configure(value=1000.0 * baixados / total)
            self.quanto.configure(text=t("%s de %s  (%d%%)") % (
                l2atualizar.tamanho(baixados), l2atualizar.tamanho(total),
                100 * baixados // total))
        else:
            self.quanto.configure(text=l2atualizar.tamanho(baixados))
        if velocidade > 0:
            falta = (total - baixados) / velocidade if total else 0
            self.ritmo.configure(text=t("%s/s  ·  faltam %s · %s") % (
                l2atualizar.tamanho(velocidade), l2atualizar.tamanho(
                    max(0, total - baixados)), l2atualizar.duracao(falta)))

    def _pedir_cancelamento(self):
        self.cancelar.set()
        self.botao_acao.configure(state="disabled")
        self.quanto.configure(text=t("cancelando…"))

    def _fim_do_download(self, caminho, erro):
        self.baixando = False
        self.botao_acao.configure(style="Primario.TButton", state="normal")
        if isinstance(erro, l2atualizar.Cancelado):
            self.quadro_download.pack_forget()
            self.mostrar(self.achado)
            return
        if erro is not None:
            self.titulo.configure(text=t("O download não terminou"))
            self.quanto.configure(text=str(erro))
            self.ritmo.configure(text="")
            self.botao_acao.configure(text=t("Tentar de novo"),
                                      command=self.baixar)
            return
        self.instalador = caminho
        self.barra.configure(value=1000)
        self.titulo.configure(text=t("Pronto para instalar"))
        self.quanto.configure(text=t("Baixado e conferido (tamanho e SHA-256)."))
        self.ritmo.configure(text="")
        self.botao_acao.configure(text=t("Instalar agora"),
                                  command=self.instalar)
        self.instalar()

    # ---- a instalação -------------------------------------------------------
    def instalar(self):
        if self.instalador is None:
            return
        ocupado = getattr(self.raiz, "ha_trabalho", None)
        if callable(ocupado) and ocupado():
            messagebox.showwarning(
                t("Há trabalho em andamento"),
                t("Uma aba ainda está trabalhando. Espere terminar e clique "
                  "em Instalar agora."), parent=self.topo)
            return
        empacotado = l2atualizar.empacotado()
        if empacotado:
            onde = l2atualizar.pasta_instalada()
            aviso = t("O L2PackTool vai fechar, instalar a versão nova e "
                      "abrir de novo sozinho. As suas configurações e os "
                      "seus projetos ficam como estão.")
            if onde is None:
                aviso += "\n\n" + t("Esta cópia não foi instalada pelo "
                                    "instalador; a versão nova vai para a "
                                    "pasta padrão (%s).") % (
                    r"%LocalAppData%\Programs\L2PackTool")
        else:
            aviso = t("Rodando pelo código-fonte: o instalador vai abrir, e "
                      "este programa continua aberto.")
        if not messagebox.askokcancel(t("Instalar a atualização"), aviso,
                                      parent=self.topo):
            return
        try:
            l2atualizar.instalar(self.instalador)
        except Exception as e:                      # noqa: BLE001
            messagebox.showerror(t("Não deu para abrir o instalador"), str(e),
                                 parent=self.topo)
            return
        if empacotado:
            # O instalador precisa do .exe livre. Sair ja, sem a pergunta de
            # "ha trabalho em andamento" -- isso foi conferido acima.
            self.raiz.after(400, self._sair_para_instalar)

    def _sair_para_instalar(self):
        """
        Fecha a janela E o processo.

        So o `destroy` nao basta: qualquer linha de execucao que nao seja
        daemon segura o Python vivo depois que a janela some, e um processo
        sem janela segurando o .exe faz o instalador desistir -- o usuario ve
        o programa fechar e nada instalar.
        """
        try:
            self.raiz.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    # ---- o resto -------------------------------------------------------------
    def ver_pagina(self):
        alvo = (self.achado or {}).get("alvo") or (self.achado or {}).get("ultima")
        webbrowser.open((alvo or {}).get("pagina") or l2atualizar.PAGINA)

    def fechar(self):
        if self.baixando:
            if not messagebox.askyesno(
                    t("Cancelar o download?"),
                    t("O download ainda está em andamento. Cancelar e fechar?"),
                    parent=self.topo):
                return
            self.cancelar.set()
        if self in _ABERTA:
            _ABERTA.remove(self)
        self.topo.destroy()
