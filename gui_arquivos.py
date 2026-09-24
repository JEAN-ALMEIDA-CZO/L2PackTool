#!/usr/bin/env python3
"""
Aba "L2Crypt" -- abrir e fechar os arquivos do cliente.

Quase tudo no cliente do L2 e criptografado: .dat, .utx, .u, .unr, .ini. Nenhum
editor comum abre isso, e o programa ja precisava decifrar para fazer o resto
do trabalho -- esta aba poe essa capacidade na mao do usuario, nos dois
sentidos.

NUNCA mexe no original: o que entra e lido, o que sai e copia nova, em outra
pasta.

Ao criptografar, o metodo sai da extensao, e nao do que estava no arquivo: um
.utx aberto a mao nao guarda em lugar nenhum que era Ver121. E o nome do
arquivo de saida importa -- a chave do Ver121 deriva dele.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import tema
import ajuda
import idioma
import l2npc
import motor
from idioma import t, N_

# O que vale oferecer na caixa de arquivos, na ordem em que se costuma querer.
TIPOS = (
    (N_("Arquivos do cliente"), "*.dat *.utx *.u *.unr *.usx *.ukx *.uax *.umx *.ini"),
    (N_("Tabelas .dat"), "*.dat"),
    (N_("Pacotes Unreal"), "*.utx *.u *.unr *.usx *.ukx *.uax *.umx"),
    (N_("Configuracao .ini"), "*.ini"),
    (N_("Todos"), "*.*"),
)

# Como cada metodo aparece na lista, em palavras de gente.
METODOS = {
    "111": N_("Blowfish (Ver111)"),
    "121": N_("XOR pelo nome (Ver121)"),
    "413": N_("RSA (Ver413)"),
    None: N_("já esta aberto"),
}

# A tabela mora no motor: a linha de comando fecha arquivo pela mesma
# regra, e ela nao alcanca este modulo.
VERSAO_POR_EXTENSAO = motor.VERSAO_POR_EXTENSAO
VERSAO_PADRAO = motor.VERSAO_PADRAO
versao_de = motor.versao_de


class JanelaArquivos:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.arquivos = []          # [{caminho, metodo}]

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980, foreground=tema.TEXTO_FRACO,
                  text=t("Abre e fecha os arquivos do cliente: .dat, .utx, "
                         ".u, .unr, .ini. Escolha os arquivos, escolha onde "
                         "salvar, e use Descriptografar ou Criptografar. O "
                         "original nunca é tocado.")).pack(anchor="w")

        # ---- escolha ----
        topo = ttk.Frame(quadro)
        topo.pack(fill="x", pady=(8, 0))
        ttk.Button(topo, text=t("Escolher arquivos…"),
                   style="Primario.TButton",
                   command=self.escolher_arquivos).pack(side="left")
        ttk.Button(topo, text=t("Escolher uma pasta…"),
                   command=self.escolher_pasta).pack(side="left", padx=(6, 0))
        ttk.Button(topo, text=t("Tirar da lista"),
                   command=self.tirar).pack(side="left", padx=(6, 0))
        ttk.Button(topo, text=t("Limpar"),
                   command=self.limpar).pack(side="left", padx=(6, 0))
        ajuda.ajuda(topo, lambda: t(
            "Uma pasta entra inteira, sem descer em subpastas.\n\n"
            "Arquivo que já está aberto (sem criptografia) também pode entrar: "
            "ele é copiado como está, para você ter tudo num lugar só."))

        # ---- a lista ----
        corpo = ttk.LabelFrame(quadro, text=t("Arquivos"), padding=6)
        corpo.pack(fill="both", expand=True, pady=(8, 0))

        dentro = ttk.Frame(corpo)
        dentro.pack(fill="both", expand=True)
        colunas = (N_("arquivo"), N_("tamanho"), N_("criptografado"),
                   N_("pasta"))
        self.lista = ttk.Treeview(dentro, columns=colunas, show="headings",
                                  height=14, selectmode="extended")
        for nome, largura in zip(colunas, (240, 90, 170, 420)):
            self.lista.heading(nome, text=t(nome))
            self.lista.column(nome, width=largura, anchor="w")
        rolagem = ttk.Scrollbar(dentro, orient="vertical", command=self.lista.yview)
        self.lista.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)

        self.resumo = ttk.Label(corpo, text="", foreground=tema.TEXTO_FRACO)
        self.resumo.pack(anchor="w", pady=(6, 0))

        # ---- destino e acao ----
        baixo = ttk.Frame(quadro)
        baixo.pack(fill="x", pady=(8, 0))
        ttk.Label(baixo, text=t("Salvar em:")).pack(side="left")
        self.destino = tk.StringVar(
            value=motor.ler_opcao("arquivos", "destino", str(motor.BASE / "abertos")))
        ttk.Entry(baixo, textvariable=self.destino).pack(side="left", fill="x",
                                                         expand=True, padx=(6, 0))
        ttk.Button(baixo, text=t("Escolher…"),
                   command=self.escolher_destino).pack(side="left", padx=(6, 0))

        acao = ttk.Frame(quadro)
        acao.pack(fill="x", pady=(8, 0))
        self.botao = ttk.Button(acao, text=t("Descriptografar"),
                                command=self.descriptografar, state="disabled")
        self.botao.pack(side="left")
        self.botao_fechar = ttk.Button(acao, text=t("Criptografar"),
                                       command=self.criptografar,
                                       state="disabled")
        self.botao_fechar.pack(side="left", padx=(6, 0))
        ajuda.ajuda(acao, lambda: t(
            "Grava uma cópia aberta de cada arquivo na pasta escolhida.\n\n"
            "O método é descoberto pelo cabeçalho do próprio arquivo, e não "
            "pela extensão: um .dat pode ser RSA e um .utx pode ser XOR "
            "derivado do nome -- é por isso que renomear um .utx antes de "
            "abrir o corrompe em silêncio.\n\n"
            "Arquivo já aberto é copiado como está.\n\n"
            "Criptografar faz o caminho inverso, e aí o método vem da "
            "extensão: um arquivo aberto não guarda de onde veio. O nome do "
            "arquivo importa, porque a chave do Ver121 deriva dele."),
            padx=(10, 0))
        self.estado = ttk.Label(acao, text="", foreground=tema.TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

        # ---- registro ----
        reg = ttk.LabelFrame(quadro, text=t("Andamento"), padding=4)
        reg.pack(fill="x", pady=(8, 0))
        self.texto = tk.Text(reg, height=8, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

        self.atualizar()

    # ---- ajudantes -------------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def atualizar(self):
        cifrados = sum(1 for a in self.arquivos if a["metodo"])
        self.resumo.config(
            text=t("%d arquivos na lista, %d criptografados.")
            % (len(self.arquivos), cifrados))
        pronto = "normal" if self.arquivos and not self.rodando else "disabled"
        self.botao.config(state=pronto)
        self.botao_fechar.config(state=pronto)

    def acrescentar(self, caminhos):
        ja = {a["caminho"] for a in self.arquivos}
        novos = 0
        for caminho in caminhos:
            caminho = Path(caminho)
            if caminho in ja or not caminho.is_file():
                continue
            try:
                metodo = l2npc.metodo_do_arquivo(caminho)
            except Exception:
                metodo = None
            self.arquivos.append({"caminho": caminho, "metodo": metodo})
            self.lista.insert("", "end", values=(
                caminho.name, self._tamanho(caminho.stat().st_size),
                self._marca(metodo), str(caminho.parent)))
            novos += 1
        self.atualizar()
        return novos

    @staticmethod
    def _marca(metodo):
        """A coluna responde a pergunta, e so depois diz qual e o metodo."""
        if not metodo:
            return t("não")
        return t("sim — %s") % t(METODOS.get(metodo, N_("desconhecida")))

    @staticmethod
    def _tamanho(bytes_):
        for unidade, divisor in (("MB", 1048576.0), ("KB", 1024.0)):
            if bytes_ >= divisor:
                return "%.1f %s" % (bytes_ / divisor, unidade)
        return "%d B" % bytes_

    # ---- escolhas --------------------------------------------------------
    def escolher_arquivos(self):
        escolhidos = filedialog.askopenfilenames(
            title=t("Escolha os arquivos do cliente"),
            filetypes=[(t(rotulo), padrao) for rotulo, padrao in TIPOS])
        if escolhidos:
            self.log(t("%d arquivo(s) na lista.") % self.acrescentar(escolhidos))

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(title=t("Escolha uma pasta do cliente"))
        if not pasta:
            return
        # Sem subpastas: quem aponta o cliente inteiro por engano nao fica com
        # dez mil arquivos na lista sem perceber.
        achados = sorted(p for p in Path(pasta).iterdir() if p.is_file())
        self.log(t("%d arquivo(s) na lista.") % self.acrescentar(achados))

    def escolher_destino(self):
        pasta = filedialog.askdirectory(title=t("Onde salvar os arquivos abertos?"))
        if pasta:
            self.destino.set(pasta)
            motor.gravar_opcao("arquivos", "destino", pasta)

    def tirar(self):
        for item in self.lista.selection():
            nome, _tam, _met, pasta = self.lista.item(item, "values")
            alvo = Path(pasta) / nome
            self.arquivos = [a for a in self.arquivos if a["caminho"] != alvo]
            self.lista.delete(item)
        self.atualizar()

    def limpar(self):
        self.arquivos = []
        self.lista.delete(*self.lista.get_children())
        self.atualizar()

    # ---- o trabalho ------------------------------------------------------
    def descriptografar(self):
        self._comecar(abrindo=True)

    def criptografar(self):
        self._comecar(abrindo=False)

    def _comecar(self, abrindo):
        """
        Confere o que as duas acoes precisam e dispara a que foi pedida.

        A conferencia e a mesma nos dois sentidos, inclusive a do destino: a
        copia fechada por cima do original quebra tanto quanto a aberta.
        """
        if self.rodando or not self.arquivos:
            return

        destino = Path(self.destino.get().strip())
        if not destino.name:
            messagebox.showerror(t("Falta o destino"),
                                 t("Escolha a pasta onde salvar."))
            return

        l2encdec = Path(self.T.get("l2encdec", ""))
        if not l2encdec.exists():
            messagebox.showerror(t("Ferramentas ausentes"),
                                 t("Faltam: %s\n\nAjuste %s.")
                                 % ("l2encdec", motor.CONFIG))
            return

        # O destino nao pode ser a pasta de origem: sobrescrever o arquivo do
        # cliente com a versao aberta e exatamente o que quebra o cliente.
        origens = {a["caminho"].parent.resolve() for a in self.arquivos}
        try:
            if destino.resolve() in origens:
                messagebox.showerror(
                    t("Destino invalido"),
                    t("A pasta de destino é a mesma de onde os arquivos "
                      "vieram.\n\nEscrever a cópia aberta por cima do "
                      "original quebra o cliente. Escolha outra pasta."))
                return
        except OSError:
            pass

        motor.gravar_opcao("arquivos", "destino", str(destino))
        self.rodando = True
        self.atualizar()
        self.estado.config(text=t("abrindo…") if abrindo else t("fechando…"))
        threading.Thread(target=self._trabalhar, args=(destino, abrindo),
                         daemon=True).start()

    def _trabalhar(self, destino, abrindo=True):
        if not abrindo:
            return self._fechar(destino)
        feitos, falhas = [], []
        self.raiz.after(0, self.log, t("\n=== abrindo %d arquivo(s) em %s ===")
                        % (len(self.arquivos), destino))
        try:
            destino.mkdir(parents=True, exist_ok=True)
            for i, item in enumerate(self.arquivos, 1):
                origem = item["caminho"]
                alvo = destino / origem.name
                self.raiz.after(0, self.estado.config,
                                {"text": t("abrindo %d/%d  %s")
                                 % (i, len(self.arquivos), origem.name)})
                try:
                    if item["metodo"]:
                        # tenta a chave do l2encdec e, se nao for, a original
                        # da NCSoft -- cliente oficial usa a segunda
                        motor.abrir_dat(self.T, origem, alvo, limite=1800)
                        if not alvo.exists():
                            raise RuntimeError(t("o l2encdec não gravou nada"))
                        marca = t("aberto (%s)") % t(METODOS.get(item["metodo"],
                                                                 N_("desconhecida")))
                    else:
                        import shutil
                        shutil.copy2(origem, alvo)
                        marca = t("copiado, já estava aberto")
                    feitos.append(alvo)
                    self.raiz.after(0, self.log, t("  %-34s %s  (%s bytes)")
                                    % (origem.name, marca,
                                       "{:,}".format(alvo.stat().st_size)))
                except Exception as e:
                    falhas.append((origem.name, str(e)))
                    self.raiz.after(0, self.log, t("  %-34s ERRO: %s")
                                    % (origem.name, e))
        except Exception as e:
            falhas.append(("", str(e)))

        self.raiz.after(0, self._fim, destino, feitos, falhas, True)

    def _fechar(self, destino):
        """
        Grava uma copia criptografada de cada arquivo.

        O metodo vem da extensao, nao do arquivo: um arquivo aberto nao guarda
        de onde veio. E quem ja esta criptografado e copiado como esta -- fechar
        duas vezes produz um arquivo que o cliente nao le.

        A conferencia e a ida e volta: descriptografar o que acabou de sair tem
        de devolver exatamente o que entrou.
        """
        feitos, falhas = [], []
        self.raiz.after(0, self.log,
                        t("\n=== fechando %d arquivo(s) em %s ===")
                        % (len(self.arquivos), destino))
        try:
            destino.mkdir(parents=True, exist_ok=True)
            for i, item in enumerate(self.arquivos, 1):
                origem = item["caminho"]
                self.raiz.after(0, self.estado.config,
                                {"text": t("fechando %d/%d  %s")
                                 % (i, len(self.arquivos), origem.name)})
                try:
                    if item["metodo"]:
                        import shutil
                        alvo = destino / origem.name
                        shutil.copy2(origem, alvo)
                        marca = t("copiado, já estava criptografado")
                    else:
                        versao = versao_de(origem)
                        alvo, integro = motor.criptografar(
                            self.T, origem, origem.name, destino, True,
                            versao=versao)
                        if alvo is None:
                            raise RuntimeError(t("o l2encdec não gravou nada"))
                        if not integro:
                            integro = self._confere(origem, alvo, destino)
                        marca = t("fechado em %s%s") % (
                            t(METODOS.get(versao, N_("desconhecida"))),
                            "" if integro else t("  [a ida e volta não confere]"))
                    feitos.append(alvo)
                    self.raiz.after(0, self.log, t("  %-34s %s  (%s bytes)")
                                    % (origem.name, marca,
                                       "{:,}".format(alvo.stat().st_size)))
                except Exception as e:
                    falhas.append((origem.name, str(e)))
                    self.raiz.after(0, self.log, t("  %-34s ERRO: %s")
                                    % (origem.name, e))
        except Exception as e:
            falhas.append(("", str(e)))

        self.raiz.after(0, self._fim, destino, feitos, falhas, False)

    def _confere(self, entrada, saida, destino):
        """
        Abre de volta o que acabou de ser fechado e compara com o que entrou.

        E a conferencia honesta, e a mesma para todos os metodos: quem valida
        nao e o mesmo caminho que gravou.
        """
        volta = destino / ("_conferindo_" + saida.name)
        try:
            motor.executar([self.T["l2encdec"], "-d", saida, volta], limite=1800)
            if not volta.exists():
                return False
            return volta.read_bytes() == entrada.read_bytes()
        except Exception:
            return False
        finally:
            try:
                volta.unlink(missing_ok=True)
            except OSError:
                pass

    def _fim(self, destino, feitos, falhas, abrindo=True):
        self.rodando = False
        self.estado.config(text="")
        self.atualizar()
        self.log((t("  pronto: %d aberto(s), %d com erro.") if abrindo
                  else t("  pronto: %d fechado(s), %d com erro."))
                 % (len(feitos), len(falhas)))

        if feitos:
            messagebox.showinfo(
                t("Prontos"),
                (t("%d arquivo(s) abertos em:\n\n%s\n\nOs originais do "
                   "cliente não foram tocados.") if abrindo else
                 t("%d arquivo(s) criptografados em:\n\n%s\n\nOs originais "
                   "não foram tocados."))
                % (len(feitos), destino))
        else:
            messagebox.showwarning(
                t("Nada feito"),
                t("Nenhum arquivo foi processado. Veja o andamento."))
