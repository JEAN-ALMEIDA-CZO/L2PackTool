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

TIPOS = (("icone", "ícone de item (32x32)"),
         ("botao", "botão de interface"),
         ("borda", "moldura / borda"))


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
        caixa_modo = ttk.Combobox(linha, textvariable=self.modo,
                                  values=l2ia.MODOS, state="readonly",
                                  width=12)
        caixa_modo.pack(side="left", padx=(6, 0))
        # Doze modos e nome de uma palavra: sem a explicação ao lado, escolher
        # vira tentativa e erro.
        self.diz_o_modo = ttk.Label(linha, foreground=tema.TEXTO_FRACO)
        self.diz_o_modo.pack(side="left", padx=(8, 0))
        caixa_modo.bind("<<ComboboxSelected>>",
                        lambda _e: self._explicar_o_modo())
        ttk.Label(linha, text=t("quadros:")).pack(side="left", padx=(12, 0))
        self.quantos = tk.StringVar(value="8")
        ttk.Spinbox(linha, from_=2, to=32, width=5,
                    textvariable=self.quantos).pack(side="left", padx=(6, 0))


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
        self.botao_usar = ttk.Button(acao, text=t("Usar esta"),
                                     command=self.usar, state="disabled")
        self.botao_usar.pack(side="left", padx=(6, 0))
        self.botao_animar_cliente = ttk.Button(
            acao, text=t("Aplicar numa animação do cliente…"),
            command=self.aplicar_no_cliente, state="disabled")
        self.botao_animar_cliente.pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Ver o pedido"),
                   command=self.ver_o_pedido).pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Fechar"),
                   command=self.fechar).pack(side="right")

    # -- o provedor --------------------------------------------------------
    def _conferir_o_provedor(self):
        """Diz de cara se dá para gerar, e o que fazer quando não dá."""
        da, porque = l2ia.pronto(para="imagem")
        if da:
            self.recado.config(
                text=t("Usando %s, modelo %s.")
                % (l2ia.PROVEDORES[l2ia.provedor()]["nome"], l2ia.modelo()))
            return
        self.recado.config(text=porque)
        self.botao_gerar.config(state="disabled")

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
        return l2ia.montar_prompt(
            self.tipo.get(),
            self.observacoes.get("1.0", "end").strip(),
            self.objeto.get())

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
        self.botao_gerar.config(state="disabled")
        self.botao_usar.config(state="disabled")
        self.estado.config(text=t("pedindo à IA… isso leva alguns segundos."))
        threading.Thread(target=self._gerar_thread, daemon=True).start()

    def _gerar_thread(self):
        try:
            dados = l2ia.gerar_imagem(self._pedido(), self.referencias)
            alvo = self.trabalho / "gerada.png"
            alvo.write_bytes(dados)
            imagem = Image.open(alvo).convert("RGBA") if Image else None
            erro = None
        except Exception as e:                      # noqa: BLE001
            imagem, alvo, erro = None, None, e
        self.raiz.after(0, self._fim_da_geracao, imagem, alvo, erro)

    def _fim_da_geracao(self, imagem, alvo, erro):
        try:
            self.botao_gerar.config(state="normal")
        except tk.TclError:
            return
        if erro is not None:
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para gerar"), str(erro))
            return
        self.gerada = imagem
        self.caminho_gerado = alvo
        self._mostrar(imagem)
        self.estado.config(text=t("pronto: %dx%d. Veja se serve e use, ou "
                                  "gere de novo mudando as observações.")
                           % imagem.size)
        self.botao_usar.config(state="normal")
        self.botao_animar_cliente.config(state="normal")

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
        quadros = []
        if self.animar.get():
            try:
                quantos = max(2, min(32, int(self.quantos.get())))
            except ValueError:
                quantos = 8
            try:
                imagens = l2ia.animar(self.gerada, self.modo.get(), quantos)
            except Exception as erro:               # noqa: BLE001
                messagebox.showerror(t("Não deu para animar"), str(erro))
                return
            for i, imagem in enumerate(imagens):
                alvo = self.trabalho / ("quadro_%02d.png" % i)
                imagem.save(alvo)
                quadros.append(str(alvo))

        self.resposta = {"imagem": str(self.caminho_gerado),
                         "nome": _nome_do_objeto(self.objeto.get()),
                         "quadros": quadros}
        self.fechar()



    # -- pôr a animação no cliente -----------------------------------------
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

        self.botao_animar_cliente.config(state="disabled")
        self.estado.config(text=t("gravando os quadros…"))
        threading.Thread(target=self._aplicar_thread,
                         args=(caminho, familia, quantos), daemon=True).start()

    def _aplicar_thread(self, caminho, familia, quantos):
        import l2anima
        registro = []
        try:
            T = motor.carregar_config()
            quadros = l2ia.animar(self.gerada, self.modo.get(), quantos)
            pronto = l2anima.trocar_quadros(
                T, caminho, familia["prefixo"], quadros,
                self.trabalho / "animacao", aolog=registro.append)
            l2anima.instalar(T, pronto, caminho, aolog=registro.append)
            erro = None
        except Exception as e:                      # noqa: BLE001
            erro = e
        self.raiz.after(0, self._fim_da_aplicacao, registro, erro)

    def _fim_da_aplicacao(self, registro, erro):
        try:
            self.botao_animar_cliente.config(state="normal")
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


def _nome_do_objeto(texto):
    """Um nome de objeto a partir do que o usuário escreveu."""
    limpo = "".join(c if c.isalnum() else "_" for c in (texto or "").lower())
    while "__" in limpo:
        limpo = limpo.replace("__", "_")
    return limpo.strip("_")[:28] or "arte_ia"
