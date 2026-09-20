#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O manual do programa: uma janela so, com o indice a esquerda.

A dica de canto de tela responde "o que e este campo". O manual responde "o que
eu faco agora" -- e uma coisa nao substitui a outra.

Antes cada aba abria o seu proprio manual, e nao havia como ler o do vizinho
sem sair da aba em que se estava. Quem procura uma coisa sem saber em que tela
ela mora -- e e assim que se procura -- nao tinha por onde comecar. Agora e uma
janela com todas as paginas listadas: o botao do cabecalho abre no inicio, o de
cada aba abre ja naquela pagina.

## O texto nao mora no codigo

Ele fica em `recursos/manual/<assunto>.<idioma>.md`. Um manual tem milhares de
palavras: como frase traduzivel ele inflaria o arquivo de idioma, que existe
para rotulo de botao. E um manual errado se conserta trocando um arquivo, sem
recompilar nada.

Faltando o arquivo do idioma escolhido, vale o portugues -- melhor ler noutra
lingua do que abrir uma janela vazia.

## O que a janela sabe desenhar

Um subconjunto pequeno de Markdown, escolhido pelo que os manuais usam de
fato: titulo, negrito, trecho de codigo, bloco de codigo, lista, tabela,
citacao e regua. Nao e um renderizador de Markdown -- sao trinta linhas de
marcacao contra uma dependencia nova.
"""

import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import ajuda
import idioma
import motor
import tema
from idioma import t, N_

PASTA = "recursos/manual"

# O indice, na ordem em que as abas aparecem no programa. O primeiro item de
# cada par e o nome do arquivo; o segundo, como ele se chama na lista.
#
# Manter a ordem igual a das abas nao e capricho: quem procura uma pagina
# procura pela posicao que ela ocupa na cabeca, e na cabeca ela ocupa a
# posicao em que esta na tela.
PAGINAS = (
    ("comecando", N_("Começando")),
    ("projetos", N_("Projetos")),
    ("texturas", N_("Texture Upscaler")),
    ("npc", N_("NPC")),
    ("mundo", N_("NPC — lado do servidor")),
    ("video", N_("Lobby Vídeo")),
    ("itens", N_("Itens")),
    ("skills", N_("Habilidades")),
    ("glow", N_("Glow")),
    ("multisell", N_("Multisell")),
    ("mob", N_("Mob")),
    ("conferir", N_("Conferir Cliente")),
    ("l2crypt", N_("L2Crypt")),
    # A ultima porque nao e uma aba: e o outro jeito de usar o
    # programa, para quem quer fazer em lote o que a tela faz um a um.
    ("cli", N_("Linha de comando")),
)


def caminho(assunto, codigo=None):
    """O arquivo do manual no idioma pedido, ou o portugues."""
    codigo = codigo or idioma.atual()
    for raiz in (motor.AQUI, motor.BASE):
        pasta = Path(raiz) / PASTA
        for tentativa in (codigo, "pt"):
            arquivo = pasta / ("%s.%s.md" % (assunto, tentativa))
            if arquivo.is_file():
                return arquivo
    return None


def texto_de(assunto, codigo=None):
    arquivo = caminho(assunto, codigo)
    if arquivo is None:
        return None
    return arquivo.read_text(encoding="utf-8")


def paginas_existentes():
    """As paginas do indice que tem arquivo. Devolve [(assunto, rotulo)]."""
    return [(assunto, rotulo) for assunto, rotulo in PAGINAS
            if caminho(assunto) is not None]


def abrir(raiz, assunto=None, titulo=""):
    """
    Mostra o manual, na pagina pedida.

    Devolve a janela, ou None se nao ha manual nenhum instalado. `assunto`
    vazio abre na primeira pagina do indice.
    """
    if not paginas_existentes():
        return None
    return Janela(raiz, assunto, titulo or t("Manual"))


class FiltroDoCampo:
    """O campo de procura, com a mesma cara de um StringVar."""

    def __init__(self, entrada):
        self._entrada = entrada

    def get(self):
        return self._entrada.get()

    def set(self, valor):
        self._entrada.delete(0, "end")
        self._entrada.insert(0, valor)


class Janela:
    # A coluna de texto para de crescer aqui. Linha longa demais cansa de ler,
    # e e por isso que todo site de documentacao trava a largura em vez de
    # espalhar o texto pela tela inteira.
    LARGURA_DO_TEXTO = 92

    def __init__(self, raiz, assunto=None, titulo=""):
        self.paginas = paginas_existentes()
        self.assunto = assunto
        self.atual = 0
        self._itens_do_indice = []

        self.janela = tk.Toplevel(raiz)
        self.janela.title(titulo or t("Manual"))
        self.janela.transient(raiz)
        self.janela.configure(background=tema.ABISSO)
        ajuda.por_icone(self.janela)

        corpo = tk.Frame(self.janela, background=tema.ABISSO)
        corpo.pack(fill="both", expand=True)

        self._montar_indice(corpo)
        self._montar_pagina(corpo)

        self._preparar_estilos()
        self._mostrar(self._indice_de(assunto))

        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        self.janela.bind("<Prior>", lambda _e: self._andar(-1))
        self.janela.bind("<Next>", lambda _e: self._andar(1))
        ajuda.ajustar_a_tela(self.janela, 1080, 680)
        ajuda.centralizar(self.janela)
        self.entrada.focus_set()

    # -- a navegacao da esquerda -------------------------------------------
    def _montar_indice(self, corpo):
        """
        A lista de paginas, como a barra lateral de um site.

        Nao e um Listbox: ele nao aceita marca colorida ao lado do item nem
        muda de cor com o ponteiro em cima, e e disso que vem a sensacao de
        estar navegando em vez de escolher numa caixa.
        """
        lado = tk.Frame(corpo, background=tema.FUNDO, width=228)
        lado.pack(side="left", fill="y")
        lado.pack_propagate(False)

        tk.Label(lado, text=t("MANUAL"), background=tema.FUNDO,
                 foreground=tema.OURO, font=(tema.FAMILIA, 10, "bold"),
                 anchor="w", padx=tema.FOLGA + 4,
                 pady=tema.FOLGA).pack(fill="x")
        tk.Frame(lado, background=tema.BORDA, height=1).pack(fill="x")

        lista = tk.Frame(lado, background=tema.FUNDO)
        lista.pack(fill="both", expand=True, pady=(tema.PERTO, 0))

        for i, (_assunto, rotulo) in enumerate(self.paginas):
            linha = tk.Frame(lista, background=tema.FUNDO)
            linha.pack(fill="x")
            barra = tk.Frame(linha, background=tema.FUNDO, width=3)
            barra.pack(side="left", fill="y")
            texto = tk.Label(linha, text=t(rotulo), background=tema.FUNDO,
                             foreground=tema.TEXTO_FRACO, font=tema.CORPO,
                             anchor="w", padx=tema.FOLGA, pady=6)
            texto.pack(side="left", fill="x", expand=True)

            for alvo in (linha, texto, barra):
                alvo.bind("<Button-1>",
                          lambda _e, n=i: self._mostrar(n))
                alvo.bind("<Enter>", lambda _e, n=i: self._passar(n, True))
                alvo.bind("<Leave>", lambda _e, n=i: self._passar(n, False))
                alvo.configure(cursor="hand2")
            self._itens_do_indice.append((linha, barra, texto))

    def _passar(self, indice, dentro):
        """O item muda de cor com o ponteiro em cima -- menos o que esta em uso."""
        if indice == self.atual:
            return
        linha, barra, texto = self._itens_do_indice[indice]
        fundo = tema.ELEVADO if dentro else tema.FUNDO
        linha.configure(background=fundo)
        barra.configure(background=fundo)
        texto.configure(background=fundo,
                        foreground=tema.TEXTO if dentro else tema.TEXTO_FRACO)

    def _marcar_no_indice(self, indice):
        for i, (linha, barra, texto) in enumerate(self._itens_do_indice):
            em_uso = i == indice
            fundo = tema.PAINEL if em_uso else tema.FUNDO
            linha.configure(background=fundo)
            barra.configure(background=tema.OURO if em_uso else fundo)
            texto.configure(background=fundo,
                            foreground=tema.TEXTO if em_uso else tema.TEXTO_FRACO,
                            font=tema.CORPO_FORTE if em_uso else tema.CORPO)

    # -- a pagina da direita -----------------------------------------------
    def _montar_pagina(self, corpo):
        lado = tk.Frame(corpo, background=tema.PAINEL)
        lado.pack(side="left", fill="both", expand=True)

        # ---- o cabecalho da pagina ----
        topo = tk.Frame(lado, background=tema.PAINEL)
        topo.pack(fill="x", padx=tema.SECAO + 8, pady=(tema.FOLGA, 0))

        self.titulo = tk.Label(topo, text="", background=tema.PAINEL,
                               foreground=tema.TEXTO,
                               font=(tema.FAMILIA, 16, "bold"), anchor="w")
        self.titulo.pack(side="left")

        direita = tk.Frame(topo, background=tema.PAINEL)
        direita.pack(side="right")
        ttk.Button(direita, text=t("Fechar"),
                   command=self.janela.destroy).pack(side="right")
        self.entrada = ttk.Entry(direita, width=24)
        self.entrada.pack(side="right", padx=(0, tema.PERTO))
        self.entrada.bind("<Return>", lambda _e: self.procurar())
        ttk.Button(direita, text=t("Procurar"),
                   command=self.procurar).pack(side="right",
                                               padx=(0, tema.COLADO))
        self.filtro = FiltroDoCampo(self.entrada)

        self.passo = tk.Label(lado, text="", background=tema.PAINEL,
                              foreground=tema.TEXTO_FRACO, font=tema.MIUDO,
                              anchor="w")
        self.passo.pack(fill="x", padx=tema.SECAO + 8, pady=(2, tema.PERTO))

        tk.Frame(lado, background=tema.BORDA, height=1).pack(fill="x")

        # ---- o texto ----
        meio = tk.Frame(lado, background=tema.PAINEL)
        meio.pack(fill="both", expand=True)
        self.texto = tk.Text(meio, width=self.LARGURA_DO_TEXTO, height=30,
                             wrap="word", padx=tema.SECAO + 8, pady=tema.SECAO,
                             borderwidth=0, highlightthickness=0,
                             background=tema.PAINEL, foreground=tema.TEXTO,
                             insertbackground=tema.OURO,
                             selectbackground=tema.OURO_FUNDO,
                             selectforeground=tema.TEXTO,
                             spacing1=2, spacing3=3, cursor="arrow")
        barra = ttk.Scrollbar(meio, orient="vertical", command=self.texto.yview)
        self.texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.texto.pack(side="left", fill="both", expand=True)
        self.texto.bind("<MouseWheel>", self._rolar)

        # ---- o rodape ----
        tk.Frame(lado, background=tema.BORDA, height=1).pack(fill="x")
        pe = tk.Frame(lado, background=tema.PAINEL)
        pe.pack(fill="x", padx=tema.SECAO + 8, pady=tema.PERTO)
        self.botao_antes = ttk.Button(pe, text="\u2039  " + t("Anterior"),
                                      command=lambda: self._andar(-1))
        self.botao_antes.pack(side="left")
        self.botao_depois = ttk.Button(pe, text=t("Próxima") + "  \u203a",
                                       command=lambda: self._andar(1))
        self.botao_depois.pack(side="right")
        self.aviso = tk.Label(pe, text="", background=tema.PAINEL,
                              foreground=tema.TEXTO_FRACO, font=tema.MIUDO)
        self.aviso.pack()

    def _rolar(self, evento):
        self.texto.yview_scroll(-1 * (evento.delta // 120), "units")
        return "break"

    # -- navegar ------------------------------------------------------------
    def _indice_de(self, assunto):
        for i, (nome, _rotulo) in enumerate(self.paginas):
            if nome == assunto:
                return i
        return 0

    def _andar(self, passo):
        self._mostrar(self.atual + passo)

    def _mostrar(self, indice, marcar=True):
        if not self.paginas:
            return
        indice = max(0, min(indice, len(self.paginas) - 1))
        self.atual = indice
        assunto, rotulo = self.paginas[indice]
        self.assunto = assunto

        self._marcar_no_indice(indice)
        self.titulo.config(text=t(rotulo))
        self.passo.config(text=t("página %d de %d")
                          % (indice + 1, len(self.paginas)))
        self.botao_antes.config(state="normal" if indice else "disabled")
        self.botao_depois.config(
            state="disabled" if indice == len(self.paginas) - 1 else "normal")

        conteudo = texto_de(assunto) or ""
        self.texto.config(state="normal")
        self.texto.delete("1.0", "end")
        self._escrever(conteudo)
        self.texto.config(state="disabled")
        self.texto.yview_moveto(0)
        self.aviso.config(text="")

    # -- formatacao ---------------------------------------------------------
    def _preparar_estilos(self):
        t_ = self.texto.tag_configure
        self.texto.configure(font=(tema.FAMILIA, 10))

        # O `# ` da pagina ja virou o titulo do cabecalho; o que sobra sao as
        # secoes, e elas ganham regua propria -- ver `_risco`.
        t_("h2", font=(tema.FAMILIA, 13, "bold"), foreground=tema.OURO,
           spacing1=18, spacing3=4)
        t_("h3", font=(tema.FAMILIA, 10, "bold"), foreground=tema.TEXTO,
           spacing1=12, spacing3=2)
        # O traco e desenhado com um caractere de verdade, e nao com fundo
        # pintado: fundo ocupa a altura inteira da linha, e o que saia era
        # um bloco dourado. Letra desenha so a espessura dela.
        t_("risco", font=(tema.FAMILIA_FIXA, 8), foreground=tema.OURO,
           spacing3=10)

        t_("paragrafo", spacing3=8, lmargin1=0, lmargin2=0)
        t_("forte", font=(tema.FAMILIA, 10, "bold"), foreground=tema.TEXTO)
        t_("codigo", font=(tema.FAMILIA_FIXA, 9), foreground=tema.OURO_CLARO,
           background=tema.ELEVADO)

        t_("bloco", font=(tema.FAMILIA_FIXA, 9), foreground=tema.TEXTO,
           background=tema.ABISSO, lmargin1=tema.SECAO,
           lmargin2=tema.SECAO, spacing1=1, spacing3=1)

        t_("aviso", background=tema.FUNDO_ATENCAO, foreground=tema.TEXTO,
           lmargin1=tema.PERTO, lmargin2=tema.SECAO + 6, spacing1=2,
           spacing3=2)
        t_("barra_aviso", background=tema.FUNDO_ATENCAO,
           foreground=tema.ATENCAO, font=(tema.FAMILIA_FIXA, 10, "bold"))

        t_("item", lmargin1=tema.SECAO, lmargin2=tema.SECAO + 14, spacing3=4)

        t_("tab_cabeca", font=(tema.FAMILIA_FIXA, 9, "bold"),
           foreground=tema.OURO, background=tema.REALCE,
           lmargin1=tema.SECAO, lmargin2=tema.SECAO, spacing1=10, spacing3=3)
        t_("tab_par", font=(tema.FAMILIA_FIXA, 9), foreground=tema.TEXTO,
           background=tema.FUNDO, lmargin1=tema.SECAO, lmargin2=tema.SECAO,
           spacing1=2, spacing3=2)
        t_("tab_impar", font=(tema.FAMILIA_FIXA, 9), foreground=tema.TEXTO,
           background=tema.ELEVADO, lmargin1=tema.SECAO, lmargin2=tema.SECAO,
           spacing1=2, spacing3=2)

        t_("achado", background=tema.OURO, foreground=tema.ABISSO)

    _PEDACOS = re.compile(r"(\*\*[^*]+?\*\*|`[^`]+?`)")
    _MARCAS = re.compile(r"\*\*([^*]+?)\*\*|`([^`]+?)`")

    def _sem_marcacao(self, texto):
        """O texto da celula sem crase nem asterisco, para medir e alinhar."""
        return self._MARCAS.sub(lambda m: m.group(1) or m.group(2), texto)

    _CODIGO = re.compile(r"(`[^`]+?`)")

    def _escrever_pedacos(self, texto, tags):
        """Trecho de codigo dentro do texto -- valendo tambem dentro do negrito."""
        for pedaco in self._CODIGO.split(texto):
            if not pedaco:
                continue
            if pedaco.startswith("`") and pedaco.endswith("`"):
                self.texto.insert("end", pedaco[1:-1], tags + ("codigo",))
            else:
                self.texto.insert("end", pedaco, tags)

    def _escrever_linha(self, linha, tags=()):
        """
        Escreve a linha com a marcacao aplicada, inclusive aninhada.

        O negrito e aberto primeiro, e o que sobra dentro dele passa pelo
        mesmo leitor de codigo: sem isto, `**O `<ai>` e a armadilha**` casava
        inteiro como negrito e as crases apareciam cruas.
        """
        for pedaco in self._PEDACOS.split(linha):
            if not pedaco:
                continue
            if pedaco.startswith("**") and pedaco.endswith("**"):
                self._escrever_pedacos(pedaco[2:-2], tuple(tags) + ("forte",))
            elif pedaco.startswith("`") and pedaco.endswith("`"):
                self.texto.insert("end", pedaco[1:-1], tuple(tags) + ("codigo",))
            else:
                self.texto.insert("end", pedaco, tuple(tags))
        self.texto.insert("end", "\n")

    def _risco(self):
        """
        O traco curto embaixo do titulo de secao.

        A quebra de linha fica FORA da etiqueta: levando a etiqueta, ela
        estenderia o fundo ate a borda da janela.
        """
        self.texto.insert("end", "─" * 10, ("risco",))
        self.texto.insert("end", "\n")

    def _celulas(self, linha):
        return [c.strip() for c in linha.strip().strip("|").split("|")]

    def _e_separador(self, linha):
        """A linha `| --- | --- |` do markdown, que nao se mostra."""
        corpo = linha.strip().strip("|").replace("|", "")
        return bool(corpo) and set(corpo.strip()) <= set("-: ")

    def _escrever_tabela(self, linhas):
        """
        Desenha a tabela alinhada, com cabecalho e linhas alternadas.

        A marcacao sai das celulas ANTES de medir: tirar a crase depois
        mudaria a largura ja calculada, e a coluna sairia torta.
        """
        grade = [[self._sem_marcacao(c) for c in self._celulas(l)]
                 for l in linhas if not self._e_separador(l)]
        if not grade:
            return
        colunas = max(len(l) for l in grade)
        grade = [l + [""] * (colunas - len(l)) for l in grade]
        largura = [max(len(l[c]) for l in grade) for c in range(colunas)]

        for i, celulas in enumerate(grade):
            linha = "  " + "   ".join(
                celula.ljust(largura[c]) for c, celula in enumerate(celulas))
            linha = linha.rstrip()
            if i == 0:
                self.texto.insert("end", linha + "\n", ("tab_cabeca",))
            else:
                marca = "tab_par" if i % 2 else "tab_impar"
                self.texto.insert("end", linha + "\n", (marca,))
        self.texto.insert("end", "\n")

    def _escrever_bloco(self, linhas):
        """A faixa de codigo, com uma linha vazia em cima e outra embaixo."""
        self.texto.insert("end", " \n", ("bloco",))
        for linha in linhas:
            self.texto.insert("end", "  " + linha + "\n", ("bloco",))
        self.texto.insert("end", " \n", ("bloco",))
        self.texto.insert("end", "\n")

    def _escrever_aviso(self, paragrafos):
        """O cartao de aviso: barra colorida a esquerda e fundo proprio."""
        def folga():
            self.texto.insert("end", " \u258c ", ("barra_aviso",))
            self.texto.insert("end", " \n", ("aviso",))

        folga()
        for paragrafo in paragrafos:
            self.texto.insert("end", " \u258c ", ("barra_aviso",))
            if paragrafo.strip():
                self._escrever_linha(paragrafo, ("aviso",))
            else:
                self.texto.insert("end", " \n", ("aviso",))
        folga()
        self.texto.insert("end", "\n")

    def _juntar_paragrafo(self, linhas, i, parar):
        """
        Junta as linhas seguidas num paragrafo so.

        E o que faz o texto refluir na largura da janela, em vez de manter a
        quebra que o arquivo tem. Tambem e o que permite um negrito comecar
        numa linha do arquivo e terminar na outra.

        A PRIMEIRA linha entra sempre: e ela que abre o paragrafo, e um item
        de lista abre com `- `, que o teste de parada considera especial. Sem
        isto, um item devolvia o indice parado e o laco de fora nunca saia do
        lugar.
        """
        juntadas = [linhas[i].strip()]
        i += 1
        while i < len(linhas) and linhas[i].strip() and not parar(linhas[i]):
            juntadas.append(linhas[i].strip())
            i += 1
        return " ".join(juntadas), i

    _ABRE_BLOCO = ("```", "|", ">", "#", "- ", "* ")

    def _e_especial(self, linha):
        return (linha.startswith(self._ABRE_BLOCO)
                or bool(re.match(r"^\d+\. ", linha))
                or (len(linha.strip()) > 2
                    and set(linha.strip()) in ({"-"}, {"="})))

    def _escrever(self, conteudo):
        """
        Passa o texto da pagina para a tela.

        Junta antes o que e bloco -- paragrafo, tabela, codigo, aviso --
        porque cada um deles so pode ser desenhado sabendo onde termina.
        """
        linhas = conteudo.split("\n")
        i = 0
        primeira = True

        while i < len(linhas):
            linha = linhas[i]

            # o `# Titulo` ja esta no cabecalho da pagina
            if primeira and linha.startswith("# "):
                primeira = False
                i += 1
                while i < len(linhas) and not linhas[i].strip():
                    i += 1
                continue
            primeira = False

            if not linha.strip():
                i += 1
                continue

            if linha.startswith("```"):
                i += 1
                juntadas = []
                while i < len(linhas) and not linhas[i].startswith("```"):
                    juntadas.append(linhas[i])
                    i += 1
                self._escrever_bloco(juntadas)
                i += 1
                continue

            if linha.startswith("|"):
                juntadas = []
                while i < len(linhas) and linhas[i].startswith("|"):
                    juntadas.append(linhas[i])
                    i += 1
                self._escrever_tabela(juntadas)
                continue

            if linha.startswith(">"):
                cru = []
                while i < len(linhas) and linhas[i].startswith(">"):
                    corpo = linhas[i][1:]
                    cru.append(corpo[1:] if corpo[:1] == " " else corpo)
                    i += 1
                # dentro do aviso, o paragrafo tambem reflui
                paragrafos, atual = [], []
                for corpo in cru:
                    if corpo.strip() and not self._e_especial(corpo):
                        atual.append(corpo.strip())
                        continue
                    if atual:
                        paragrafos.append(" ".join(atual))
                        atual = []
                    paragrafos.append(corpo)
                if atual:
                    paragrafos.append(" ".join(atual))
                self._escrever_aviso(paragrafos)
                continue

            if linha.startswith("### "):
                self._escrever_linha(linha[4:], ("h3",))
            elif linha.startswith("## ") or linha.startswith("# "):
                corte = 3 if linha.startswith("## ") else 2
                self._escrever_linha(linha[corte:], ("h2",))
                self._risco()
            elif len(linha.strip()) > 2 and set(linha.strip()) in ({"-"}, {"="}):
                pass                    # regua de markdown: nao se mostra
            elif linha.startswith(("- ", "* ")):
                texto, i = self._juntar_paragrafo(
                    linhas, i, lambda l: self._e_especial(l))
                self._escrever_linha("\u2022  " + texto[2:], ("item",))
                continue
            elif re.match(r"^\d+\. ", linha):
                texto, i = self._juntar_paragrafo(
                    linhas, i, lambda l: self._e_especial(l))
                self._escrever_linha(texto, ("item",))
                continue
            else:
                texto, i = self._juntar_paragrafo(
                    linhas, i, lambda l: self._e_especial(l))
                self._escrever_linha(texto, ("paragrafo",))
                continue
            i += 1

    # -- procurar -----------------------------------------------------------
    def procurar(self):
        """
        Procura na pagina aberta e, nao achando, nas outras.

        Quem procura um termo raramente sabe em que pagina ele esta -- e
        justamente por nao saber que esta procurando. Achando noutra pagina, a
        janela pula para ela e marca o termo la.
        """
        alvo = self.filtro.get().strip()
        self.texto.tag_remove("achado", "1.0", "end")
        if not alvo:
            self.aviso.config(text="")
            return

        quantos = self._marcar(alvo)
        if quantos:
            self.aviso.config(text=t("%d achados") % quantos,
                              foreground=tema.TEXTO_FRACO)
            return

        aqui = self._indice_de(self.assunto)
        for passo in range(1, len(self.paginas)):
            outra = (aqui + passo) % len(self.paginas)
            assunto, rotulo = self.paginas[outra]
            if alvo.lower() not in (texto_de(assunto) or "").lower():
                continue
            self._mostrar(outra)
            quantos = self._marcar(alvo)
            self.aviso.config(text=t("%d achados em %s") % (quantos, t(rotulo)),
                              foreground=tema.OURO)
            return
        self.aviso.config(text=t("não achei em nenhuma página"),
                          foreground=tema.ATENCAO)

    def _marcar(self, alvo):
        """Pinta o termo na pagina aberta e devolve quantas vezes achou."""
        quantos, onde = 0, "1.0"
        while True:
            onde = self.texto.search(alvo, onde, nocase=True, stopindex="end")
            if not onde:
                break
            fim = "%s+%dc" % (onde, len(alvo))
            self.texto.tag_add("achado", onde, fim)
            if quantos == 0:
                self.texto.see(onde)
            quantos += 1
            onde = fim
        return quantos
