#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O lado do servidor de um NPC, como painel para viver dentro da aba de NPC.

O cliente sabe DESENHAR o NPC -- malha, textura, efeito. O que ele nao sabe e o
que o NPC E: quanta vida tem, o que larga ao morrer, onde nasce, o que vende.
Nada disso existe no cliente.

E o primeiro pedaco de tela que escreve para MAIS DE UM servidor. O cliente e
um so; o emulador nao: uns guardam tudo em XML, outros em tabelas do banco, e
ate os nomes dos campos mudam. A caixa "Servidor" escolhe, e o mesmo formulario
sai nos dois formatos.

Este painel nao tem id, nome nem lista de NPC proprios -- eles vem da aba que o
hospeda. Foi assim que as duas telas viraram uma: o NPC e um assunto so, e ter
duas gerava dois arquivos de servidor para o mesmo id.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None          # sem Pillow a lista sai sem desenho

import ajuda
import gui_arma
import l2mundo
import l2servidor
import motor
import gui_projeto
import projeto
from idioma import t, N_

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO



def _servidor_do_projeto():
    """
    A pasta de dados do servidor do projeto -- e so dela.

    Havendo projeto, o que ele diz vale, inclusive quando ele diz que nao tem
    servidor. A reserva do `config.ini` so entra quando nao ha projeto nenhum:
    ela existe para quem usava o programa antes dos projetos, e usa-la com
    projeto escolhido faria a tela ler o servidor de OUTRO projeto sem avisar.
    """
    try:
        if projeto.ha_projeto():
            return projeto.servidor()
    except Exception:                               # noqa: BLE001
        pass
    return motor.ler_opcao("conferir", "servidor", "")


class PainelServidor:
    """
    O formulario do lado do servidor.

    `dono` precisa oferecer `id_do_npc()`, `nome_do_npc()`, `titulo_do_npc()`,
    `base_do_npc()` e `log()`. A aba de NPC os fornece.
    """

    def __init__(self, pai, dono):
        self.dono = dono
        self.campos = {}
        self.drops = []
        # {id do item: (nome, referencia do icone)} -- fica FORA da entrada de
        # drop, que e escrita no XML: um campo a mais ali vazaria para o
        # arquivo do servidor.
        self.nomes_de_drop = {}
        self.loja = []
        self.spawn = {}
        # O que a ultima leitura do servidor pos em nome e titulo. Serve para
        # saber se o que esta no campo foi o usuario que escreveu.
        self._lido_nome = ""
        self._lido_titulo = ""

        quadro = ttk.Frame(pai, padding=8)
        self.quadro = quadro    # a ancora dos `after` desta aba
        quadro.bind("<Destroy>", self._ao_morrer)
        quadro.pack(fill="both", expand=True)

        self._montar_topo(quadro)

        abas = ttk.Notebook(quadro)
        abas.pack(fill="both", expand=True, pady=(8, 0))
        abas.add(self._montar_atributos(abas), text=t(" Atributos "))
        abas.add(self._montar_drop(abas), text=t(" Drop "))
        abas.add(self._montar_spawn(abas), text=t(" Spawn "))
        abas.add(self._montar_loja(abas), text=t(" Loja "))
        abas.add(self._montar_previa(abas), text=t(" Prévia "))
        self.abas = abas
        abas.bind("<<NotebookTabChanged>>", lambda _e: self.atualizar_previa())

    # ---- topo ------------------------------------------------------------
    def _montar_topo(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x")

        ttk.Label(linha, text=t("Servidor:")).pack(side="left")
        # A primeira escolha nao e um perfil: e ler a pasta e montar um. Um
        # arquivo por servidor nao se sustentava -- o servidor de alguem e um
        # core conhecido com tres ou quatro mudancas, e essas mudancas estao
        # escritas nos arquivos dele.
        self.rotulo_detectar = t("Detectar pelo servidor")
        nomes = ([self.rotulo_detectar]
                 + (l2servidor.nomes_dos_perfis() or ["aCis (XML)"]))
        guardado = motor.ler_opcao("servidor", "perfil", l2servidor.DETECTAR)
        self.perfil_nome = tk.StringVar(
            value=self.rotulo_detectar if guardado == l2servidor.DETECTAR
            else guardado)
        if self.perfil_nome.get() not in nomes:
            self.perfil_nome.set(self.rotulo_detectar)
        caixa = ttk.Combobox(linha, textvariable=self.perfil_nome, values=nomes,
                             state="readonly", width=22)
        caixa.pack(side="left", padx=(6, 0))
        caixa.bind("<<ComboboxSelected>>", self.ao_trocar_perfil)

        self.detectado = ttk.Label(linha, text="", foreground=COR_TEXTO_FRACO)
        self.detectado.pack(side="left", padx=(8, 0))

        de_onde = ttk.Frame(pai)
        de_onde.pack(fill="x", pady=(6, 0))
        ttk.Label(de_onde, text=t("Pasta do servidor:")).pack(side="left")
        # A mesma opcao da aba de conferencia: quem apontou o servidor uma vez
        # nao deve ter de apontar de novo noutra tela.
        # Do projeto primeiro: e ele que manda desde que existe a tela de
        # projetos. O `config.ini` fica como reserva, para quem ainda nao
        # criou projeto nenhum.
        self.pasta_do_servidor = tk.StringVar(value=_servidor_do_projeto())
        projeto.ao_trocar(lambda _nome, _cliente, servidor:
                          servidor and self.pasta_do_servidor.set(servidor))
        self.botao_ler = ttk.Button(de_onde, text=t("Ler do servidor"),
                                    command=self.ler_do_servidor)
        self.botao_ler.pack(side="left", padx=(6, 0))
        ajuda.ajuda(de_onde, lambda: t(
            "Traz do servidor o NPC que est\u00e1 MARCADO NA LISTA -- e "
            "n\u00e3o o do campo \"id novo\".\n\n"
            "Vem o que o cliente n\u00e3o guarda: atributos, drop, spawn e "
            "loja. \u00c9 assim que se copiam os n\u00fameros de um monstro "
            "que j\u00e1 funciona.\n\n"
            "Se ele n\u00e3o estiver l\u00e1, ainda n\u00e3o existe do lado "
            "do servidor: \u00e9 o caso de preencher e gerar."), padx=(8, 0))

        self.situacao = ttk.Label(pai, text="", foreground=COR_TEXTO_FRACO,
                                  wraplength=560, justify="left")
        self.situacao.pack(anchor="w", pady=(4, 0))

        marca = ttk.Frame(pai)
        marca.pack(fill="x", pady=(6, 0))
        self.gravar_no_servidor = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            marca, variable=self.gravar_no_servidor,
            text=t("gravar a XML na pasta do servidor")).pack(side="left",
                                                              padx=(0, 14))
        self.nome_pelo_servidor = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            marca, variable=self.nome_pelo_servidor,
            text=t("o servidor manda o nome e o título")).pack(side="left")
        ajuda.ajuda(marca, lambda: t(
            "Escreve usingServerSideName e usingServerSideTitle no XML. Com "
            "eles o servidor envia o nome junto com o NPC, e o cliente só "
            "desenha o que recebeu.\n\n"
            "É a saída quando o cliente não resolve o nome sozinho -- um NPC "
            "com classe própria, gerada aqui, costuma aparecer como "
            "\"NoNameNPC\" no visualizador mesmo com o nome gravado no "
            "npcname-e.dat.\n\n"
            "Desmarque se quiser que valha o nome que está no cliente -- num "
            "cliente traduzido, por exemplo."), padx=(8, 0))

        linha2 = ttk.Frame(pai)
        linha2.pack(fill="x", pady=(6, 0))
        ttk.Label(linha2, text=t("Sai em:")).pack(side="left")
        self.destino = tk.StringVar(
            value=motor.ler_opcao("servidor", "destino",
                                  str(Path(motor.BASE) / "servidor")))
        ttk.Entry(linha2, textvariable=self.destino).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Button(linha2, text=t("Escolher…"),
                   command=self.escolher_destino).pack(side="left", padx=(6, 0))
        ttk.Button(linha2, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "O cliente do Lineage 2 é um só; o emulador não. Uns guardam o "
            "NPC em XML, outros em tabelas do banco, e os nomes dos campos "
            "mudam entre eles.\n\n"
            "\"Detectar pelo servidor\" lê a pasta que você apontou e monta "
            "o perfil a partir dela: onde ficam as coisas, se o alvo da "
            "habilidade leva prefixo, como a gaveta de drop é escrita e em "
            "que unidade vai a chance. O que foi visto aparece ao lado da "
            "caixa.\n\n"
            "Os perfis prontos continuam na lista para quem quiser mandar, e "
            "um core novo se acrescenta largando um arquivo em "
            "recursos/servidores."), padx=(8, 0))

    def ao_trocar_perfil(self, _evento=None):
        motor.gravar_opcao("servidor", "perfil", self.escolha())
        self.dono.log(t("Servidor: %s") % self.perfil_nome.get())
        self.atualizar_previa()

    def escolha(self):
        """O que guardar na configuracao: o rotulo traduzido nao serve."""
        return (l2servidor.DETECTAR
                if self.perfil_nome.get() == self.rotulo_detectar
                else self.perfil_nome.get())

    def dizer_o_detectado(self, perfil_em_uso):
        """
        Mostra em uma linha o que a leitura viu.

        Detectar em silencio trocaria um palpite do usuario por um palpite meu.
        Escrito na tela, ele confere em vez de confiar.
        """
        rotulo = getattr(self, "detectado", None)
        if rotulo is None:
            return
        achados = perfil_em_uso.get("achados")
        if not achados:
            rotulo.config(text="")
            return
        rotulo.config(text=t("detectado: %s") % "; ".join(achados))

    def ler_do_servidor(self):
        """
        Traz do servidor o NPC MARCADO NA LISTA.

        Le o id da lista, e nao o do campo "id novo": o campo diz para onde o
        NPC vai, a lista diz de onde ele vem. Misturar os dois trazia outro NPC
        sem explicar por que.

        Nao achando, diz isso -- "ainda nao existe do lado do servidor" e uma
        resposta util, e nao um erro.
        """
        import l2servidor

        pasta = self.pasta_do_servidor.get().strip()
        if not pasta or not Path(pasta).is_dir():
            messagebox.showerror(
                t("Sem servidor neste projeto"),
                t("Este projeto n\u00e3o tem pasta de servidor, ou ela n\u00e3o "
                  "existe mais.\n\nO caminho vem do projeto -- abra Projetos… "
                  "no alto da janela e aponte a pasta de dados."))
            return

        perfil = self.perfil()
        alvo = str(self.dono.base_do_npc() or "").strip()
        if not alvo:
            messagebox.showinfo(t("Escolha primeiro"),
                                t("Escolha um NPC na lista."))
            return

        motor.gravar_opcao("conferir", "servidor", pasta)
        self.situacao.config(text=t("procurando o %s\u2026") % alvo)
        self.dono.raiz.update_idletasks()

        try:
            achado = l2servidor.achar_npc(pasta, alvo, perfil)
        except Exception as erro:                   # noqa: BLE001
            self.situacao.config(text="")
            messagebox.showerror(t("N\u00e3o deu para ler o servidor"),
                                 str(erro))
            return

        if achado is None:
            self.situacao.config(
                text=t("%s n\u00e3o est\u00e1 no servidor. Preencha e gere: "
                       "\u00e9 um NPC novo tamb\u00e9m do lado de l\u00e1.")
                % alvo)
            self.dono.log(t("  %s não esta no servidor; preencha e gere.")
                          % alvo)
            messagebox.showinfo(
                t("Ainda n\u00e3o existe no servidor"),
                t("N\u00e3o achei %s na pasta do servidor.\n\n"
                  "Isso quer dizer que o NPC ainda n\u00e3o existe do lado de "
                  "l\u00e1. Preencha os atributos e gere -- o arquivo sai "
                  "junto com o que vai para o cliente.") % alvo)
            return

        self.aplicar(achado)
        aviso = achado.get("aviso") or ""
        self.situacao.config(
            text=t("Trazido o %s, de %s. %d campos, %d drops.%s")
            % (alvo, achado["arquivo"].name, len(achado["campos"]),
               len(achado["drops"]), (" " + t("Aten\u00e7\u00e3o: %s.") % aviso)
               if aviso else ""))
        self.dono.log(t("  lido %s de %s") % (alvo, achado["arquivo"].name))

    def aplicar(self, achado):
        """Poe no formulario o que veio do servidor."""
        for chave, valor in (achado.get("campos") or {}).items():
            if chave in self.campos:
                self.campos[chave].set(valor)

        self.drops = list(achado.get("drops") or [])
        self._redesenhar_drops()

        spawn = achado.get("spawn") or {}
        for chave, variavel in self.spawn.items():
            if spawn.get(chave):
                variavel.set(spawn[chave])
        if spawn:
            self.fazer_spawn.set(True)

        loja = achado.get("loja") or {}
        if loja:
            self.loja_id.set(loja.get("id", self.loja_id.get()))
            self.loja = [{"paga": list(l["paga"]), "recebe": list(l["recebe"])}
                         for l in loja["linhas"] if l["paga"] and l["recebe"]]
            self._refazer(self.tabela_loja, self.loja,
                          lambda e: (e["paga"][0][0], e["paga"][0][1],
                                     e["recebe"][0][0], e["recebe"][0][1]))

        # O nome e o titulo sao do passo 1. Entram quando o campo esta vazio ou
        # quando o que esta la veio de uma leitura anterior -- senao, ler um
        # NPC depois do outro deixava o nome do primeiro grudado no segundo.
        # O que o usuario digitou nunca e apagado.
        for valor, variavel, lembrado in (
                (achado.get("nome") or "", self.dono.nome_novo, self._lido_nome),
                (achado.get("titulo") or "", self.dono.titulo_novo,
                 self._lido_titulo)):
            # Vazio tambem entra: o Gremlin nao tem titulo, e deixar o
            # "Gatekeeper" da leitura anterior seria pior do que limpar.
            if variavel.get().strip() in ("", lembrado):
                variavel.set(valor)
        self._lido_nome = achado.get("nome") or ""
        self._lido_titulo = achado.get("titulo") or ""

        self.atualizar_previa()

    def escolher_destino(self):
        pasta = filedialog.askdirectory(title=t("Onde salvar o que for gerado"))
        if pasta:
            self.destino.set(pasta)
            motor.gravar_opcao("servidor", "destino", pasta)

    def pasta_do_npc_no_servidor(self):
        """
        Onde a XML deste NPC deve cair, dentro da pasta do servidor.

        Sai do perfil -- detectado ou escolhido --, mais uma subpasta `custom`,
        que e a convencao dos datapacks L2J. Misturar com os arquivos de
        fabrica torna impossivel saber depois o que foi acrescentado.

        Devolve None quando nao da para saber: pasta nao apontada, ou um perfil
        que nao diz onde os NPCs moram. Melhor nao gravar do que gravar no
        lugar errado.
        """
        if not self.gravar_no_servidor.get():
            return None
        import l2servidor
        return l2servidor.pasta_de(self.pasta_do_servidor.get().strip(),
                                   self.perfil(), "npcs")

    def perfil(self):
        em_uso = l2servidor.perfil_escolhido(
            self.escolha(), self.pasta_do_servidor.get().strip())
        self.dizer_o_detectado(em_uso)
        return em_uso

    def abrir_manual(self):
        import manual

        if manual.abrir(self.dono.raiz, "mundo",
                        t("Manual — NPC e loja")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))

    def _montar_atributos(self, pai):
        aba = ttk.Frame(pai, padding=8)

        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(10, 0))
        grade.columnconfigure(1, weight=1)
        grade.columnconfigure(3, weight=1)
        for i, (chave, rotulo, padrao) in enumerate(l2mundo.CAMPOS_DE_NPC):
            coluna = (i % 2) * 2
            fila = i // 2
            ttk.Label(grade, text=t(rotulo) + ":").grid(
                row=fila, column=coluna, sticky="w", pady=1)
            variavel = tk.StringVar(value=padrao)
            self.campos[chave] = variavel
            if chave == "type":
                widget = ttk.Combobox(grade, textvariable=variavel,
                                      values=list(l2mundo.TIPOS_DE_NPC),
                                      width=14)
            elif chave == "sex":
                widget = ttk.Combobox(grade, textvariable=variavel,
                                      values=list(l2mundo.SEXOS), width=14)
            elif chave in ("targetable", "undying"):
                widget = ttk.Combobox(grade, textvariable=variavel,
                                      values=list(l2mundo.SIM_NAO), width=14)
            else:
                widget = ttk.Entry(grade, textvariable=variavel, width=14)
            widget.grid(row=fila, column=coluna + 1, sticky="ew",
                        padx=(6, 12), pady=1)

        rodape = ttk.Frame(aba)
        rodape.pack(fill="x", pady=(10, 0))
        ttk.Button(rodape, text=t("Medir a colisão pela malha"),
                   command=self.medir_colisao).pack(side="left")
        ajuda.ajuda(rodape, lambda: t(
            "Preenche raio e altura de colisão com o tamanho real da malha do "
            "NPC base, medido da nuvem de vértices.@@"
            "A altura de colisão é a METADE da altura do boneco -- é assim que "
            "o motor a define. Pequena demais, o NPC nasce enterrado no chão; "
            "grande demais, flutua.@@"
            "São valores medidos, não os oficiais: servem de ponto de partida "
            "honesto em vez do 8 e 24 fixos que vinham antes.").replace(
                "@@", chr(10) + chr(10)), padx=(8, 0))

        ttk.Button(rodape, text=t("Escolher a arma…"),
                   command=self.escolher_arma).pack(side="left", padx=(10, 0))
        self.aviso_arma = ttk.Label(rodape, text="",
                                    foreground=COR_TEXTO_FRACO)
        self.aviso_arma.pack(side="left", padx=(8, 0))
        return aba

    def medir_colisao(self, calado=False):
        """
        Poe em raio e altura o tamanho medido da malha do NPC base.

        Sem isto os dois vinham de um numero fixo, e um esqueleto de 53,9
        unidades nascia com meia altura 24 -- enterrado ate a cintura.
        """
        dados = getattr(self.dono, "dados_da_malha_atual", None)
        if not dados or not dados.get("altura"):
            if not calado:
                messagebox.showinfo(
                    t("Falta a malha"),
                    t("Escolha o NPC base na lista: o tamanho vem da malha "
                      "dele."))
            return
        # O tamanho do boneco entra na conta: um NPC dobrado com colisao
        # simples fica com meio corpo enterrado e uma caixa de acerto que nao
        # bate com o que se ve.
        escala = self.dono.tamanho_do_npc()
        altura = float(dados["altura"]) * escala
        raio = (float(dados.get("raio") or 0) or float(dados["altura"]) / 4.0)             * escala
        self.campos["height"].set("%d" % int(round(altura / 2.0)))
        self.campos["radius"].set("%d" % int(round(raio)))
        self.dono.log(t("  colisão medida da malha: altura %s, raio %s "
                        "(tamanho %.2f)")
                      % (self.campos["height"].get(),
                         self.campos["radius"].get(), escala))
        self.atualizar_previa()

    def escolher_arma(self):
        """A arma na mao, escolhida vendo o desenho em vez de digitar o id."""
        import gui_arma

        escolhido = gui_arma.EscolherArma(self.dono.raiz, self.dono,
                                          self.campos["rHand"].get()).resposta
        if escolhido is None:
            return
        self.campos["rHand"].set(str(escolhido["id"]))
        self.aviso_arma.config(text=t("%s (%s)")
                               % (escolhido["nome"], escolhido["id"]))
        self.atualizar_previa()

    def _montar_drop(self, pai):
        aba = ttk.Frame(pai, padding=8)
        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("O que o NPC larga ao morrer. A chance é percentual: "
                         "2.5 é 2,5%. Para o servidor de banco o número é "
                         "convertido para a escala dele.")).pack(anchor="w")

        linha = ttk.Frame(aba)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Button(linha, text=t("+ item"),
                   command=self.por_drop).pack(side="left")
        ttk.Button(linha, text=t("Mudar…"),
                   command=self.mudar_drop).pack(side="left", padx=(4, 0))
        ttk.Button(linha, text=t("Tirar"),
                   command=self.tirar_drop).pack(side="left", padx=(4, 0))
        ajuda.ajuda(linha, lambda: t(
            "O mesmo seletor da aba de Itens e da de Mob: nome, desenho e "
            "busca.@@"
            "O catálogo do cliente é lido uma vez e serve as duas abas — "
            "escolher aqui não paga de novo o que a outra já leu."))

        dentro = ttk.Frame(aba)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("id"), N_("mínimo"), N_("máximo"), N_("chance %"),
                   N_("gaveta"))
        self.tabela_drop = ttk.Treeview(dentro, columns=colunas,
                                        show="tree headings", height=8,
                                        selectmode="extended",
                                        style="Icone.Treeview")
        self.tabela_drop.heading("#0", text=t("item"))
        self.tabela_drop.column("#0", width=230, minwidth=140, stretch=True)
        for nome, largura in zip(colunas, (70, 72, 72, 84, 96)):
            self.tabela_drop.heading(nome, text=t(nome))
            self.tabela_drop.column(nome, width=largura, anchor="e",
                                    stretch=False)
        self.tabela_drop.bind("<Double-1>", lambda _e: self.mudar_drop())
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.tabela_drop.yview)
        self.tabela_drop.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela_drop.pack(side="left", fill="both", expand=True)

        return aba

    def _montar_spawn(self, pai):
        aba = ttk.Frame(pai, padding=8)
        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Onde o NPC nasce. As coordenadas se pegam em jogo, "
                         "no comando que mostra a posição.")).pack(anchor="w")

        grade = ttk.Frame(aba)
        grade.pack(fill="x", pady=(10, 0))
        grade.columnconfigure(1, weight=1)
        self.spawn = {}
        for i, (chave, rotulo, padrao) in enumerate(
                (("x", N_("x"), ""), ("y", N_("y"), ""), ("z", N_("z"), ""),
                 ("direcao", N_("direção"), "0"),
                 ("quantos", N_("quantos"), "1"),
                 ("intervalo", N_("renasce em (s)"), "60"))):
            ttk.Label(grade, text=t(rotulo) + ":").grid(row=i, column=0,
                                                        sticky="w", pady=2)
            variavel = tk.StringVar(value=padrao)
            self.spawn[chave] = variavel
            ttk.Entry(grade, textvariable=variavel, width=16).grid(
                row=i, column=1, sticky="w", padx=(6, 0), pady=2)

        self.fazer_spawn = tk.BooleanVar(value=False)
        ttk.Checkbutton(aba, variable=self.fazer_spawn,
                        text=t("gerar o spawn junto")).pack(anchor="w",
                                                            pady=(10, 0))
        return aba

    def _montar_loja(self, pai):
        aba = ttk.Frame(pai, padding=8)
        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("A loja do NPC: o que o jogador paga e o que recebe. "
                         "Adena é o item 57. O multisell é XML nos dois "
                         "formatos de servidor.")).pack(anchor="w")

        linha = ttk.Frame(aba)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Label(linha, text=t("id da loja") + ":").pack(side="left")
        self.loja_id = tk.StringVar(value="1001")
        ttk.Entry(linha, textvariable=self.loja_id, width=8).pack(
            side="left", padx=(6, 0))

        troca = ttk.Frame(aba)
        troca.pack(fill="x", pady=(8, 0))
        for coluna, rotulo in enumerate((N_("paga o item"), N_("quantidade"),
                                         N_("recebe o item"),
                                         N_("quantidade"))):
            ttk.Label(troca, text=t(rotulo) + ":").grid(row=0, column=coluna,
                                                        sticky="w", padx=(0, 6))
        self.paga_item = tk.StringVar(value="57")
        self.paga_qtd = tk.StringVar(value="1000000")
        self.recebe_item = tk.StringVar()
        self.recebe_qtd = tk.StringVar(value="1")
        for coluna, var in enumerate((self.paga_item, self.paga_qtd,
                                      self.recebe_item, self.recebe_qtd)):
            ttk.Entry(troca, textvariable=var, width=12).grid(
                row=1, column=coluna, sticky="w", padx=(0, 6))
        ttk.Button(troca, text=t("Acrescentar"),
                   command=self.acrescentar_loja).grid(row=1, column=4,
                                                       sticky="w")

        dentro = ttk.Frame(aba)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("paga"), N_("quantidade"), N_("recebe"),
                   N_("quantidade"))
        self.tabela_loja = ttk.Treeview(dentro, columns=colunas,
                                        show="headings", height=7,
                                        selectmode="extended")
        for nome, largura in zip(colunas, (90, 110, 90, 110)):
            self.tabela_loja.heading(nome, text=t(nome))
            self.tabela_loja.column(nome, width=largura, anchor="e")
        rolagem = ttk.Scrollbar(dentro, orient="vertical",
                                command=self.tabela_loja.yview)
        self.tabela_loja.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.tabela_loja.pack(side="left", fill="both", expand=True)

        ttk.Button(aba, text=t("Tirar"),
                   command=self.tirar_loja).pack(anchor="w", pady=(6, 0))
        return aba






    def por_drop(self):
        """
        Escolhe o item no seletor, e pergunta quanto cai no modal.

        O dono do seletor é a ABA de NPC, e não este painel: é dela que vêm o
        caminho do cliente e a pasta de trabalho, e é o catálogo dela que fica
        guardado -- lido uma vez, serve as duas telas.
        """
        escolha = gui_arma.EscolherArma(
            self.dono.raiz, self.dono, grupos=("weapon", "armor", "etc"),
            titulo=t("O que o NPC larga"))
        if not escolha.resposta:
            return
        item = escolha.resposta
        janela = gui_arma.MudarDrop(
            self.dono.raiz, item.get("nome", ""), item["id"],
            percentual=True, gavetas=list(l2mundo.CATEGORIAS_ROTULO),
            gaveta="DROP")
        if janela.resposta is None:
            return
        self._guardar_drop(str(item["id"]), janela.resposta,
                           item.get("nome", ""), item.get("icone", ""))

    def mudar_drop(self):
        marcados = self.tabela_drop.selection()
        if not marcados:
            return
        indice = int(marcados[0])
        if indice >= len(self.drops):
            return
        entrada = self.drops[indice]
        ident = str(entrada.get("item", ""))
        nome, _icone = self.nomes_de_drop.get(ident, ("", ""))
        janela = gui_arma.MudarDrop(
            self.dono.raiz, nome, ident, entrada.get("minimo", "1"),
            entrada.get("maximo", "1"), entrada.get("chance", "1"),
            percentual=True, gavetas=list(l2mundo.CATEGORIAS_ROTULO),
            gaveta=entrada.get("categoria", "DROP"))
        if janela.resposta is None:
            return
        entrada["minimo"] = janela.resposta["minimo"]
        entrada["maximo"] = janela.resposta["maximo"]
        entrada["chance"] = janela.resposta["chance"]
        entrada["categoria"] = janela.resposta["gaveta"] or "DROP"
        self._redesenhar_drops()

    def _guardar_drop(self, ident, valores, nome="", icone=""):
        self.drops.append({"item": ident, "minimo": valores["minimo"],
                           "maximo": valores["maximo"],
                           "chance": valores["chance"],
                           "categoria": valores["gaveta"] or "DROP"})
        if nome or icone:
            self.nomes_de_drop[ident] = (nome, icone)
        self._redesenhar_drops()

    def _redesenhar_drops(self):
        """Refaz a árvore inteira: os índices das linhas são a ordem da lista."""
        self.tabela_drop.delete(*self.tabela_drop.get_children())
        for i, entrada in enumerate(self.drops):
            ident = str(entrada.get("item", ""))
            nome, icone = self._sobre_o_item(ident)
            self.tabela_drop.insert(
                "", "end", iid=str(i), image=self._icone_do_drop(icone),
                text=" " + (nome or t("item %s") % ident),
                values=(ident, entrada.get("minimo", ""),
                        entrada.get("maximo", ""), entrada.get("chance", ""),
                        entrada.get("categoria", "")))

    def _catalogo(self):
        """
        {id: (nome, ícone)} do cliente, se alguma tela já o leu.

        A gaveta é a MESMA que o seletor de item enche -- ele guarda o
        catálogo na aba de NPC, e não em si. Por isso o drop lido do servidor
        aparece com nome e desenho assim que o seletor tiver sido aberto uma
        vez, sem pagar a leitura de novo.
        """
        gaveta = "itens_do_cliente_armor_etc_weapon"
        lidos = getattr(self.dono, gaveta, None) or []
        if len(lidos) == getattr(self, "_quantos_no_catalogo", -1):
            return self._catalogo_pronto
        self._quantos_no_catalogo = len(lidos)
        self._catalogo_pronto = dict(
            (str(i["id"]), (i.get("nome") or "", i.get("icone") or ""))
            for i in lidos)
        return self._catalogo_pronto

    def _sobre_o_item(self, ident):
        """O nome e o ícone daquele id: do que foi escolhido, ou do catálogo."""
        ident = str(ident)
        if ident in self.nomes_de_drop:
            return self.nomes_de_drop[ident]
        return self._catalogo().get(ident, ("", ""))

    def _icone_do_drop(self, referencia):
        """
        O desenho do item. Pede uma vez e guarda no cache da aba de NPC.

        O cache é o dela, e não deste painel: é o mesmo que o seletor de item
        usa, então o desenho já extraído ali não é extraído de novo aqui.
        """
        if not referencia or ImageTk is None:
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
        import l2item
        import motor_
        try:
            arquivo = l2item.extrair_icone(
                self.dono.T, self.dono.cliente.get(), referencia,
                self.dono.trabalho() / "icones")
            imagem = motor_.abrir_imagem(arquivo, self.dono.T) if arquivo else None
        except Exception:                           # noqa: BLE001
            imagem = None
        try:
            self.dono.raiz.after(0, self._icone_chegou, referencia, imagem)
        except (tk.TclError, RuntimeError):
            pass

    def _icone_chegou(self, referencia, imagem):
        if imagem is None:
            return
        self.dono.icones[referencia] = ImageTk.PhotoImage(imagem)
        # Um redesenho so, por mais icones que cheguem juntos.
        if getattr(self, "_redesenho_pedido", False):
            return
        self._redesenho_pedido = True
        try:
            self._redesenho_marcado = self.quadro.after(
                150, self._redesenhar_agora)
        except (tk.TclError, RuntimeError):
            self._redesenho_pedido = False

    def _ao_morrer(self, evento):
        # Em `<Destroy>` o Tkinter as vezes entrega o NOME do widget, e nao
        # o objeto. A conferencia existe para nao fechar a aba quando quem
        # morreu foi um filho do quadro.
        if str(evento.widget) == str(self.quadro):
            self.fechar()

    def fechar(self):
        """
        Chamado antes de destruir a aba, ao trocar o idioma.

        Cancela o que estava marcado. Sem isto o tempo vence depois da
        aba, e o Tcl reclama de um comando que ja nao existe.
        """
        for atributo in ("_marcado", "_redesenho_marcado"):
            bilhete = getattr(self, atributo, None)
            if bilhete is None:
                continue
            try:
                self.quadro.after_cancel(bilhete)
            except tk.TclError:
                pass                    # ja venceu, ou o quadro se foi
            setattr(self, atributo, None)

    def _redesenhar_agora(self):
        self._redesenho_pedido = False
        self._redesenho_marcado = None
        try:
            self._redesenhar_drops()
        except tk.TclError:
            pass

    def tirar_drop(self):
        for indice in sorted((int(i) for i in self.tabela_drop.selection()),
                             reverse=True):
            del self.drops[indice]
        self._redesenhar_drops()
        self.atualizar_previa()

    def acrescentar_loja(self):
        recebe = self.recebe_item.get().strip()
        paga = self.paga_item.get().strip()
        if not (recebe.isdigit() and paga.isdigit()):
            messagebox.showerror(t("Item inválido"),
                                 t("Os dois ids têm de ser números."))
            return
        entrada = {"paga": [(paga, self.paga_qtd.get().strip() or "1")],
                   "recebe": [(recebe, self.recebe_qtd.get().strip() or "1")]}
        self.loja.append(entrada)
        self.tabela_loja.insert("", "end", iid=str(len(self.loja) - 1),
                                values=(paga, entrada["paga"][0][1], recebe,
                                        entrada["recebe"][0][1]))
        self.recebe_item.set("")
        self.atualizar_previa()

    def tirar_loja(self):
        for indice in sorted((int(i) for i in self.tabela_loja.selection()),
                             reverse=True):
            del self.loja[indice]
        self._refazer(self.tabela_loja, self.loja,
                      lambda e: (e["paga"][0][0], e["paga"][0][1],
                                 e["recebe"][0][0], e["recebe"][0][1]))
        self.atualizar_previa()

    @staticmethod
    def _refazer(tabela, dados, como):
        tabela.delete(*tabela.get_children())
        for i, entrada in enumerate(dados):
            tabela.insert("", "end", iid=str(i), values=como(entrada))

    # ---- o que vai ser gerado --------------------------------------------
    def pecas(self):
        """
        Tudo o que sai para o servidor, como [(nome do arquivo, texto)].

        O id, o nome e o titulo vem do dono -- e o mesmo NPC que a aba esta
        criando no cliente. Era isso que faltava quando as duas telas eram
        separadas: cada uma tinha o seu id, e nada garantia que fossem o mesmo.
        """
        perfil = self.perfil()
        ident = str(self.dono.id_do_npc() or "").strip()
        if not ident:
            raise l2mundo.ErroDeMundo(t("Escolha o NPC base e o id novo."))

        campos = dict((c, v.get().strip()) for c, v in self.campos.items())
        texto, ext = l2mundo.xml_do_npc(
            perfil, ident, self.dono.nome_do_npc(), self.dono.titulo_do_npc(),
            campos, self.drops, id_base=self.dono.base_do_npc(),
            nome_pelo_servidor=self.nome_pelo_servidor.get())
        pecas = [("npc_%s%s" % (ident, ext), texto)]

        if self.fazer_spawn.get():
            faltam = [c for c in ("x", "y", "z")
                      if not self.spawn[c].get().strip()]
            if faltam:
                raise l2mundo.ErroDeMundo(
                    t("Faltam as coordenadas do spawn: %s") % ", ".join(faltam))
            texto, ext = l2mundo.spawn(
                perfil, ident, self.spawn["x"].get().strip(),
                self.spawn["y"].get().strip(), self.spawn["z"].get().strip(),
                self.spawn["direcao"].get().strip() or "0",
                self.spawn["quantos"].get().strip() or "1",
                self.spawn["intervalo"].get().strip() or "60")
            pecas.append(("spawn_%s%s" % (ident, ext), texto))

        if self.loja:
            loja_id = self.loja_id.get().strip() or "1001"
            pecas.append((l2mundo.nome_do_multisell(loja_id),
                          l2mundo.multisell(loja_id, [ident], self.loja,
                                            "Gerado pelo L2PackTool")))
        return pecas

    def principal(self):
        """So o arquivo do NPC: (texto, extensao). E o que vai com o cliente."""
        perfil = self.perfil()
        ident = str(self.dono.id_do_npc() or "").strip()
        campos = dict((c, v.get().strip()) for c, v in self.campos.items())
        return l2mundo.xml_do_npc(
            perfil, ident, self.dono.nome_do_npc(), self.dono.titulo_do_npc(),
            campos, self.drops, id_base=self.dono.base_do_npc())

    def gravar_extras(self, destino, aolog=None):
        """
        Grava o spawn e a loja, que nao acompanham o arquivo do NPC.

        O NPC em si vai junto com o que a aba gera para o cliente, para os dois
        sairem na mesma pasta e ninguem instalar so metade.
        """
        destino = Path(destino)
        saiu = []
        for nome, texto in self.pecas()[1:]:
            alvo = l2mundo.gravar(destino, nome, texto)
            saiu.append(alvo)
            if aolog:
                aolog(t("gravado %s") % alvo.name)
        return saiu

    # ---- a previa --------------------------------------------------------
    def _montar_previa(self, pai):
        """
        O que vai sair, do jeito que vai sair.

        Existe porque XML e INSERT sao coisas que se conferem de relance: um
        campo que ficou em branco, um valor na escala errada. Ver o arquivo
        pronto evita gerar tres vezes para descobrir isso.
        """
        aba = ttk.Frame(pai, padding=8)
        ttk.Label(aba, justify="left", wraplength=420,
                  foreground=COR_TEXTO_FRACO,
                  text=t("O que vai ser gravado, no formato do servidor "
                         "escolhido. Atualiza sozinho.")).pack(anchor="w")

        dentro = ttk.Frame(aba)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        self.previa = tk.Text(dentro, height=18, wrap="none",
                              font=("Consolas", 9))
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.previa.yview)
        deitada = ttk.Scrollbar(aba, orient="horizontal",
                                command=self.previa.xview)
        self.previa.config(yscrollcommand=barra.set,
                           xscrollcommand=deitada.set)
        barra.pack(side="right", fill="y")
        self.previa.pack(side="left", fill="both", expand=True)
        deitada.pack(fill="x")

        ttk.Button(aba, text=t("Atualizar"),
                   command=self.atualizar_previa).pack(anchor="w", pady=(6, 0))
        return aba

    def dizer_o_alvo(self):
        """Escreve no botao o id que ele vai ler, para nao restar duvida."""
        botao = getattr(self, "botao_ler", None)
        # A previa se atualiza durante a montagem, e ai nem o botao nem a lista
        # de NPCs do passo 1 existem ainda.
        if botao is None or not hasattr(self.dono, "lista_npc"):
            return
        alvo = str(self.dono.base_do_npc() or "").strip()
        botao.config(text=(t("Ler o %s do servidor") % alvo) if alvo
                     else t("Ler do servidor"))

    def atualizar_previa(self, _evento=None):
        self.dizer_o_alvo()
        if not hasattr(self, "previa"):
            return
        try:
            pecas = self.pecas()
            texto = "\n".join("=== %s\n%s" % (nome, corpo)
                              for nome, corpo in pecas)
        except Exception as erro:                   # noqa: BLE001
            texto = t("(%s)") % erro
        self.previa.config(state="normal")
        self.previa.delete("1.0", "end")
        self.previa.insert("1.0", texto)
        self.previa.config(state="disabled")





def _inteiro(texto, padrao=0):
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return padrao
