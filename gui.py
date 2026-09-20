#!/usr/bin/env python3
"""
Interface grafica do L2PackTool.

Usa tkinter, que acompanha o Python -- nenhuma dependencia a mais no
executavel. O trabalho pesado fica no motor.py; aqui so ha a janela.

Dois modos, escolhidos pelo que o usuario seleciona:

  UM pacote  -> abre o navegador de texturas: extrai, mostra as miniaturas com
                caixa de selecao, e amplia so as marcadas
  VARIOS     -> lote direto, sem previa, porque examinar centenas de texturas
                uma a uma nao seria util

O processamento roda em thread separada. Sem isso a janela congelaria durante
os minutos que o Upscayl leva, e o Windows a marcaria como "nao respondendo".
"""

import os
import queue
import shutil
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import tema
import ajuda
import rolagem
import idioma
from idioma import t, N_
import motor

RECURSOS = motor.AQUI / "recursos"

MODELO_PADRAO = "upscayl-standard-4x"

# Resumo de cada modelo. As caracteristicas foram medidas rodando os sete na
# mesma textura de pedra do cliente (nitidez por energia de borda, ruido por
# desvio do detalhe fino) e conferidas a olho.
#
# N_ nao traduz nada: so marca a frase para entrar no catalogo. A tabela e
# montada na importacao, antes de o idioma ser escolhido, entao quem traduz de
# verdade e o t() la no descrever_modelo.
DESCRICOES = {
    "upscayl-standard-4x":
        N_("Equilibrado. O padrão do Upscayl e o melhor ponto de partida."),
    "high-fidelity-4x":
        N_("O mais conservador: menos nitidez e menos ruido inventado. Bom para "
           "pele, rosto e superficies lisas; amacia demais pedra e tecido."),
    "remacri-4x":
        N_("O mais nitido, e o que mais inventa grao. Bom para pedra, metal e "
           "tecido; exagera em superficies que deveriam ser lisas."),
    "ultramix-balanced-4x":
        N_("Entre o remacri e o padrão, com contraste mais alto. Boa escolha "
           "quando o padrão ficou apagado demais."),
    "ultrasharp-4x":
        N_("Bordas duras. Bom para interface e ícones; em terreno marca a costura "
           "entre tiles, justamente onde o jogador mais anda."),
    "digital-art-4x":
        N_("Para arte desenhada e cores chapadas: ícones, retratos, cartazes. "
           "Em textura fotografica achata o material."),
    "upscayl-lite-4x":
        N_("O mais rapido e o que menos acrescenta detalhe. Util para lotes "
           "grandes ou para uma primeira passada de avaliacao."),
}

# As ferramentas de cada aba. A de NPC declara as dela em gui_npc.
PRECISA_TEXTURA = ("l2encdec", "umodel", "upscayl", "texconv", "ucc", "modelos")

LADO_MINIATURA = 96
COLUNAS = 6

# Quanto do tempo total e gasto ampliando. Medido: uma textura 512x512 em 2x
# leva ~80 s numa Intel HD 620, enquanto descriptografar, comprimir, remontar e
# criptografar o pacote inteiro somam poucos segundos. Dar 88% da barra ao
# upscale e o que faz o desenho corresponder ao relogio -- com pesos iguais por
# etapa, a barra ficava quase parada em 20% durante horas e depois pulava.
PESO_AMPLIAR = 0.88

# Simbolo que gira a cada quadro. Enquanto o upscayl trabalha numa textura de
# 1024 nao ha nada a reportar por dezenas de segundos; sem algo se mexendo a
# janela e indistinguivel de uma travada.
GIRO = ("|", "/", "-", chr(92))


def caminho_do_registro():
    """
    Onde gravar o que deu errado.

    Ao lado do executavel, que e onde o usuario vai procurar. Se a pasta for
    somente leitura -- Arquivos de Programas, por exemplo -- cai no temporario
    do sistema, porque um log inacessivel e o mesmo que log nenhum.
    """
    try:
        alvo = motor.BASE / "erros.log"
        with open(alvo, "a", encoding="utf-8"):
            pass
        return alvo
    except OSError:
        import tempfile
        return Path(tempfile.gettempdir()) / "L2PackTool-erros.log"


class _Eco:
    """Saida que escreve no arquivo de registro. Nunca levanta."""

    def __init__(self, arquivo):
        self.arquivo = arquivo

    def write(self, texto):
        try:
            with open(self.arquivo, "a", encoding="utf-8", errors="replace") as f:
                f.write(texto)
        except OSError:
            pass
        return len(texto)

    def flush(self):
        pass

    def isatty(self):
        return False


def instalar_rede(raiz):
    """
    Impede que um erro feche a janela sem dizer nada.

    Sem isto, qualquer excecao dentro de um callback do Tk mata o processo no
    executavel congelado: o tratador padrao escreve o traceback em
    `sys.stderr`, que ali e None, e a falha dentro do tratador nao tem quem a
    pegue. O sintoma e a janela desaparecer no meio de uma operacao.
    """
    registro = caminho_do_registro()

    # Em modo janela as duas sao None; em modo console ficam como estao.
    if sys.stdout is None:
        sys.stdout = _Eco(registro)
    if sys.stderr is None:
        sys.stderr = _Eco(registro)

    def contar(titulo, erro):
        texto = "".join(traceback.format_exception(type(erro), erro,
                                                   erro.__traceback__))
        carimbo = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(registro, "a", encoding="utf-8", errors="replace") as f:
                f.write("\n=== %s  %s ===\n%s" % (carimbo, titulo, texto))
        except OSError:
            pass

        try:
            messagebox.showerror(
                titulo,
                t("%s: %s\n\nO detalhe completo esta em:\n%s")
                % (type(erro).__name__, erro, registro))
        except Exception:
            pass        # se nem a janela de erro abre, ao menos o log ficou

    def de_callback(_tipo, valor, _tb):
        contar(t("Erro na interface"), valor)

    raiz.report_callback_exception = de_callback

    def de_thread(dados):
        if dados.exc_type is SystemExit:
            return
        contar(t("Erro em segundo plano"), dados.exc_value)

    threading.excepthook = de_thread
    return registro


def _contar_formatos(inventario):
    """Quantas texturas de cada formato, so para a linha do registro."""
    contagem = {}
    for dados in inventario.values():
        marca = dados.get("formato", "?").replace("TEXF_", "")
        contagem[marca] = contagem.get(marca, 0) + 1
    return contagem


def duracao(segundos):
    """Tempo em forma curta: 45s, 12min, 2h07min."""
    segundos = int(max(0, segundos))
    if segundos < 60:
        return "%ds" % segundos
    if segundos < 3600:
        return "%dmin" % (segundos // 60)
    return "%dh%02dmin" % (segundos // 3600, (segundos % 3600) // 60)


def listar_modelos(pasta_modelos):
    """
    Modelos lidos da PASTA, nao de uma lista fixa.

    Cada modelo e um par .param + .bin. Fixar os nomes a mao ja custou caro: a
    lista anterior tinha seis e omitia justamente o upscayl-standard-4x, que e
    o padrao do Upscayl.
    """
    try:
        nomes = sorted({p.stem for p in Path(pasta_modelos).glob("*.param")})
    except Exception:
        nomes = []
    if not nomes:
        return [MODELO_PADRAO]
    if MODELO_PADRAO in nomes:
        nomes.remove(MODELO_PADRAO)
        nomes.insert(0, MODELO_PADRAO)
    return nomes


class Janela:
    def __init__(self, raiz, pai=None):
        # `raiz` continua sendo a janela -- e dela o title, o icone e o
        # after() que traz as threads de volta. `pai` e onde os controles sao
        # desenhados, que desde as abas nao e mais a janela inteira.
        self.raiz = raiz
        pai = raiz if pai is None else pai

        self.arquivos = []
        self.texturas = []          # [{caminho, var, foto, largura, altura, substituta}]

        # Formato, tamanho e uso de alfa de cada textura do pacote aberto, lido
        # do proprio .utx. E o que impede o programa de devolver tudo em BC3:
        # uma textura que era DXT1 volta DXT1, e uma que tinha alfa continua
        # tendo. Ver motor.inventario.
        self.formatos = {}

        # Textura em foco no painel de propriedades. Selecionar e clicar na
        # miniatura; a caixa de marcacao continua sendo so "amplia ou nao".
        self.selecionada = None
        self.pacote_atual = None    # Path do pacote aberto no navegador
        self.base_trabalho = None
        self.estava_cifrado = False
        self.fila = queue.Queue()
        self.rodando = False

        # Progresso em duas variaveis: `alvo` e escrito pela thread de
        # trabalho, `valor` e o que esta desenhado. O laco de 120 ms move o
        # segundo em direcao ao primeiro. Escrever direto na barra a partir da
        # thread faria a agulha SALTAR de um percentual do upscayl para o
        # seguinte e ficar imovel entre eles -- que e exatamente a impressao de
        # travado que se quer evitar.
        self.alvo_barra = 0.0
        self.valor_barra = 0.0
        self.estado_texto = ""
        self.giro = 0
        self.img_inicio = 0.0

        # Fatia da barra que o pacote atual ocupa: (0, 1) num pacote so,
        # ((i-1)/N, 1/N) durante um lote.
        self.faixa_ini = 0.0
        self.faixa_tam = 1.0

        # Contabilidade da fase de upscale, para a previsao de termino.
        self.ampliar_inicio = 0.0
        self.ampliar_feitas = 0.0
        self.ampliar_total = 0

        try:
            # `default=` faz toda janela filha nascer com este icone. Sem ele,
            # cada janela nova precisa lembrar de pedir o seu -- e uma que
            # esquecesse aparecia com a pena do Tk, parecendo de outro
            # programa.
            raiz.iconbitmap(default=str(RECURSOS / "icone.ico"))
        except Exception:
            pass

        self.T = motor.carregar_config()
        self.modelos = listar_modelos(self.T.get("modelos", ""))
        modelo_salvo, escala_salva = motor.ler_preferencias(MODELO_PADRAO)

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        # A marca fica no cabecalho, e so la: ela ja aparece no topo de toda
        # aba. Repetida no meio desta, roubava a primeira tela de altura util
        # sem dizer nada que o cabecalho ja nao dissesse.

        # ---- o selo de beta ----
        # A ampliacao depende de um programa de fora (o upscayl) e de modelos
        # que mudam de versao para versao: o resultado varia com a maquina e
        # com o modelo escolhido. Dizer isso na cara da pagina evita que o
        # usuario descubra sozinho depois de ampliar um acervo inteiro.
        faixa = tk.Frame(quadro, background=tema.FUNDO_ATENCAO)
        faixa.pack(fill="x", pady=(0, 8))
        tk.Label(faixa, text=" BETA ", background=tema.ATENCAO,
                 foreground=tema.ABISSO, font=tema.MIUDO).pack(
                     side="left", padx=8, pady=5)
        tk.Label(faixa, background=tema.FUNDO_ATENCAO, foreground=tema.ATENCAO,
                 font=tema.CORPO, justify="left",
                 text=t("Em testes. Comece por um pacote só e entre no jogo "
                        "antes de ampliar o acervo inteiro.")).pack(
                            side="left", padx=(0, 8))

        # ---- selecao ----
        sel = ttk.LabelFrame(quadro, text=t("Pacote"), padding=8)
        sel.pack(fill="x")
        ttk.Button(sel, text=t("Abrir um .utx…"),
                   command=self.abrir_pacote).pack(side="left")
        ajuda.ajuda(sel, lambda: t(
            "Abre UM pacote e mostra as texturas de dentro dele, uma a uma, "
            "com miniatura.\n\n"
            "É aqui que dá para escolher o que ampliar, trocar uma imagem por "
            "outra e ver as propriedades de cada textura."))

        ttk.Button(sel, text=t("Lote: escolher pasta…"),
                   command=self.escolher_pasta).pack(side="left", padx=(8, 0))
        ajuda.ajuda(sel, lambda: t(
            "Processa TODOS os .utx de uma pasta, sem prévia.\n\n"
            "Amplia todas as texturas de todos os pacotes: não há como "
            "escolher uma a uma. Examinar centenas de miniaturas não seria "
            "útil, mas o custo de memória no cliente também é o de todas.\n\n"
            "Comece por um pacote só e entre no jogo antes de rodar o acervo "
            "inteiro."))
        self.rotulo_sel = ttk.Label(sel, text=t("nenhum pacote aberto"))
        self.rotulo_sel.pack(side="left", padx=(12, 0))

        # ---- opcoes ----
        op = ttk.LabelFrame(quadro, text=t("Opções"), padding=8)
        op.pack(fill="x", pady=(8, 0))

        caixa_escala = ttk.Frame(op)
        caixa_escala.grid(row=0, column=0, sticky="w")
        ttk.Label(caixa_escala, text=t("Escala:")).pack(side="left")
        ajuda.ajuda(caixa_escala, lambda: t(
            "Quantas vezes cada lado da textura cresce.\n\n"
            "2x dá quatro vezes mais pixels; 4x dá dezesseis. O cliente do L2 "
            "é de 32 bits e fecha sozinho quando a memória de textura "
            "estoura -- 2x é o que quase sempre cabe.\n\n"
            "O tamanho continua potência de dois, que é o que o cliente "
            "exige."))

        self.escala = tk.IntVar(value=escala_salva)
        for i, v in enumerate((2, 3, 4)):
            ttk.Radiobutton(op, text=t("%dx") % v, value=v,
                            variable=self.escala).grid(row=0, column=1 + i, padx=4)

        caixa_modelo = ttk.Frame(op)
        caixa_modelo.grid(row=0, column=4, padx=(20, 4), sticky="e")
        ttk.Label(caixa_modelo, text=t("Modelo:")).pack(side="left")
        ajuda.ajuda(caixa_modelo, lambda: t(
            "A rede que inventa os pixels que não existiam.\n\n"
            "Cada uma erra de um jeito: umas inventam grão demais em "
            "superfície lisa, outras amaciam pedra e tecido. A linha abaixo "
            "descreve a escolhida.\n\n"
            "Os modelos são lidos da pasta ferramentas/upscayl-models -- "
            "acrescentar um .param com o .bin ao lado faz ele aparecer "
            "aqui."))
        self.modelo = tk.StringVar(
            value=modelo_salvo if modelo_salvo in self.modelos else self.modelos[0])
        combo = ttk.Combobox(op, textvariable=self.modelo, values=self.modelos,
                             state="readonly", width=24)
        combo.grid(row=0, column=5)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.descrever_modelo())

        self.rotulo_modelo = ttk.Label(op, foreground=tema.TEXTO_FRACO, wraplength=900,
                                       justify="left")
        self.rotulo_modelo.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        ttk.Label(op, foreground=tema.ATENCAO, wraplength=900, justify="left",
                  text=(t("O cliente do L2 e de 32 bits. Escala 2x quadruplica a memória de "
                        "textura; 4x multiplica por 16. Marcar so o que o jogador ve de "
                        "perto e o que evita o cliente fechar sozinho em certas áreas."))
                  ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

        # ---- navegador de texturas ----
        nav = ttk.LabelFrame(quadro, text=t("Texturas do pacote"), padding=6)
        nav.pack(fill="both", expand=True, pady=(8, 0))

        barra_sel = ttk.Frame(nav)
        barra_sel.pack(fill="x", pady=(0, 4))
        ttk.Button(barra_sel, text=t("Marcar todas"),
                   command=lambda: self.marcar(True)).pack(side="left")
        ttk.Button(barra_sel, text=t("Desmarcar todas"),
                   command=lambda: self.marcar(False)).pack(side="left", padx=(6, 0))
        self.botao_exportar = ttk.Button(
            barra_sel, text=t("Exportar marcadas…"),
            command=self.exportar_marcadas, state="disabled")
        self.botao_exportar.pack(side="left", padx=(6, 0))
        ajuda.Dica(self.botao_exportar, lambda: t(
            "Tira do pacote as texturas marcadas e grava numa pasta sua, no "
            "formato em que elas estão -- DDS com o mesmo DXT, ou TGA quando a "
            "textura não é comprimida.\n\n"
            "Os bytes são os mesmos que estão dentro do .utx: nada é "
            "recomprimido, nada é convertido.\n\n"
            "Serve para guardar o original antes de mexer, abrir no Photoshop "
            "ou levar a textura para outro pacote."))

        ajuda.ajuda(barra_sel, lambda: t(
            "A marca diz o que vai ser AMPLIADO.\n\n"
            "O que ficar desmarcado não some do pacote: entra na remontagem do "
            "jeito que estava, no tamanho e no formato originais.\n\n"
            "Marcar só o que o jogador vê de perto -- rosto, armadura, chão "
            "de cidade -- é o que evita o cliente fechar sozinho."))
        self.rotulo_marcadas = ttk.Label(barra_sel, text="")
        self.rotulo_marcadas.pack(side="left", padx=(12, 0))

        corpo = ttk.Frame(nav)
        corpo.pack(fill="both", expand=True)

        # O painel de propriedades fica a direita da grade, com largura fixa:
        # quem esta escolhendo uma textura para trocar precisa ver as duas
        # coisas ao mesmo tempo.
        painel = ttk.Frame(corpo, width=250)
        painel.pack(side="right", fill="y", padx=(8, 0))
        painel.pack_propagate(False)
        titulo_props = ttk.Frame(painel)
        titulo_props.pack(fill="x")
        ttk.Label(titulo_props, text=t("Propriedades"), font=("Segoe UI", 9, "bold")
                  ).pack(side="left")
        ajuda.ajuda(titulo_props, lambda: t(
            "O que esta textura é dentro do pacote, lido do próprio .utx.\n\n"
            "O formato (DXT1, DXT3, DXT5, RGBA8...) é o que o pacote exige "
            "para ela, e é nele que a textura volta a ser gravada -- ampliada "
            "ou trocada.\n\n"
            "\"sai como\" mostra em que formato ela vai sair desta vez."))
        self.texto_props = tk.Text(painel, width=30, height=10, wrap="none",
                                   font=("Consolas", 8), relief="flat",
                                   background=tema.FUNDO, state="disabled")
        self.botao_exportar_sel = ttk.Button(
            painel, text=t("Exportar esta…"), command=self.exportar_selecionada,
            state="disabled")
        self.botao_exportar_sel.pack(side="bottom", fill="x", pady=(4, 0))
        ajuda.Dica(self.botao_exportar_sel, lambda: t(
            "Grava esta textura num arquivo seu, do jeito que ela está no "
            "pacote.\n\n"
            "Comprimida sai .dds com o mesmo DXT; sem compressão sai .tga. Em "
            "nenhum dos dois há conversão: são os bytes do .utx."))

        self.botao_melhorar_sel = ttk.Button(
            painel, text=t("Melhorar só esta"), command=self.melhorar_selecionada,
            state="disabled")
        self.botao_melhorar_sel.pack(side="bottom", fill="x", pady=(4, 0))
        ajuda.Dica(self.botao_melhorar_sel, lambda: t(
            "Amplia só a textura selecionada e remonta o pacote com ela dentro.\n\n"
            "As outras entram do jeito que estavam, no tamanho e no formato "
            "originais -- o pacote sai completo, com uma textura melhor e o "
            "resto intacto.\n\n"
            "É o caminho rápido para corrigir uma textura só, sem esperar o "
            "pacote inteiro."))

        self.botao_trocar_sel = ttk.Button(painel, text=t("Trocar esta imagem…"),
                                           command=self.trocar_selecionada,
                                           state="disabled")
        self.botao_trocar_sel.pack(side="bottom", fill="x", pady=(4, 0))
        ajuda.Dica(self.botao_trocar_sel, lambda: t(
            "Põe uma imagem sua no lugar desta textura.\n\n"
            "Serve PNG, JPG, BMP, TGA, WEBP e DDS -- inclusive DDS em formato "
            "que o pacote não usa.\n\n"
            "O programa encaixa a imagem sozinho: reduz para a resolução "
            "original, corta o excesso se a proporção for outra, herda o alfa "
            "da textura antiga quando a nova não tem, e grava no formato que "
            "AQUELA textura tem no pacote."))

        # Por ultimo e sem side: o Text fica com a altura que sobrou depois dos
        # botoes, em vez de empurra-los para fora da janela.
        self.texto_props.pack(fill="both", expand=True, pady=(4, 0))

        self.tela = tk.Canvas(corpo, height=210, highlightthickness=0)
        rol = ttk.Scrollbar(corpo, orient="vertical", command=self.tela.yview)
        self.tela.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.tela.pack(side="left", fill="both", expand=True)

        self.grade = ttk.Frame(self.tela)
        self.tela.create_window((0, 0), window=self.grade, anchor="nw")
        self.grade.bind("<Configure>",
                        lambda _e: self.tela.configure(scrollregion=self.tela.bbox("all")))
        # Sem `bind_all`: ele e global, e faria a roda mexer nesta grade com o
        # ponteiro em qualquer lugar do programa -- inclusive dentro de outra
        # aba. O registro deixa o tratador unico decidir pelo ponteiro.
        rolagem.registrar(self.tela, self.grade)

        # ---- acao ----
        acao = ttk.Frame(quadro)
        acao.pack(fill="x", pady=(8, 0))
        self.botao = ttk.Button(acao, text=t("Processar"), command=self.iniciar,
                                state="disabled")
        self.botao.pack(side="left")
        ajuda.ajuda(acao, lambda: t(
            "Amplia as texturas marcadas, encaixa as imagens trocadas e "
            "remonta o pacote.\n\n"
            "O .utx pronto NÃO é copiado para o cliente: ele fica numa pasta "
            "que o programa mostra no fim, para você copiar por cima só depois "
            "de conferir.\n\n"
            "Pode demorar. Uma textura 512x512 em 2x leva perto de um minuto "
            "numa placa modesta."))

        medidor = ttk.Frame(acao)
        medidor.pack(side="left", fill="x", expand=True, padx=(12, 0))
        # maximum=1000 e nao o numero de imagens: assim a barra aceita valor
        # fracionario e anda dentro de uma unica textura.
        self.barra = ttk.Progressbar(medidor, mode="determinate", maximum=1000)
        self.barra.pack(fill="x")
        self.rotulo_estado = ttk.Label(medidor, text="", foreground=tema.TEXTO_FRACO,
                                       font=("Consolas", 9))
        self.rotulo_estado.pack(fill="x", pady=(2, 0))

        # ---- registro ----
        reg = ttk.LabelFrame(quadro, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=7, wrap="word", state="disabled")
        rol2 = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol2.set)
        rol2.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

        self.descrever_modelo()
        self.conferir_ferramentas()
        self.varrer_sobras()
        self.raiz.after(120, self.drenar_fila)

    def varrer_sobras(self):
        """
        Apaga o que ficou de uma execucao anterior interrompida.

        Se o programa foi fechado no meio, ou o salvamento foi cancelado,
        trabalho/ fica com PNGs e DDS de pacotes que ja nao interessam --
        centenas de megabytes acumulando em silencio a cada tentativa.
        _saida_provisoria e o unico que se preserva: e ali que ficam os .utx
        prontos de um salvamento cancelado, que o usuario ainda pode querer.
        """
        sobra = motor.BASE / "trabalho"
        if not sobra.is_dir():
            return
        try:
            quantos = sum(1 for _ in sobra.iterdir())
        except OSError:
            return
        if quantos:
            shutil.rmtree(sobra, ignore_errors=True)
            self.log(t("Limpou %d pasta(s) de trabalho de uma execucao anterior.") % quantos)

    # -- utilidades --------------------------------------------------------
    def descrever_modelo(self):
        self.rotulo_modelo.config(
            text=t(DESCRICOES.get(self.modelo.get(),
                                  N_("Modelo adicional instalado pelo usuário."))))

    def log(self, msg):
        self.fila.put(msg)

    def drenar_fila(self):
        # A aba pode ter sido destruida -- e o que acontece ao trocar de
        # idioma, que monta a janela de novo. Sem esta saida o laco seguiria
        # marcado no Tk, batendo a cada 120 ms num widget que nao existe mais.
        if not self.texto.winfo_exists():
            return

        try:
            while True:
                msg = self.fila.get_nowait()
                self.texto.configure(state="normal")
                self.texto.insert("end", msg + "\n")
                self.texto.see("end")
                self.texto.configure(state="disabled")
        except queue.Empty:
            pass

        self.desenhar_progresso()
        self.raiz.after(120, self.drenar_fila)

    def desenhar_progresso(self):
        """
        Move a barra em direcao ao alvo e atualiza a linha de estado.

        O deslocamento e de uma fracao da distancia que falta, e nao um salto:
        quando o upscayl reporta 11% de uma vez, a agulha caminha ate la ao
        longo de alguns quadros em vez de pular. Junto com o relogio, que corre
        de segundo em segundo, sempre ha algo se mexendo -- mesmo nos minutos
        em que a ferramenta esta calculando uma textura grande e nao tem nada
        novo a dizer.
        """
        if abs(self.alvo_barra - self.valor_barra) > 0.0002:
            self.valor_barra += (self.alvo_barra - self.valor_barra) * 0.20
            self.barra.config(value=self.valor_barra * 1000)

        if not self.rodando:
            return

        self.giro += 1
        partes = [GIRO[self.giro % len(GIRO)]]
        if self.estado_texto:
            partes.append(self.estado_texto)

        if self.ampliar_inicio and self.ampliar_total:
            passado = time.time() - self.ampliar_inicio
            partes.append(t("decorrido %s") % duracao(passado))
            # A previsao so aparece depois de meia textura pronta: antes disso
            # a media e feita de um unico ponto e oscila de forma absurda.
            if self.ampliar_feitas >= 0.5:
                resta = (passado / self.ampliar_feitas) * (self.ampliar_total - self.ampliar_feitas)
                partes.append(t("faltam ~%s") % duracao(resta))

        self.rotulo_estado.config(text="   ".join(partes))

    def definir_progresso(self, fracao, texto=None):
        """
        Chamada da thread de trabalho. So anota; quem desenha e o laco.

        A fracao e sempre relativa ao PACOTE atual; a faixa converte para a
        barra inteira. Assim o mesmo codigo serve para um pacote (faixa 0..1) e
        para o lote, onde cada pacote ocupa uma fatia.
        """
        fracao = max(0.0, min(1.0, fracao))
        self.alvo_barra = self.faixa_ini + fracao * self.faixa_tam
        if texto is not None:
            self.estado_texto = texto

    def conferir_ferramentas(self):
        faltando = [k for k, v in self.T.items() if not v.exists()]
        if faltando:
            self.log(t("AVISO: ferramentas não encontradas: %s") % ", ".join(faltando))
            self.log(t("Ajuste os caminhos em %s (ver LEIA-ME.md).") % motor.CONFIG)
            return
        embutidas = all(str(v).startswith(str(motor.AQUI)) for v in self.T.values())
        self.log(t("Pronto.") if embutidas else t("Ferramentas encontradas. Pronto."))

    # -- abertura de um pacote --------------------------------------------
    def abrir_pacote(self):
        if self.rodando:
            return
        nome = filedialog.askopenfilename(
            title=t("Abrir pacote"),
            filetypes=[(t("Texturas Unreal"), "*.utx"),
                       (t("Todos os pacotes Unreal"), "*.utx *.u *.ukx *.uax"),
                       (t("Todos"), "*.*")])
        if not nome:
            return

        self.arquivos = []
        self.pacote_atual = Path(nome)
        self.limpar_grade()
        self.rotulo_sel.config(text=t("abrindo %s…") % self.pacote_atual.name)
        self.botao.config(state="disabled")
        self.rodando = True
        threading.Thread(target=self.extrair_para_previa, daemon=True).start()

    def extrair_para_previa(self):
        """Descriptografa e extrai numa thread; a grade e montada na interface."""
        utx = self.pacote_atual
        base = motor.BASE / "trabalho" / utx.stem
        shutil.rmtree(base, ignore_errors=True)
        self.base_trabalho = base
        self.estava_cifrado = motor.versao_pacote(utx) is None

        self.log(t("\nAbrindo %s") % utx.name)
        dec, detalhe = motor.descriptografar(self.T, utx, base / "dec")
        if dec is None:
            self.log(t("  ERRO ao descriptografar: %s") % detalhe)
            self.raiz.after(0, self.fim_abertura, [])
            return
        self.log("  %s" % detalhe)

        # O inventario sai do .utx original, nao do descriptografado: o umodel
        # abre os dois, e assim a leitura continua valendo se o passo anterior
        # tiver mudado de lugar algum dia.
        self.formatos = motor.inventario(self.T, utx)
        self.log(t("  formatos: %s")
                 % (", ".join("%s x%d" % (f, n) for f, n in
                              sorted(_contar_formatos(self.formatos).items()))
                    or t("não identificados")))

        imagens, _ = motor.extrair(self.T, dec, base / "extraido")
        if not imagens:
            self.log(t("  nenhuma textura neste pacote"))
            self.raiz.after(0, self.fim_abertura, [])
            return

        # Normaliza para PNG uma vez so: serve de miniatura E de entrada do
        # Upscayl, que nao le TGA.
        png = motor.converter(imagens, base / "png", ".png")

        # A arvore do umodel e o pacote aberto ja cumpriram o papel. Mantidos,
        # cada textura ficaria em duas copias em disco antes mesmo de o
        # processamento comecar.
        shutil.rmtree(base / "extraido", ignore_errors=True)
        shutil.rmtree(base / "dec", ignore_errors=True)

        self.log(t("  %d texturas") % len(png))
        self.raiz.after(0, self.fim_abertura, png)

    def fim_abertura(self, imagens):
        self.rodando = False
        if not imagens:
            self.rotulo_sel.config(text=t("nada para mostrar"))
            return
        self.montar_grade(imagens)
        self.rotulo_sel.config(text=t("%s  (%d texturas)")
                               % (self.pacote_atual.name, len(imagens)))
        self.botao.config(state="normal")

    # -- grade de miniaturas ----------------------------------------------
    def limpar_grade(self):
        for filho in self.grade.winfo_children():
            filho.destroy()
        self.texturas = []
        self.selecionada = None
        self.rotulo_marcadas.config(text="")
        if hasattr(self, "texto_props"):
            self.texto_props.config(state="normal")
            self.texto_props.delete("1.0", "end")
            self.texto_props.config(state="disabled")
            self.botao_trocar_sel.config(state="disabled")
            self.botao_melhorar_sel.config(state="disabled")
            self.botao_exportar_sel.config(state="disabled")
            self.botao_exportar.config(state="disabled")

    def montar_grade(self, imagens):
        self.limpar_grade()
        for i, caminho in enumerate(sorted(imagens)):
            try:
                with Image.open(caminho) as im:
                    largura, altura = im.size
                    previa = im.convert("RGBA").copy()
                previa.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.LANCZOS)
                foto = ImageTk.PhotoImage(previa)
            except Exception:
                foto, largura, altura = None, 0, 0

            var = tk.BooleanVar(value=True)
            var.trace_add("write", lambda *_a: self.contar_marcadas())

            celula = ttk.Frame(self.grade, padding=4)
            celula.grid(row=i // COLUNAS, column=i % COLUNAS, sticky="n")

            info = self.formatos.get(caminho.stem.lower(), {})
            item = {"caminho": caminho, "var": var, "foto": foto,
                    "largura": largura, "altura": altura,
                    "substituta": None, "celula": celula}

            item["imagem"] = ttk.Label(celula, image=foto) if foto else ttk.Label(celula)
            item["imagem"].pack()
            # Clicar na miniatura poe a textura no painel. A caixa de marcacao
            # continua respondendo so por "amplia ou nao".
            item["imagem"].bind("<Button-1>", lambda _e, t=item: self.selecionar(t))
            ttk.Checkbutton(celula, text=caminho.stem[:16], variable=var).pack()
            item["legenda"] = ttk.Label(
                celula, foreground=tema.TEXTO_FRACO,
                text=t("%dx%d  %s") % (largura, altura,
                                    info.get("formato", "?").replace("TEXF_", "")))
            item["legenda"].pack()
            ttk.Button(celula, text=t("trocar…"), width=8,
                       command=lambda t=item: self.trocar_imagem(t)).pack()

            # A foto precisa de referencia viva, senao some da tela.
            self.texturas.append(item)

        self.contar_marcadas()

    def trocar_imagem(self, item):
        """
        Poe uma imagem do disco no lugar de uma textura do pacote.

        A troca e o oposto da ampliacao, entao a textura sai da selecao: nao
        faz sentido ampliar uma imagem que o usuario acabou de escolher no
        tamanho que quer. O encaixe -- tamanho, proporcao e alfa -- so acontece
        na hora de processar, em motor.preparar_substituta; aqui apenas se
        anota a escolha e se mostra como ficou.
        """
        if self.rodando:
            return

        nome = filedialog.askopenfilename(
            title=t("Imagem para %s (%dx%d)") % (item["caminho"].stem,
                                              item["largura"], item["altura"]),
            filetypes=[(t("Imagens"), "*.png *.jpg *.jpeg *.bmp *.tga *.webp *.dds"),
                       (t("Todos"), "*.*")])
        if not nome:
            return

        # Pelo motor, e nao pelo Pillow direto: DDS que o Pillow recusa ainda
        # entra pelo texconv, e e justamente em DDS que a imagem costuma vir
        # quando alguem pega uma textura de outro pacote.
        try:
            previa = motor.abrir_imagem(nome, self.T)
            previa.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.LANCZOS)
            foto = ImageTk.PhotoImage(previa)
        except Exception as e:
            messagebox.showerror(t("Imagem invalida"), t("Não consegui abrir:\n%s\n\n%s")
                                 % (nome, e))
            return

        item["substituta"] = Path(nome)
        item["foto"] = foto                 # referencia viva, senao some
        item["imagem"].config(image=foto)
        item["legenda"].config(text=t("trocada  ->  %dx%d") % (item["largura"],
                                                            item["altura"]),
                               foreground=tema.BOM)
        item["var"].set(False)
        self.log(t("  trocar %s por %s") % (item["caminho"].stem, Path(nome).name))
        self.contar_marcadas()
        if self.selecionada is item:
            self.mostrar_propriedades(item)

    def selecionar(self, item):
        """Poe uma textura no painel de propriedades."""
        if self.selecionada is item:
            return

        anterior = self.selecionada
        self.selecionada = item
        if anterior is not None:
            anterior["celula"].configure(relief="flat", borderwidth=0)
        item["celula"].configure(relief="solid", borderwidth=1)
        livre = "disabled" if self.rodando else "normal"
        self.botao_trocar_sel.config(state=livre)
        self.botao_melhorar_sel.config(state=livre)
        self.botao_exportar_sel.config(state=livre)
        self.mostrar_propriedades(item)

    def mostrar_propriedades(self, item):
        """
        Escreve no painel o que a textura e, nao so como ela parece.

        Os valores vem do inventario lido do proprio .utx pelo umodel. O que
        nao estiver no dump simplesmente nao aparece -- inventar "desconhecido"
        para cada campo ausente encheria o painel de ruido.
        """
        info = self.formatos.get(item["caminho"].stem.lower(), {})
        linhas = [("nome", item["caminho"].stem)]

        formato = info.get("formato", "")
        if formato:
            linhas.append((t("formato"), formato.replace("TEXF_", "")))
        linhas.append((t("tamanho"), "%d x %d" % (item["largura"], item["altura"])))

        if info.get("alfa") is not None:
            linhas.append((t("alfa"), t("sim") if info["alfa"] else t("não")))
        if info.get("mascarado") is not None:
            linhas.append((t("mascarado"),
                           t("sim") if info["mascarado"] else t("não")))

        rotulos = (
            ("UBits", N_("bits U")), ("VBits", N_("bits V")),
            ("UClamp", N_("clamp U")), ("VClamp", N_("clamp V")),
            ("UClampMode", N_("modo U")), ("VClampMode", N_("modo V")),
            ("LODSet", N_("LOD")), ("MinLOD", N_("LOD min")),
            ("StrippedNumMips", N_("mips cortados")),
            ("HasBeenStripped", N_("cortada")),
            ("bTwoSided", N_("dois lados")),
            ("bHighTextureQuality", N_("alta qualidade")),
            ("bRealtime", N_("tempo real")),
            ("DetailScale", N_("escala detalhe")),
            ("Detail", N_("detalhe")), ("Palette", N_("paleta")),
            ("AnimNext", N_("proxima anim")), ("SurfaceType", N_("superficie")),
        )
        for chave, rotulo in rotulos:
            valor = info.get(chave)
            if valor not in (None, "", "None"):
                linhas.append((t(rotulo), str(valor)))

        if item.get("substituta"):
            linhas.append(("", ""))
            linhas.append((t("trocar por"), Path(item["substituta"]).name))
            # O que vai ser feito com a imagem escolhida, dito ANTES de
            # processar. Sem isto o usuario so descobre que a imagem foi
            # reduzida, cortada ou regravada em outro formato depois -- ou nao
            # descobre.
            for chave, valores in self.encaixe_da_substituta(item, info):
                linhas.append((" ", chave % valores if valores else chave))

        destino, alvo = None, None
        if formato:
            alvo, _obs = motor.formato_alvo(info, item["caminho"])
            linhas.append(("", ""))
            linhas.append((t("sai como"), alvo))

        self.texto_props.config(state="normal")
        self.texto_props.delete("1.0", "end")
        for rotulo, valor in linhas:
            self.texto_props.insert("end", "%-15s %s\n" % (rotulo, valor) if rotulo
                                    else "\n")
        self.texto_props.config(state="disabled")

    def encaixe_da_substituta(self, item, info):
        """
        As frases do encaixe: o que muda da imagem escolhida para o pacote.

        O motor devolve pares (o que, valores); quem escreve a frase e aqui,
        que sabe o idioma. Frase nenhuma quer dizer que a imagem ja chega do
        jeito que o pacote quer.
        """
        try:
            notas = motor.notas_da_substituta(
                item["substituta"], info, item["largura"], item["altura"], self.T)
        except Exception as e:
            return [(t("não consegui ler: %s"), (e,))]

        frases = []
        for chave, valores in notas:
            if chave == "tamanho":
                frases.append((t("%dx%d -> %dx%d"), valores))
            elif chave == "proporcao":
                frases.append((t("cortada no centro"), ()))
            elif chave == "alfa":
                frases.append((t("alfa herdado da antiga"), ()))
            elif chave == "formato":
                # Nao e o formato do arquivo que manda: e o que a textura era
                # dentro do pacote.
                frases.append((t("%s -> %s (%s)"), valores))
            elif chave == "aviso":
                frases.append(("%s", valores))
            elif chave == "erro":
                frases.append((t("não consegui ler: %s"), valores))
        return frases

    def trocar_selecionada(self):
        """O botao do painel: troca a textura que esta em foco."""
        if self.selecionada is None:
            messagebox.showinfo(t("Nenhuma escolhida"),
                                t("Clique numa miniatura para escolher a textura."))
            return
        self.trocar_imagem(self.selecionada)

    def exportar_marcadas(self):
        """As marcadas, para uma pasta escolhida pelo usuario."""
        if self.rodando:
            return
        marcadas = [tex for tex in self.texturas if tex["var"].get()]
        if not marcadas:
            messagebox.showinfo(
                t("Nada marcado"),
                t("Marque as texturas que você quer exportar.\n\n"
                  "A marca é a mesma da ampliação: marque, exporte, e "
                  "desmarque depois se não for ampliar."))
            return

        pasta = filedialog.askdirectory(
            title=t("Onde salvar %d textura(s)?") % len(marcadas))
        if not pasta:
            return
        self._exportar(marcadas, Path(pasta))

    def exportar_selecionada(self):
        """A que está no painel, com nome de arquivo escolhido."""
        if self.rodando:
            return
        if self.selecionada is None:
            messagebox.showinfo(t("Nenhuma escolhida"),
                                t("Clique numa miniatura para escolher a textura."))
            return

        item = self.selecionada
        nome = item["caminho"].stem
        info = self.formatos.get(nome.lower(), {})
        extensao = motor.extensao_de_exportacao(info)
        formato = info.get("formato", "").replace("TEXF_", "") or "?"

        alvo = filedialog.asksaveasfilename(
            title=t("Salvar %s (%s)") % (nome, formato),
            defaultextension=extensao,
            initialfile=nome + extensao,
            filetypes=[(t("Textura %s") % extensao.upper().lstrip("."),
                        "*" + extensao), (t("Todos"), "*.*")])
        if not alvo:
            return
        self._exportar([item], Path(alvo).parent, renomear=Path(alvo))

    def _exportar(self, itens, pasta, renomear=None):
        self.rodando = True
        self.botao.config(state="disabled")
        self.botao_exportar.config(state="disabled")
        self.ampliar_inicio = self.ampliar_feitas = 0.0
        self.ampliar_total = 0
        self.estado_texto = t("exportando…")
        threading.Thread(target=self._exportar_thread,
                         args=(itens, pasta, renomear), daemon=True).start()

    def _exportar_thread(self, itens, pasta, renomear):
        """
        A exportacao em si. Nao toca no pacote nem nas texturas ja abertas: le
        do .utx original de novo, que e o que garante o arquivo como esta la.
        """
        nomes = [item["caminho"].stem for item in itens]
        self.log(t("\nExportando %d textura(s) para %s") % (len(nomes), pasta))
        gravados, erro = [], None
        try:
            gravados = motor.exportar(
                self.T, self.pacote_atual, nomes, pasta,
                progresso=lambda i, total: self.definir_progresso(
                    i / float(max(1, total))),
                aolog=lambda m: self.log("  " + m))

            if renomear is not None and len(gravados) == 1:
                # O usuario escolheu o nome; a extensao, porem, e a do formato
                # que saiu -- renomear .tga para .dds nao mudaria o conteudo,
                # so faria o arquivo mentir sobre o que e.
                destino = renomear.with_suffix(gravados[0].suffix)
                if destino != gravados[0]:
                    if destino.exists():
                        destino.unlink()
                    gravados[0] = Path(shutil.move(str(gravados[0]), str(destino)))
        except Exception as e:
            erro = e

        for arquivo in gravados:
            info = self.formatos.get(arquivo.stem.lower(), {})
            self.log(t("  %s  %s  %d bytes")
                     % (arquivo.name,
                        info.get("formato", "").replace("TEXF_", "") or "?",
                        arquivo.stat().st_size))

        self.raiz.after(0, self._fim_exportacao, gravados, pasta, erro)

    def _fim_exportacao(self, gravados, pasta, erro):
        self.rodando = False
        self.estado_texto = ""
        self.definir_progresso(0.0)
        self.contar_marcadas()
        if self.selecionada is not None:
            self.botao_exportar_sel.config(state="normal")
            self.botao_trocar_sel.config(state="normal")
            self.botao_melhorar_sel.config(state="normal")

        if erro is not None:
            self.log(t("  ERRO ao exportar: %s") % erro)
            messagebox.showerror(t("Não deu para exportar"), str(erro))
            return

        if not gravados:
            messagebox.showwarning(
                t("Nada exportado"),
                t("O umodel não gravou nenhum arquivo. Veja o andamento."))
            return

        self.log(t("  pronto: %d arquivo(s) em %s") % (len(gravados), pasta))
        messagebox.showinfo(
            t("Exportado"),
            t("%d arquivo(s) em:\n%s\n\n"
              "Estão no formato original do pacote -- os mesmos bytes que "
              "estão dentro do .utx.") % (len(gravados), pasta))

    def melhorar_selecionada(self):
        """
        Amplia so a textura em foco e remonta o pacote com ela dentro.

        E a mesma passagem de sempre, com uma marcada so: as outras texturas
        entram na remontagem do jeito que estavam. O atalho existe porque
        corrigir uma textura e o caso mais comum, e marcar uma, desmarcar as
        outras e clicar em Processar e trabalho que a janela pode fazer
        sozinha.
        """
        if self.rodando:
            return
        if self.selecionada is None:
            messagebox.showinfo(t("Nenhuma escolhida"),
                                t("Clique numa miniatura para escolher a textura."))
            return

        item = self.selecionada
        if item.get("substituta"):
            messagebox.showinfo(
                t("Essa textura já foi trocada"),
                t("Esta textura tem uma imagem sua esperando para entrar no "
                  "lugar dela.\n\nAmpliar não faria sentido: a imagem que você "
                  "escolheu já esta no tamanho certo.\n\nClique em Processar "
                  "para grava-la no pacote."))
            return

        self.marcar(False)
        item["var"].set(True)
        self.contar_marcadas()
        self.log(t("\nMelhorando so %s; o resto do pacote entra como estava.")
                 % item["caminho"].stem)
        self.iniciar()

    def marcar(self, valor):
        for tex in self.texturas:
            # Uma textura trocada nao e ampliada: ela ja esta no tamanho certo.
            if not tex.get("substituta"):
                tex["var"].set(valor)

    def contar_marcadas(self):
        n = sum(1 for tex in self.texturas if tex["var"].get())
        trocadas = sum(1 for tex in self.texturas if tex.get("substituta"))
        self.rotulo_marcadas.config(
            text=t("%d de %d marcadas%s")
            % (n, len(self.texturas), (t("  |  %d trocadas") % trocadas) if trocadas else ""))
        if not self.rodando:
            self.botao.config(
                state="normal" if (n or trocadas or self.arquivos) else "disabled")
            # Exportar so depende de haver textura marcada num pacote aberto:
            # nao tem nada a ver com ampliar nem com trocar.
            self.botao_exportar.config(
                state="normal" if (n and self.pacote_atual) else "disabled")

    # -- lote --------------------------------------------------------------
    def escolher_pasta(self):
        if self.rodando:
            return
        pasta = filedialog.askdirectory(title=t("Escolha a pasta com os .utx"))
        if not pasta:
            return
        self.arquivos = sorted(Path(pasta).glob("*.utx"))
        self.pacote_atual = None
        self.limpar_grade()
        if not self.arquivos:
            self.rotulo_sel.config(text=t("nenhum .utx encontrado"))
            self.botao.config(state="disabled")
            return
        self.rotulo_sel.config(text=t("lote: %d pacotes (sem previa)") % len(self.arquivos))
        self.botao.config(state="normal")
        self.log(t("\nLote selecionado: %d pacotes.") % len(self.arquivos))

    # -- processamento -----------------------------------------------------
    def iniciar(self):
        if self.rodando:
            return
        # So o que ESTA aba usa. O dicionario inteiro inclui o l2asm e o
        # l2disasm, que sao da aba de NPC; exigi-los aqui deixaria sem ampliar
        # textura quem nunca vai criar NPC nenhum.
        faltando = [k for k in PRECISA_TEXTURA if not self.T.get(k, Path("")).exists()]
        if faltando:
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.") % (", ".join(faltando), motor.CONFIG))
            return

        motor.gravar_preferencias(self.modelo.get(), self.escala.get())
        self.alvo_barra = self.valor_barra = 0.0
        self.barra.config(value=0)
        self.ampliar_inicio = self.ampliar_feitas = 0.0
        self.ampliar_total = 0
        self.faixa_ini, self.faixa_tam = 0.0, 1.0
        self.estado_texto = t("preparando…")

        if self.pacote_atual:
            marcadas = [tex["caminho"] for tex in self.texturas
                        if tex["var"].get() and not tex.get("substituta")]
            if not marcadas and not any(tex.get("substituta") for tex in self.texturas):
                messagebox.showinfo(t("Nada a fazer"),
                                    t("Marque ao menos uma textura para ampliar, "
                                    "ou troque alguma imagem."))
                return
            self.rodando = True
            self.botao.config(state="disabled")
            threading.Thread(target=self.trabalhar_um, args=(marcadas,), daemon=True).start()
        else:
            self.rodando = True
            self.botao.config(state="disabled")
            threading.Thread(target=self.trabalhar_lote, daemon=True).start()

    def trabalhar_um(self, marcadas):
        """
        Um pacote, so as texturas marcadas.

        As NAO marcadas entram na remontagem no tamanho original. Sem isso o
        pacote sairia com menos texturas do que entrou, e o jogo mostraria
        buracos onde elas apareciam.
        """
        base = self.base_trabalho
        utx = self.pacote_atual
        provisorio = motor.BASE / "_saida_provisoria"
        shutil.rmtree(provisorio, ignore_errors=True)

        trocadas = [t for t in self.texturas if t.get("substituta")]
        marcadas_nomes = {c.name for c in marcadas}
        marcadas_nomes |= {item["caminho"].name for item in trocadas}
        todas = sorted((base / "png").glob("*.png"))
        intactas = [i for i in todas if i.name not in marcadas_nomes]

        self.log(t("\nProcessando %s: %d de %d texturas")
                 % (utx.name, len(marcadas) + len(trocadas), len(todas)))

        # As trocadas primeiro: sao rapidas, e se alguma imagem escolhida
        # estiver quebrada e melhor descobrir agora do que depois de vinte
        # minutos de upscale.
        substitutas = []
        for item in trocadas:
            alvo = base / "trocadas" / (item["caminho"].stem + ".png")
            try:
                arquivo, observacao = motor.preparar_substituta(
                    item["substituta"], alvo, item["largura"], item["altura"],
                    alfa_de=item["caminho"], T=self.T)
            except Exception as e:
                self.log(t("  ERRO ao encaixar %s: %s") % (item["caminho"].stem, e))
                continue
            substitutas.append(arquivo)
            self.log(t("  trocada %s <- %s  (%dx%d)%s")
                     % (item["caminho"].stem, Path(item["substituta"]).name,
                        item["largura"], item["altura"],
                        ("  " + observacao) if observacao else ""))

        if not marcadas:
            self.log(t("  nenhuma para ampliar."))
            ampliadas = []
        else:
            self.log(t("  ampliando %d imagens (%dx, %s)")
                     % (len(marcadas), self.escala.get(), self.modelo.get()))

        # As marcadas vao como LISTA para o motor. Antes eram copiadas para
        # selecionadas/ so porque a funcao recebia um diretorio -- uma copia
        # inteira do pacote em disco para nao dizer nada de novo.
            ampliadas = motor.ampliar(self.T, marcadas, base / "ampliado",
                                      self.escala.get(), self.modelo.get(),
                                      self.acompanhar_upscale)
            if not ampliadas:
                self.log(t("  ERRO: upscayl não gerou nada"))
                self.raiz.after(0, self.terminar, [], provisorio)
                return

        # As nao marcadas entram no tamanho original. Sem elas o pacote sairia
        # com menos texturas do que entrou e o jogo mostraria buracos.
        if intactas:
            self.log(t("  mantidas no tamanho original: %d") % len(intactas))

        self.definir_progresso(PESO_AMPLIAR + 0.03, t("comprimindo…"))
        entrada = ampliadas + substitutas + intactas
        self.log(t("  comprimindo %d texturas, cada uma no formato dela…") % len(entrada))
        dds = motor.comprimir(self.T, entrada, base / "dds",
                              formatos=self.formatos,
                              aviso=lambda m: self.log("    " + m))
        if not dds:
            self.log(t("  ERRO: texconv não gerou DDS"))
            self.raiz.after(0, self.terminar, [], provisorio)
            return
        self.log(t("  comprimidas: %d  (%s)")
                 % (len(dds), motor.resumo_formatos(entrada, self.formatos)))

        self.definir_progresso(PESO_AMPLIAR + 0.06, t("remontando o pacote…"))
        self.log(t("  remontando o pacote…"))
        pacote, _ = motor.montar(self.T, utx.stem, dds, self.T["ucc"].parent.parent)
        if pacote is None:
            self.log(t("  ERRO no ucc make"))
            self.raiz.after(0, self.terminar, [], provisorio)
            return
        self.log(t("  pacote montado: %d bytes") % pacote.stat().st_size)

        self.definir_progresso(PESO_AMPLIAR + 0.10, t("gravando e conferindo…"))
        arquivo, integro = motor.criptografar(self.T, pacote, utx.name,
                                              provisorio, self.estava_cifrado)
        pacote.unlink(missing_ok=True)    # copia do ucc no System do editor
        if arquivo is None:
            self.log(t("  ERRO ao gravar"))
            self.raiz.after(0, self.terminar, [], provisorio)
            return
        self.log(t("  pronto: %d bytes%s")
                 % (arquivo.stat().st_size,
                    "" if integro else t("  [AVISO: ida e volta não confere]")))

        # Ampliadas e DDS ja estao dentro do .utx montado; guardar as duas
        # arvores deixaria cada textura em tres copias em disco. png/ fica: e
        # o que alimenta as miniaturas na tela e permite processar o mesmo
        # pacote de novo com outra selecao sem reabrir o arquivo.
        shutil.rmtree(base / "ampliado", ignore_errors=True)
        shutil.rmtree(base / "trocadas", ignore_errors=True)
        shutil.rmtree(base / "dds", ignore_errors=True)

        self.definir_progresso(1.0, "concluido")
        self.raiz.after(0, self.terminar, [utx.name], provisorio)

    def acompanhar_upscale(self, i, total, nome, fracao):
        """
        Ponte entre o motor e a barra, durante a fase longa.

        Recebe tambem as fracoes intermediarias de cada textura; so vira linha
        no registro no inicio e no fim de cada uma, senao o andamento viraria
        centenas de linhas de porcentagem e esconderia os avisos.
        """
        if not self.ampliar_total:
            self.ampliar_total = total
            self.ampliar_inicio = time.time()

        if fracao <= 0.0:
            self.img_inicio = time.time()
            self.log(t("    [%d/%d] %s") % (i, total, nome))
        elif fracao >= 1.0:
            self.log(t("        pronta em %s")
                     % duracao(time.time() - getattr(self, "img_inicio", time.time())))

        self.ampliar_feitas = (i - 1) + fracao
        self.definir_progresso(
            PESO_AMPLIAR * (self.ampliar_feitas / max(1, total)),
            "%d/%d  %s  %3d%%" % (i, total, nome[:22], round(fracao * 100)))

    def trabalhar_lote(self):
        trabalho = motor.BASE / "trabalho"
        provisorio = motor.BASE / "_saida_provisoria"
        shutil.rmtree(provisorio, ignore_errors=True)

        concluidos = []
        total = len(self.arquivos)
        for i, utx in enumerate(self.arquivos, 1):
            # Cada pacote ocupa a sua fatia da barra; dentro dela o progresso
            # volta a ser 0..1, com as mesmas regras do modo de um pacote so.
            self.faixa_ini, self.faixa_tam = (i - 1) / total, 1.0 / total
            self.ampliar_inicio = self.ampliar_feitas = 0.0
            self.ampliar_total = 0
            self.log(t("\n[%d/%d] %s") % (i, total, utx.name))
            try:
                if self.processar_completo(utx, trabalho, provisorio):
                    concluidos.append(utx.name)
            except Exception as e:
                self.log(t("  ERRO inesperado: %s") % e)
        self.faixa_ini, self.faixa_tam = 0.0, 1.0
        self.definir_progresso(1.0, "concluido")
        self.raiz.after(0, self.terminar, concluidos, provisorio)

    def processar_completo(self, utx, trabalho, saida):
        base = trabalho / utx.stem
        shutil.rmtree(base, ignore_errors=True)
        estava_cifrado = motor.versao_pacote(utx) is None

        self.definir_progresso(0.0, t("descriptografando…"))
        self.log(t("  descriptografando…"))
        dec, detalhe = motor.descriptografar(self.T, utx, base / "dec")
        if dec is None:
            self.log(t("  ERRO ao descriptografar: %s") % detalhe)
            return False
        self.log("  %s" % detalhe)

        formatos = motor.inventario(self.T, utx)

        self.definir_progresso(0.02, t("extraindo texturas…"))
        self.log(t("  extraindo texturas…"))
        imagens, _ = motor.extrair(self.T, dec, base / "extraido")
        if not imagens:
            self.log(t("  ERRO: nenhuma textura extraida"))
            return False
        self.log(t("  extraidas: %d") % len(imagens))

        motor.converter(imagens, base / "png", ".png")
        # Ja em PNG: o que o umodel exportou e o pacote aberto nao servem mais.
        shutil.rmtree(base / "extraido", ignore_errors=True)
        shutil.rmtree(base / "dec", ignore_errors=True)

        self.log(t("  ampliando %d imagens…") % len(imagens))
        ampliadas = motor.ampliar(self.T, base / "png", base / "ampliado",
                                  self.escala.get(), self.modelo.get(),
                                  self.acompanhar_upscale)
        if not ampliadas:
            self.log(t("  ERRO: upscayl não gerou nada"))
            return False

        self.definir_progresso(PESO_AMPLIAR + 0.03, "comprimindo…")
        self.log(t("  comprimindo, cada textura no formato dela…"))
        dds = motor.comprimir(self.T, ampliadas, base / "dds", formatos=formatos,
                              aviso=lambda m: self.log("    " + m))
        if not dds:
            self.log(t("  ERRO: texconv não gerou DDS"))
            return False
        self.log(t("  comprimidas: %d  (%s)")
                 % (len(dds), motor.resumo_formatos(ampliadas, formatos)))

        self.definir_progresso(PESO_AMPLIAR + 0.06, "remontando o pacote…")
        self.log(t("  remontando o pacote…"))
        pacote, _ = motor.montar(self.T, utx.stem, dds, self.T["ucc"].parent.parent)
        if pacote is None:
            self.log(t("  ERRO no ucc make"))
            return False

        self.definir_progresso(PESO_AMPLIAR + 0.10, "gravando e conferindo…")
        arquivo, integro = motor.criptografar(self.T, pacote, utx.name, saida, estava_cifrado)
        pacote.unlink(missing_ok=True)
        if arquivo is None:
            self.log(t("  ERRO ao gravar"))
            return False
        self.log(t("  pronto: %d bytes%s")
                 % (arquivo.stat().st_size,
                    "" if integro else "  [AVISO: ida e volta nao confere]"))

        # No lote nao ha miniaturas para sustentar: o pacote inteiro sai.
        shutil.rmtree(base, ignore_errors=True)
        self.definir_progresso(1.0)
        return True

    def terminar(self, concluidos, provisorio):
        self.rodando = False
        self.botao.config(state="normal")

        if concluidos and self.ampliar_inicio:
            self.log(t("\nTempo total: %s") % duracao(time.time() - self.ampliar_inicio))
        self.rotulo_estado.config(
            text=t("concluido") if concluidos
            else t("interrompido — veja o andamento"))

        if not concluidos:
            messagebox.showerror(t("Nada concluido"),
                                 t("Nenhum pacote foi gerado. Veja o andamento."))
            return

        # Perguntar o destino so agora, com o trabalho feito: se algo falhar no
        # meio, o usuario nao escolheu pasta a toa.
        destino = filedialog.askdirectory(
            title=t("Onde salvar %d pacote(s) pronto(s)?") % len(concluidos))
        if not destino:
            self.log(t("\nSalvamento cancelado. Os arquivos ficaram em %s") % provisorio)
            return

        destino = Path(destino)
        for nome in concluidos:
            origem = provisorio / nome
            if origem.exists():
                shutil.copy2(origem, destino / nome)
        shutil.rmtree(provisorio, ignore_errors=True)

        # Com os .utx a salvo no destino escolhido, nada em trabalho/ tem mais
        # uso. No modo de um pacote so sobra o png/, que sustenta as miniaturas
        # ainda na tela -- apagar aqui deixaria a grade mostrando texturas cujo
        # arquivo nao existe mais e impediria reprocessar com outra selecao.
        if not self.pacote_atual:
            shutil.rmtree(motor.BASE / "trabalho", ignore_errors=True)

        self.log(t("\n%d pacote(s) salvos em %s") % (len(concluidos), destino))
        messagebox.showinfo(
            t("Concluido"),
            t("%d pacote(s) salvos em:\n%s\n\nCopie para a pasta Textures do cliente, "
            "mantendo os nomes.") % (len(concluidos), destino))


def autoteste(raiz, registro):
    """
    Faz sozinho o que o usuario faria, anotando cada passo.

    Existe porque uma falha que so aparece no executavel nao tem como ser
    investigada pelo codigo-fonte: e preciso rodar no mesmo lugar, com as
    mesmas ferramentas e os mesmos caminhos. O arquivo que ele deixa diz ate
    onde chegou.
    """
    import gui_npc

    def anotar(*partes):
        linha = " ".join(str(x) for x in partes)
        try:
            with open(registro, "a", encoding="utf-8", errors="replace") as f:
                f.write(linha + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            pass

    anotar(t("\n===== autoteste %s =====") % time.strftime("%Y-%m-%d %H:%M:%S"))
    anotar(t("congelado: %s") % getattr(sys, "frozen", False))
    anotar(t("executavel: %s") % sys.executable)
    anotar(t("BASE: %s") % motor.BASE)
    anotar(t("AQUI: %s") % motor.AQUI)

    T = motor.carregar_config()
    for chave in sorted(T):
        anotar(t("  %-10s %-6s %s") % (chave, "ok" if Path(T[chave]).exists() else "FALTA",
                                    T[chave]))

    abas = ttk.Notebook(raiz)
    abas.pack(fill="both", expand=True)
    aba = ttk.Frame(abas)
    abas.add(aba, text=t("NPC"))
    janela = gui_npc.JanelaNpc(raiz, aba)
    anotar(t("janela montada. cliente: %s") % (janela.cliente.get() or "(nenhum)"))

    if not janela.cliente.get():
        anotar(t("sem cliente detectado; não da para seguir"))
        raiz.after(100, raiz.quit)
        return

    estado = {"fase": 0}

    def ler():
        anotar(t("[1] lendo o cliente"))
        janela.ler_cliente()
        raiz.after(2000, espera_leitura)

    def espera_leitura():
        if janela.rodando:
            raiz.after(2000, espera_leitura)
            return
        anotar(t("[2] %d NPCs, %d efeitos, %d pacotes recusados")
               % (len(janela.npcs), len(janela.efeitos), len(janela.recusados)))
        if not janela.npcs or not janela.efeitos:
            anotar(t("    não carregou; parando"))
            raiz.after(100, raiz.quit)
            return
        raiz.after(200, escolher)

    def escolher():
        janela.busca_npc.set(janela.npcs[0]["tag"])
        raiz.update_idletasks()
        filhos = janela.lista_npc.get_children()
        anotar(t("[3] NPCs filtrados: %d") % len(filhos))
        if not filhos:
            raiz.after(100, raiz.quit)
            return
        janela.lista_npc.selection_set(filhos[0])

        janela.busca_fx.set(janela.efeitos[0]["classe"])
        raiz.update_idletasks()
        fx = janela.lista_fx.get_children()
        anotar(t("[4] efeitos filtrados: %d") % len(fx))
        if not fx:
            raiz.after(100, raiz.quit)
            return
        janela.lista_fx.selection_set(fx[0])
        janela.adicionar_efeito()
        anotar(t("    escolhido: %s") % janela.escolhidos)

        janela.id_novo.set("59999")
        janela.nome_novo.set("Autoteste")
        raiz.after(200, gerar)

    def gerar():
        anotar(t("[5] Gerar"))
        janela.gerar()
        raiz.after(3000, espera_geracao)

    def espera_geracao():
        estado["fase"] += 1
        if janela.rodando:
            if estado["fase"] % 10 == 0:
                anotar(t("    ainda gerando (%d)") % estado["fase"])
            raiz.after(3000, espera_geracao)
            return
        anotar(t("[6] terminou. relatorio: %s")
               % ("sim" if janela.ultimo_relatorio else "NAO"))
        anotar(t("--- registro da janela ---"))
        anotar(janela.texto.get("1.0", "end").strip())
        anotar(t("===== fim do autoteste ====="))
        raiz.after(300, raiz.quit)

    raiz.after(500, ler)


def marca_do_projeto(widget, lado=16):
    """
    O icone do programa em miniatura, branco, como ele foi desenhado.

    Duas razoes para ele estar aqui em vez de um simbolo de engrenagem: o
    ⚙ depende da fonte instalada e ja apareceu como uma pena em maquina de
    usuario, e a marca do proprio programa e o que identifica a janela.

    Houve um tempo em que esta funcao o escurecia. O icone nasceu branco, para
    a barra de titulo escura do Windows, e num botao cinza-claro de 16 pixels
    ele sumia -- entao a luminancia era invertida e puxada para um
    azul-ardosia. Com o tema escuro isso passou a trabalhar contra: o mesmo
    problema ao contrario, um desenho escuro num botao quase preto. Sem
    transformacao nenhuma ele volta a ser legivel.
    """
    try:
        from PIL import Image, ImageTk
        with Image.open(RECURSOS / "icone.ico") as bruto:
            pequeno = bruto.convert("RGBA").resize((lado, lado), Image.LANCZOS)
        return ImageTk.PhotoImage(pequeno, master=widget)
    except Exception:
        return None


PROJETO = "https://github.com/JEAN-ALMEIDA-CZO"
AUTOR = "Jean Almeida - \u00d0ark\u00d0omi"
PIX = "jeanalmeida418@gmail.com"


def _versao():
    """O numero de `versao.py`, que e o mesmo gravado dentro do .exe."""
    try:
        import versao
        return ".".join(str(n) for n in versao.VERSAO[:3])
    except Exception:                               # noqa: BLE001
        return "?"


def abrir_o_manual(raiz, assunto=None):
    """
    Abre o manual, na pagina pedida ou no inicio.

    Nao achar o texto nao pode ser um erro silencioso: sem os .md o botao
    pareceria quebrado, e a pessoa nao teria como saber que o que falta e um
    arquivo que nao veio junto.
    """
    import manual

    if manual.abrir(raiz, assunto) is None:
        messagebox.showinfo(
            t("Manual não encontrado"),
            t("O texto do manual não veio junto com o programa."))


def janela_de_creditos(raiz):
    """
    Quem fez, onde fica o projeto e como apoiar.

    A chave PIX tem botao de copiar: chave lida da tela e digitada a mao e
    exatamente onde se troca um caractere e o dinheiro vai para outra pessoa.
    """
    import webbrowser

    janela = ajuda.por_icone(tk.Toplevel(raiz))
    janela.title(t("Sobre"))
    janela.transient(raiz)
    janela.resizable(False, False)

    quadro = ttk.Frame(janela, padding=18)
    quadro.pack(fill="both", expand=True)

    topo = ttk.Frame(quadro)
    topo.pack(anchor="w")
    marca = marca_do_projeto(topo, lado=32)
    if marca is not None:
        selo = ttk.Label(topo, image=marca)
        selo.imagem = marca
        selo.pack(side="left", padx=(0, 10))
    nomes = ttk.Frame(topo)
    nomes.pack(side="left")
    ttk.Label(nomes, text="L2PackTool",
              font=("Segoe UI", 14, "bold")).pack(anchor="w")
    ttk.Label(nomes, text=t("Versão %s") % _versao(),
              foreground="#667").pack(anchor="w")

    ttk.Separator(quadro).pack(fill="x", pady=12)

    ttk.Label(quadro, text=t("Desenvolvedor"),
              font=("Segoe UI", 9, "bold")).pack(anchor="w")
    ttk.Label(quadro, text=AUTOR).pack(anchor="w", pady=(0, 10))

    ttk.Label(quadro, text=t("Rede social"),
              font=("Segoe UI", 9, "bold")).pack(anchor="w")
    ligacao = ttk.Label(quadro, text=PROJETO, foreground=tema.INFO,
                        cursor="hand2")
    ligacao.pack(anchor="w")
    ligacao.bind("<Button-1>", lambda _e: webbrowser.open(PROJETO))
    # O sublinhado so no passar do mouse: um rotulo azul e sublinhado o tempo
    # todo compete com o resto da janela por atencao.
    ligacao.bind("<Enter>", lambda _e: ligacao.configure(
        font=("Segoe UI", 9, "underline")))
    ligacao.bind("<Leave>", lambda _e: ligacao.configure(font=("Segoe UI", 9)))

    ttk.Separator(quadro).pack(fill="x", pady=12)

    ttk.Label(quadro, text=t("Apoie o projeto"),
              font=("Segoe UI", 9, "bold")).pack(anchor="w")
    ttk.Label(quadro, foreground="#555", justify="left", wraplength=340,
              text=t("Uma doacao de qualquer valor ajuda a manter o "
                     "programa.")).pack(anchor="w", pady=(2, 8))

    linha = ttk.Frame(quadro)
    linha.pack(anchor="w", fill="x")
    ttk.Label(linha, text=t("PIX:")).pack(side="left")
    caixa = ttk.Entry(linha, width=30)
    caixa.insert(0, PIX)
    caixa.configure(state="readonly")
    caixa.pack(side="left", padx=(6, 6))

    copiado = ttk.Label(quadro, text="", foreground=tema.BOM)

    def copiar():
        try:
            janela.clipboard_clear()
            janela.clipboard_append(PIX)
            copiado.configure(text=t("Chave copiada."))
        except tk.TclError:
            copiado.configure(text=t("Não deu para copiar."),
                              foreground=tema.ATENCAO)

    ttk.Button(linha, text=t("Copiar"), command=copiar).pack(side="left")
    copiado.pack(anchor="w", pady=(6, 0))

    ttk.Button(quadro, text=t("Fechar"),
               command=janela.destroy).pack(anchor="e", pady=(16, 0))

    janela.bind("<Escape>", lambda _e: janela.destroy())
    janela.update_idletasks()
    x = raiz.winfo_rootx() + (raiz.winfo_width() - janela.winfo_width()) // 2
    y = raiz.winfo_rooty() + 90
    janela.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
    janela.grab_set()
    return janela


def janela_de_configuracoes(raiz, ocupado, refazer):
    """
    Configuracoes. Por enquanto so o idioma, mas ja com lugar para o resto.

    Trocar de idioma refaz as abas, porque o texto de um rotulo do Tk fica
    decidido na hora em que ele e criado: nao existe "retraduzir" sem montar
    de novo. Refazer, porem, joga fora o que estiver carregado nas abas, entao
    com trabalho em andamento a escolha fica guardada para a proxima abertura.
    """
    janela = ajuda.por_icone(tk.Toplevel(raiz))
    janela.title(t("Configurações"))
    janela.transient(raiz)
    janela.resizable(False, False)

    quadro = ttk.Frame(janela, padding=16)
    quadro.pack(fill="both", expand=True)

    ttk.Label(quadro, text=t("Idioma"),
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(quadro, foreground="#666", justify="left", wraplength=330,
              text=t("Frase ainda sem tradução aparece em portugues.")
              ).pack(anchor="w", pady=(2, 8))

    escolha = tk.StringVar(value=idioma.atual())
    for codigo, nome in idioma.IDIOMAS:
        ttk.Radiobutton(quadro, text=nome, value=codigo,
                        variable=escolha).pack(anchor="w", pady=2)

    ttk.Label(quadro, foreground="#666", justify="left", wraplength=330,
              text=t("As traducoes ficam em arquivos .ini na pasta idiomas, ao "
                     "lado do programa: da para corrigir uma frase sem "
                     "recompilar nada.")).pack(anchor="w", pady=(10, 0))

    linha = ttk.Frame(quadro)
    linha.pack(fill="x", pady=(16, 0))

    def aplicar():
        codigo = escolha.get()
        janela.destroy()
        if codigo == idioma.atual():
            return

        idioma.gravar_preferencia(motor.CONFIG, codigo)
        if ocupado():
            messagebox.showinfo(
                t("Idioma"),
                t("Tem trabalho em andamento, entao deixo a janela como "
                  "esta.\n\nO idioma escolhido entra na proxima vez que o "
                  "programa abrir."))
            return
        idioma.escolher(codigo)
        refazer()

    ttk.Button(linha, text=t("Aplicar"), command=aplicar).pack(side="right")
    ttk.Button(linha, text=t("Cancelar"),
               command=janela.destroy).pack(side="right", padx=(0, 8))

    janela.update_idletasks()
    x = raiz.winfo_rootx() + (raiz.winfo_width() - janela.winfo_width()) // 2
    y = raiz.winfo_rooty() + 120
    janela.geometry("+%d+%d" % (max(x, 0), max(y, 0)))
    janela.grab_set()


def montar(raiz):
    """
    Barra de cima e abas. Separado de main() para poder rodar de novo quando o
    idioma muda: as abas sao destruidas e montadas outra vez, ja traduzidas.
    """
    abertas = []

    import gui_projeto
    import projeto

    # O cabecalho leva a marca e o projeto em uso. Trocar de projeto troca a
    # pasta do cliente e a do servidor em TODAS as abas de uma vez -- era o
    # que antes se fazia em dezoito campos, um par por aba.
    cabecalho = gui_projeto.Cabecalho(raiz, raiz, ao_trocar=lambda: None)
    cabecalho.pack(fill="x")
    ttk.Separator(raiz, orient="horizontal").pack(fill="x")

    barra = cabecalho.direita
    botao = ttk.Button(barra, compound="left")
    botao.pack(side="right")

    botao.imagem = marca_do_projeto(botao)
    if botao.imagem is not None:
        botao.configure(image=botao.imagem)

    # Empacotado depois e tambem a direita, entao ele cai a ESQUERDA do de
    # Configuracoes -- que e onde a pessoa espera achar o secundario.
    creditos = ttk.Button(barra, command=lambda: janela_de_creditos(raiz))
    creditos.pack(side="right", padx=(0, 6))

    # O manual fica ao lado de `Sobre`, e nao dentro de cada aba: quem procura
    # uma coisa sem saber em que tela ela mora precisa de um lugar so.
    livro = ttk.Button(barra, command=lambda: abrir_o_manual(raiz))
    livro.pack(side="right", padx=(0, 6))

    corpo = ttk.Frame(raiz)
    corpo.pack(fill="both", expand=True)

    def ocupado():
        # Processando textura, gerando NPC ou esperando o jogo fechar para
        # devolver os .ini: em qualquer um desses, destruir as abas perderia o
        # trabalho ou deixaria o cliente com os .ini trocados.
        return any(getattr(j, "rodando", False) or getattr(j, "vigiando", False)
                   for j in abertas)

    # Quem fecha a janela vive noutra funcao e nao enxerga as abas. A
    # pergunta fica pendurada na raiz, que as duas enxergam.
    raiz.ha_trabalho = ocupado

    def montar_abas():
        del abertas[:]
        # As abas antigas foram destruidas; os observadores delas nao podem
        # sobreviver apontando para widget morto.
        projeto.limpar_inscritos()
        abas = ttk.Notebook(corpo)
        abas.pack(fill="both", expand=True)

        aba_texturas = rolagem.Area(abas)
        abas.add(aba_texturas, text=t("  Texture Upscaler · Beta  "))
        gui_projeto.SeletorDeProjeto(aba_texturas.dentro, raiz).pack(fill="x")
        abertas.append(Janela(raiz, aba_texturas.dentro))

        # A aba de NPC e opcional de proposito: ela depende do l2asm e do
        # l2disasm, e quem so quer ampliar textura nao deve ficar sem programa
        # porque uma ferramenta que nao usa esta faltando.
        try:
            import gui_npc
            aba_npc = rolagem.Area(abas)
            abas.add(aba_npc, text=t("  NPC  "))
            gui_projeto.SeletorDeProjeto(aba_npc.dentro, raiz).pack(fill="x")
            abertas.append(gui_npc.JanelaNpc(raiz, aba_npc.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  NPC  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de NPC não carregou:\n\n%s") % e).pack()

        # O video do lobby. Fica antes das outras abas de lobby porque e o que
        # a maioria quer: escolher um video e pronto.
        try:
            import gui_video
            aba_video = rolagem.Area(abas)
            abas.add(aba_video, text=t("  Lobby Vídeo  "))
            gui_projeto.SeletorDeProjeto(aba_video.dentro, raiz).pack(fill="x")
            abertas.append(gui_video.JanelaVideo(raiz, aba_video.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Lobby Vídeo  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de video não carregou:\n\n%s") % e).pack()

        # Itens depende do l2disasm e do l2asm, como a de NPC -- e pela mesma
        # razao fica opcional.
        try:
            import gui_item
            aba_item = rolagem.Area(abas)
            abas.add(aba_item, text=t("  Itens  "))
            gui_projeto.SeletorDeProjeto(aba_item.dentro, raiz).pack(fill="x")
            abertas.append(gui_item.JanelaItem(raiz, aba_item.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Itens  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de itens não carregou:\n\n%s") % e).pack()

        # Habilidades anda junto com Itens: mesmas ferramentas, mesmo jeito de
        # trabalhar, e quem cria um item costuma querer a habilidade tambem.
        try:
            import gui_skill
            aba_skill = rolagem.Area(abas)
            abas.add(aba_skill, text=t("  Habilidades  "))
            gui_projeto.SeletorDeProjeto(aba_skill.dentro, raiz).pack(fill="x")
            abertas.append(gui_skill.JanelaSkill(raiz, aba_skill.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Habilidades  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de habilidades não carregou:\n\n%s") % e).pack()

        # O glow vem depois das habilidades porque le as mesmas tabelas de
        # item: quem chega ate aqui ja tem o cliente aberto e as armas listadas.
        try:
            import gui_glow
            aba_glow = rolagem.Area(abas)
            abas.add(aba_glow, text=t("  Glow  "))
            gui_projeto.SeletorDeProjeto(aba_glow.dentro, raiz).pack(fill="x")
            abertas.append(gui_glow.JanelaGlow(raiz, aba_glow.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Glow  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de glow não carregou:\n\n%s") % e).pack()

        # Multisell fica ao lado do Glow: as duas leem as tabelas de item do
        # cliente e a pasta do servidor, e quem cria uma arma costuma querer
        # a loja que a vende.
        try:
            import gui_multisell
            aba_ms = rolagem.Area(abas)
            abas.add(aba_ms, text=t("  Multisell  "))
            gui_projeto.SeletorDeProjeto(aba_ms.dentro, raiz).pack(fill="x")
            abertas.append(gui_multisell.JanelaMultisell(raiz, aba_ms.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Multisell  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de multisell não carregou:\n\n%s") % e).pack()

        # Mob fica ao lado de Multisell porque as duas mexem no datapack do
        # servidor e leem as tabelas de item do cliente -- a lista de drop pede
        # o nome e o desenho do item exatamente como o checkout pede.
        try:
            import gui_mob
            aba_mob = rolagem.Area(abas)
            abas.add(aba_mob, text=t("  Mob  "))
            gui_projeto.SeletorDeProjeto(aba_mob.dentro, raiz).pack(fill="x")
            abertas.append(gui_mob.JanelaMob(raiz, aba_mob.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Mob  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de mob não carregou:\n\n%s") % e).pack()

        # A conferencia e a unica aba que nao muda nada por conta propria: le o
        # cliente e diz o que falta. Por isso vem antes da que abre arquivos.
        try:
            import gui_conferir
            aba_conf = rolagem.Area(abas)
            abas.add(aba_conf, text=t("  Conferir Cliente  "))
            gui_projeto.SeletorDeProjeto(aba_conf.dentro, raiz).pack(fill="x")
            abertas.append(gui_conferir.JanelaConferir(raiz, aba_conf.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  Conferir Cliente  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de conferência não carregou:\n\n%s") % e).pack()

        # Abrir arquivo do cliente so precisa do l2encdec, que e a ferramenta
        # mais basica do conjunto -- por isso esta aba quase nunca falta.
        try:
            import gui_arquivos
            aba_arq = rolagem.Area(abas)
            abas.add(aba_arq, text=t("  L2Crypt  "))
            gui_projeto.SeletorDeProjeto(aba_arq.dentro, raiz).pack(fill="x")
            abertas.append(gui_arquivos.JanelaArquivos(raiz, aba_arq.dentro))
        except Exception as e:
            aviso = ttk.Frame(abas)
            abas.add(aviso, text=t("  L2Crypt  "))
            ttk.Label(aviso, padding=20, justify="left", foreground=tema.ATENCAO,
                      text=t("A aba de arquivos não carregou:\n\n%s") % e).pack()

        # Cada aba passa a seguir o projeto: recebe as pastas agora e a cada
        # troca, em vez de cada uma guardar a sua.
        for tela in abertas:
            try:
                gui_projeto.ligar(tela)
            except Exception:                       # noqa: BLE001
                pass            # aba com defeito nao impede as outras

    def refazer():
        # Quem tem laco proprio para antes de ser destruido: um tempo
        # marcado segue valendo depois da aba sumir, e volta procurando
        # widget que ja morreu.
        for tela in abertas:
            fechar = getattr(tela, "fechar", None)
            if callable(fechar):
                try:
                    fechar()
                except Exception:               # noqa: BLE001
                    pass        # aba com defeito nao impede as outras
        for filho in corpo.winfo_children():
            filho.destroy()
        botao.configure(text="  " + t("Configurações"))
        creditos.configure(text=t("Sobre"))
        livro.configure(text=t("Manual"))
        montar_abas()
        cabecalho.atualizar()

    botao.configure(text="  " + t("Configurações"),
                    command=lambda: janela_de_configuracoes(raiz, ocupado, refazer))
    ajuda.Dica(botao, lambda: t("Idioma da interface e outras preferências."))
    creditos.configure(text=t("Sobre"))
    ajuda.Dica(creditos, lambda: t("Quem fez, a versão e como apoiar."))
    livro.configure(text=t("Manual"))
    ajuda.Dica(livro, lambda: t("O manual do programa, página por página."))
    montar_abas()


def main():
    raiz = tk.Tk()
    registro = instalar_rede(raiz)

    idioma.carregar()
    idioma.escolher(idioma.ler_preferencia(motor.CONFIG))

    if "--autoteste" in sys.argv:
        raiz.title("L2PackTool — autoteste")
        raiz.geometry("1060x780")
        autoteste(raiz, registro)
        raiz.mainloop()
        return

    raiz.title("L2PackTool")
    raiz.geometry("1060x780")
    raiz.minsize(900, 660)
    # O tema inteiro sai do `tema`: paleta, tipografia, metrica e o estilo de
    # cada widget. Antes daqui a janela usava o cinza de fabrica do Windows,
    # com cada tela escolhendo a propria cor -- e trocar o visual era trocar
    # dez arquivos.
    try:
        import tema
        tema.aplicar(raiz)
    except Exception:                           # noqa: BLE001
        # Tema ausente nao pode impedir o programa de abrir: sem ele a janela
        # fica feia, com ele quebrado ela nao abre.
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass

    # Quem ja usava o programa tem as pastas no config.ini. Elas viram um
    # projeto chamado `Padrao` na primeira execucao: ninguem perde o que tinha
    # configurado, e ninguem precisa saber que a estrutura mudou.
    try:
        import projeto as _projeto
        _projeto.migrar()
    except Exception:                               # noqa: BLE001
        pass

    montar(raiz)

    def ao_fechar():
        """
        Fechar a janela fecha o que ela abriu: UnrealEd, visualizador do umodel.

        Sem isto eles ficam orfaos na memoria depois que o programa some da
        tela, e ninguem associa meio giga preso ao programa que ja fechou.

        A pergunta existe porque o UnrealEd pode ter cena nao salva: matar o
        editor sem avisar custaria trabalho do usuario. O jogo aberto em
        DevMode NAO entra aqui -- ele e aberto pelo Windows (ShellExecute, por
        causa da elevacao) e nao ha processo para segurar; alem disso, e o
        fechamento dele que dispara a devolucao dos .ini.
        """
        # Trabalho em andamento primeiro: fechar no meio de uma instalacao
        # deixa o cliente com meio lobby dentro.
        trabalhando = getattr(raiz, "ha_trabalho", lambda: False)()
        if trabalhando and not messagebox.askyesno(
                t("Cancelar o que está rodando?"),
                t("Há trabalho em andamento. Fechar agora cancela no meio, e "
                  "o que já foi gravado no cliente fica pela metade.\n\n"
                  "Cancelar mesmo assim?")):
            return

        vivos = motor.filhos_vivos()
        if vivos and not messagebox.askyesno(
                t("Fechar tudo?"),
                t("Isto ainda esta aberto por conta do programa:\n\n  %s\n\n"
                  "Fechar o L2PackTool fecha também. O que não foi salvo no "
                  "UnrealEd se perde.\n\nFechar assim mesmo?")
                % "\n  ".join(vivos)):
            return
        motor.encerrar_filhos()
        raiz.destroy()

    raiz.protocol("WM_DELETE_WINDOW", ao_fechar)
    raiz.mainloop()


if __name__ == "__main__":
    main()
