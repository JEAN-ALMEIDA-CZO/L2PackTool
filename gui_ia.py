#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A janela que pede arte à IA: ícone, botão ou borda -- parado ou animado.

Ela existe separada das abas porque o pedido é sempre o mesmo, venha de onde
vier: a aba de Itens quer um ícone, a de Glow quer um ícone, quem monta
interface quer um botão. Uma janela só, chamada de todos os lugares, evita
três telas parecidas e três jeitos de escrever o mesmo pedido.

## O que fica com o usuário e o que não fica

O que ele escreve é o DETALHE: o objeto, o material, a cor, o que lembrar. A
parte que mantém o resultado utilizável no jogo -- 32x32, fundo transparente,
sem texto, luz de cima -- é fixa e não aparece como campo. Não é para
esconder: é porque editá-la é a forma mais rápida de receber uma imagem
bonita que não serve como ícone. O pedido montado fica à vista, embaixo, para
quem quiser conferir.

## A animação

Os quadros não são pedidos à IA. Cada chamada desenha de novo, e quadros
desenhados de novo piscam. A arte vem da IA uma vez, e o movimento é feito
sobre ela -- pulso, giro ou varredura --, em ciclo fechado. O pacote sai com
os quadros numerados, que é como o cliente espera uma sequência.
"""

import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import l2ia
import motor
import tema
from idioma import t

try:
    from PIL import Image, ImageTk
except ImportError:                                 # noqa: BLE001
    Image = ImageTk = None

LADO_DA_PREVIA = 128

# A previa do tamanho real e menor de proposito: ela mostra 32 ou 64 pixels
# ampliados, e ampliar demais nao acrescenta informacao nenhuma.
LADO_DA_PREVIA_REAL = 96

TIPOS = (("icone", "ícone de item"),
         ("botao", "botão de interface"),
         ("borda", "moldura / borda"))

# O tamanho comum de cada coisa no cliente. E so o ponto de partida: a caixa
# ao lado aceita outro, porque ha cliente com icone de 64 e interface de 256.
LADOS = {"icone": 32, "botao": 128, "borda": 256}

# O fundo da arte. Transparente e o padrao porque icone entra sobre a moldura
# do inventario, mas botao e moldura as vezes querem fundo solido -- e trocar
# isso depois nao pode obrigar a gerar de novo.
FUNDOS = (("transparente", None),
          ("preto", "#000000"),
          ("branco", "#ffffff"),
          ("cinza escuro", "#1b1b1b"),
          ("escolher cor…", "escolher"))


class JanelaDeArte:
    """
    Devolve em `.resposta` {"imagem": caminho, "nome": ..., "quadros": [...]}.

    `quadros` vem preenchido só quando a animação foi pedida; é uma lista de
    caminhos, na ordem do ciclo.
    """

    def __init__(self, raiz, dono, sugestao="", tipo="icone", pai=None):
        self.raiz = raiz
        self.dono = dono
        self.pai = pai or raiz
        self.resposta = None
        self.gerada = None          # PIL.Image do que a IA devolveu
        self.previa_tk = None
        self.referencias = []
        # Quando a arte vem de um GIF, estes sao os quadros dele -- e eles
        # mandam na animacao, porque foram desenhados.
        self.quadros_do_arquivo = []
        # A arte como veio, antes do fundo. Trocar de fundo nao pode custar
        # outra geracao, nem pode perder a transparencia de volta.
        self.gerada_original = None
        self.cor_do_fundo = None
        self.rodando = False
        self.trabalho = Path(motor.BASE) / "trabalho" / "ia"
        self.trabalho.mkdir(parents=True, exist_ok=True)

        self.janela = ajuda.por_icone(tk.Toplevel(self.pai))
        self.janela.title(t("Gerar arte com IA"))
        self.janela.transient(self.pai)

        # Quem chamou pode ser modal -- a tela de escolher icone e. Nesse
        # caso ela esta com o grab do Tk, e todo clique iria para la: esta
        # janela apareceria e nao responderia. Toma-se o bastao aqui e
        # devolve-se ao fechar, senao a de tras fica sem modalidade depois.
        self._grab_anterior = self.janela.grab_current()
        try:
            self.janela.grab_set()
        except tk.TclError:
            pass
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)

        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)

        self._montar_topo(quadro, tipo, sugestao)
        self._montar_referencias(quadro)
        self._montar_observacoes(quadro)
        self._montar_animacao(quadro)
        self._montar_previa_e_acao(quadro)

        self._explicar_o_modo()
        self._conferir_o_provedor()
        self.janela.bind("<Escape>", lambda _e: self.fechar())
        self.janela.lift()
        self.janela.focus_force()
        raiz.wait_window(self.janela)

    def fechar(self):
        """Fecha devolvendo o grab a quem o tinha."""
        try:
            self.janela.grab_release()
        except tk.TclError:
            pass
        anterior = getattr(self, "_grab_anterior", None)
        if anterior is not None:
            try:
                anterior.grab_set()
            except tk.TclError:
                pass
        try:
            self.janela.destroy()
        except tk.TclError:
            pass

    # -- as partes da tela -------------------------------------------------
    def _montar_topo(self, quadro, tipo, sugestao):
        topo = ttk.Frame(quadro)
        topo.pack(fill="x")

        ttk.Label(topo, text=t("o que gerar:")).pack(side="left")
        self.tipo = tk.StringVar(value=tipo)
        for chave, rotulo in TIPOS:
            ttk.Radiobutton(topo, text=t(rotulo), value=chave,
                            variable=self.tipo).pack(side="left", padx=(8, 0))

        # O tamanho do jogo, e nao o da geracao: a IA devolve 1024x1024
        # sempre, e o que importa e para que tamanho a arte vai encolher.
        ttk.Label(topo, text=t("no cliente:")).pack(side="left", padx=(16, 0))
        self.lado = tk.StringVar(value=str(LADOS.get(tipo, 32)))
        ttk.Combobox(topo, textvariable=self.lado, values=("32", "64", "128",
                                                           "256"),
                     state="readonly", width=5).pack(side="left", padx=(6, 0))
        ttk.Label(topo, text=t("fundo:")).pack(side="left", padx=(12, 0))
        self.fundo = tk.StringVar(value=FUNDOS[0][0])
        caixa_fundo = ttk.Combobox(
            topo, textvariable=self.fundo, state="readonly", width=12,
            values=[rotulo for rotulo, _cor in FUNDOS])
        caixa_fundo.pack(side="left", padx=(6, 0))
        caixa_fundo.bind("<<ComboboxSelected>>", lambda _e: self._trocar_fundo())

        ajuda.ajuda(topo, lambda: t(
            "O tamanho que a arte terá dentro do jogo.@@"
            "Ícone de item é 32x32 na maioria das crônicas, e 64x64 em "
            "algumas. Botão e moldura são maiores.@@"
            "Entra no pedido à IA — desenhar pensando em 32x32 é diferente de "
            "desenhar um quadro grande — e manda na prévia real, ao lado da "
            "grande."))
        self.tipo.trace_add("write", lambda *_a: self._tamanho_do_tipo())
        self.lado.trace_add("write", lambda *_a: self._mudou_o_tamanho())

        linha = ttk.Frame(quadro)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text=t("o objeto:")).pack(side="left")
        self.objeto = tk.StringVar(value=sugestao)
        ttk.Entry(linha, textvariable=self.objeto).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "O que a arte mostra: uma espada curva de gelo, uma poção "
            "vermelha, um botão de confirmar.@@"
            "Entra no pedido junto com a parte fixa, que é o que mantém o "
            "resultado utilizável no jogo."))

        self.recado = ttk.Label(quadro, foreground=tema.ATENCAO,
                                justify="left", wraplength=560)
        self.recado.pack(anchor="w", pady=(6, 0))

    def _montar_referencias(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Referências (opcional)"),
                               padding=6)
        caixa.pack(fill="x", pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("Imagens que o modelo olha para seguir o estilo. É o "
                         "que faz o resultado parecer com o resto do seu "
                         "cliente, em vez de parecer com a média da "
                         "internet.")).pack(anchor="w")
        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(6, 0))
        self.lista_ref = tk.Listbox(linha, height=3,
                                    background=tema.PAINEL,
                                    foreground=tema.TEXTO,
                                    highlightthickness=1,
                                    highlightbackground=tema.BORDA,
                                    borderwidth=0)
        self.lista_ref.pack(side="left", fill="x", expand=True)
        botoes = ttk.Frame(linha)
        botoes.pack(side="left", padx=(6, 0))
        ttk.Button(botoes, text=t("Juntar…"),
                   command=self.juntar_referencia).pack(fill="x")
        ttk.Button(botoes, text=t("Tirar"),
                   command=self.tirar_referencia).pack(fill="x", pady=(4, 0))

    def _montar_observacoes(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Observações"), padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("O detalhe que você quer: material, cor, época, o "
                         "que lembrar. A parte fixa do pedido — tamanho, "
                         "fundo transparente, sem texto, luz de cima — já "
                         "está garantida e não precisa ser repetida aqui.")
                  ).pack(anchor="w")
        self.observacoes = tk.Text(caixa, height=4, wrap="word",
                                   background=tema.PAINEL,
                                   foreground=tema.TEXTO,
                                   insertbackground=tema.TEXTO,
                                   highlightthickness=1,
                                   highlightbackground=tema.BORDA,
                                   borderwidth=0, font=tema.CORPO)
        self.observacoes.pack(fill="both", expand=True, pady=(6, 0))

    def _montar_animacao(self, quadro):
        caixa = ttk.LabelFrame(quadro, text=t("Animação (opcional)"),
                               padding=6)
        caixa.pack(fill="x", pady=(10, 0))
        ttk.Label(caixa, foreground=tema.TEXTO_FRACO, justify="left",
                  wraplength=560,
                  text=t("Os quadros não são pedidos à IA: cada chamada "
                         "desenharia de novo e a animação piscaria. A arte "
                         "vem uma vez e o movimento é feito sobre ela, em "
                         "ciclo fechado.")).pack(anchor="w")
        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(6, 0))
        self.animar = tk.BooleanVar(value=False)
        ttk.Checkbutton(linha, text=t("gerar animação"),
                        variable=self.animar).pack(side="left")
        ttk.Label(linha, text=t("modo:")).pack(side="left", padx=(12, 0))
        self.modo = tk.StringVar(value=l2ia.MODOS[0])
        self.caixa_modo = ttk.Combobox(linha, textvariable=self.modo,
                                       values=l2ia.MODOS, state="readonly",
                                       width=12)
        self.caixa_modo.pack(side="left", padx=(6, 0))
        # Doze modos e nome de uma palavra: sem a explicação ao lado, escolher
        # vira tentativa e erro.
        self.diz_o_modo = ttk.Label(linha, foreground=tema.TEXTO_FRACO)
        self.diz_o_modo.pack(side="left", padx=(8, 0))
        self.caixa_modo.bind("<<ComboboxSelected>>",
                             lambda _e: self._explicar_o_modo())
        ttk.Label(linha, text=t("quadros:")).pack(side="left", padx=(12, 0))
        self.quantos = tk.StringVar(value="8")
        ttk.Spinbox(linha, from_=2, to=32, width=5,
                    textvariable=self.quantos).pack(side="left", padx=(6, 0))
        # A velocidade só vale para a corrente do motor: numa família quem
        # manda no ritmo é o código da interface, e não o pacote.
        ttk.Label(linha, text=t("por segundo:")).pack(side="left", padx=(12, 0))
        self.taxa = tk.StringVar(value="15")
        ttk.Spinbox(linha, from_=1, to=60, width=5,
                    textvariable=self.taxa).pack(side="left", padx=(6, 0))


    def _dizer_o_modo(self):
        """
        Liga ou desliga a escolha de movimento, conforme de onde vêm os quadros.

        Com animação trazida de arquivo não há movimento a escolher: os
        quadros já existem. Deixar a caixa habilitada prometeria um efeito
        que não vai ser aplicado.
        """
        try:
            if self.quadros_do_arquivo:
                self.caixa_modo.config(state="disabled")
                self.diz_o_modo.config(
                    text=t("%d quadros vindos do arquivo")
                    % len(self.quadros_do_arquivo))
            else:
                self.caixa_modo.config(state="readonly")
                self._explicar_o_modo()
        except tk.TclError:
            pass

    def _explicar_o_modo(self):
        """Diz em uma linha o que o modo escolhido faz."""
        try:
            self.diz_o_modo.config(text=t(l2ia.EXPLICACAO.get(self.modo.get(),
                                                              "")))
        except tk.TclError:
            pass

    def _montar_previa_e_acao(self, quadro):
        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(12, 0))

        self.previa = tk.Canvas(baixo, width=LADO_DA_PREVIA,
                                height=LADO_DA_PREVIA,
                                background=tema.ABISSO, highlightthickness=1,
                                highlightbackground=tema.BORDA)
        self.previa.pack(side="left")

        # A prévia que importa: o tamanho final, ampliado SEM suavizar. É o
        # único jeito de ver antes que o detalhe de 1024 vira borrão em 32.
        coluna = ttk.Frame(baixo)
        coluna.pack(side="left", padx=(8, 0))
        self.previa_real = tk.Canvas(coluna, width=LADO_DA_PREVIA_REAL,
                                     height=LADO_DA_PREVIA_REAL,
                                     background=tema.ABISSO,
                                     highlightthickness=1,
                                     highlightbackground=tema.BORDA)
        self.previa_real.pack()
        self.diz_o_tamanho = ttk.Label(coluna, style="Miudo.TLabel")
        self.diz_o_tamanho.pack()

        direita = ttk.Frame(baixo)
        direita.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.estado = ttk.Label(direita, foreground=tema.TEXTO_FRACO,
                                justify="left", wraplength=400)
        self.estado.pack(anchor="w")

        acao = ttk.Frame(direita)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_gerar = ttk.Button(acao, text=t("Gerar"),
                                      style="Primario.TButton",
                                      command=self.gerar)
        self.botao_gerar.pack(side="left")
        self.botao_abrir = ttk.Button(acao, text=t("Abrir imagem…"),
                                      command=self.abrir_do_disco)
        self.botao_abrir.pack(side="left", padx=(6, 0))
        self.botao_usar = ttk.Button(acao, text=t("Usar esta"),
                                     command=self.usar, state="disabled")
        self.botao_usar.pack(side="left", padx=(6, 0))
        self.botao_animar_cliente = ttk.Button(
            acao, text=t("Animar no cliente…"),
            command=self.animar_no_cliente, state="disabled")
        self.botao_animar_cliente.pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Ver o pedido"),
                   command=self.ver_o_pedido).pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Fechar"),
                   command=self.fechar).pack(side="right")

    # -- o provedor --------------------------------------------------------
    def _conferir_o_provedor(self):
        """Diz de cara se dá para gerar, e o que fazer quando não dá."""
        self._atualizar_botoes()
        da, porque = l2ia.pronto(para="imagem")
        if da:
            self.recado.config(
                text=t("Usando %s, modelo %s.")
                % (l2ia.PROVEDORES[l2ia.provedor()]["nome"], l2ia.modelo()))
            return
        self.recado.config(
            text=t("%s\nO resto da tela continua valendo: “Abrir imagem…” "
                   "traz um PNG ou um GIF seu, e daí dá para animar e gravar "
                   "no cliente sem chave de API nenhuma.") % porque)

    # -- referências -------------------------------------------------------
    def juntar_referencia(self):
        nomes = filedialog.askopenfilenames(
            title=t("Imagens de referência"), parent=self.janela,
            filetypes=[(t("Imagens"), "*.png *.jpg *.jpeg *.webp *.bmp")])
        for nome in nomes:
            if nome not in self.referencias:
                self.referencias.append(nome)
                self.lista_ref.insert("end", Path(nome).name)

    def tirar_referencia(self):
        marcado = self.lista_ref.curselection()
        if not marcado:
            return
        indice = marcado[0]
        self.lista_ref.delete(indice)
        del self.referencias[indice]

    # -- gerar -------------------------------------------------------------
    def _pedido(self):
        """
        O pedido como ele vai: com o tamanho do jogo e com as referências.

        Quantas referências vão junto muda a natureza do pedido -- com imagem
        anexada o modelo EDITA o que recebeu, sem ela desenha do zero --, e o
        `montar_prompt` precisa saber disso.
        """
        return l2ia.montar_prompt(
            self.tipo.get(),
            self.observacoes.get("1.0", "end").strip(),
            self.objeto.get(),
            referencias=len(self.referencias),
            lado=self.lado_no_cliente())

    def ver_o_pedido(self):
        janela = ajuda.por_icone(tk.Toplevel(self.janela))
        janela.title(t("O pedido que vai para a IA"))
        texto = tk.Text(janela, wrap="word", width=78, height=22,
                        background=tema.PAINEL, foreground=tema.TEXTO,
                        borderwidth=0, font=tema.CORPO)
        texto.pack(fill="both", expand=True, padx=10, pady=10)
        texto.insert("1.0", self._pedido())
        texto.config(state="disabled")

    def gerar(self):
        if not self.objeto.get().strip():
            messagebox.showinfo(t("Falta dizer o quê"),
                                t("Escreva o que a arte deve mostrar."))
            return
        self.rodando = True
        self._atualizar_botoes()
        self.estado.config(text=t("pedindo à IA… isso leva alguns segundos."))
        threading.Thread(target=self._gerar_thread, daemon=True).start()

    def _gerar_thread(self):
        # Arte nova apaga a animação antiga: os quadros que vieram do GIF não
        # têm nada a ver com o desenho que a IA acabou de fazer.
        self.quadros_do_arquivo = []
        try:
            dados = l2ia.gerar_imagem(self._pedido(), self.referencias)
            alvo = self.trabalho / "gerada.png"
            alvo.write_bytes(dados)
            imagem = Image.open(alvo).convert("RGBA") if Image else None
            # Hoje a resposta é sempre um quadro só -- essas APIs não devolvem
            # animação. Perguntar mesmo assim custa nada, e no dia em que
            # devolverem, a animação entra em vez de virar quadro parado.
            try:
                vindos = l2ia.quadros_de_arquivo(alvo)
            except Exception:                       # noqa: BLE001
                vindos = None
            if vindos:
                self.quadros_do_arquivo = vindos
            erro = None
        except Exception as e:                      # noqa: BLE001
            imagem, alvo, erro = None, None, e
        self.raiz.after(0, self._fim_da_geracao, imagem, alvo, erro)

    def _fim_da_geracao(self, imagem, alvo, erro):
        self.rodando = False
        try:
            self._atualizar_botoes()
        except tk.TclError:
            return
        if erro is not None:
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para gerar"), str(erro),
                                 parent=self.janela)
            return
        self.gerada_original = imagem
        self.caminho_gerado = alvo
        # O fundo escolhido vale para a arte nova também: quem pediu preto
        # antes não quer transparente na próxima.
        self.gerada = (l2ia.por_fundo(imagem, self.cor_do_fundo)
                       if self.cor_do_fundo else imagem)
        self._mostrar(self.gerada)
        self._mostrar_real(self.gerada)
        self._dizer_o_estado()
        self._dizer_o_modo()
        self._atualizar_botoes()

    # -- o estado da tela, decidido num lugar so ---------------------------
    def _atualizar_botoes(self):
        """
        Liga e desliga cada botão conforme o que já existe de verdade.

        Um botão habilitado é uma promessa. "Usar esta" antes de haver arte, ou
        "Gerar" sem chave configurada, prometem o que a tela não pode cumprir
        -- e o usuário só descobre no erro. Aqui o estado dos cinco sai do
        mesmo lugar, para não haver dois pareceres sobre a mesma tela.
        """
        try:
            tem_arte = self.gerada is not None
            da_para_gerar, _porque = l2ia.pronto(para="imagem")

            if self.rodando:
                self.botao_gerar.config(text=t("Gerando…"), state="disabled")
            else:
                self.botao_gerar.config(
                    text=t("Gerar de novo") if tem_arte else t("Gerar"),
                    state="normal" if da_para_gerar else "disabled")

            livre = "normal" if not self.rodando else "disabled"
            self.botao_abrir.config(state=livre)
            pronto_para_usar = ("normal" if tem_arte and not self.rodando
                                else "disabled")
            self.botao_usar.config(state=pronto_para_usar)
            self.botao_animar_cliente.config(state=pronto_para_usar)
        except (AttributeError, tk.TclError):
            pass

    def _dizer_o_estado(self):
        """A frase sob a prévia, recalculada -- ela muda com o tamanho."""
        try:
            if self.gerada is None:
                return
            lado = self.lado_no_cliente()
            largura, altura = self.gerada.size
            if self.quadros_do_arquivo:
                self.estado.config(
                    text=t("%d quadros de %dx%d — no cliente entram %dx%d, que "
                           "é a prévia da direita.")
                    % (len(self.quadros_do_arquivo), largura, altura, lado,
                       lado))
            else:
                self.estado.config(
                    text=t("pronto: %dx%d — no cliente entra %dx%d, que é a "
                           "prévia da direita. Veja se serve e use, ou gere de "
                           "novo mudando as observações.")
                    % (largura, altura, lado, lado))
        except tk.TclError:
            pass

    # -- o fundo -----------------------------------------------------------
    def _trocar_fundo(self):
        """
        Aplica o fundo escolhido sobre a arte que já existe.

        Parte sempre do original: trocar preto por transparente tem de
        devolver a transparência, e não empilhar um fundo sobre o outro.
        """
        escolha = dict(FUNDOS).get(self.fundo.get(), None)
        if escolha == "escolher":
            from tkinter import colorchooser

            cor = colorchooser.askcolor(parent=self.janela,
                                        title=t("A cor do fundo"))[1]
            if not cor:
                self.fundo.set(FUNDOS[0][0])
                return
            self.cor_do_fundo = cor
        else:
            self.cor_do_fundo = escolha

        if self.gerada_original is None:
            return
        try:
            self.gerada = l2ia.por_fundo(self.gerada_original,
                                         self.cor_do_fundo)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para trocar o fundo"), str(erro),
                                 parent=self.janela)
            return
        # O arquivo entregue tem de ser o que está na tela, e não o de antes.
        try:
            self.gerada.save(self.caminho_gerado)
        except Exception:                           # noqa: BLE001
            pass
        self._mostrar(self.gerada)
        self._mostrar_real(self.gerada)

    def _mudou_o_tamanho(self):
        """A prévia real e a frase acompanham a caixa de tamanho."""
        self._mostrar_real(self.gerada)
        self._dizer_o_estado()

    def _tamanho_do_tipo(self):
        """Ao trocar o que gerar, o tamanho vai para o comum daquele tipo."""
        try:
            self.lado.set(str(LADOS.get(self.tipo.get(), 32)))
        except tk.TclError:
            pass

    def lado_no_cliente(self):
        """O tamanho final, em pixels. Sempre um número utilizável."""
        return _inteiro(self.lado.get(), 32)

    def _mostrar_real(self, imagem):
        """
        A prévia no tamanho do jogo, ampliada sem suavizar.

        Ampliar com NEAREST é de propósito: mostra o pixel como ele vai ficar.
        Suavizar aqui enganaria -- a tela ficaria bonita e o jogo, não.
        """
        if ImageTk is None or imagem is None:
            return
        lado = self.lado_no_cliente()
        try:
            pequena = l2ia.encaixar(imagem, lado)
        except Exception:                           # noqa: BLE001
            return
        vezes = max(1, LADO_DA_PREVIA_REAL // lado)
        ampliada = pequena.resize((lado * vezes, lado * vezes), Image.NEAREST)
        self.previa_real_tk = ImageTk.PhotoImage(ampliada)
        self.previa_real.delete("all")
        self.previa_real.create_image(LADO_DA_PREVIA_REAL // 2,
                                      LADO_DA_PREVIA_REAL // 2,
                                      image=self.previa_real_tk)
        self.diz_o_tamanho.config(text=t("%dx%d no jogo") % (lado, lado))

    def quadros_da_animacao(self, quantos):
        """
        Os quadros a usar: os do GIF que veio, ou o movimento feito aqui.

        Quando o usuário trouxe uma animação, ela manda -- foi desenhada, e
        nenhum movimento sintético melhora isso. A contagem é reamostrada ao
        longo do tempo, e não cortada no fim, senão a volta fica pela metade.
        """
        if self.quadros_do_arquivo:
            vindos = l2ia.reamostrar(self.quadros_do_arquivo, quantos)
            if self.cor_do_fundo:
                # O fundo escolhido vale para a animação também: preto na
                # arte e transparente nos quadros seria o programa se
                # contradizendo.
                vindos = [l2ia.por_fundo(q, self.cor_do_fundo) for q in vindos]
            return vindos
        return l2ia.animar(self.gerada, self.modo.get(), quantos)

    def _mostrar(self, imagem):
        if ImageTk is None or imagem is None:
            return
        copia = imagem.copy()
        copia.thumbnail((LADO_DA_PREVIA, LADO_DA_PREVIA), Image.LANCZOS)
        self.previa_tk = ImageTk.PhotoImage(copia)
        self.previa.delete("all")
        self.previa.create_image(LADO_DA_PREVIA // 2, LADO_DA_PREVIA // 2,
                                 image=self.previa_tk)

    # -- usar --------------------------------------------------------------
    def usar(self):
        """Fecha devolvendo o caminho -- e os quadros, se houver animação."""
        if self.gerada is None:
            return
        lado = self.lado_no_cliente()
        quadros = []
        if self.animar.get():
            quantos = max(2, min(48, _inteiro(self.quantos.get(), 8)))
            try:
                imagens = self.quadros_da_animacao(quantos)
            except Exception as erro:               # noqa: BLE001
                messagebox.showerror(t("Não deu para animar"), str(erro),
                                     parent=self.janela)
                return
            for i, imagem in enumerate(imagens):
                alvo = self.trabalho / ("quadro_%02d.png" % i)
                l2ia.encaixar(imagem, lado).save(alvo)
                quadros.append(str(alvo))

        # A arte sai no tamanho do jogo, e não nos 1024 da IA. Quem monta o
        # pacote encolheria de qualquer forma; encolher aqui é o que faz a
        # prévia e o arquivo entregue serem a mesma coisa.
        pronta = self.trabalho / ("arte_%d.png" % lado)
        try:
            l2ia.encaixar(self.gerada, lado).save(pronta)
        except Exception:                           # noqa: BLE001
            pronta = self.caminho_gerado

        self.resposta = {"imagem": str(pronta),
                         "original": str(self.caminho_gerado),
                         "lado": lado,
                         "nome": _nome_do_objeto(self.objeto.get()),
                         "quadros": quadros}
        self.fechar()



    def abrir_do_disco(self):
        """
        Usa uma imagem sua no lugar da gerada.

        O movimento, a corrente e a troca de quadros não dependem de IA --
        dependem de uma imagem. Quem já desenhou a sua não precisa de chave de
        API para animá-la.
        """
        caminho = filedialog.askopenfilename(
            title=t("A imagem ou o GIF que vai virar arte"),
            parent=self.janela,
            filetypes=[(t("Imagem ou animação"),
                        "*.png *.jpg *.jpeg *.bmp *.tga *.webp *.gif"),
                       (t("Todos os arquivos"), "*.*")])
        if not caminho:
            return
        try:
            animada = l2ia.quadros_de_arquivo(caminho)
            imagem = (animada[0] if animada
                      else Image.open(caminho).convert("RGBA"))
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não consegui abrir a imagem"), str(erro),
                                 parent=self.janela)
            return
        # Animação trazida pronta manda: os quadros dela foram desenhados, e
        # nenhum movimento sintético melhora isso.
        self.quadros_do_arquivo = animada or []
        if animada:
            self.animar.set(True)
            self.quantos.set(str(len(animada)))
            self._dizer_o_modo()
        alvo = self.trabalho / ("minha" + Path(caminho).suffix.lower())
        alvo.parent.mkdir(parents=True, exist_ok=True)
        imagem.save(alvo) if alvo.suffix == ".png" else shutil.copy2(caminho,
                                                                     alvo)
        self._fim_da_geracao(imagem, alvo, None)
        if self.quadros_do_arquivo:
            self.estado.config(
                text=t("%s: %d quadros de %dx%d. A animação é a do arquivo; o "
                       "modo de movimento não se aplica.")
                % (Path(caminho).name, len(self.quadros_do_arquivo),
                   imagem.size[0], imagem.size[1]))
        else:
            self.estado.config(
                text=t("%s: %dx%d. Dá para animar direto, ou gerar outra com "
                       "a IA.") % (Path(caminho).name, imagem.size[0],
                                   imagem.size[1]))

    # -- pôr a animação no cliente -----------------------------------------
    def animar_no_cliente(self):
        """
        Pergunta por qual dos dois caminhos, e segue por ele.

        São mecanismos diferentes, e a escolha não é de gosto: um anima o que
        hoje está parado, o outro muda a cara do que já anda.
        """
        if self.gerada is None:
            return
        metodo = EscolherMetodo(self.janela).resposta
        if metodo == "corrente":
            self.animar_pela_corrente()
        elif metodo == "familia":
            self.aplicar_no_cliente()

    def _pacote_do_cliente(self, titulo):
        """O pacote que o usuário escolher, começando na pasta do cliente."""
        import l2conferir
        import projeto

        cliente = (projeto.cliente() or "").strip()
        inicio = str(l2conferir.raiz_do_cliente(cliente)) if cliente else None
        return filedialog.askopenfilename(
            title=t(titulo), initialdir=inicio, parent=self.janela,
            filetypes=[(t("Pacote do cliente"), "*.utx *.u *.usx *.unr"),
                       (t("Todos os arquivos"), "*.*")])

    def animar_pela_corrente(self):
        """
        Faz uma textura parada do cliente animar, pela corrente do motor.

        `AnimNext` é propriedade do próprio Unreal: uma textura aponta para a
        seguinte, e o motor percorre a corrente sozinho. A textura escolhida
        não muda de conteúdo nem de endereço -- quem a usa hoje continua a
        achando, e agora ela anda. Os quadros vão num pacote novo, ao lado.
        """
        import l2anima

        caminho = self._pacote_do_cliente(
            "O pacote onde está a textura (ex.: Icon.utx)")
        if not caminho:
            return

        self.estado.config(text=t("lendo o pacote…"))
        self.janela.update_idletasks()
        try:
            _pacote, texturas = l2anima.texturas_do_arquivo(
                motor.carregar_config(), caminho)
        except Exception as erro:                   # noqa: BLE001
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para ler o pacote"), str(erro),
                                 parent=self.janela)
            return
        self.estado.config(text="")
        if not texturas:
            messagebox.showinfo(
                t("Sem textura aqui"),
                t("Não achei textura nenhuma em %s.") % Path(caminho).name,
                parent=self.janela)
            return

        escolhida = EscolherTextura(self.janela, texturas).resposta
        if not escolhida:
            return

        _indice, nome, largura, altura = escolhida
        quantos = max(2, min(l2anima.MAXIMO_DE_QUADROS,
                             _inteiro(self.quantos.get(), 8)))
        taxa = max(1, min(60, _inteiro(self.taxa.get(), 15)))
        if not messagebox.askyesno(
                t("Animar %s?") % nome,
                t("A textura %s (%dx%d) vai passar a percorrer %d quadros "
                  "novos, a %d por segundo.\n\n"
                  "Ela não muda de conteúdo nem de endereço: ganha uma "
                  "propriedade. Os quadros vão num pacote à parte, na pasta "
                  "de texturas do cliente.\n\n"
                  "O %s original vai para backup_animacao antes.\n\n"
                  "Feche o jogo: o cliente segura o arquivo enquanto roda.\n\n"
                  "Animar?")
                % (nome, largura, altura, quantos, taxa, Path(caminho).name),
                parent=self.janela):
            return

        self.rodando = True
        self._atualizar_botoes()
        self.estado.config(text=t("montando a corrente…"))
        threading.Thread(target=self._corrente_thread,
                         args=(caminho, nome, (largura, altura), quantos,
                               taxa), daemon=True).start()

    def _corrente_thread(self, caminho, textura, tamanho, quantos, taxa):
        import l2anima
        registro = []
        try:
            T = motor.carregar_config()
            quadros = self.quadros_da_animacao(quantos)
            feito = l2anima.animar_textura_do_cliente(
                T, caminho, textura, quadros, self.trabalho / "corrente",
                aolog=registro.append, taxa=float(taxa), tamanho=tamanho)
            registro.append("endereço novo: %s" % feito["endereco"])
            erro = None
        except Exception as e:                      # noqa: BLE001
            erro = e
        self.raiz.after(0, self._fim_da_aplicacao, registro, erro)

    def aplicar_no_cliente(self):
        """
        Troca o desenho de uma sequência que o cliente já toca.

        É assim que o Lineage 2 anima a interface: famílias de textura
        numeradas -- `ToggleEffect001..013`, `cooltime000..359` -- que o
        código do cliente escolhe a cada instante. Trocar o desenho delas é
        animação nova no jogo, hoje, sem mexer em interface.
        """
        import l2anima
        import l2conferir
        import projeto

        if self.gerada is None:
            return
        cliente = (projeto.cliente() or "").strip()
        inicio = str(l2conferir.raiz_do_cliente(cliente)) if cliente else None
        caminho = filedialog.askopenfilename(
            title=t("O pacote com a animação (ex.: L2_SkillTime.utx)"),
            initialdir=inicio, parent=self.janela,
            filetypes=[(t("Pacote de textura"), "*.utx")])
        if not caminho:
            return

        self.estado.config(text=t("lendo o pacote…"))
        self.janela.update_idletasks()
        try:
            _pacote, achadas = l2anima.familias_do_arquivo(
                motor.carregar_config(), caminho)
        except Exception as erro:                   # noqa: BLE001
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para ler o pacote"), str(erro),
                                 parent=self.janela)
            return
        self.estado.config(text="")
        if not achadas:
            messagebox.showinfo(
                t("Sem animação aqui"),
                t("Não achei sequência numerada em %s.\n\nUma animação da "
                  "interface é uma família de texturas com número no fim do "
                  "nome, como ToggleEffect001..013. Sem isso, não há o que "
                  "trocar.") % Path(caminho).name, parent=self.janela)
            return

        familia = EscolherSequencia(self.janela, achadas).resposta
        if not familia:
            return

        quantos = familia["quantos"]
        if not messagebox.askyesno(
                t("Trocar os quadros de %s?") % familia["prefixo"],
                t("Serão regravados %d quadros de %dx%d, no formato %s, "
                  "dentro de %s.\n\nO original vai para backup_animacao "
                  "antes.\n\nFeche o jogo antes: o cliente segura o arquivo "
                  "enquanto roda.\n\nTrocar?")
                % (quantos, familia["largura"], familia["altura"],
                   familia["formato"], Path(caminho).name),
                parent=self.janela):
            return

        self.rodando = True
        self._atualizar_botoes()
        self.estado.config(text=t("gravando os quadros…"))
        threading.Thread(target=self._aplicar_thread,
                         args=(caminho, familia, quantos), daemon=True).start()

    def _aplicar_thread(self, caminho, familia, quantos):
        import l2anima
        registro = []
        try:
            T = motor.carregar_config()
            quadros = self.quadros_da_animacao(quantos)
            pronto = l2anima.trocar_quadros(
                T, caminho, familia["prefixo"], quadros,
                self.trabalho / "animacao", aolog=registro.append)
            l2anima.instalar(T, pronto, caminho, aolog=registro.append)
            erro = None
        except Exception as e:                      # noqa: BLE001
            erro = e
        self.raiz.after(0, self._fim_da_aplicacao, registro, erro)

    def _fim_da_aplicacao(self, registro, erro):
        self.rodando = False
        try:
            self._atualizar_botoes()
            self.estado.config(text="")
        except tk.TclError:
            return
        if erro is not None:
            messagebox.showerror(t("Não deu para aplicar"), str(erro),
                                 parent=self.janela)
            return
        messagebox.showinfo(
            t("Animação trocada"),
            t("%s\n\nFeche e abra o jogo para ver: o cliente lê o pacote no "
              "arranque.") % "\n".join(registro[-3:]), parent=self.janela)


class EscolherSequencia:
    """A lista de famílias achadas no pacote. Devolve a escolhida em `.resposta`."""

    def __init__(self, pai, familias):
        self.resposta = None
        self.familias = familias

        self.janela = ajuda.por_icone(tk.Toplevel(pai))
        self.janela.title(t("Qual animação trocar"))
        self.janela.transient(pai)
        self.janela.grab_set()

        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, justify="left", wraplength=460,
                  foreground=tema.TEXTO_FRACO,
                  text=t("Cada linha é uma sequência que o cliente toca "
                         "sozinho. Os quadros são trocados no mesmo tamanho e "
                         "no mesmo formato -- os nomes não mudam, e por isso "
                         "o cliente continua achando o que procura.")
                  ).pack(anchor="w")

        self.lista = tk.Listbox(quadro, height=8, width=58,
                                background=tema.PAINEL, foreground=tema.TEXTO,
                                selectbackground=tema.OURO_FUNDO,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                borderwidth=0, font=tema.CORPO)
        self.lista.pack(fill="both", expand=True, pady=(8, 0))
        for familia in familias:
            self.lista.insert("end", "%-18s %4d quadros   %dx%d   %s"
                              % (familia["prefixo"], familia["quantos"],
                                 familia["largura"], familia["altura"],
                                 familia["formato"]))
        self.lista.selection_set(0)
        self.lista.bind("<Double-1>", lambda _e: self.aceitar())

        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(10, 0))
        ttk.Button(botoes, text=t("Usar esta"), style="Primario.TButton",
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")

        pai.wait_window(self.janela)

    def aceitar(self):
        marcado = self.lista.curselection()
        if marcado:
            self.resposta = self.familias[marcado[0]]
        self.janela.destroy()



class EscolherMetodo:
    """
    Por qual dos dois caminhos animar. Devolve "corrente", "familia" ou None.

    A pergunta existe porque os dois mecanismos são de camadas diferentes do
    jogo, e nenhum substitui o outro.
    """

    def __init__(self, pai):
        self.resposta = None
        self.escolha = tk.StringVar(value="corrente")

        self.janela = ajuda.por_icone(tk.Toplevel(pai))
        self.janela.title(t("Como animar"))
        self.janela.transient(pai)
        self.janela.grab_set()

        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)

        ttk.Radiobutton(quadro, variable=self.escolha, value="corrente",
                        text=t("Animar uma textura que hoje está parada")
                        ).pack(anchor="w")
        ttk.Label(quadro, justify="left", wraplength=470,
                  foreground=tema.TEXTO_FRACO,
                  text=t("A corrente do motor. A textura escolhida passa a "
                         "apontar para os seus quadros, e o Unreal percorre "
                         "sozinho -- serve para ícone, botão, moldura, céu. "
                         "Ela não muda de endereço: quem a usa hoje continua "
                         "a achando.")
                  ).pack(anchor="w", padx=(22, 0), pady=(0, 10))

        ttk.Radiobutton(quadro, variable=self.escolha, value="familia",
                        text=t("Mudar o desenho de uma animação que já existe")
                        ).pack(anchor="w")
        ttk.Label(quadro, justify="left", wraplength=470,
                  foreground=tema.TEXTO_FRACO,
                  text=t("A família numerada, como ToggleEffect001..013. Aqui "
                         "quem escolhe o quadro a cada instante é o código da "
                         "interface, então não dá para inventar nome novo -- "
                         "dá para trocar o desenho do que existe.")
                  ).pack(anchor="w", padx=(22, 0))

        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(12, 0))
        ttk.Button(botoes, text=t("Continuar"), style="Primario.TButton",
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")

        pai.wait_window(self.janela)

    def aceitar(self):
        self.resposta = self.escolha.get()
        self.janela.destroy()


class EscolherTextura:
    """
    A lista de texturas do pacote, com filtro. Devolve a escolhida.

    O filtro não é enfeite: um Icon.utx oficial tem 4.662 texturas, e rolar
    isso à procura de um nome é pior do que não ter a lista.
    """

    QUANTAS_MOSTRAR = 400

    def __init__(self, pai, texturas):
        self.resposta = None
        self.todas = list(texturas)
        self.mostradas = []

        self.janela = ajuda.por_icone(tk.Toplevel(pai))
        self.janela.title(t("Qual textura animar"))
        self.janela.transient(pai)
        self.janela.grab_set()

        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, justify="left", wraplength=470,
                  foreground=tema.TEXTO_FRACO,
                  text=t("%d texturas neste pacote. Escreva parte do nome "
                         "para achar.") % len(self.todas)).pack(anchor="w")

        linha = ttk.Frame(quadro)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text=t("filtro:")).pack(side="left")
        self.filtro = tk.StringVar()
        campo = ttk.Entry(linha, textvariable=self.filtro)
        campo.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.filtro.trace_add("write", lambda *_a: self._encher())

        self.lista = tk.Listbox(quadro, height=12, width=58,
                                background=tema.PAINEL, foreground=tema.TEXTO,
                                selectbackground=tema.OURO_FUNDO,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                borderwidth=0, font=tema.CORPO)
        self.lista.pack(fill="both", expand=True, pady=(8, 0))
        self.lista.bind("<Double-1>", lambda _e: self.aceitar())
        self.conta = ttk.Label(quadro, foreground=tema.TEXTO_FRACO)
        self.conta.pack(anchor="w", pady=(4, 0))

        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(10, 0))
        ttk.Button(botoes, text=t("Usar esta"), style="Primario.TButton",
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")

        self._encher()
        campo.focus_set()
        pai.wait_window(self.janela)

    def _encher(self):
        procurado = self.filtro.get().strip().lower()
        casaram = [x for x in self.todas
                   if not procurado or procurado in x[1].lower()]
        self.mostradas = casaram[:self.QUANTAS_MOSTRAR]
        self.lista.delete(0, "end")
        for _indice, nome, largura, altura in self.mostradas:
            self.lista.insert("end", "%-34s %dx%d" % (nome, largura, altura))
        if self.mostradas:
            self.lista.selection_set(0)
        sobraram = len(casaram) - len(self.mostradas)
        self.conta.config(
            text=(t("%d encontradas; mostrando as %d primeiras.")
                  % (len(casaram), len(self.mostradas))) if sobraram else
                 (t("%d encontradas.") % len(casaram)))

    def aceitar(self):
        marcado = self.lista.curselection()
        if marcado:
            self.resposta = self.mostradas[marcado[0]]
        self.janela.destroy()


def _inteiro(texto, padrao):
    """O número que está escrito na caixa, ou o padrão quando não há um."""
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao

def _nome_do_objeto(texto):
    """Um nome de objeto a partir do que o usuário escreveu."""
    limpo = "".join(c if c.isalnum() else "_" for c in (texto or "").lower())
    while "__" in limpo:
        limpo = limpo.replace("__", "_")
    return limpo.strip("_")[:28] or "arte_ia"
