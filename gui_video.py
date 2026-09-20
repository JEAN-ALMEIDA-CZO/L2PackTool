#!/usr/bin/env python3
"""
Aba "Lobby Video" -- por o video do usuario na tela de login.

Escolher o video, cortar o trecho, por a logo, aplicar. Quantos quadros, que
tamanho, que formato e que enquadramento saem do proprio video e do modelo.

O lobby modelo viaja dentro do programa, e nao e o pacote de video inteiro --
sao os poucos kilobytes que ele tem de proprio: a tabela de nomes, a de imports
e os 562 bytes da malha da tela. Junto vai o mapa, que planta essa tela na cena
e aponta a camera. Nada e procurado no cliente.

Esta aba ja foi outra coisa. A primeira versao animava uma textura do lobby com
a corrente `AnimNext`, que e como o proprio cliente anima fogo e agua. Passava
em tudo o que da para conferir de fora -- propriedade escrita, umodel lendo a
corrente inteira, cliente carregando sem erro -- e na tela nao acontecia nada.
O filme e um `MaterialSequence`, o material feito para tocar uma lista no
tempo, aplicado a uma malha plana na frente da camera.
"""

import io
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import tema
import ajuda
import versao
import gui_projeto
import l2criar
import l2seq
import l2upscale as motor
from idioma import t

# A previa nao guarda um quadro para cada quadro do filme: centenas de imagens
# vivas na memoria do Tk sao centenas de megabytes. Ela amostra ate este tanto,
# do video INTEIRO, e a regua de corte so escolhe a fatia -- ver
# `extrair_previa`. Tocando sempre na duracao do trecho, o ritmo do que se ve e
# o ritmo do que vai ao jogo.
MAXIMO_DA_PREVIA = 140
LARGURA_DA_PREVIA = 560


class JanelaVideo:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()

        self.lobby = None           # o lobby instalado, para a previa exata
        self.modelos = l2criar.modelos_embutidos()
        self.modelo = self._modelo_por_chave(
            motor.ler_opcao("lobby", "modelo", ""))
        self.previa = []            # PhotoImage de cada quadro da previa
        self.atual = 0
        self.tocando = None
        self.marcado = None
        self._tempos = []       # bilhetes de `after`, para cancelar ao fechar
        self.comecou = 0.0
        self.arrastando = False
        self.do_pacote = False
        self.duracao = None         # segundos do video escolhido
        self.cadencia = None        # quadros por segundo do video escolhido
        self.logo = tk.StringVar(value=motor.ler_opcao("logo", "arquivo", ""))
        self.logo_pil = None        # a imagem original, para reescalar
        self.logo_tk = None         # a escalada, presa contra o coletor
        self.pegou_logo = None      # (dx, dy) enquanto o mouse arrasta
        self.serie = 0              # numero da previa em andamento
        self.quadros_previa = []    # o video inteiro, amostrado
        self.tempos_previa = []     # o segundo de cada um deles

        quadro = ttk.Frame(pai, padding=10)
        self.quadro = quadro    # a ancora dos `after` desta aba
        quadro.bind("<Destroy>", self._ao_morrer)
        quadro.pack(fill="both", expand=True)

        # ---- o cliente ----
        topo = ttk.Frame(quadro)
        topo.pack(fill="x")
        self.rotulo_lobby = ttk.Label(topo, text="", foreground=tema.TEXTO_FRACO)
        self.rotulo_lobby.pack(side="left")
        ttk.Button(topo, text=t("Projetos…"),
                   command=self.escolher_cliente).pack(side="right")
        ajuda.ajuda(topo, lambda: t(
            "Pasta system do cliente onde o lobby será instalado."))

        linha_mod = ttk.Frame(quadro)
        linha_mod.pack(fill="x", pady=(8, 0))
        ttk.Label(linha_mod, text=t("Lobby modelo:")).pack(side="left")
        self.escolhido = tk.StringVar()
        self.combo_modelo = ttk.Combobox(linha_mod, state="readonly", width=34,
                                         textvariable=self.escolhido,
                                         values=self._valores_do_combo())
        self.combo_modelo.pack(side="left", padx=(6, 0))
        self.combo_modelo.bind("<<ComboboxSelected>>", self.ao_trocar_modelo)
        if self.modelo:
            self.escolhido.set(self._rotulo(self.modelo))
        ajuda.ajuda(linha_mod, lambda: t(
            "Lobby que serve de base. Cada crônica tem o seu, com tamanho "
            "de quadro e nome de pacote próprios.\n\n"
            "Do modelo vêm o mapa, a malha da tela e as posições dos "
            "personagens. Os quadros, a sequência e o shader são gerados.\n\n"
            "Os lobbys das crônicas entram no cliente como são, com a música "
            "deles. O do L2PackTool é o que recebe o vídeo."))

        # ---- video ----
        vid = ttk.LabelFrame(quadro, text=t("Vídeo"), padding=8)
        vid.pack(fill="x", pady=(8, 0))
        linha = ttk.Frame(vid)
        linha.pack(fill="x")
        self.video = tk.StringVar(value=motor.ler_opcao("video", "ultimo", ""))
        ttk.Entry(linha, textvariable=self.video).pack(side="left", fill="x",
                                                       expand=True)
        ttk.Button(linha, text=t("Escolher vídeo…"),
                   command=self.escolher_video).pack(side="left", padx=(8, 0))
        ajuda.ajuda(linha, lambda: t(
            "Formatos aceitos: MP4, AVI, MKV, MOV, WEBM, GIF e WEBP "
            "animado.\n\n"
            "O enquadramento é automático: o vídeo entra inteiro e "
            "centralizado, sem corte nas laterais."))

        # ---- a regua de corte ----
        corte = ttk.Frame(vid)
        corte.pack(fill="x", pady=(10, 0))
        self.inicio = tk.DoubleVar(value=0.0)
        self.fim = tk.DoubleVar(value=0.0)

        linha_a = ttk.Frame(corte)
        linha_a.pack(fill="x")
        ttk.Label(linha_a, text=t("início"), width=7).pack(side="left")
        self.regua_inicio = ttk.Scale(linha_a, from_=0, to=1,
                                      variable=self.inicio,
                                      command=self.ao_cortar)
        self.regua_inicio.pack(side="left", fill="x", expand=True)

        linha_b = ttk.Frame(corte)
        linha_b.pack(fill="x", pady=(2, 0))
        ttk.Label(linha_b, text=t("fim"), width=7).pack(side="left")
        self.regua_fim = ttk.Scale(linha_b, from_=0, to=1, variable=self.fim,
                                   command=self.ao_cortar)
        self.regua_fim.pack(side="left", fill="x", expand=True)

        linha_c = ttk.Frame(corte)
        linha_c.pack(fill="x", pady=(6, 0))
        self.repetir = tk.BooleanVar(value=True)
        ttk.Checkbutton(linha_c, variable=self.repetir,
                        text=t("repetir sem parar no jogo")).pack(side="left")
        ttk.Button(linha_c, text=t("Vídeo inteiro"),
                   command=self.tudo).pack(side="left", padx=(12, 0))
        ajuda.ajuda(linha_c, lambda: t(
            "Define o trecho do vídeo que será usado.\n\n"
            "O número de quadros é calculado pela cadência do vídeo, o que "
            "mantém a velocidade original. Cada quadro ocupa cerca de 2 MB no "
            "pacote; acima do limite, a cadência é reduzida automaticamente."))

        self.ritmo = ttk.Label(vid, text="", foreground=tema.TEXTO_FRACO)
        self.ritmo.pack(anchor="w", pady=(6, 0))

        # ---- logo ----
        marca = ttk.LabelFrame(quadro, text=t("Logo"), padding=8)
        marca.pack(fill="x", pady=(8, 0))
        linha_l = ttk.Frame(marca)
        linha_l.pack(fill="x")
        ttk.Entry(linha_l, textvariable=self.logo).pack(side="left", fill="x",
                                                        expand=True)
        ttk.Button(linha_l, text=t("Escolher imagem…"),
                   command=self.escolher_logo).pack(side="left", padx=(8, 0))
        ttk.Button(linha_l, text=t("Tirar"),
                   command=self.tirar_logo).pack(side="left", padx=(6, 0))

        linha_m = ttk.Frame(marca)
        linha_m.pack(fill="x", pady=(8, 0))
        self.logo_largura = tk.DoubleVar(
            value=float(motor.ler_opcao("logo", "largura", "20") or 20))
        self.logo_x = tk.DoubleVar(
            value=float(motor.ler_opcao("logo", "x", "4") or 4))
        self.logo_y = tk.DoubleVar(
            value=float(motor.ler_opcao("logo", "y", "6") or 6))
        for rotulo, variavel, ate in ((t("tamanho"), self.logo_largura, 100),
                                      (t("horizontal"), self.logo_x, 100),
                                      (t("vertical"), self.logo_y, 100)):
            caixa = ttk.Frame(linha_m)
            caixa.pack(side="left", fill="x", expand=True, padx=(0, 10))
            ttk.Label(caixa, text=rotulo).pack(anchor="w")
            ttk.Scale(caixa, from_=0, to=ate, variable=variavel,
                      command=self.ao_mexer_logo).pack(fill="x")
        linha_t = ttk.Frame(marca)
        linha_t.pack(fill="x", pady=(8, 0))
        self.logo_trecho = tk.BooleanVar(value=False)
        ttk.Checkbutton(linha_t, variable=self.logo_trecho,
                        text=t("só num trecho"),
                        command=self.ao_mexer_logo).pack(side="left")
        self.logo_entra = tk.DoubleVar(value=0.0)
        self.logo_sai = tk.DoubleVar(value=0.0)
        for rotulo, variavel in ((t("entra"), self.logo_entra),
                                 (t("sai"), self.logo_sai)):
            caixa = ttk.Frame(linha_t)
            caixa.pack(side="left", fill="x", expand=True, padx=(12, 0))
            ttk.Label(caixa, text=rotulo).pack(anchor="w")
            escala = ttk.Scale(caixa, from_=0, to=1, variable=variavel,
                               command=self.ao_mexer_logo)
            escala.pack(fill="x")
            if rotulo == t("entra"):
                self.escala_entra = escala
            else:
                self.escala_sai = escala

        self.rotulo_logo = ttk.Label(marca, text="", foreground=tema.TEXTO_FRACO)
        self.rotulo_logo.pack(anchor="w", pady=(6, 0))
        ajuda.ajuda(linha_m, lambda: t(
            "Imagem sobreposta ao vídeo, aplicada aos quadros gerados.\n\n"
            "Tamanho e posição são dados em porcentagem da área visível, e "
            "não em pixels: a prévia e o quadro final ficam iguais apesar de "
            "terem resoluções diferentes.\n\n"
            "PNG com transparência é preservado.\n\n"
            "Sem \"só num trecho\", a logo fica durante todo o vídeo. Com a "
            "opção marcada, ela aparece entre os dois tempos, contados a "
            "partir do início do trecho escolhido na régua."))

        # ---- previa ----
        tela = ttk.LabelFrame(quadro, text=t("Como vai ficar"), padding=8)
        tela.pack(fill="both", expand=True, pady=(8, 0))
        self.alto_da_previa = int(LARGURA_DA_PREVIA / l2seq.ASPECTO_PADRAO)
        self.alto_da_previa -= self.alto_da_previa % 2
        self.tela = tk.Canvas(tela, width=LARGURA_DA_PREVIA,
                              height=self.alto_da_previa, background=tema.ABISSO,
                              highlightthickness=0)
        self.tela.pack()
        self.item_quadro = self.tela.create_image(0, 0, anchor="nw")
        self.item_logo = self.tela.create_image(0, 0, anchor="nw",
                                                state="hidden")
        self.tela.bind("<ButtonPress-1>", self.pegar_logo)
        self.tela.bind("<B1-Motion>", self.arrastar_logo)
        self.tela.bind("<ButtonRelease-1>", self.soltar_logo)

        controles = ttk.Frame(tela)
        controles.pack(fill="x", pady=(6, 0))
        self.botao_tocar = ttk.Button(controles, text="▶", width=3,
                                      command=self.alternar)
        self.botao_tocar.pack(side="left")
        ttk.Button(controles, text="⟲", width=3,
                   command=self.recomecar).pack(side="left", padx=(4, 10))
        self.botao_pacote = ttk.Button(controles, text=t("Ver o do cliente"),
                                       command=self.previa_do_pacote,
                                       state="disabled")
        self.botao_pacote.pack(side="left", padx=(0, 10))
        self.laco = tk.BooleanVar(value=True)
        ttk.Checkbutton(controles, variable=self.laco,
                        text=t("repetir em loop")).pack(side="left")
        self.posicao = tk.DoubleVar(value=0)
        self.regua = ttk.Scale(controles, from_=0, to=1, variable=self.posicao,
                               command=self.ao_arrastar)
        self.regua.pack(side="left", fill="x", expand=True, padx=(12, 8))
        self.contador = ttk.Label(controles, text="", foreground=tema.TEXTO_FRACO,
                                  width=22, anchor="e")
        self.contador.pack(side="right")

        self.aviso_previa = ttk.Label(
            tela, foreground=tema.TEXTO_FRACO, justify="left", wraplength=940,
            text=t("Escolha um vídeo para ver a prévia."))
        self.aviso_previa.pack(anchor="w", pady=(6, 0))
        ajuda.ajuda(tela, lambda: t(
            "Mostra o enquadramento e a velocidade finais, em resolução "
            "reduzida e sem a compressão do pacote.\n\n"
            "\"Ver o do cliente\" exibe os quadros lidos do pacote já "
            "instalado."))

        # ---- acao ----
        acao = ttk.Frame(quadro)
        acao.pack(fill="x", pady=(10, 0))
        self.botao_lobby = ttk.Button(acao, text=t("Instalar lobby"),
                                      command=self.instalar_lobby,
                                      state="disabled")
        self.botao_lobby.pack(side="left", padx=(0, 8))
        self.botao_criar = ttk.Button(acao, text=t("Gerar vídeo e instalar"),
                                      command=self.criar, state="disabled")
        self.botao_criar.pack(side="left")
        self.estado = ttk.Label(acao, text="")
        self.estado.pack(side="left", padx=(10, 0))
        self.barra = ttk.Progressbar(acao, length=220, mode="determinate")
        self.barra.pack(side="right")

        # ---- registro ----
        reg = ttk.LabelFrame(quadro, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=6, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

        self.mostrar_cliente()
        self.ao_mexer_logo()
        self._marcar(300, self.olhar_o_instalado)
        if Path(self.video.get()).is_file():
            self._marcar(600, lambda: self.medir(Path(self.video.get())))

    # ---- ajudantes -------------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def trabalho(self):
        pasta = motor.BASE / "trabalho" / "video"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def system(self):
        return Path(motor.ler_opcao("cliente", "system", ""))

    def corte(self):
        inicio = max(0.0, float(self.inicio.get()))
        fim = float(self.fim.get())
        if self.duracao:
            fim = min(fim or self.duracao, self.duracao)
        if fim - inicio < 0.1:
            fim = min(inicio + 0.1, self.duracao or (inicio + 0.1))
        return inicio, fim

    def conta(self):
        """Quantos quadros o trecho pede, e quanto isso custa em disco."""
        if not self.cadencia or not self.modelo:
            return None
        inicio, fim = self.corte()
        # DXT1 gasta meio byte por pixel; o tamanho do quadro vem do modelo,
        # porque ele muda de uma cronica para outra.
        por_quadro = self.modelo["largura"] * self.modelo["altura"] // 2
        return l2criar.quadros_do_video({"fps": self.cadencia}, inicio, fim,
                                        bytes_por_quadro=por_quadro)

    def duracao_da_previa(self):
        if self.do_pacote and self.lobby and self.lobby.get("tempo_total"):
            return max(0.2, float(self.lobby["tempo_total"]))
        conta = self.conta()
        return max(0.2, conta["segundos"] if conta else 1.0)

    def atualizar_botoes(self):
        tem_video = Path(self.video.get()).is_file()
        pronto = bool(self.modelo) and self.system().is_dir() and not self.rodando
        self.botao_criar.config(
            state="normal" if (pronto and tem_video) else "disabled")
        self.botao_lobby.config(state="normal" if pronto else "disabled")

    # ---- instalar o lobby, sem video -------------------------------------
    def instalar_lobby(self):
        """
        Poe no cliente o lobby escolhido, do jeito que ele e.

        E o caminho de quem so quer trocar a tela de entrada pela de outra
        cronica: mapa, cenario, texturas e a musica daquele lobby.
        """
        if self.rodando or not self.modelo:
            return
        if not messagebox.askokcancel(
                t("Instalar o lobby"),
                t("Lobby: %s\nDestino: %s\n\nO que existir com o mesmo nome "
                  "vai para backup_lobby antes.\n\nO cliente precisa estar "
                  "fechado.\n\nContinuar?")
                % (self.modelo["nome"], self.system().parent)):
            return
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("instalando…"))
        self.log(t("Instalando %s") % self.modelo["nome"])
        threading.Thread(target=self._lobby_thread, daemon=True).start()

    def _lobby_thread(self):
        erro = None
        try:
            l2criar.instalar(self.system(), self.modelo, None,
                             aolog=lambda x: self._no_tk(self.log, "  " + x),
                             guardar_copias=True, com_video=False, T=self.T)
        except Exception as e:                      # noqa: BLE001
            erro = e
        self._no_tk(self._fim_acao, erro, False)

    # ---- o cliente e o modelo --------------------------------------------
    # ---- o cliente -------------------------------------------------------
    def escolher_cliente(self):
        """
        O cliente vem do projeto, como em toda outra aba.

        Esta tela quer a `system` e não a raiz -- é lá que o lobby é
        instalado --, por isso pede `system` ao projeto em vez de montar o
        caminho aqui.
        """
        pasta = gui_projeto.pedir_pasta(self.raiz, "system")
        if pasta:
            motor.gravar_opcao("cliente", "system", pasta)
            self.log(t("Cliente: %s") % pasta)
            self.mostrar_cliente()
            self.olhar_o_instalado()

    @staticmethod
    def _rotulo(modelo):
        """O nome, e so. O tamanho do quadro nao ajuda a escolher."""
        return modelo["nome"]

    def _valores_do_combo(self):
        return [self._rotulo(m) for m in self.modelos]

    def _modelo_por_chave(self, chave):
        for modelo in self.modelos:
            if modelo["chave"] == chave:
                return modelo
        return l2criar.modelo_embutido(chave)

    def ao_trocar_modelo(self, _evento=None):
        rotulo = self.escolhido.get()
        for modelo in self.modelos:
            if self._rotulo(modelo) == rotulo:
                self.modelo = modelo
                motor.gravar_opcao("lobby", "modelo", modelo["chave"])
                self.log(t("Modelo: %s") % modelo["nome"])
                break
        self.mostrar_cliente()
        self.olhar_o_instalado()

    def mostrar_cliente(self):
        system = self.system()
        if system.is_dir():
            self.rotulo_lobby.config(text=t("cliente: %s") % system.parent)
        else:
            self.rotulo_lobby.config(
                text=t("selecione a pasta system do cliente"))
        if self.modelo is None:
            self.rotulo_lobby.config(
                text=t("nenhum lobby modelo disponível"))
        self.atualizar_botoes()

    def olhar_o_instalado(self):
        """
        Le o lobby que ESTE programa instala, num caminho so.

        Nao e varredura: o arquivo tem nome conhecido e mora numa pasta
        conhecida. Nao existindo, nao ha o que mostrar -- e isso e normal num
        cliente que ainda nao recebeu o lobby.
        """
        if self.modelo is None or not self.system().is_dir():
            return
        alvo = (l2criar.pasta_do_cliente(self.system(), ".usx")
                / self.modelo["nome_do_arquivo"])
        if not alvo.is_file():
            self.lobby = None
            self.botao_pacote.config(state="disabled")
            return
        threading.Thread(target=self._instalado_thread, args=(alvo,),
                         daemon=True).start()

    def _no_tk(self, funcao, *argumentos):
        """
        Devolve a chamada para a thread do Tk -- e engole a janela fechada.

        Todo trabalho pesado desta aba roda fora da thread da interface e
        volta por aqui. Fechar o programa com uma extração em voo destrói a
        janela antes da thread terminar, e aí o `after` estoura lá dentro:
        traceback no console sem nada quebrado, ou silêncio total num
        executável sem console.

        São DOIS erros, e não um. `TclError` é a janela destruída; mas quando
        o laço principal já saiu, o `tkinter` nem chega a falar com o Tcl --
        ele levanta `RuntimeError: main thread is not in main loop` ao
        registrar o callback. Guardar só o primeiro deixa passar justamente o
        caso de fechar o programa, que é o comum.
        Ha um terceiro caso, que nao e a janela fechar: trocar de idioma
        destroi as abas e monta outras no lugar, e a raiz -- que e quem
        carrega o `after` -- continua viva. A volta chegava e falava com um
        widget desta aba que ja nao existia. Por isso a conferencia acontece
        na HORA DA VOLTA, e nao na hora de marcar.
        """
        def quando_der():
            if not self.aba_viva():
                return                          # a aba morreu no caminho
            funcao(*argumentos)

        try:
            self.raiz.after(0, quando_der)
        except (tk.TclError, RuntimeError):
            pass                                # a janela fechou

    def aba_viva(self):
        """Esta aba ainda esta na tela? Falsa depois de refazer as abas."""
        try:
            return bool(self.quadro.winfo_exists())
        except (tk.TclError, RuntimeError, AttributeError):
            return False

    def _instalado_thread(self, alvo):
        info = None
        try:
            info = l2seq.ler_sequencia(alvo)
        except Exception:
            info = None
        self._no_tk(self._fim_instalado, info)

    def _fim_instalado(self, info):
        """
        So habilita o botao. A previa que abre e a do video escolhido -- ler o
        pacote do cliente e coisa de quem pediu, nao de quem abriu a aba.
        """
        self.lobby = info
        self.botao_pacote.config(state="normal" if info else "disabled")

    # ---- video, corte e previa -------------------------------------------
    def escolher_video(self):
        nome = filedialog.askopenfilename(
            title=t("Escolha o vídeo"),
            filetypes=[(t("Vídeo e animação"),
                        "*.mp4 *.avi *.mkv *.mov *.webm *.gif *.webp"),
                       (t("Todos"), "*.*")])
        if not nome:
            return
        self.video.set(nome)
        motor.gravar_opcao("video", "ultimo", nome)
        self.log(t("Vídeo: %s") % nome)
        self.duracao = None
        self.atualizar_botoes()
        self.medir(Path(nome))

    def medir(self, origem):
        """Pergunta ao ffmpeg a duracao e a cadencia, e arma a regua."""
        self.aviso_previa.config(text=t("medindo o vídeo…"))
        threading.Thread(target=self._medir_thread, args=(origem,),
                         daemon=True).start()

    def _medir_thread(self, origem):
        dados, erro = {}, None
        try:
            dados = l2seq.dados_do_video(self.T, origem)
        except Exception as e:
            erro = e
        self._no_tk(self._fim_medida, dados, erro)

    def _fim_medida(self, dados, erro):
        if erro is not None:
            self.aviso_previa.config(text=t("falha ao medir o vídeo: %s")
                                     % erro)
            return
        self.duracao = dados.get("duracao")
        self.cadencia = dados.get("fps")
        if self.duracao:
            self.regua_inicio.config(to=self.duracao)
            self.regua_fim.config(to=self.duracao)
            self.inicio.set(0.0)
            self.fim.set(self.duracao)
            self.log(t("  o vídeo tem %.2f s a %.3g quadros por segundo")
                     % (self.duracao, self.cadencia or 0))
        self.ao_cortar()
        self.extrair_previa(Path(self.video.get()))

    def escolher_logo(self):
        nome = filedialog.askopenfilename(
            title=t("Escolha a imagem da logo"),
            filetypes=[(t("Imagem"), "*.png *.tga *.jpg *.jpeg *.bmp *.webp"),
                       (t("Todos"), "*.*")])
        if not nome:
            return
        self.logo.set(nome)
        motor.gravar_opcao("logo", "arquivo", nome)
        self.ao_mexer_logo()

    def tirar_logo(self):
        self.logo.set("")
        motor.gravar_opcao("logo", "arquivo", "")
        self.ao_mexer_logo()

    def ao_mexer_logo(self, _valor=None):
        """Guarda a escolha, acerta os limites do trecho e remarca a prévia."""
        arquivo = self.logo.get().strip()
        inicio, fim = self.corte()
        duracao = max(0.1, fim - inicio)
        estado = "normal" if self.logo_trecho.get() else "disabled"
        for escala in (self.escala_entra, self.escala_sai):
            escala.config(to=duracao, state=estado)
        if self.logo_sai.get() <= 0 or self.logo_sai.get() > duracao:
            self.logo_sai.set(duracao)
        if self.logo_entra.get() > self.logo_sai.get():
            self.logo_entra.set(0.0)

        self.guardar_logo()
        self.escrever_rotulo_da_logo()
        self.desenhar_logo()

    # ---- a logo sobre a previa -------------------------------------------
    def desenhar_logo(self):
        """
        Reescala e reposiciona o item da logo. Sem ffmpeg, sem espera.

        A imagem original fica guardada; so a copia escalada e refeita, e ela
        cabe numa tela de 640 -- e trabalho de milissegundos.
        """
        arquivo = self.logo.get().strip()
        if not arquivo or not Path(arquivo).is_file():
            self.logo_pil = None
            self.tela.itemconfig(self.item_logo, state="hidden")
            return
        if getattr(self, "_logo_aberta", None) != arquivo:
            try:
                self.logo_pil = Image.open(arquivo).convert("RGBA")
                self._logo_aberta = arquivo
            except Exception:
                self.logo_pil = None
                self.tela.itemconfig(self.item_logo, state="hidden")
                return

        larga = max(8, int(round(LARGURA_DA_PREVIA
                                 * self.logo_largura.get() / 100.0)))
        alta = max(4, int(round(larga * self.logo_pil.height
                                / float(self.logo_pil.width))))
        self.logo_tk = ImageTk.PhotoImage(
            self.logo_pil.resize((larga, alta), Image.LANCZOS))
        self.tela.itemconfig(self.item_logo, image=self.logo_tk)
        self.tela.coords(self.item_logo,
                         int(round(LARGURA_DA_PREVIA * self.logo_x.get()
                                   / 100.0)),
                         int(round(self.alto_da_previa * self.logo_y.get()
                                   / 100.0)))
        self.tela.tag_raise(self.item_logo)
        self.acertar_visibilidade_da_logo()

    def acertar_visibilidade_da_logo(self):
        """Fora do trecho escolhido, a logo some -- como vai sumir no jogo."""
        if self.logo_pil is None:
            self.tela.itemconfig(self.item_logo, state="hidden")
            return
        mostrar = True
        if self.logo_trecho.get() and self.previa:
            quando = (self.duracao_da_previa() * self.atual
                      / max(1, len(self.previa)))
            mostrar = self.logo_entra.get() <= quando <= self.logo_sai.get()
        self.tela.itemconfig(self.item_logo,
                             state="normal" if mostrar else "hidden")

    def pegar_logo(self, evento):
        if self.logo_pil is None:
            return
        x1, y1, x2, y2 = self.tela.bbox(self.item_logo)
        if x1 <= evento.x <= x2 and y1 <= evento.y <= y2:
            self.pegou_logo = (evento.x - x1, evento.y - y1)

    def arrastar_logo(self, evento):
        if not self.pegou_logo or self.logo_pil is None:
            return
        dx, dy = self.pegou_logo
        x1, y1, x2, y2 = self.tela.bbox(self.item_logo)
        larga, alta = x2 - x1, y2 - y1
        x = min(max(0, evento.x - dx), LARGURA_DA_PREVIA - larga)
        y = min(max(0, evento.y - dy), self.alto_da_previa - alta)
        self.tela.coords(self.item_logo, x, y)
        self.logo_x.set(100.0 * x / LARGURA_DA_PREVIA)
        self.logo_y.set(100.0 * y / self.alto_da_previa)
        self.escrever_rotulo_da_logo()

    def soltar_logo(self, _evento=None):
        if self.pegou_logo:
            self.pegou_logo = None
            self.guardar_logo()

    def guardar_logo(self):
        if self.logo.get().strip():
            motor.gravar_opcao("logo", "largura",
                               "%.0f" % self.logo_largura.get())
            motor.gravar_opcao("logo", "x", "%.1f" % self.logo_x.get())
            motor.gravar_opcao("logo", "y", "%.1f" % self.logo_y.get())

    def escrever_rotulo_da_logo(self):
        arquivo = self.logo.get().strip()
        if not arquivo:
            self.rotulo_logo.config(text=t("sem logo"))
            return
        recado = t("%s — %.0f%% de largura, a %.0f%% x %.0f%%") % (
            Path(arquivo).name, self.logo_largura.get(), self.logo_x.get(),
            self.logo_y.get())
        if self.logo_trecho.get():
            recado += t(", de %.1f s a %.1f s") % (self.logo_entra.get(),
                                                   self.logo_sai.get())
        else:
            recado += t(", o vídeo inteiro")
        self.rotulo_logo.config(text=recado)

    def marca_dagua(self):
        """
        A logo como o extrator espera: fracoes, e nao pixeis.

        Guardar em fracao e o que faz a previa a 640 e o quadro a 2048 caírem
        no mesmo lugar. Em pixeis, a logo sairia tres vezes maior num do que no
        outro.
        """
        arquivo = self.logo.get().strip()
        if not arquivo or not Path(arquivo).is_file():
            return None
        pedido = {"arquivo": arquivo,
                  "largura": max(0.01, self.logo_largura.get() / 100.0),
                  "x": self.logo_x.get() / 100.0,
                  "y": self.logo_y.get() / 100.0}
        if self.logo_trecho.get():
            pedido["entra"] = self.logo_entra.get()
            pedido["sai"] = self.logo_sai.get()
        return pedido

    def tudo(self):
        if self.duracao:
            self.inicio.set(0.0)
            self.fim.set(self.duracao)
            self.ao_cortar()

    def ao_cortar(self, _valor=None):
        """Régua mexida: acerta o texto e remarca a prévia."""
        if self.duracao and self.inicio.get() > self.fim.get() - 0.1:
            self.inicio.set(max(0.0, self.fim.get() - 0.1))
        conta = self.conta()
        if conta:
            inicio, fim = self.corte()
            recado = t("%.1f s → %.1f s  ·  %d quadros a %.1f/s  ·  %.0f MB") % (
                inicio, fim, conta["quadros"], conta["por_segundo"],
                conta["bytes"] / 1048576.0)
            if conta["cortado"]:
                recado += t("   (%d reduzidos para caber no limite)") % \
                    conta["pedido"]
            else:
                recado += t("   velocidade original")
            self.ritmo.config(text=recado)
        self.atualizar_botoes()
        if getattr(self, "escala_entra", None) is not None:
            duracao = max(0.1, self.corte()[1] - self.corte()[0])
            for escala in (self.escala_entra, self.escala_sai):
                escala.config(to=duracao)
            if self.logo_sai.get() > duracao:
                self.logo_sai.set(duracao)
        self.recortar_previa()

    # ---- a previa do video -----------------------------------------------
    def extrair_previa(self, origem):
        """
        Amostra o video INTEIRO, uma vez.

        Decodificar e o que custa -- e custa pela duracao, nao pela quantidade
        de quadros. Extrair a cada mexida na regua seria pagar isso de novo a
        cada movimento; extraindo o video todo, a regua passa a escolher entre
        quadros que ja estao na memoria.
        """
        if not self.duracao:
            return
        quantos = max(24, min(MAXIMO_DA_PREVIA, int(self.duracao * 12)))
        self.serie += 1
        self.aviso_previa.config(
            text=t("montando a prévia do vídeo (%d quadros)…") % quantos)
        threading.Thread(target=self._previa_thread,
                         args=(origem, quantos, self.duracao, self.serie),
                         daemon=True).start()

    def _previa_thread(self, origem, quantos, duracao, serie):
        imagens, erro = [], None
        try:
            alto = int(LARGURA_DA_PREVIA / l2seq.ASPECTO_PADRAO)
            alto -= alto % 2
            # Pasta por execucao: duas previas ao mesmo tempo na mesma pasta se
            # apagam, porque o extrator limpa o destino antes de comecar.
            imagens = l2seq.extrair_quadros(
                self.T, origem, self.trabalho() / ("previa%d" % (serie % 3)),
                quantos, LARGURA_DA_PREVIA, alto, faixa=False)
        except Exception as e:
            erro = e
        self._no_tk(self._fim_previa, imagens, erro, serie, duracao)

    def _fim_previa(self, imagens, erro, serie=None, duracao=None):
        if serie is not None and serie != self.serie:
            return                      # chegou atrasada; ja ha outra valendo
        if erro is not None:
            self.aviso_previa.config(text=t("falha ao montar a prévia: %s")
                                     % erro)
            return
        self.parar()
        self.quadros_previa, self.tempos_previa = [], []
        total = max(1, len(imagens))
        for k, caminho in enumerate(imagens):
            try:
                self.quadros_previa.append(
                    ImageTk.PhotoImage(Image.open(caminho)))
                self.tempos_previa.append((duracao or 0.0) * k / total)
            except Exception:
                continue
        if not self.quadros_previa:
            self.aviso_previa.config(text=t("a prévia saiu vazia."))
            return
        self.recortar_previa()

    def recortar_previa(self):
        """
        Escolhe os quadros do trecho. Sem ffmpeg, sem espera.

        E o que faz a regua responder na hora: os quadros ja estao prontos, e
        cortar e so decidir quais entram.
        """
        if not self.quadros_previa:
            return
        inicio, fim = self.corte()
        escolhidos = [q for q, quando in zip(self.quadros_previa,
                                             self.tempos_previa)
                      if inicio <= quando <= fim]
        if not escolhidos:
            escolhidos = [self.quadros_previa[0]]
        self.parar()
        self.previa = escolhidos
        self.do_pacote = False
        conta = self.conta()
        self.aviso_previa.config(
            text=t("Prévia: %d quadros para os %d do filme, na velocidade "
                   "final.")
            % (len(self.previa), conta["quadros"] if conta else 0))
        self.regua.config(to=max(1, len(self.previa) - 1))
        self.desenhar_logo()
        self.botao_tocar.config(text="⏸")
        self.do_comeco(0)

    def _vivo(self):
        """A tela da previa ainda existe? Falso depois de refazer as abas."""
        try:
            return bool(self.tela.winfo_exists())
        except tk.TclError:
            return False

    def _marcar(self, ms, funcao):
        """
        Marca um tempo e guarda o bilhete.

        Destruir o widget apaga o comando registrado nele, mas o tempo
        segue marcado: ele vence, o Tcl nao acha mais o comando e reclama.
        Guardando o bilhete da para cancelar de verdade em `fechar`.
        """
        bilhete = self.quadro.after(ms, funcao)
        self._tempos.append(bilhete)
        return bilhete

    def _ao_morrer(self, evento):
        # Em `<Destroy>` o Tkinter as vezes entrega o NOME do widget, e
        # nao o objeto -- comparar pelo nome vale nos dois casos. A
        # conferencia existe para nao fechar a aba quando quem morreu
        # foi um filho do quadro.
        if str(evento.widget) == str(self.quadro):
            self.fechar()

    def fechar(self):
        """Chamado antes de destruir a aba. Para o que anda sozinho."""
        for bilhete in self._tempos:
            try:
                self.quadro.after_cancel(bilhete)
            except tk.TclError:
                pass                        # ja venceu, ou o quadro se foi
        del self._tempos[:]
        self.parar()

    # ---- o tocador -------------------------------------------------------
    def mostrar(self, indice):
        if not self.previa or not self._vivo():
            return
        self.atual = max(0, min(len(self.previa) - 1, indice))
        self.tela.itemconfig(self.item_quadro, image=self.previa[self.atual])
        self.acertar_visibilidade_da_logo()
        if not self.arrastando:
            self.posicao.set(self.atual)
        segundos = self.duracao_da_previa()
        self.contador.config(
            text=t("%d/%d · %.1f s · %.1f/s")
            % (self.atual + 1, len(self.previa),
               segundos * (self.atual + 1) / len(self.previa),
               len(self.previa) / segundos))

    def tocar(self):
        """
        Anda ate o quadro que o RELOGIO manda, e marca o proximo.

        Contar `after()` acumula atraso: cada chamada volta um pouco depois do
        pedido, e em duzentos quadros o filme da previa fica visivelmente mais
        lento do que o do jogo. Aqui a posicao sai do tempo decorrido, como faz
        um tocador de video: se a maquina engasgar, pula quadro em vez de
        atrasar o filme inteiro.
        """
        if not self.previa:
            self.tocando = None
            return
        duracao = self.duracao_da_previa()
        passo = duracao / len(self.previa)
        decorrido = time.perf_counter() - self.comecou

        if decorrido >= duracao:
            if not self.laco.get():
                self.mostrar(len(self.previa) - 1)
                self.tocando = None
                self.botao_tocar.config(text="▶")
                return
            self.comecou += duracao * int(decorrido // duracao)
            decorrido = time.perf_counter() - self.comecou

        indice = min(len(self.previa) - 1, int(decorrido / passo))
        self.mostrar(indice)
        falta = (indice + 1) * passo - (time.perf_counter() - self.comecou)
        # Marcado no CANVAS, e nao na raiz: trocar o idioma destroi as abas
        # e monta de novo, e um tempo marcado na raiz sobreviveria a isso
        # para voltar mexendo num canvas que ja morreu.
        self.tocando = self.tela.after(max(1, int(falta * 1000)), self.tocar)

    def parar(self):
        if self.tocando:
            try:
                self.tela.after_cancel(self.tocando)
            except tk.TclError:
                pass                        # o canvas ja foi embora
            self.tocando = None
        try:
            self.botao_tocar.config(text="▶")
        except tk.TclError:
            pass                        # a aba ja foi destruida

    def alternar(self):
        if self.tocando:
            self.parar()
        elif self.previa:
            if self.atual >= len(self.previa) - 1:
                self.atual = 0
            self.botao_tocar.config(text="⏸")
            self.do_comeco(self.atual)

    def recomecar(self):
        if not self.previa:
            return
        if self.tocando:
            try:
                self.tela.after_cancel(self.tocando)
            except tk.TclError:
                pass
            self.do_comeco(0)
        else:
            self.mostrar(0)

    def do_comeco(self, indice):
        duracao = self.duracao_da_previa()
        self.atual = indice
        self.comecou = time.perf_counter() - indice * duracao / len(self.previa)
        self.tocar()

    def ao_arrastar(self, _valor=None):
        if not self.previa:
            return
        indice = int(round(self.posicao.get()))
        if indice == self.atual:
            return
        self.arrastando = True
        try:
            if self.tocando:
                self.parar()
            self.mostrar(indice)
        finally:
            self.arrastando = False

    # ---- a previa vinda do pacote ----------------------------------------
    def previa_do_pacote(self):
        """
        Refaz a previa com quadros lidos de dentro do arquivo instalado.

        E a unica previa que nao precisa de ressalva: os pixeis vem do pacote,
        ja comprimidos em DXT1, recortados na faixa que a malha mostra.
        """
        if not self.lobby:
            return
        self.aviso_previa.config(text=t("lendo os quadros do pacote…"))
        threading.Thread(target=self._pacote_thread, daemon=True).start()

    def _pacote_thread(self):
        """
        A ordem das operacoes importa mais do que parece: cortar e `reduce()`
        antes de converter deixa o trabalho cinco vezes mais rapido, porque
        `convert()` obriga o Pillow a decodificar o DXT1 inteiro de uma vez.
        """
        imagens, erro = [], None
        try:
            quantos = min(MAXIMO_DA_PREVIA, len(self.lobby["quadros"]))
            alto = int(LARGURA_DA_PREVIA / l2seq.ASPECTO_PADRAO)
            amostras = l2seq.amostrar_do_pacote(self.lobby, quantos)
            for k, (_indice, dds) in enumerate(amostras):
                imagem = Image.open(io.BytesIO(dds))
                largura, altura = imagem.size
                util = int(round(largura / l2seq.ASPECTO_PADRAO))
                topo = max(0, (altura - util) // 2)
                imagem = imagem.crop((0, topo, largura, topo + util))
                if largura >= LARGURA_DA_PREVIA * 2:
                    imagem = imagem.reduce(largura // LARGURA_DA_PREVIA)
                imagens.append(imagem.resize((LARGURA_DA_PREVIA, alto),
                                             Image.BILINEAR).convert("RGB"))
                if k % 20 == 0:
                    self._no_tk(self.aviso_previa.config,
                                {"text": t("lendo os quadros do pacote… "
                                           "%d de %d")
                                 % (k + 1, len(amostras))})
        except Exception as e:
            erro = e
        self._no_tk(self._fim_pacote, imagens, erro)

    def _fim_pacote(self, imagens, erro):
        if erro is not None:
            self.aviso_previa.config(
                text=t("falha ao ler os quadros do pacote: %s") % erro)
            return
        self.parar()
        self.previa = [ImageTk.PhotoImage(im) for im in imagens]
        if not self.previa:
            return
        self.do_pacote = True       # `recortar_previa` devolve a do video
        self.aviso_previa.config(
            text=t("Pacote instalado: %d quadros, como o cliente exibe.")
            % len(self.previa))
        self.regua.config(to=max(1, len(self.previa) - 1))
        self.botao_tocar.config(text="⏸")
        self.desenhar_logo()
        self.do_comeco(0)

    # ---- criar -----------------------------------------------------------
    def criar(self):
        if self.rodando or not self.modelo:
            return
        conta = self.conta()
        if not conta:
            return
        inicio, fim = self.corte()
        if not messagebox.askyesno(
                t("Criar o lobby"),
                t("Destino: %s\n\n%d quadros, de %.1f s a %.1f s, %.0f MB."
                  "\n\nIsto demora: cada quadro é convertido e comprimido, e "
                  "o pacote passa de cem megabytes. Enquanto roda, a janela "
                  "pode parecer parada — é normal, acompanhe pela barra.\n\n"
                  "Arquivos existentes com o mesmo nome serão copiados "
                  "para backup_lobby.\n\nO cliente precisa estar fechado."
                  "\n\nContinuar?")
                % (self.system().parent, conta["quadros"], inicio, fim,
                   conta["bytes"] / 1048576.0)):
            return
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("preparando…"))
        self.barra["value"] = 0
        threading.Thread(target=self._criar_thread,
                         args=(Path(self.video.get()), conta, inicio, fim,
                               self.marca_dagua()),
                         daemon=True).start()

    def _criar_thread(self, origem, conta, inicio, fim, logo):
        erro = None
        try:
            def anotar(texto):
                self._no_tk(self.log, "  " + texto)

            # O filme vai no lobby que foi feito para receber tela; se o
            # que estiver escolhido for um lobby de cronica, e esse que
            # manda, e o log diz.
            modelo = l2criar.lobby_de_video() or self.modelo
            if modelo is not self.modelo:
                anotar(t("o vídeo vai no lobby %s") % modelo["nome"])
            molde = modelo["molde"]
            nome = modelo["nome_do_arquivo"]

            pngs = l2seq.extrair_quadros(
                self.T, origem, self.trabalho() / "quadros", conta["quadros"],
                self.modelo["largura"], self.modelo["altura"], aolog=anotar,
                comeco=inicio, fim=fim, logo=logo)

            def progresso(feitos, total):
                self._no_tk(self._progresso, feitos, total)

            feito = l2criar.montar(
                self.T, molde, pngs, self.trabalho() / nome,
                conta["segundos"], repetir=self.repetir.get(),
                aolog=anotar, aoprogresso=progresso)

            self._no_tk(self.estado.config,
                        {"text": t("instalando…")})
            l2criar.instalar(self.system(), modelo, feito["arquivo"],
                             aolog=anotar, guardar_copias=False, T=self.T)
        except Exception as e:
            erro = e
        self._no_tk(self._fim_acao, erro, True)

    # ---- fim de qualquer das duas ----------------------------------------
    def _progresso(self, feitos, total):
        self.barra["maximum"] = total
        self.barra["value"] = feitos
        self.estado.config(text=t("%d de %d quadros") % (feitos, total))

    def _fim_acao(self, erro, _criou=True):
        self.rodando = False
        self.estado.config(text="")
        self.barra["value"] = 0
        self.atualizar_botoes()
        if erro is not None:
            self.log(t("  falha: %s") % erro)
            messagebox.showerror(t("Não deu"), str(erro))
            return
        self.log(t("  concluído."))
        self._marcar(500, self.olhar_o_instalado)
        messagebox.showinfo(
            t("Pronto"),
            t("Lobby criado e instalado. Abra o cliente para conferir."))
