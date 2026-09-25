#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A aba de proteção: fechar o cliente com a chave de quem é dono dele.

A tela tem três partes, na ordem em que a pessoa precisa delas:

    1. o que este cliente permite -- dito ANTES de escolher qualquer coisa,
       porque do Kamael em diante a chave não é trocável e é melhor saber
       disso antes do que depois de marcar trinta arquivos;
    2. a frase, que é a chave;
    3. o que proteger, e o botão.

O texto de cima não vende o que a proteção não faz. Quem lê precisa sair
sabendo que isto tranca a ESCRITA, e não a leitura -- ver o l2protecao.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import l2conferir
import l2cripto
import l2protecao
import motor
import tema
from idioma import t

COR_FRACO = tema.TEXTO_FRACO


class JanelaProtecao:
    """Precisa de `dono` só para o registro; as pastas vêm do projeto."""

    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.escolhas = {}
        self.avulsos = []               # os escolhidos a mao, alem dos grupos
        self.estado_do_cliente = {}

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_FRACO,
                  text=t("Fecha as tabelas do cliente com uma chave gerada a "
                         "partir de uma frase sua, e escreve essa chave dentro "
                         "do executável — o jogo continua abrindo os arquivos, "
                         "e mais ninguém consegue gerar arquivos que ele "
                         "aceite.")).pack(anchor="w")

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=tema.ATENCAO,
                  text=t("Isto tranca a ESCRITA, não a leitura. Para jogar, o "
                         "cliente precisa abrir os arquivos, então ele carrega "
                         "a chave de leitura dentro de si — quem tiver o seu "
                         "cliente pode achá-la. O que muda é sair do «qualquer "
                         "um abre com um clique» para o «quem souber "
                         "procurar».")).pack(anchor="w", pady=(6, 0))

        self._montar_cliente(quadro)
        self._montar_chave(quadro)
        self._montar_escolha(quadro)
        self._montar_registro(quadro)
        self.atualizar_botoes()
        self.raiz.after(200, self.reler_cliente)

    # ---- montagem --------------------------------------------------------
    def _montar_cliente(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("O cliente"), padding=8)
        caixa.pack(fill="x", pady=(10, 0))

        linha = ttk.Frame(caixa)
        linha.pack(fill="x")
        ttk.Label(linha, text=t("system:")).pack(side="left")
        self.cliente = tk.StringVar()
        ttk.Entry(linha, textvariable=self.cliente).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(linha, text=t("Reler"),
                   command=self.reler_cliente).pack(side="left", padx=(6, 0))

        self.diz_o_cliente = ttk.Label(caixa, justify="left", wraplength=940,
                                       foreground=COR_FRACO)
        self.diz_o_cliente.pack(anchor="w", pady=(6, 0))

    def _montar_chave(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("A sua chave"), padding=8)
        caixa.pack(fill="x", pady=(10, 0))

        ttk.Label(caixa, justify="left", wraplength=940, foreground=COR_FRACO,
                  text=t("A chave é gerada a partir da frase — a mesma frase "
                         "dá sempre a mesma chave, em qualquer máquina. Ela "
                         "não é guardada em lugar nenhum: se você esquecer a "
                         "frase, não há como gerar arquivos novos para esse "
                         "cliente (o backup, esse continua valendo).")
                  ).pack(anchor="w")

        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(6, 0))
        ttk.Label(linha, text=t("frase:")).pack(side="left")
        self.frase = tk.StringVar()
        self.campo_frase = ttk.Entry(linha, textvariable=self.frase, show="•")
        self.campo_frase.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(linha, text=t("ver"), variable=self.mostrar,
                        command=self._mostrar_frase).pack(side="left",
                                                          padx=(6, 0))
        ttk.Button(linha, text=t("Gerar chave"),
                   command=self.gerar_chave).pack(side="left", padx=(6, 0))
        self.botao_guardar = ttk.Button(linha, text=t("Salvar…"),
                                        command=self.salvar_frase,
                                        state="disabled")
        self.botao_guardar.pack(side="left", padx=(6, 0))
        ttk.Button(linha, text=t("Ver a marca"),
                   command=self.ver_a_marca).pack(side="left", padx=(6, 0))
        self.frase.trace_add("write", lambda *_a: self.atualizar_botoes())

        self.diz_a_chave = ttk.Label(caixa, foreground=COR_FRACO)
        self.diz_a_chave.pack(anchor="w", pady=(6, 0))

    def _montar_escolha(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("O que proteger"), padding=8)
        caixa.pack(fill="x", pady=(10, 0))

        linha = ttk.Frame(caixa)
        linha.pack(fill="x")
        for chave, rotulo, nomes in l2protecao.GRUPOS:
            var = tk.BooleanVar(value=chave in ("itens", "skills", "npcs"))
            self.escolhas[chave] = var
            ttk.Checkbutton(linha, text=t(rotulo), variable=var,
                            command=self.contar).pack(side="left", padx=(0, 14))
            ajuda.ajuda(linha, (lambda ns: lambda: t("Nesta escolha: %s")
                                % ", ".join(ns))(nomes))

        avulsos = ttk.Frame(caixa)
        avulsos.pack(fill="x", pady=(8, 0))
        ttk.Label(avulsos, text=t("ou arquivo a arquivo:")).pack(side="left")
        ttk.Button(avulsos, text=t("Escolher…"),
                   command=self.escolher_arquivos).pack(side="left",
                                                        padx=(6, 0))
        ttk.Button(avulsos, text=t("Todos os .dat"),
                   command=self.todos_os_dat).pack(side="left", padx=(6, 0))
        self.botao_tirar = ttk.Button(avulsos, text=t("Tirar"),
                                      command=self.tirar_arquivo,
                                      state="disabled")
        self.botao_tirar.pack(side="left", padx=(6, 0))
        self.botao_limpar = ttk.Button(avulsos, text=t("Limpar a lista"),
                                       command=self.limpar_avulsos,
                                       state="disabled")
        self.botao_limpar.pack(side="left", padx=(6, 0))

        self.lista = tk.Listbox(caixa, height=5, selectmode="extended",
                                background=tema.PAINEL, foreground=tema.TEXTO,
                                selectbackground=tema.OURO_FUNDO,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                borderwidth=0, font=tema.CORPO)
        self.lista.pack(fill="x", pady=(6, 0))

        self.diz_a_conta = ttk.Label(caixa, foreground=COR_FRACO)
        self.diz_a_conta.pack(anchor="w", pady=(6, 0))

        acao = ttk.Frame(caixa)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_proteger = ttk.Button(acao, text=t("Proteger"),
                                         style="Primario.TButton",
                                         command=self.proteger)
        self.botao_proteger.pack(side="left")
        self.botao_desfazer = ttk.Button(acao, text=t("Voltar ao original"),
                                         command=self.desfazer)
        self.botao_desfazer.pack(side="left", padx=(6, 0))
        self.estado = ttk.Label(acao, foreground=COR_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

    def _montar_registro(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Andamento"), padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))
        self.registro = tk.Text(caixa, height=12, wrap="word",
                                background=tema.ABISSO, foreground=tema.TEXTO,
                                insertbackground=tema.TEXTO, borderwidth=0,
                                font=tema.MONO if hasattr(tema, "MONO")
                                else tema.CORPO)
        self.registro.pack(fill="both", expand=True)
        self.registro.configure(state="disabled")

    # ---- estado ----------------------------------------------------------
    def log(self, texto=""):
        try:
            self.registro.configure(state="normal")
            self.registro.insert("end", texto + "\n")
            self.registro.see("end")
            self.registro.configure(state="disabled")
        except tk.TclError:
            pass

    def system(self):
        bruto = (self.cliente.get() or "").strip()
        if not bruto:
            return None
        return l2conferir.raiz_do_cliente(bruto) / "system"

    def _mostrar_frase(self):
        self.campo_frase.config(show="" if self.mostrar.get() else "•")

    def reler_cliente(self):
        """Diz o que este cliente permite -- antes de a pessoa escolher."""
        alvo = self.system()
        if alvo is None or not alvo.is_dir():
            self.estado_do_cliente = {}
            self.diz_o_cliente.config(
                text=t("Sem cliente: abra Projetos… no alto da janela e aponte "
                       "a pasta do cliente."), foreground=tema.ATENCAO)
            self.atualizar_botoes()
            return
        try:
            info = l2protecao.relatorio(alvo)
        except Exception as erro:                   # noqa: BLE001
            self.diz_o_cliente.config(text=str(erro), foreground=tema.ATENCAO)
            self.atualizar_botoes()
            return

        self.estado_do_cliente = info
        if info["trocavel"]:
            recado = t("Chave trocável: %s guardam o módulo, e a marca atual é "
                       "%s.") % (", ".join(p.name for p in info["executaveis"]),
                                 info["marca"])
            cor = COR_FRACO
        else:
            recado = t("Este cliente guarda a chave empacotada (Kamael em "
                       "diante): ela só existe em memória, entregue pelo "
                       "loader, e não dá para escrever a sua nela. Proteger "
                       "aqui exigiria um loader próprio.")
            cor = tema.ATENCAO
        if info.get("protegidos"):
            recado += t("\nJá há %d arquivo(s) em %s, de %s — dá para voltar "
                        "ao original.") % (len(info["protegidos"]),
                                           l2protecao.PASTA_GUARDA,
                                           info.get("quando") or "antes")
        self.diz_o_cliente.config(text=recado, foreground=cor)
        self.contar()

    def contar(self):
        alvo = self.system()
        if alvo is None or not alvo.is_dir():
            self.diz_a_conta.config(text="")
            self.atualizar_botoes()
            return
        arquivos = self.alvos()
        self.diz_a_conta.config(
            text=t("%d arquivo(s) neste cliente: %s")
            % (len(arquivos), ", ".join(p.name for p in arquivos[:8])
               + ("…" if len(arquivos) > 8 else "")))
        self.atualizar_botoes()

    # ---- os arquivos avulsos ---------------------------------------------
    def alvos(self):
        """A união do que os grupos marcam com o que foi escolhido à mão."""
        sistema = self.system()
        if sistema is None or not sistema.is_dir():
            return []
        dos_grupos = l2protecao.arquivos_do_grupo(
            sistema, [c for c, v in self.escolhas.items() if v.get()])
        juntos, vistos = [], set()
        for caminho in list(dos_grupos) + list(self.avulsos):
            chave = str(caminho).lower()
            if chave not in vistos:
                vistos.add(chave)
                juntos.append(Path(caminho))
        return sorted(juntos, key=lambda p: p.name.lower())

    def escolher_arquivos(self):
        """
        Acrescenta arquivos à lista, um a um ou vários de uma vez.

        Só entra o que mora na `system` do cliente aberto: a chave que vai
        para o executável é a daquele cliente, e fechar com ela um arquivo de
        fora produziria um arquivo que nenhum cliente lê -- nem o dele.
        """
        sistema = self.system()
        if sistema is None or not sistema.is_dir():
            messagebox.showinfo(
                t("Sem cliente"),
                t("Abra Projetos… no alto da janela e aponte o cliente "
                  "primeiro."))
            return
        escolhidos = filedialog.askopenfilenames(
            title=t("Arquivos do cliente para proteger"), parent=self.raiz,
            initialdir=str(sistema),
            filetypes=[(t("Tabelas e pacotes"), "*.dat *.utx *.u *.unr *.int"),
                       (t("Todos os arquivos"), "*.*")])
        de_fora, novos = [], 0
        for caminho in escolhidos:
            alvo = Path(caminho)
            try:
                alvo.resolve().relative_to(sistema.resolve())
            except (ValueError, OSError):
                de_fora.append(alvo.name)
                continue
            if str(alvo).lower() not in (str(p).lower() for p in self.avulsos):
                self.avulsos.append(alvo)
                novos += 1
        if de_fora:
            messagebox.showwarning(
                t("Fora do cliente"),
                t("Estes não estão na pasta %s e foram deixados de fora: "
                  "%s.\n\nA chave gravada no executável é a daquele cliente; "
                  "um arquivo de fora, fechado com ela, não seria lido por "
                  "cliente nenhum.") % (sistema, ", ".join(de_fora[:6])))
        if novos:
            self.log(t("%d arquivo(s) juntados à lista") % novos)
        self._encher_lista()

    def todos_os_dat(self):
        """Põe na lista todo `.dat` do cliente -- inclusive os que não têm grupo."""
        sistema = self.system()
        if sistema is None or not sistema.is_dir():
            return
        achados = [p for p in sorted(sistema.iterdir())
                   if p.is_file() and p.suffix.lower() == ".dat"]
        ja = {str(p).lower() for p in self.avulsos}
        for p in achados:
            if str(p).lower() not in ja:
                self.avulsos.append(p)
        self.log(t("%d arquivo(s) .dat na lista") % len(self.avulsos))
        self._encher_lista()

    def tirar_arquivo(self):
        for indice in sorted(self.lista.curselection(), reverse=True):
            del self.avulsos[indice]
        self._encher_lista()

    def limpar_avulsos(self):
        self.avulsos = []
        self._encher_lista()

    def _encher_lista(self):
        try:
            self.lista.delete(0, "end")
            for caminho in self.avulsos:
                self.lista.insert("end", caminho.name)
            tem = bool(self.avulsos)
            self.botao_tirar.config(state="normal" if tem else "disabled")
            self.botao_limpar.config(state="normal" if tem else "disabled")
        except tk.TclError:
            pass
        self.contar()

    def atualizar_botoes(self):
        """Ligado só quando há cliente, frase e arquivo — e nada rodando."""
        try:
            info = self.estado_do_cliente
            alvo = self.system()
            tem_cliente = bool(info.get("trocavel"))
            tem_frase = len((self.frase.get() or "").strip()) >= 8
            tem_arquivo = bool(self.alvos())
            pronto = (tem_cliente and tem_frase and tem_arquivo
                      and not self.rodando)
            self.botao_proteger.config(state="normal" if pronto
                                       else "disabled")
            self.botao_desfazer.config(
                state="normal" if info.get("protegidos") and not self.rodando
                else "disabled")
            self.botao_guardar.config(state="normal" if tem_frase
                                      else "disabled")
            if self.rodando:
                falta = ""
            elif not info:
                falta = ""
            elif not tem_cliente:
                falta = t("este cliente não aceita chave própria")
            elif not tem_frase:
                falta = t("escreva a frase (oito caracteres ou mais)")
            elif not tem_arquivo:
                falta = t("marque um grupo, ou escolha arquivos à mão")
            else:
                falta = ""
            self.estado.config(text=falta)
        except (AttributeError, tk.TclError):
            pass

    # ---- ações -----------------------------------------------------------
    def gerar_chave(self):
        """
        Sorteia uma frase forte e a põe no campo.

        Frase inventada na hora é quase sempre o nome do servidor mais o ano,
        e essa qualquer um adivinha -- o que aqui significa gerar arquivos que
        o seu cliente aceita.
        """
        if (self.frase.get() or "").strip() and not messagebox.askyesno(
                t("Trocar a frase?"),
                t("Já há uma frase escrita. Gerar outra descarta essa.\n\n"
                  "Se o cliente já foi protegido com ela, guarde-a antes: sem "
                  "ela não dá para gerar mais nada para esse cliente.\n\n"
                  "Gerar mesmo assim?"), parent=self.raiz):
            return
        self.frase.set(l2protecao.frase_nova())
        self.mostrar.set(True)
        self._mostrar_frase()
        self.ver_a_marca()
        self.log(t("frase nova gerada — salve antes de fechar o programa."))
        messagebox.showinfo(
            t("Chave gerada"),
            t("A frase está no campo, à vista.\n\nGuarde-a agora, em «Salvar…» "
              "ou onde você guarda senha: ela não fica gravada no programa, e "
              "sem ela não há como gerar arquivos novos para o cliente que for "
              "protegido com ela."))
        self.atualizar_botoes()

    def salvar_frase(self):
        """
        Grava a frase num arquivo, fora do cliente.

        Dentro do cliente é recusado, e não apenas avisado: dali o arquivo iria
        junto com o cliente para os jogadores, e a proteção inteira iria com
        ele.
        """
        frase = (self.frase.get() or "").strip()
        if len(frase) < 8:
            messagebox.showinfo(t("Falta a frase"),
                                t("Escreva ou gere a frase primeiro."))
            return
        alvo = filedialog.asksaveasfilename(
            title=t("Onde guardar a chave"), parent=self.raiz,
            defaultextension=".txt", initialfile="chave-do-cliente.txt",
            filetypes=[(t("Texto"), "*.txt")])
        if not alvo:
            return

        sistema = self.system()
        if sistema and l2protecao.dentro_do_cliente(alvo, sistema):
            messagebox.showerror(
                t("Aí não"),
                t("Esse lugar fica dentro da pasta do cliente — e o cliente é "
                  "o que você distribui. O arquivo da chave iria junto, e a "
                  "proteção junto com ele.\n\nEscolha uma pasta fora do "
                  "cliente."))
            return

        try:
            par = l2cripto.par_da_frase(frase)
            escrito = l2protecao.guardar_frase(
                alvo, frase, l2protecao.marca_da_chave(par["modulo"]),
                str(sistema or ""))
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para salvar"), str(erro))
            return
        self.log(t("chave guardada em %s") % escrito)
        messagebox.showinfo(
            t("Chave guardada"),
            t("Em %s.\n\nEsse arquivo é a chave: quem o tiver gera arquivos "
              "que o seu cliente aceita. Trate-o como senha.") % escrito)

    def ver_a_marca(self):
        """A marca da chave da frase, para conferir sem mostrar a chave."""
        frase = (self.frase.get() or "").strip()
        if len(frase) < 8:
            messagebox.showinfo(t("Falta a frase"),
                                t("Escreva a frase primeiro — oito caracteres "
                                  "ou mais."))
            return
        self.diz_a_chave.config(text=t("calculando…"))
        self.raiz.update_idletasks()
        try:
            par = l2cripto.par_da_frase(frase)
        except Exception as erro:                   # noqa: BLE001
            self.diz_a_chave.config(text=str(erro))
            return
        self.diz_a_chave.config(
            text=t("marca da sua chave: %s — a mesma frase dá sempre esta "
                   "marca.") % l2protecao.marca_da_chave(par["modulo"]))

    def proteger(self):
        alvo = self.system()
        escolhidos = self.alvos()
        if not messagebox.askyesno(
                t("Proteger %d arquivo(s)?") % len(escolhidos),
                t("Cada arquivo é copiado para %s antes, refeito com a sua "
                  "chave e conferido — só entra no cliente se voltar "
                  "idêntico.\n\nA chave do executável é trocada por último, e "
                  "só se todos passarem.\n\nFeche o jogo antes.\n\nProteger?")
                % l2protecao.PASTA_GUARDA):
            return
        self.rodando = True
        self.atualizar_botoes()
        self.log(t("\n=== protegendo %d arquivo(s) ===") % len(escolhidos))
        threading.Thread(target=self._proteger_thread,
                         args=(alvo, escolhidos, self.frase.get()),
                         daemon=True).start()

    def _proteger_thread(self, alvo, escolhidos, frase):
        linhas = []
        try:
            feito = l2protecao.proteger(self.T, alvo, escolhidos, frase,
                                        aolog=linhas.append)
            erro = None
        except Exception as e:                      # noqa: BLE001
            feito, erro = None, e
        self.raiz.after(0, self._fim, linhas, feito, erro)

    def _fim(self, linhas, feito, erro):
        self.rodando = False
        for linha in linhas:
            self.log(linha)
        if erro is not None:
            self.log(t("Parou: %s") % erro)
            messagebox.showerror(t("Não deu para proteger"), str(erro))
        elif feito:
            self.log(t("pronto: %d protegido(s), %d recusado(s)")
                     % (len(feito["prontos"]), len(feito["recusados"])))
            messagebox.showinfo(
                t("Cliente protegido"),
                t("%d arquivo(s) fechados com a sua chave (marca %s).\n\n"
                  "Executável: %s\n\nOs originais estão em %s. Abra o jogo "
                  "para conferir antes de distribuir o cliente.")
                % (len(feito["prontos"]), feito["marca"],
                   ", ".join(feito["executaveis"]) or t("não alterado"),
                   l2protecao.PASTA_GUARDA))
        self.reler_cliente()

    def desfazer(self):
        alvo = self.system()
        if not messagebox.askyesno(
                t("Voltar ao original?"),
                t("Põe de volta tudo o que está em %s, inclusive a chave do "
                  "executável.\n\nVoltar?") % l2protecao.PASTA_GUARDA):
            return
        try:
            voltaram = l2protecao.desfazer(alvo, aolog=self.log)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para voltar"), str(erro))
            return
        self.log(t("voltaram %d arquivo(s)") % len(voltaram))
        self.reler_cliente()
