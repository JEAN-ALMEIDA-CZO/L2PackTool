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


def _paragrafos(texto):
    """
    As linhas do Markdown com cada parágrafo numa linha só.

    O texto da release é quebrado à mão a cada 80 colunas, como o CHANGELOG.
    O GitHub junta essas linhas; a janela também precisa juntar, senão o
    parágrafo sai picotado no meio da frase. Título, item de lista, tabela e
    linha em branco começam linha nova; o resto continua a anterior.
    """
    saida = []
    for linha in texto.split("\n"):
        crua = linha.rstrip()
        especial = (not crua.strip()
                    or re.match(r"^\s*(#{1,6}\s|[-*+]\s|\||---\s*$|```|>)", crua))
        if saida and not especial and saida[-1].strip() and \
                not saida[-1].lstrip().startswith(("#", "|", "```")) and \
                saida[-1].strip() != "---":
            saida[-1] = saida[-1] + " " + crua.strip()
        else:
            saida.append(crua)
    return saida


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
        self.notas.tag_configure("versao", font=tema.TITULO,
                                 foreground=tema.OURO, spacing1=6, spacing3=4)
        self.notas.tag_configure("data", font=tema.MIUDO,
                                 foreground=tema.TEXTO_FRACO, spacing3=6)
        self.notas.tag_configure("h", font=tema.SUBTITULO,
                                 foreground=tema.TEXTO, spacing1=8, spacing3=2)
        self.notas.tag_configure("item", lmargin1=8, lmargin2=22, spacing1=1)
        self.notas.tag_configure("forte", font=tema.CORPO_FORTE)
        self.notas.tag_configure("codigo", font=tema.FIXA,
                                 foreground=tema.OURO_CLARO)
        self.notas.tag_configure("italico", font=(tema.FAMILIA, 9, "italic"))
        self.notas.tag_configure("tabela", font=tema.FIXA,
                                 foreground=tema.TEXTO_FRACO)
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
        O texto da release, que é Markdown, num Text com estilo.

        Sem biblioteca de Markdown: as notas usam título, lista, negrito e
        `código`, e é só isso que se desenha. O resto sai como texto.
        """
        caixa = self.notas
        caixa.configure(state="normal")
        caixa.delete("1.0", "end")
        for release in releases:
            caixa.insert("end", t("Versão %s") % release["texto"] + "\n",
                         "versao")
            if release.get("data"):
                caixa.insert("end", t("publicada em %s") % release["data"]
                             + "\n", "data")
            for linha in _paragrafos(release.get("notas") or t("(sem notas)")):
                self._linha(linha)
            caixa.insert("end", "\n")
        caixa.configure(state="disabled")
        caixa.yview_moveto(0)

    def _linha(self, linha):
        caixa = self.notas
        crua = linha.rstrip()
        titulo = re.match(r"^\s*#{1,6}\s+(.*)$", crua)
        item = re.match(r"^(\s*)[-*+]\s+(.*)$", crua)
        if crua.strip() == "---":
            return
        if crua.lstrip().startswith("|"):
            # Tabela: a linha de tracos some, e cada linha vira as celulas
            # lado a lado, em fonte fixa para as colunas se alinharem.
            celulas = [c.strip() for c in crua.strip().strip("|").split("|")]
            if all(re.match(r"^:?-{2,}:?$", c) for c in celulas if c):
                return
            caixa.insert("end", "   " + "  │  ".join(
                re.sub(r"\*\*|`", "", c).ljust(14) for c in celulas).rstrip()
                + "\n", ("tabela",))
            return
        if titulo:
            self._inline(titulo.group(1), ("h",))
            caixa.insert("end", "\n")
        elif item:
            nivel = len(item.group(1).expandtabs(4)) // 2
            caixa.insert("end", "    " * nivel + "•  ", ("item",))
            self._inline(item.group(2), ("item",))
            caixa.insert("end", "\n", ("item",))
        else:
            self._inline(crua, ())
            caixa.insert("end", "\n")

    def _inline(self, texto, base):
        """**negrito**, `código` e [rótulo](link) -> só o rótulo."""
        texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
        for pedaco in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|(?<![\w*])\*[^*\s][^*]*\*(?!\w))",
                               texto):
            if not pedaco:
                continue
            if pedaco.startswith("**") and pedaco.endswith("**"):
                self.notas.insert("end", pedaco[2:-2], base + ("forte",))
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
            self.raiz.after(400, self.raiz.destroy)

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
