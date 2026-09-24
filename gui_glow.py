#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A aba de Glow: o brilho que acompanha a arma.

Mesmo desenho das outras: a lista do que existe a esquerda, o formulario a
direita, gerar numa pasta a parte e so entao instalar no cliente -- com copia
de seguranca e prova de ciclo antes de qualquer gravacao.

O que muda aqui e a regua. No NPC ela mostra o boneco de pe e onde o efeito cai
no corpo; na arma ela mostra a lamina deitada e onde o glow cai entre o cabo e
a ponta. Os dois numeros sao medidos da malha, e nao supostos: a arma deita no
eixo de maior alcance, e e nesse eixo que o ajuste longitudinal anda.

**A regua nao desenha o glow.** Particula do Unreal Engine 2 so o motor do jogo
desenha -- nem o umodel abre. Ela diz ONDE o efeito vai ficar; como ele parece,
so em jogo.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import gui_icone
import l2conferir
import l2env
import l2glow
import l2item
import l2npc
import motor
import gui_mundo
import gui_projeto
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE
LADO_DO_ICONE = 32

LARGURA_REGUA = 300
ALTURA_REGUA = 120


def _cor_de(campos, lado):
    """
    `#rrggbb` de uma das duas cores do nivel. Preto quando falta numero.

    O arquivo guarda os canais separados -- `R1`, `G1`, `B1` --, e o Tk quer a
    cor junta. Valor fora de 0..255 e cortado em vez de recusado: o arquivo e
    de quem o editou, e um numero estranho nao pode impedir a tela de desenhar.
    """
    canais = []
    for canal in ("R", "G", "B"):
        try:
            numero = int(float(str(campos.get(canal + lado, 0)).replace(",", ".")))
        except (TypeError, ValueError):
            numero = 0
        canais.append(max(0, min(255, numero)))
    return "#%02x%02x%02x" % tuple(canais)


class JanelaGlow:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.itens = None
        self.lista = []
        self.mostradas = []
        self.efeitos = []
        self.efeitos_mostrados = []
        self.icones = {}
        self.gravados = []
        self.icone_pendente = None      # o pacote de icone feito e nao posto
        self.resumo = {}
        self.medida_falhou = ""
        self.base = None
        self.medida = None
        self.malha_atual = ""
        self.sugeridas = []             # o que o cliente usa nesta arma
        self.criadas = []               # as armas fora da faixa do jogo
        self.perfil_servidor = None
        self._mexendo_na_cor = False    # trava: a barra escreve, o numero move
        self.env = None                 # o env.int lido do cliente
        self.env_gerado = None          # o env.int novo, ainda nao instalado

        quadro = ttk.Frame(pai, padding=10)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("Põe um efeito de brilho na arma -- o risco de luz "
                         "que acompanha a lâmina. Clique numa arma da lista "
                         "para ver e mexer no que ela tem.")).pack(anchor="w")

        self._montar_cliente(quadro)
        self._montar_servidor(quadro)

        self.abas = ttk.Notebook(quadro)
        self.abas.pack(fill="both", expand=True, pady=(8, 0))

        pagina = ttk.Frame(self.abas, padding=6)
        self.abas.add(pagina, text=t("  Editar glow  "))

        painel = ttk.Panedwindow(pagina, orient="horizontal")
        painel.pack(fill="both", expand=True)
        painel.add(self._montar_armas(painel), weight=2)
        painel.add(self._montar_efeitos(painel), weight=2)
        self._montar_ajustes(pagina)

        self.abas.add(self._montar_criadas(self.abas),
                      text=t("  Armas criadas  "))
        self.abas.add(self._montar_encantamento(self.abas),
                      text=t("  Encantamento  "))

        self._montar_rodape(quadro)
        self.atualizar_botoes()

    # ---- topo ------------------------------------------------------------
    def _montar_cliente(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))

        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))

        self.botao_abrir = ttk.Button(linha, text=t("Carregar"),
                                      style="Primario.TButton",
                                      command=self.abrir)
        self.botao_abrir.pack(side="left", padx=(6, 0))
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Abrir lê o weapongrp.dat e o itemname-e.dat do cliente.\n\n"
            "Antes de qualquer coisa ser gravada, a tabela é remontada e "
            "comparada com o binário original. Se a volta não reproduz a ida "
            "byte a byte, a definição não descreve este cliente e nada é "
            "escrito."), padx=(8, 0))

    def _montar_servidor(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(6, 0))

        self.pasta_do_servidor = tk.StringVar(
            value=gui_mundo._servidor_do_projeto())
        self.gravar_no_servidor = tk.BooleanVar(
            value=bool(motor.ler_opcao("conferir", "servidor", "")))
        ttk.Checkbutton(linha, variable=self.gravar_no_servidor,
                        text=t("gravar a XML em")).pack(side="left",
                                                        padx=(8, 0))
        # A subpasta nao e sempre `custom`: ha pack que reparte a pasta de itens
        # por tipo, e que nao le arma de `custom`. Qual usar sai do servidor.
        self.subpasta = tk.StringVar(
            value=motor.ler_opcao("servidor", "subpasta_itens", ""))
        self.caixa_subpasta = ttk.Combobox(linha, textvariable=self.subpasta,
                                           width=14, state="readonly")
        self.caixa_subpasta.pack(side="left", padx=(4, 0))
        self.caixa_subpasta.bind(
            "<<ComboboxSelected>>",
            lambda _e: motor.gravar_opcao("servidor", "subpasta_itens",
                                          self.subpasta.get()))
        ajuda.ajuda(linha, lambda: t(
            "A pasta de dados do servidor. Marcada a caixa, a XML da arma "
            "criada é copiada direto para a pasta de itens dele.@@"
            "A subpasta ao lado sai do próprio servidor: o programa lista as "
            "que existem e marca a que casa com o tipo do item — `weapons` "
            "para arma, quando ela existe. Nem todo pack lê arma de `custom`, "
            "e gravar no lugar errado entrega o arquivo onde o servidor "
            "ignora.@@"
            "Onde é essa pasta sai do próprio servidor: o programa lê os "
            "arquivos dele para descobrir. Se não der para saber, nada é "
            "gravado -- melhor não gravar do que gravar no lugar errado.")
            .replace("@@", chr(10) + chr(10)), padx=(8, 0))

    def perfil(self):
        """
        O perfil deste servidor, se já foi lido. Nunca lê aqui.

        Ler custa segundos -- a pasta de dados inteira --, e esta função é
        chamada a cada atualização da lista. Fazer a leitura aqui congelaria a
        janela toda vez. Quem lê é `farejar_servidor`, numa thread, uma vez.
        """
        return self.perfil_servidor or {}

    def farejar_servidor(self, aoterminar=None):
        """Lê o perfil do servidor fora da thread da tela, uma vez."""
        pasta = self.pasta_do_servidor.get().strip()
        if not pasta or self.perfil_servidor is not None:
            if aoterminar:
                aoterminar()
            return

        def olhar():
            import l2servidor
            try:
                achado = l2servidor.perfil_escolhido(
                    motor.ler_opcao("servidor", "perfil", l2servidor.DETECTAR),
                    pasta)
            except Exception:                       # noqa: BLE001
                achado = {}
            self.raiz.after(0, self._perfil_chegou, achado, aoterminar)

        threading.Thread(target=olhar, daemon=True).start()

    def _perfil_chegou(self, achado, aoterminar=None):
        self.perfil_servidor = achado or {}
        self._encher_subpastas()
        onde = self.pasta_de_itens_do_servidor()
        if onde is not None:
            self.log(t("Itens do servidor em %s") % onde)
        elif self.pasta_do_servidor.get().strip():
            self.log(t("Não descobri onde os itens moram nessa pasta do "
                       "servidor."))
        if aoterminar:
            aoterminar()

    def _encher_subpastas(self):
        """
        Enche a caixa com as subpastas que o servidor tem, e marca a certa.

        A que casa com o tipo do item vem marcada -- `weapons` para arma --,
        mas a escolha do usuário manda: se ele já escolheu uma e ela continua
        existindo, ela fica.
        """
        import l2servidor
        raiz = self.pasta_do_servidor.get().strip()
        nomes = l2servidor.subpastas_de(raiz, self.perfil(), "itens")
        A_PROPRIA = t("(a própria pasta)")
        self.caixa_subpasta.config(values=[A_PROPRIA] + nomes)

        escolhida = self.subpasta.get().strip()
        if escolhida and escolhida != A_PROPRIA and escolhida in nomes:
            return                      # a escolha do usuário continua valendo
        melhor = l2servidor.subpasta_preferida(raiz, self.perfil(), "itens",
                                               "weapon")
        self.subpasta.set(melhor or A_PROPRIA)

    def pasta_de_itens_do_servidor(self):
        """Onde a XML deve cair, ou None quando não dá para saber."""
        import l2servidor
        sub = self.subpasta.get().strip()
        if sub == t("(a própria pasta)"):
            sub = ""
        return l2servidor.pasta_de(self.pasta_do_servidor.get().strip(),
                                   self.perfil(), "itens", sub)

    # ---- a lista de armas ------------------------------------------------
    def _montar_armas(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Armas do cliente"), padding=6)

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        ttk.Label(topo, text=t("Procurar:")).pack(side="left")
        self.filtro = tk.StringVar()
        entrada = ttk.Entry(topo, textvariable=self.filtro)
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self.preencher())
        self.conta = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="left", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("nome"), N_("glow"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=12, selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (70, 230, 150),
                                              ("e", "w", "w")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento)
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", self.ao_escolher)
        # A mesma descrição da página de Itens: aqui ela ajuda a confirmar que
        # a arma da linha é mesmo a que se quer dar brilho.
        import gui_arma
        gui_arma.DicaDaLinha(self.tabela, self._descricao_da_arma)
        return caixa

    def _descricao_da_arma(self, linha):
        """O texto do jogo para a arma desta linha."""
        try:
            arma = self.mostradas[int(linha)]
        except (ValueError, IndexError, TypeError):
            return ""
        descricao = (arma.get("descricao") or "").strip()
        destaque = (arma.get("destaque") or "").strip()
        if not descricao and not destaque:
            return ""
        titulo = arma["nome"] or t("sem nome")
        if destaque:
            titulo += "   %s" % destaque
        partes = ["%s   (id %s)" % (titulo, arma["id"])]
        if descricao:
            partes.append("")
            partes.append(descricao)
        return "\n".join(partes)

    # ---- a lista de efeitos ----------------------------------------------
    def _montar_efeitos(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Efeitos instalados"), padding=6)

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        self.so_sugeridos = tk.BooleanVar(value=True)
        ttk.Checkbutton(topo, variable=self.so_sugeridos,
                        text=t("só os que o jogo usa em arma"),
                        command=self.filtrar_efeitos).pack(side="left")
        self.conta_fx = ttk.Label(topo, text="", foreground=COR_TEXTO_FRACO)
        self.conta_fx.pack(side="right")

        procura = ttk.Frame(caixa)
        procura.pack(fill="x", pady=(4, 0))
        ttk.Label(procura, text=t("Procurar:")).pack(side="left")
        self.filtro_fx = tk.StringVar()
        entrada = ttk.Entry(procura, textvariable=self.filtro_fx)
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 0))
        entrada.bind("<KeyRelease>", lambda _e: self.filtrar_efeitos())

        self.aviso_fx = ttk.Label(caixa, foreground=tema.ATENCAO, wraplength=460,
                                  justify="left", font=("Segoe UI", 8),
                                  text=t("Nem todo efeito instalado serve "
                                         "para arma: muitos são de NPC, de "
                                         "chão ou de crônica mais nova, e "
                                         "nesta não aparecem. Os da lista "
                                         "marcada o jogo já desenha em armas "
                                         "deste cliente."))
        self.aviso_fx.pack(anchor="w", pady=(4, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("caminho"), N_("usado em"), N_("emissores"))
        self.lista_fx = ttk.Treeview(dentro, columns=colunas, show="headings",
                                     height=11, selectmode="browse")
        for nome, largura in zip(colunas, (250, 130, 110)):
            self.lista_fx.heading(nome, text=t(nome))
            self.lista_fx.column(nome, width=largura, anchor="w")
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.lista_fx.yview)
        self.lista_fx.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lista_fx.pack(side="left", fill="both", expand=True)
        self.lista_fx.bind("<Double-1>", lambda _e: self.usar_efeito())

        baixo = ttk.Frame(caixa)
        baixo.pack(fill="x", pady=(6, 0))
        self.botao_usar = ttk.Button(baixo, text=t("Pôr na arma"),
                                     command=self.usar_efeito)
        self.botao_usar.pack(side="left")
        ttk.Button(baixo, text=t("Copiar de outra arma…"),
                   command=self.copiar_de_outra_arma).pack(side="left",
                                                           padx=(6, 0))
        ttk.Button(baixo, text=t("Tirar o glow"),
                   command=self.tirar_glow).pack(side="left", padx=(6, 0))
        ajuda.ajuda(baixo, lambda: t(
            "A lista é a mesma da aba de NPC: todo efeito de partícula "
            "instalado neste cliente.\n\n"
            "Nem todo efeito foi feito para arma. Os que o jogo usa em armas "
            "começam com c_u -- c_u000, c_u006 -- e são os que costumam ficar "
            "bem na lâmina."), padx=(8, 0))
        return caixa

    # ---- a pagina das armas criadas --------------------------------------
    def _montar_criadas(self, pai):
        aba = ttk.Frame(pai, padding=8)

        ttk.Label(aba, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("As armas do cliente com id acima de %d — a faixa que "
                         "o jogo não usa. A lista sai do próprio "
                         "weapongrp.dat, então ela continua certa mesmo se "
                         "você trocar de cliente ou restaurar um backup.")
                  % l2item.PRIMEIRO_ID_LIVRE).pack(anchor="w")

        dentro = ttk.Frame(aba)
        dentro.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("id"), N_("nome"), N_("tipo"), N_("glow"), N_("XML"))
        self.tabela_criadas = ttk.Treeview(dentro, columns=colunas,
                                           show="headings", height=14,
                                           selectmode="browse")
        for nome, largura, alinhamento in zip(colunas, (70, 230, 90, 190, 210),
                                              ("e", "w", "w", "w", "w")):
            self.tabela_criadas.heading(nome, text=t(nome))
            self.tabela_criadas.column(nome, width=largura, anchor=alinhamento)
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela_criadas.yview)
        self.tabela_criadas.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela_criadas.pack(side="left", fill="both", expand=True)
        self.tabela_criadas.bind("<Double-1>", lambda _e: self.editar_criada())

        baixo = ttk.Frame(aba)
        baixo.pack(fill="x", pady=(8, 0))
        self.botao_editar = ttk.Button(baixo, text=t("Editar o glow desta"),
                                       command=self.editar_criada)
        self.botao_editar.pack(side="left")
        ttk.Button(baixo, text=t("Ver a XML"),
                   command=self.ver_xml_criada).pack(side="left", padx=(6, 0))
        ttk.Button(baixo, text=t("Gravar a XML no servidor"),
                   command=self.gravar_xml_da_criada).pack(side="left",
                                                           padx=(6, 0))
        ttk.Button(baixo, text=t("Excluir"),
                   command=self.excluir_criada).pack(side="left", padx=(16, 0))
        ttk.Button(baixo, text=t("Atualizar"),
                   command=self.refazer_criadas).pack(side="right")
        ajuda.ajuda(baixo, lambda: t(
            "Editar traz a arma para a outra página, com o glow que ela tem "
            "hoje.@@"
            "A XML é montada na hora, a partir da linha do cliente — ela tem "
            "só o que dá para ler de lá. Dano, defesa e preço são do "
            "servidor, e se preenchem na aba Itens.@@"
            "Excluir tira a arma das tabelas na memória. O cliente só muda em "
            "Instalar no cliente, e a XML no servidor é apagada junto: item "
            "que existe só de um lado é confusão garantida.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))
        return aba

    def refazer_criadas(self):
        """Relê do cliente as armas fora da faixa do jogo."""
        self.criadas = []
        tabela = getattr(self, "tabela_criadas", None)
        if tabela is None:
            return
        if self.itens is not None:
            for arma in self.lista:
                try:
                    if int(arma["id"]) < l2item.PRIMEIRO_ID_LIVRE:
                        continue
                except (TypeError, ValueError):
                    continue
                self.criadas.append(arma)

        tabela.delete(*tabela.get_children())
        pasta = self.pasta_de_itens_do_servidor()
        for i, arma in enumerate(self.criadas):
            xml = self._onde_esta_a_xml(arma["id"], pasta)
            try:
                tipo = l2glow.tipo_da_arma(self.itens, arma["linha"]) or "—"
            except Exception:                       # noqa: BLE001
                tipo = "—"
            tabela.insert("", "end", iid=str(i),
                          values=(arma["id"], arma["nome"] or t("sem nome"),
                                  tipo, self._glow_curto(arma["id"]),
                                  xml.name if xml else t("não gerada")))
        # Na montagem da aba ainda nao ha tabela aberta, e o "0 armas"
        # apareceria antes de o usuario ter feito qualquer coisa.
        if self.itens is not None:
            self.log(t("\n%d armas fora da faixa do jogo.") % len(self.criadas))

    def _onde_esta_a_xml(self, ident, pasta=None):
        """A XML daquela arma, na pasta de saída ou na do servidor."""
        nome = "%s-item.xml" % ident
        candidatos = [self.saida() / nome]
        if pasta is None:
            pasta = self.pasta_de_itens_do_servidor()
        if pasta is not None:
            candidatos.append(pasta / nome)
        for alvo in candidatos:
            try:
                if alvo.is_file():
                    return alvo
            except OSError:
                continue
        return None

    def criada_marcada(self):
        marcada = self.tabela_criadas.selection()
        if not marcada:
            messagebox.showinfo(t("Escolha uma arma"),
                                t("Marque na lista a arma que você quer."))
            return None
        indice = int(marcada[0])
        return self.criadas[indice] if indice < len(self.criadas) else None

    def editar_criada(self):
        """Leva a arma marcada para a página de edição, já escolhida."""
        arma = self.criada_marcada()
        if arma is None:
            return
        self.filtro.set(str(arma["id"]))
        self.preencher()
        for i, mostrada in enumerate(self.mostradas):
            if mostrada["id"] == arma["id"]:
                self.tabela.selection_set(str(i))
                self.tabela.see(str(i))
                self.ao_escolher()
                break
        self.abas.select(0)

    def _xml_de(self, arma):
        """A XML daquela arma, montada a partir da linha do cliente."""
        campos = l2item.campos_do_servidor(self.itens, "weapon", arma["linha"])
        return l2item.xml_servidor(arma["id"], arma["nome"], "weapon",
                                   arma["id"], campos=campos,
                                   tipo=campos.get("tipo"))

    def ver_xml_da_marcada(self):
        """A XML da arma escolhida na primeira página."""
        if self.base is None:
            messagebox.showinfo(t("Escolha uma arma"),
                                t("Marque na lista a arma que você quer."))
            return
        self.ver_xml_de(self.base)

    def gravar_xml_da_marcada(self):
        if self.base is None:
            messagebox.showinfo(t("Escolha uma arma"),
                                t("Marque na lista a arma que você quer."))
            return
        self.gravar_xml_de(self.base)

    def ver_xml_criada(self):
        arma = self.criada_marcada()
        if arma is not None:
            self.ver_xml_de(arma)

    def ver_xml_de(self, arma):
        janela = ajuda.por_icone(tk.Toplevel(self.raiz))
        janela.title(t("XML da arma %s") % arma["id"])
        janela.transient(self.raiz)

        ttk.Label(janela, padding=(8, 8, 8, 0), foreground=COR_TEXTO_FRACO,
                  wraplength=560, justify="left",
                  text=t("Montada agora, a partir da linha do cliente. Dano, "
                         "defesa e preço não existem no weapongrp.dat — eles "
                         "se preenchem na aba Itens.")).pack(anchor="w")

        caixa = tk.Text(janela, width=74, height=24, wrap="none")
        caixa.pack(fill="both", expand=True, padx=8, pady=8)
        caixa.insert("1.0", self._xml_de(arma))
        caixa.config(state="disabled")

        baixo = ttk.Frame(janela, padding=(8, 0, 8, 8))
        baixo.pack(fill="x")
        ttk.Button(baixo, text=t("Fechar"),
                   command=janela.destroy).pack(side="right")
        ttk.Button(baixo, text=t("Gravar a XML no servidor"),
                   command=lambda: self.gravar_xml_de(arma)).pack(side="left")
        janela.bind("<Escape>", lambda _e: janela.destroy())

    def gravar_xml_da_criada(self):
        arma = self.criada_marcada()
        if arma is not None:
            self.gravar_xml_de(arma)

    def gravar_xml_de(self, arma):
        """Escreve a XML na pasta de itens do servidor."""
        pasta = self.pasta_de_itens_do_servidor()
        if pasta is None:
            messagebox.showinfo(
                t("Não sei onde gravar"),
                t("Aponte a pasta de dados do servidor no alto da tela.\n\n"
                  "Se ela já está apontada, o programa não conseguiu "
                  "descobrir onde os itens moram dentro dela — e gravar no "
                  "lugar errado é pior do que não gravar."))
            return
        alvo = pasta / ("%s-item.xml" % arma["id"])
        if alvo.exists() and not messagebox.askyesno(
                t("A XML já está lá"),
                t("%s já existe.\n\nEscrever por cima?") % alvo):
            return
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            alvo.write_text(self._xml_de(arma), encoding="utf-8")
        except OSError as erro:
            self.log(t("Não consegui gravar: %s") % erro)
            messagebox.showerror(t("Não consegui gravar"), str(erro))
            return
        self.log(t("XML gravada em %s") % alvo)
        self.refazer_criadas()
        messagebox.showinfo(
            t("XML gravada"),
            t("%s\n\nFalta recarregar no jogo: //reload item") % alvo)

    def excluir_criada(self):
        """Tira a arma das tabelas, e a XML do servidor junto."""
        arma = self.criada_marcada()
        if arma is None:
            return
        pasta = self.pasta_de_itens_do_servidor()
        xml = self._onde_esta_a_xml(arma["id"], pasta)
        no_servidor = (pasta / ("%s-item.xml" % arma["id"])) if pasta else None

        aviso = t("A arma %s — %s sai das tabelas do cliente.\n\nAs tabelas "
                  "são regravadas e instaladas agora; os originais ficam "
                  "guardados em %s.\n\nFeche o cliente antes: ele segura os "
                  "arquivos enquanto roda.") % (
                      arma["id"], arma["nome"] or t("sem nome"),
                      l2item.PASTA_GUARDA)
        if no_servidor is not None and no_servidor.is_file():
            aviso += t("\n\nA XML em %s também é apagada.") % no_servidor
        aviso += t("\n\nExcluir?")
        if not messagebox.askyesno(t("Excluir a arma %s") % arma["id"], aviso):
            return

        saiu = self.itens.remover(arma["id"])
        apagadas = []
        for alvo in (xml, no_servidor):
            if alvo is not None and alvo.is_file():
                try:
                    alvo.unlink()
                    apagadas.append(alvo)
                except OSError as erro:
                    self.log(t("  não consegui apagar %s: %s") % (alvo, erro))

        self.log(t("\nArma %s tirada de: %s") % (arma["id"],
                                                  ", ".join(saiu) or "—"))
        for alvo in apagadas:
            self.log(t("  XML apagada: %s") % alvo)

        # A exclusao so existe de verdade quando chega no cliente. Fazer isso
        # aqui e o que o usuario pediu ao clicar em Excluir -- mandar ele
        # gerar e instalar depois era pedir duas acoes para terminar uma.
        instaladas, erro = self.gravar_e_instalar()

        self.lista = [i for i in self.itens.listar() if i["grupo"] == "weapon"]
        self.resumo_do_glow()
        self.base = None
        self.preencher()
        self.refazer_criadas()
        self.atualizar_botoes()

        if erro is not None:
            messagebox.showerror(
                t("A arma saiu das tabelas, mas não do cliente"),
                t("%s\n\nAs tabelas na memória já estão sem ela. Use Gerar e "
                  "Instalar no cliente quando o problema estiver resolvido.")
                % erro)
            return
        messagebox.showinfo(
            t("Arma excluída"),
            t("A arma %s saiu das tabelas e do cliente (%d arquivo(s) "
              "atualizado(s)).\n\nFeche e abra o cliente: o weapongrp.dat só "
              "é lido no arranque.") % (arma["id"], instaladas))

    def gravar_e_instalar(self):
        """
        Grava as tabelas e as poe no cliente, numa tacada.

        Devolve (quantas foram instaladas, erro). O erro volta em vez de
        estourar porque quem chama precisa terminar a limpeza da tela de
        qualquer jeito -- a memoria ja mudou, e deixar a tela mostrando o que
        nao existe mais seria pior.
        """
        # Regravar as quatro tabelas leva alguns segundos, e a janela fica
        # parada nesse tempo. Dizer o que esta acontecendo antes de travar e
        # o minimo -- barra de progresso aqui exigiria thread, e uma thread
        # no meio de uma exclusao ja confirmada complica mais do que ajuda.
        try:
            self.estado.config(text=t("regravando as tabelas…"))
            self.raiz.update_idletasks()
        except Exception:                           # noqa: BLE001
            pass
        try:
            gravadas = self.itens.gravar(self.saida(),
                                         aolog=lambda s: self.log("  " + s))
            postas = l2item.instalar(gravadas, self.system(),
                                     aolog=lambda s: self.log("  " + s))
            self.gravados = gravadas
            self._limpar_estado()
            return len(postas), None
        except Exception as erro:                   # noqa: BLE001
            self.log(t("  a instalação parou: %s") % erro)
            self._limpar_estado()
            return 0, erro

    def _limpar_estado(self):
        try:
            self.estado.config(text="")
        except Exception:                           # noqa: BLE001
            pass

    # ---- a pagina do encantamento ----------------------------------------
    def _montar_encantamento(self, pai):
        aba = ttk.Frame(pai, padding=8)

        ttk.Label(aba, font=("Segoe UI", 9, "bold"), foreground=tema.ATENCAO,
                  justify="left", wraplength=980,
                  text=t("Isto vale para TODAS as armas do servidor, e não "
                         "para a arma escolhida. É a regra do cliente sobre o "
                         "brilho de encantamento — o halo que a arma ganha ao "
                         "ser refinada.")).pack(anchor="w")
        ttk.Label(aba, foreground=COR_TEXTO_FRACO, justify="left",
                  wraplength=980,
                  text=t("O glow da outra página é da arma: ela brilha já em "
                         "+0. Este é o do encantamento, e mora no env.int. O "
                         "original é guardado na primeira instalação, e "
                         "Restaurar original desfaz tudo.")).pack(
            anchor="w", pady=(2, 8))

        linha = ttk.Frame(aba)
        linha.pack(fill="x")
        self.campos_env = {}
        for chave, rotulo in l2env.MOSTRAR:
            celula = ttk.Frame(linha)
            celula.pack(side="left", padx=(0, 24))
            ttk.Label(celula, text=t(rotulo)).pack(side="left")
            variavel = tk.StringVar()
            self.campos_env[chave] = variavel
            ttk.Spinbox(celula, textvariable=variavel, from_=0,
                        to=l2env.NIVEIS - 1, width=4).pack(side="left",
                                                           padx=(4, 4))
            ttk.Label(celula, text=chave, foreground=COR_TEXTO_FRACO,
                      font=("Segoe UI", 8)).pack(side="left")
        ajuda.ajuda(linha, lambda: t(
            "No cliente do jogo original a malha muda no +4 e o brilho "
            "aparece no +7. Baixando o segundo para 4, toda arma +4 passa a "
            "brilhar.@@"
            "Os dois são independentes: dá para a malha mudar sem brilho, e o "
            "contrário.@@"
            "Isto não tem nada a ver com o item: é o cliente decidindo quando "
            "desenhar o halo, e vale para a arma de todo mundo.")
            .replace("@@", chr(10) + chr(10)))

        caixa = ttk.LabelFrame(aba, text=t("A cor de cada nível"), padding=6)
        caixa.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(caixa, foreground=COR_TEXTO_FRACO, wraplength=940,
                  justify="left",
                  text=t("Cada nível tem duas cores. Nos 21 de fábrica a "
                         "segunda é sempre a mesma cor da primeira, um pouco "
                         "mais escura — o que exatamente o jogo faz com as "
                         "duas só dá para ver em jogo. A linha do arquivo se "
                         "escreve sozinha enquanto você move as "
                         "barras.")).pack(anchor="w")
        ttk.Label(caixa, foreground=COR_TEXTO_FRACO, wraplength=940,
                  justify="left",
                  text=t("O cliente de fábrica tem %d níveis, e acima deles "
                         "vale a linha `Enchant=` — a última caixa. Servidor "
                         "que encanta mais alto pode dar cor própria até o "
                         "+%d; os níveis tracejados na faixa ainda não têm "
                         "uma.")
                  % (l2env.NIVEIS_DE_FABRICA, l2env.NIVEIS - 1)).pack(
            anchor="w", pady=(2, 0))

        # A faixa dos 21 niveis, desenhada. A progressao do cliente -- cinza
        # ate o +3, azul ate o +15, vermelho dali em diante -- se le de uma
        # vez, o que a tabela de numeros nao deixa ver.
        self.faixa_env = tk.Canvas(caixa, height=46, highlightthickness=1,
                                   highlightbackground=tema.BORDA_FORTE,
                                   background=tema.FUNDO)
        self.faixa_env.pack(fill="x", pady=(8, 0))
        self.faixa_env.bind("<Button-1>", self.clicar_na_faixa)
        self.faixa_env.bind("<Configure>", lambda _e: self.desenhar_faixa())

        corpo = ttk.Frame(caixa)
        corpo.pack(fill="both", expand=True, pady=(10, 0))

        escolha = ttk.Frame(corpo)
        escolha.pack(fill="x")
        ttk.Label(escolha, text=t("editando o nível") + " +").pack(side="left")
        self.nivel_env = tk.StringVar(value="7")
        caixa_nivel = ttk.Spinbox(escolha, textvariable=self.nivel_env,
                                  from_=0, to=l2env.NIVEIS - 1, width=4,
                                  command=lambda: self.editar_nivel())
        caixa_nivel.bind("<Return>", lambda _e: self.editar_nivel())
        caixa_nivel.pack(side="left", padx=(4, 0))
        self.rotulo_nivel = ttk.Label(escolha, text="",
                                      foreground=COR_TEXTO_FRACO)
        self.rotulo_nivel.pack(side="left", padx=(10, 0))

        grupos = ttk.Frame(corpo)
        grupos.pack(fill="x", pady=(8, 0))

        self.campos_cor = {}
        self.amostras = {}
        for lado, rotulo in (("1", N_("Cor 1")), ("2", N_("Cor 2"))):
            self.amostras[lado] = self._montar_cor(grupos, lado, t(rotulo))

        forca = ttk.LabelFrame(grupos, text=t("Força"), padding=8)
        forca.pack(side="left", fill="y")
        for nome, rotulo in (("Opacity", N_("opacidade")),
                             ("Num", N_("intensidade"))):
            self._montar_barra(forca, nome, t(rotulo), 0.1, 1.0, casas=2)
        ttk.Label(forca, foreground=tema.ATENCAO, wraplength=190, justify="left",
                  font=("Segoe UI", 8),
                  text=t("O jogo nunca passa de 1 nos dois. Acima disso a "
                         "partícula pesa em quem joga, não no servidor: ela é "
                         "desenhada todo quadro, em toda arma encantada na "
                         "tela.")).pack(anchor="w", pady=(6, 0))

        acima = ttk.Frame(corpo)
        acima.pack(fill="x", pady=(8, 0))
        self.usar_acima = tk.BooleanVar(value=False)
        ttk.Checkbutton(acima, variable=self.usar_acima,
                        command=self.trocar_para_acima,
                        text=t("este é o `Enchant=`, que vale acima do último "
                               "nível")).pack(side="left")
        ajuda.ajuda(acima, lambda: t(
            "A linha `Enchant=` sem número fica logo abaixo da série, e é o "
            "que o cliente usa para qualquer encantamento acima do último "
            "nível escrito.@@"
            "Neste cliente ela é igual ao +20 — por isso um +40 hoje tem a "
            "mesma cor do +20.@@"
            "Marcando a caixa, Guardar escreve nela em vez de num nível. É o "
            "jeito de dizer \"daqui para cima, esta cor\" sem escrever "
            "quarenta linhas.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))

        linha_gerada = ttk.Frame(corpo)
        linha_gerada.pack(fill="x", pady=(10, 0))
        ttk.Label(linha_gerada, text=t("no arquivo:")).pack(side="left")
        self.linha_env = tk.StringVar()
        entrada = ttk.Entry(linha_gerada, textvariable=self.linha_env,
                            font=("Consolas", 9))
        entrada.pack(side="left", fill="x", expand=True, padx=(6, 6))
        entrada.config(state="readonly")
        ttk.Button(linha_gerada, text=t("Copiar"),
                   command=self.copiar_linha_env).pack(side="left")

        acao = ttk.Frame(corpo)
        acao.pack(fill="x", pady=(8, 0))
        ttk.Button(acao, text=t("Guardar o nível"),
                   command=self.guardar_nivel).pack(side="left")
        ttk.Button(acao, text=t("Voltar ao original"),
                   command=self.voltar_nivel).pack(side="left", padx=(6, 0))
        ttk.Button(acao, text=t("Cor 2 = cor 1 mais escura"),
                   command=self.escurecer_cor2).pack(side="left", padx=(6, 0))
        ajuda.ajuda(acao, lambda: t(
            "O que o jogo faz com as duas cores — alterna, mistura, usa uma no "
            "núcleo e outra na borda — não dá para ler do cliente: quem lê "
            "estas linhas é o código nativo do executável, e não "
            "UnrealScript.@@"
            "O que se sabe é que nos 21 níveis de fábrica a cor 2 é sempre a "
            "mesma cor da 1, um pouco mais escura, sem exceção. `Cor 2 = cor 1 "
            "mais escura` reproduz isso num clique.@@"
            "Para descobrir o resto: ponha duas cores bem diferentes num nível "
            "que o cliente certamente lê — o +7, por exemplo — e olhe em jogo.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))
        ttk.Button(acao, text=t("Copiar para os de cima"),
                   command=self.copiar_para_cima).pack(side="left",
                                                       padx=(16, 0))
        ajuda.ajuda(acao, lambda: t(
            "`Copiar para os de cima` repete este nível em todos os acima "
            "dele. É o caminho curto para \"do +7 em diante tudo vermelho\" "
            "sem mexer em catorze níveis a mão.@@"
            "`Voltar ao original` desfaz só este nível, com o que estava no "
            "arquivo quando ele foi lido.")
            .replace("@@", chr(10) + chr(10)), padx=(10, 0))

        dentro = ttk.Frame(corpo)
        dentro.pack(fill="both", expand=True, pady=(10, 0))
        colunas = (N_("nível"),) + l2env.CORES
        self.tabela_env = ttk.Treeview(dentro, columns=colunas,
                                       show="headings", height=7,
                                       selectmode="browse")
        for nome in colunas:
            self.tabela_env.heading(nome, text=t(nome) if nome == "nível"
                                    else nome)
            # `stretch=False`: sem isto o Treeview reparte a largura da janela
            # entre as nove colunas, e cada numero de tres digitos fica no meio
            # de um vazio de duzentos pixels.
            self.tabela_env.column(nome, width=64, minwidth=52, anchor="e",
                                   stretch=False)
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela_env.yview)
        self.tabela_env.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela_env.pack(side="left", fill="both", expand=True)
        self.tabela_env.bind("<<TreeviewSelect>>",
                             lambda _e: self.editar_nivel())

        baixo = ttk.Frame(aba)
        baixo.pack(fill="x", pady=(8, 0))
        ttk.Button(baixo, text=t("Ler do cliente"),
                   command=self.ler_env).pack(side="left")
        self.botao_env_gerar = ttk.Button(baixo, text=t("Gerar"),
                                          command=self.gerar_env,
                                          state="disabled")
        self.botao_env_gerar.pack(side="left", padx=(6, 0))
        self.botao_env_instalar = ttk.Button(
            baixo, text=t("Instalar no cliente"), command=self.instalar_env,
            state="disabled")
        self.botao_env_instalar.pack(side="left", padx=(6, 0))
        self.botao_env_restaurar = ttk.Button(
            baixo, text=t("Restaurar original"), command=self.restaurar_env,
            state="disabled")
        self.botao_env_restaurar.pack(side="left", padx=(16, 0))
        self.estado_env = ttk.Label(baixo, text="",
                                    foreground=COR_TEXTO_FRACO)
        self.estado_env.pack(side="left", padx=(12, 0))
        return aba

    def _montar_cor(self, pai, lado, rotulo):
        """Uma cor: a amostra e as três barras. Devolve a amostra."""
        caixa = ttk.LabelFrame(pai, text=rotulo, padding=8)
        caixa.pack(side="left", fill="y", padx=(0, 12))

        topo = ttk.Frame(caixa)
        topo.pack(fill="x")
        amostra = tk.Canvas(topo, width=52, height=52, highlightthickness=1,
                            highlightbackground=tema.TEXTO_FRACO,
                            highlightcolor=tema.TEXTO_FRACO, background="#000000")
        amostra.pack(side="left", padx=(0, 10))

        barras = ttk.Frame(topo)
        barras.pack(side="left")
        for canal, cor in (("R", N_("vermelho")), ("G", N_("verde")),
                           ("B", N_("azul"))):
            self._montar_barra(barras, canal + lado, t(cor), 0, 255, casas=0)
        return amostra

    def _montar_barra(self, pai, campo, rotulo, menor, maior, casas):
        """
        Um rótulo, uma barra e a caixa do número, sempre em acordo.

        Os dois mexem na MESMA variável: a barra escreve o número, e o número
        move a barra. Duas cópias do mesmo valor seria a tela mostrando uma
        coisa e gravando outra.
        """
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=1)
        ttk.Label(linha, text=rotulo, width=11).pack(side="left")

        variavel = tk.StringVar()
        self.campos_cor[campo] = variavel

        def ao_arrastar(valor):
            # `%g` e nao `%.2f`: o arquivo escreve `0.4` e `1`, e nao `0.40` e
            # `1.00`. Duas casas deixariam as linhas mexidas visivelmente
            # diferentes das outras dezoito.
            numero = float(valor)
            texto = ("%g" % round(numero, 2)) if casas else "%d" % numero
            if variavel.get() != texto:
                variavel.set(texto)

        barra = ttk.Scale(linha, from_=menor, to=maior, length=140,
                          command=ao_arrastar)
        barra.pack(side="left", padx=(0, 6))
        variavel.barra = barra
        variavel.casas = casas
        variavel.limites = (menor, maior)

        ttk.Entry(linha, textvariable=variavel, width=6).pack(side="left")
        variavel.trace_add("write", lambda *_a: self._cor_mudou(campo))
        return variavel

    def _cor_mudou(self, campo):
        """
        Um número mudou: a barra segue, a amostra repinta, a linha se reescreve.

        Guardado contra reentrância -- a barra escreve na variável, que chama
        isto, que moveria a barra, que escreveria de novo.
        """
        if getattr(self, "_mexendo_na_cor", False):
            return
        self._mexendo_na_cor = True
        try:
            variavel = self.campos_cor[campo]
            try:
                numero = float((variavel.get() or "0").replace(",", "."))
            except ValueError:
                return                  # número pela metade: só não faz nada
            menor, maior = variavel.limites
            if variavel.barra.get() != numero:
                variavel.barra.set(max(menor, min(maior, numero)))
        finally:
            self._mexendo_na_cor = False
        self._pintar_amostras()
        self._escrever_linha()

    def _numero_do_campo(self, campo, padrao=0):
        try:
            return float((self.campos_cor[campo].get() or "").replace(",", "."))
        except (KeyError, ValueError):
            return padrao

    def _pintar_amostras(self):
        for lado, amostra in getattr(self, "amostras", {}).items():
            cor = "#%02x%02x%02x" % tuple(
                max(0, min(255, int(self._numero_do_campo(canal + lado))))
                for canal in ("R", "G", "B"))
            try:
                amostra.config(background=cor)
            except tk.TclError:
                pass

    def campos_do_nivel(self):
        """Os oito valores como o arquivo os escreve."""
        saida = {}
        for nome in l2env.CORES:
            variavel = self.campos_cor.get(nome)
            if variavel is None:
                continue
            texto = (variavel.get() or "").strip().replace(",", ".")
            if texto:
                saida[nome] = texto
        return saida

    def _escrever_linha(self):
        """A linha do arquivo, montada agora. É o que vai ser gravado."""
        corpo = l2env._linha_de_cor(self.campos_do_nivel())
        if getattr(self, "usar_acima", None) is not None \
                and self.usar_acima.get():
            self.linha_env.set("Enchant=%s" % corpo)
            return
        try:
            nivel = int(self.nivel_env.get())
        except ValueError:
            nivel = 0
        self.linha_env.set("Enchant%d=%s" % (nivel, corpo))

    def copiar_linha_env(self):
        try:
            self.raiz.clipboard_clear()
            self.raiz.clipboard_append(self.linha_env.get())
            self.log(t("  copiado: %s") % self.linha_env.get())
        except tk.TclError:
            pass

    # ---- a faixa dos niveis ----------------------------------------------
    def desenhar_faixa(self):
        """
        Os 21 níveis lado a lado, cada um partido nas suas duas cores.

        Serve para ver a progressão inteira de uma vez -- neste cliente, cinza
        até o +3, azul do +4 ao +15 e vermelho dali em diante. A tabela de
        números tem os mesmos dados e não deixa ver isso.
        """
        tela = getattr(self, "faixa_env", None)
        if tela is None:
            return
        tela.delete("all")
        if self.env is None:
            tela.create_text(10, 22, anchor="w", fill=tema.TEXTO_FRACO,
                             font=("Segoe UI", 8),
                             text=t("use Ler do cliente para começar"))
            return

        largura = max(tela.winfo_width(), 200)
        passo = largura / float(l2env.NIVEIS)
        escolhido = self.nivel_env.get()
        acima = self.env.get(l2env.ACIMA) or {}
        # Com 61 colunas nao cabe um numero em cada uma. De cinco em cinco, mais
        # o que esta sendo editado, e a faixa continua legivel.
        de_quanto = 1 if passo >= 16 else (5 if passo >= 5 else 10)

        for nivel in range(l2env.NIVEIS):
            proprio = nivel in self.env["cores"]
            campos = self.env["cores"].get(nivel) or acima
            x = nivel * passo
            for lado, (topo, base) in (("1", (2, 18)), ("2", (18, 34))):
                tela.create_rectangle(x + 0.5, topo, x + passo - 0.5, base,
                                      fill=_cor_de(campos, lado), width=0)
            marcado = str(nivel) == escolhido
            # Tracejado quando o nivel ainda nao tem linha propria: a cor que
            # aparece e emprestada do `Enchant=`, e dizer isso evita que ela
            # pareca escolhida.
            tela.create_rectangle(
                x + 0.5, 2, x + passo - 0.5, 34,
                outline=tema.INFO if marcado else tema.BORDA_FORTE,
                dash=() if proprio else (2, 2),
                width=2 if marcado else 1)
            if marcado or nivel % de_quanto == 0:
                tela.create_text(x + passo / 2, 40, text=str(nivel),
                                 font=("Segoe UI", 7),
                                 fill=tema.INFO if marcado else tema.TEXTO_APAGADO)

    def clicar_na_faixa(self, evento):
        if self.env is None:
            return
        largura = self.faixa_env.winfo_width()
        if largura <= l2env.NIVEIS:
            return                      # ainda nao desenhada: clique em nada
        nivel = int(evento.x / (largura / float(l2env.NIVEIS)))
        self.editar_nivel(max(0, min(l2env.NIVEIS - 1, nivel)))

    # ---- o env.int -------------------------------------------------------
    def voltar_nivel(self):
        """Desfaz só este nível, com o que o arquivo tinha quando foi lido."""
        if self.env is None:
            return
        try:
            nivel = int(self.nivel_env.get())
        except ValueError:
            return
        original = (self.env.get("cores_lidas") or {}).get(nivel)
        if original is None:
            messagebox.showinfo(t("Sem original"),
                                t("Não guardei como este nível estava."))
            return
        self.env["cores"][nivel] = dict(original)
        self._refazer_niveis()
        self.editar_nivel(nivel)
        self.log(t("  nível %d voltou ao original.") % nivel)

    def copiar_para_cima(self):
        """Repete este nível em todos os acima dele."""
        if self.env is None:
            return
        try:
            nivel = int(self.nivel_env.get())
        except ValueError:
            return
        campos = self.campos_do_nivel()
        if not campos:
            return
        teto = self._teto_dos_niveis()
        if not messagebox.askyesno(
                t("Copiar para os de cima"),
                t("Os níveis de +%d a +%d ficam todos com esta cor, e a linha "
                  "`Enchant=` junto.\n\nContinuar?") % (nivel + 1, teto)):
            return
        for alvo in range(nivel, teto + 1):
            self.env["cores"][alvo] = dict(campos)
        self.env[l2env.ACIMA] = dict(campos)
        self._refazer_niveis()
        self.desenhar_faixa()
        self.log(t("  do nível %d ao %d: %s")
                 % (nivel, teto, l2env._linha_de_cor(campos)))
        self.atualizar_botoes()

    def trocar_para_acima(self):
        """
        A caixa do `Enchant=` traz os números dele, e não os do nível.

        Sem isto a marca só mudava para onde o Guardar escreve, e os campos
        continuavam com a cor anterior: a tela mostraria uma coisa e gravaria
        outra com esse nome.
        """
        if self.env is None:
            return
        if self.usar_acima.get():
            campos = dict(self.env.get(l2env.ACIMA) or {})
            for nome in l2env.CORES:
                self.campos_cor[nome].set(campos.get(nome, ""))
            self.rotulo_nivel.config(
                text=t("(editando a linha que vale acima do último nível)"))
            self._escrever_linha()
        else:
            self.editar_nivel()

    def escurecer_cor2(self):
        """
        Põe na cor 2 a cor 1 um pouco mais escura, que é o que o jogo faz.

        Nos 21 níveis de fábrica a cor 2 é sempre a mesma cor da 1, entre 10 e
        25 pontos abaixo -- os 21, sem exceção. Quem quer o visual do jogo
        chega nele com um clique, em vez de acertar seis números.
        """
        for canal in ("R", "G", "B"):
            claro = self._numero_do_campo(canal + "1")
            self.campos_cor[canal + "2"].set("%d" % max(0, int(claro) - 20))
        self._pintar_amostras()
        self._escrever_linha()

    def _teto_dos_niveis(self):
        """
        Até onde "copiar para os de cima" vai.

        O nível que está sendo editado, quando ele passa dos que o arquivo tem:
        quem foi até o +45 quer até o +45, e escrever até o +60 por conta
        própria acrescentaria quinze linhas que ninguém pediu.
        """
        try:
            escolhido = int(self.nivel_env.get())
        except ValueError:
            escolhido = 0
        existentes = max(self.env["cores"]) if self.env["cores"] else 0
        return min(l2env.NIVEIS - 1, max(existentes, escolhido))

    def ler_env(self):
        """Lê o env.int do cliente e enche a tela."""
        try:
            self.env = l2env.ler(self.T, self.system(),
                                 self.trabalho() / "env")
        except Exception as erro:                   # noqa: BLE001
            self.log(t("Não deu para ler o env.int: %s") % erro)
            messagebox.showerror(t("Não deu para ler o env.int"), str(erro))
            return

        # Como cada nivel estava quando o arquivo foi lido. E o que o botao
        # "Voltar ao original" devolve, sem precisar reler o cliente inteiro.
        self.env["cores_lidas"] = dict((n, dict(c))
                                       for n, c in self.env["cores"].items())

        for chave, _rotulo in l2env.MOSTRAR:
            self.campos_env[chave].set(self.env["mostrar"].get(chave, ""))
        self._refazer_niveis()
        self.editar_nivel(int(self.nivel_env.get() or 0))
        self.env_gerado = None
        self.estado_env.config(text=t("lido de %s") % self.system())

        # Lixo de uma versao anterior deste programa: niveis escritos antes do
        # primeiro cabecalho, fora de toda secao, onde o jogo nao os le.
        perdidas = l2env.linhas_fora_da_secao(self.env)
        if perdidas:
            self.log(t("  %d linhas Enchant estão fora da seção "
                       "[EnchantEffect] — o jogo não as lê. Gerar de novo "
                       "limpa.") % len(perdidas))
            messagebox.showwarning(
                t("Este env.int tem linhas no lugar errado"),
                t("%d linhas `Enchant` estão fora da seção "
                  "[EnchantEffect].\n\nElas foram escritas por uma versão "
                  "anterior deste programa e o jogo nunca as leu — é por isso "
                  "que a cor não mudava.\n\nGerar e instalar de novo limpa o "
                  "arquivo e põe tudo no lugar certo.") % len(perdidas))
        self.log(t("\nenv.int lido: a malha muda no +%s, o brilho aparece no "
                   "+%s.")
                 % (self.env["mostrar"].get("EnchantMeshShow", "?"),
                    self.env["mostrar"].get("EnchantEffectShow", "?")))
        self.atualizar_botoes()

    def _refazer_niveis(self):
        tabela = self.tabela_env
        tabela.delete(*tabela.get_children())
        if self.env is None:
            return
        for nivel in sorted(self.env["cores"]):
            campos = self.env["cores"][nivel]
            tabela.insert("", "end", iid=str(nivel),
                          values=(nivel,) + tuple(campos.get(n, "")
                                                  for n in l2env.CORES))

    def editar_nivel(self, nivel=None):
        """Traz os números daquele nível para os campos de cima."""
        if self.env is None:
            return
        if nivel is None:
            marcado = self.tabela_env.selection()
            if not marcado:
                return
            nivel = int(marcado[0])
        campos = self.env["cores"].get(nivel)
        if campos is None:
            # Nivel sem linha propria: hoje ele usa o `Enchant=`. Comecar dali
            # e o ponto de partida honesto -- campos vazios diriam que a cor e
            # nenhuma, e nao e.
            campos = dict(self.env.get(l2env.ACIMA) or {})
        self.nivel_env.set(str(nivel))
        for nome in l2env.CORES:
            self.campos_cor[nome].set(campos.get(nome, ""))
        mostrar = self.env["mostrar"].get("EnchantEffectShow", "")
        if nivel not in self.env["cores"]:
            recado = t("(sem linha própria: hoje usa o `Enchant=`)")
        elif mostrar.isdigit() and nivel < int(mostrar):
            recado = t("(abaixo do +%s o brilho nem aparece)") % mostrar
        else:
            recado = ""
        self.rotulo_nivel.config(text=recado)
        self._escrever_linha()
        self.desenhar_faixa()

    def guardar_nivel(self):
        """Guarda os campos de cima no nível escolhido, na memória."""
        if self.env is None:
            messagebox.showinfo(t("Leia o env.int primeiro"),
                                t("Use Ler do cliente para começar."))
            return
        try:
            nivel = int(self.nivel_env.get())
        except ValueError:
            messagebox.showerror(t("Nível inválido"),
                                 t("O nível tem de ser um número."))
            return
        if not 0 <= nivel < l2env.NIVEIS:
            messagebox.showerror(t("Nível inválido"),
                                 t("O nível vai de 0 a %d.") % (l2env.NIVEIS - 1))
            return

        if self.usar_acima.get():
            self.env[l2env.ACIMA] = dict(self.campos_do_nivel())
            self.log(t("  acima do último nível: %s")
                     % l2env._linha_de_cor(self.env[l2env.ACIMA]))
            self.desenhar_faixa()
            self.atualizar_botoes()
            return

        campos = dict(self.env["cores"].get(nivel) or {})
        campos.update(self.campos_do_nivel())
        self.env["cores"][nivel] = campos
        self._refazer_niveis()
        self.desenhar_faixa()
        self.tabela_env.selection_set(str(nivel))
        self.log(t("  nível %d: %s") % (nivel, l2env._linha_de_cor(campos)))
        self.atualizar_botoes()

    def gerar_env(self):
        """Escreve o env.int novo numa pasta à parte, com prova de volta."""
        if self.env is None:
            return
        mostrar = dict((c, self.campos_env[c].get().strip())
                       for c, _r in l2env.MOSTRAR
                       if self.campos_env[c].get().strip())
        try:
            # Tira primeiro o lixo de versao anterior: sem isto o arquivo novo
            # sairia com o bloco fantasma junto, e o proximo Gerar tambem.
            perdidas = l2env.linhas_fora_da_secao(self.env)
            if perdidas:
                self.env["texto"] = l2env.limpar_fora_da_secao(self.env)
                self.log(t("  %d linhas fora de seção foram tiradas.")
                         % len(perdidas))
            texto = l2env.aplicar(self.env, mostrar=mostrar,
                                  cores=self.env["cores"],
                                  acima=self.env.get(l2env.ACIMA))
            alvo, bateu = l2env.gravar(self.T, self.env, texto,
                                       self.saida() / "env")
        except Exception as erro:                   # noqa: BLE001
            self.log(t("A geração parou: %s") % erro)
            messagebox.showerror(t("A geração parou"), str(erro))
            return

        if not bateu:
            self.env_gerado = None
            self.log(t("A volta não confere: o arquivo cifrado não decifra de "
                       "volta igual. Nada será instalado."))
            messagebox.showerror(
                t("A volta não confere"),
                t("O env.int cifrado não decifra de volta igual ao que eu "
                  "queria gravar.\n\nNada foi instalado. Um env.int "
                  "quebrado deixa o cliente sem iluminação nenhuma."))
            self.atualizar_botoes()
            return

        self.env_gerado = alvo
        self.estado_env.config(text=t("gerado em %s") % alvo.parent)
        self.log(t("  env.int gerado em %s (%s bytes), volta conferida.")
                 % (alvo, "{:,}".format(alvo.stat().st_size)))
        self.atualizar_botoes()

    def instalar_env(self):
        if not self.env_gerado:
            return
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("O env.int vale para TODAS as armas do servidor.\n\nO "
                  "original é guardado em %s na primeira vez, e Restaurar "
                  "original desfaz.\n\nContinuar?") % l2env.PASTA_GUARDA):
            return
        try:
            posto = l2env.instalar(self.env_gerado, self.system(),
                                   aolog=lambda s: self.log("  " + s))
        except Exception as erro:                   # noqa: BLE001
            self.log(t("A instalação parou: %s") % erro)
            messagebox.showerror(t("A instalação parou"), str(erro))
            return
        self.atualizar_botoes()
        messagebox.showinfo(
            t("Instalação terminada"),
            t("%s instalado.\n\nFeche e abra o cliente: o env.int só é lido "
              "no arranque.") % posto.name)

    def restaurar_env(self):
        if not messagebox.askyesno(
                t("Restaurar original"),
                t("O env.int guardado volta para o cliente, desfazendo o que "
                  "foi instalado. Continuar?")):
            return
        voltou = l2env.restaurar(self.system(),
                                 aolog=lambda s: self.log("  " + s))
        self.atualizar_botoes()
        if voltou is None:
            messagebox.showinfo(t("Não havia cópia"),
                                t("Não há env.int guardado para restaurar."))
            return
        self.ler_env()
        messagebox.showinfo(t("Pronto"), t("env.int restaurado."))

    # ---- os cinco ajustes e a regua --------------------------------------
    def _montar_ajustes(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Glow"), padding=8)
        caixa.pack(fill="x", pady=(8, 0))

        esquerda = ttk.Frame(caixa)
        esquerda.pack(side="left", fill="both", expand=True)

        self.aviso_arma = ttk.Label(esquerda, text="", foreground=tema.ATENCAO,
                                    wraplength=520, justify="left",
                                    font=("Segoe UI", 8))
        self.rotulo_arma = ttk.Label(esquerda, text=t("Escolha uma arma na "
                                                      "lista."),
                                     font=("Segoe UI", 10, "bold"),
                                     wraplength=520, justify="left")
        self.rotulo_arma.pack(anchor="w")
        self.aviso_arma.pack(anchor="w")

        topo = ttk.Frame(esquerda)
        topo.pack(fill="x", pady=(6, 0))
        self.moldura = tk.Frame(topo, bg=COR_FUNDO_ICONE,
                                width=LADO_DO_ICONE + 10,
                                height=LADO_DO_ICONE + 10,
                                highlightthickness=1,
                                highlightbackground=tema.BORDA,
                                highlightcolor=tema.BORDA)
        self.moldura.pack(side="left")
        self.moldura.pack_propagate(False)
        self.tela_icone = tk.Label(self.moldura, bg=COR_FUNDO_ICONE,
                                   fg=tema.TEXTO_APAGADO, text="—",
                                   font=("Segoe UI", 8))
        self.tela_icone.pack(expand=True)

        campos = ttk.Frame(topo)
        campos.pack(side="left", fill="x", expand=True, padx=(10, 0))

        ttk.Label(campos, text=t("efeito:")).grid(row=0, column=0, sticky="w")
        self.efeito = tk.StringVar()
        ttk.Entry(campos, textvariable=self.efeito, width=36).grid(
            row=0, column=1, columnspan=4, sticky="ew", padx=(6, 0))

        self.valores = {}
        for i, (chave, rotulo, _menor, _maior) in enumerate(l2glow.CAMPOS):
            ttk.Label(campos, text=t(rotulo) + ":").grid(
                row=1 + i // 3, column=(i % 3) * 2, sticky="w", pady=(6, 0))
            variavel = tk.StringVar(value="0")
            self.valores[chave] = variavel
            entrada = ttk.Entry(campos, textvariable=variavel, width=9)
            entrada.grid(row=1 + i // 3, column=(i % 3) * 2 + 1, sticky="w",
                         padx=(6, 12), pady=(6, 0))
            variavel.trace_add("write", lambda *_a: self.desenhar_regua())

        ajuda.ajuda(campos, grid=True, row=0, column=5, sticky="e",
                    padx=(6, 0), texto=lambda: t(
            "Os cinco números são a posição, o tamanho e a intensidade do "
            "brilho.@@"
            "Nas armas do próprio jogo eles vão de -20 a 4 no comprimento, "
            "0,80 a 1,55 no tamanho e 0,20 a 1,00 na intensidade. Não são "
            "limites -- são a faixa que o jogo usa, para você saber se está "
            "perto ou longe dela.@@"
            "Tamanho e intensidade altos pesam: é partícula desenhada todo "
            "quadro, em toda arma igual a esta que estiver na tela.")
            .replace("@@", chr(10) + chr(10)))

        acao = ttk.Frame(esquerda)
        acao.pack(fill="x", pady=(10, 0))
        self.botao_nova = ttk.Button(acao, text=t("Criar arma nova…"),
                                     command=self.criar_arma)
        self.botao_nova.pack(side="left")
        self.botao_gerar = ttk.Button(acao, text=t("Gerar"), command=self.gerar)
        self.botao_gerar.pack(side="left", padx=(6, 0))
        self.botao_instalar = ttk.Button(acao, text=t("Instalar no cliente"),
                                         command=self.instalar)
        self.botao_instalar.pack(side="left", padx=(6, 0))
        self.botao_restaurar = ttk.Button(acao, text=t("Restaurar originais"),
                                          command=self.restaurar)
        self.botao_restaurar.pack(side="left", padx=(6, 0))

        # A XML fica ao lado de Instalar porque e ai que ela e precisa: quem
        # acabou de mandar a arma para o cliente ainda tem de manda-la para o
        # servidor.
        self.botao_ver_xml = ttk.Button(acao, text=t("Ver a XML"),
                                        command=self.ver_xml_da_marcada)
        self.botao_ver_xml.pack(side="left", padx=(16, 0))
        self.botao_xml_servidor = ttk.Button(
            acao, text=t("Gravar a XML no servidor"),
            command=self.gravar_xml_da_marcada)
        self.botao_xml_servidor.pack(side="left", padx=(6, 0))
        self.estado = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

        direita = ttk.Frame(caixa)
        direita.pack(side="left", fill="y", padx=(14, 0))
        self.regua = tk.Canvas(direita, width=LARGURA_REGUA,
                               height=ALTURA_REGUA, highlightthickness=1,
                               highlightbackground=tema.BORDA,
                               highlightcolor=tema.BORDA,
                               bg=tema.PAINEL)
        self.regua.pack()
        self.botao_3d = ttk.Button(direita, text=t("Ver a arma em 3D"),
                                   command=self.ver_malha, state="disabled")
        self.botao_3d.pack(fill="x", pady=(6, 0))
        ajuda.ajuda(direita, lambda: t(
            "A régua mostra a lâmina deitada, medida da malha desta arma, e "
            "onde o glow cai entre o cabo e a ponta.@@"
            "Ela NÃO desenha o efeito: partícula do Unreal Engine 2 só o motor "
            "do jogo desenha, e nem o umodel abre. Para ver o brilho de "
            "verdade, use o DevMode na aba de NPC.")
            .replace("@@", chr(10) + chr(10)))

    def _montar_rodape(self, pai):
        reg = ttk.LabelFrame(pai, text=t("Andamento"), padding=4)
        reg.pack(fill="both", expand=True, pady=(8, 0))
        self.texto = tk.Text(reg, height=6, wrap="word")
        rol = ttk.Scrollbar(reg, command=self.texto.yview)
        self.texto.configure(yscrollcommand=rol.set)
        rol.pack(side="right", fill="y")
        self.texto.pack(fill="both", expand=True)

    # ---- ajudantes -------------------------------------------------------
    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def _avisar_do_icone(self, recado):
        """
        O ícone veio de outro pacote -- dizer isso, da thread para o registro.

        A leitura do ícone roda fora da thread do Tk, e escrever no widget de
        lá trava a interface de um jeito que só aparece em máquina lenta.
        """
        try:
            self.raiz.after(0, self.log, recado)
        except Exception:                           # noqa: BLE001
            pass

    def system(self):
        return l2conferir.raiz_do_cliente(self.cliente.get().strip()) / "system"

    def trabalho(self):
        pasta = Path(motor.BASE) / "trabalho" / "glow"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def saida(self):
        return Path(motor.BASE) / "glow_gerado"

    def atualizar_botoes(self):
        parado = not self.rodando
        # Cinza so enquanto algo roda; faltando pasta ele diz o que falta.
        self.botao_abrir.config(state="normal" if parado else "disabled")
        pronto = parado and self.itens is not None and self.base is not None
        self.botao_gerar.config(state="normal" if pronto else "disabled")
        self.botao_nova.config(state="normal" if pronto else "disabled")
        self.botao_ver_xml.config(state="normal" if pronto else "disabled")
        self.botao_xml_servidor.config(state="normal" if pronto else "disabled")
        self.botao_usar.config(state="normal" if pronto else "disabled")
        self.botao_3d.config(
            state="normal" if pronto and self.malha_atual else "disabled")
        self.botao_instalar.config(
            state="normal" if parado and self.gravados else "disabled")
        self.botao_restaurar.config(
            state="normal" if parado and (self.system() /
                                          l2item.PASTA_GUARDA).is_dir()
            else "disabled")

        botao = getattr(self, "botao_env_gerar", None)
        if botao is not None:
            botao.config(state="normal" if self.env is not None else "disabled")
            self.botao_env_instalar.config(
                state="normal" if self.env_gerado else "disabled")
            self.botao_env_restaurar.config(
                state="normal" if l2env.tem_guardado(self.system())
                else "disabled")

    def abrir(self):
        if self.rodando:
            return
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas(precisa_servidor=False)
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("lendo…"))
        self.log(t("\n=== abrindo as armas de %s ===") % self.system())
        threading.Thread(target=self._abrir_thread, daemon=True).start()

    def _abrir_thread(self):
        try:
            itens = l2item.Itens(self.T, self.system(), self.trabalho())
            armas = [i for i in itens.listar() if i["grupo"] == "weapon"]
            # O catalogo de efeitos e o mesmo da aba de NPC, e o cache tambem:
            # varrer 787 MB de pacotes uma vez por aba seria cobrar duas vezes
            # do usuario pela mesma resposta.
            efeitos, _recusados = l2npc.catalogar_efeitos(
                self.system(), self.T, self.trabalho() / "fx",
                cache=Path(motor.BASE) / "efeitos.json")
            erro = None
        except Exception as e:                      # noqa: BLE001
            itens, armas, efeitos, erro = None, [], [], e
        self.raiz.after(0, self._fim_abertura, itens, armas, efeitos, erro)

    def _fim_abertura(self, itens, armas, efeitos, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            self.log(t("Não deu para abrir: %s") % erro)
            messagebox.showerror(t("Não deu para abrir"), str(erro))
            self.atualizar_botoes()
            return
        self.itens = itens

        # Cronica sem glow: dizer agora, e nao quando o usuario clicar numa
        # arma e receber um erro de dentro do programa.
        if not l2glow.tem_glow(itens):
            import l2item
            cronica = l2item.rotulo_da_cronica(l2item.cronica_em_uso())
            self.lista = []
            self.preencher()
            self.atualizar_botoes()
            recado = t("%s não tem brilho de arma: as colunas de glow "
                       "chegaram em crônicas posteriores.\n\nAs %d armas do "
                       "cliente foram lidas e aparecem nas outras abas -- "
                       "Itens edita nome, ícone e status delas.") % (
                           cronica, len(armas))
            self.log("\n" + recado)
            messagebox.showinfo(t("Esta crônica não tem glow"), recado)
            return

        self.lista = armas
        self.efeitos = efeitos
        self.resumo_do_glow()
        self.refazer_sugestoes()
        self.refazer_criadas()
        self.farejar_servidor(self.refazer_criadas)
        self.log(t("%d armas, %d efeitos instalados.")
                 % (len(armas), len(efeitos)))
        self.preencher()
        self.filtrar_efeitos()
        self.atualizar_botoes()

    # ---- as listas -------------------------------------------------------
    def preencher(self):
        procurado = self.filtro.get().strip().lower()
        self.mostradas = [a for a in self.lista
                          if not procurado
                          or procurado in a["nome"].lower()
                          or procurado in str(a["id"])]
        self.tabela.delete(*self.tabela.get_children())
        for i, a in enumerate(self.mostradas):
            self.tabela.insert("", "end", iid=str(i),
                               values=(a["id"], a["nome"],
                                       self._glow_curto(a["id"])))
        self.conta.config(text=t("%d de %d") % (len(self.mostradas),
                                                len(self.lista)))

    def resumo_do_glow(self):
        """
        {id: nome curto do efeito} para a coluna da lista.

        Numa passada so pela tabela. Perguntar arma por arma custaria uma
        varredura inteira por linha -- 1.346 vezes 1.346 -- a cada tecla
        digitada no filtro.
        """
        self.resumo = {}
        try:
            tabela = self.itens.tabelas["weapon"]
            coluna_id = tabela.coluna("id")
            coluna_fx = tabela.coluna(l2glow.EFEITO["a"])
        except (KeyError, ValueError):
            return
        for linha in tabela.linhas:
            caminho = linha[coluna_fx].strip()
            if caminho:
                self.resumo[linha[coluna_id]] = caminho.split(".")[-1]

    def _glow_curto(self, ident):
        return self.resumo.get(str(ident), "")

    def refazer_sugestoes(self):
        """
        Os efeitos que o próprio cliente usa, os desta arma na frente.

        Não é lista de compatibilidade -- é lista do que este cliente já
        desenha. Um efeito fora dela pode funcionar; um efeito dela funciona,
        porque o jogo o usa todo dia.
        """
        self.sugeridas = []
        if self.itens is None:
            return
        tipo = ""
        if self.base is not None:
            try:
                tipo = l2glow.tipo_da_arma(self.itens, self.base["linha"])
            except Exception:                       # noqa: BLE001
                tipo = ""
        try:
            self.sugeridas = l2glow.sugerir(self.itens, tipo or None)
        except Exception:                           # noqa: BLE001
            self.sugeridas = []

    def filtrar_efeitos(self):
        procurado = self.filtro_fx.get().strip().lower()
        # Os emissores vêm do catálogo; a sugestão só sabe o caminho. Casar os
        # dois deixa a coluna preenchida nos dois modos.
        por_caminho = dict((e["caminho"], e) for e in self.efeitos)

        if self.so_sugeridos.get():
            fonte = []
            for sugerida in self.sugeridas:
                dele = por_caminho.get(sugerida["caminho"], {})
                usado = sugerida["familia"] or ""
                if sugerida["neste_tipo"]:
                    usado = t("%s, %d nesta arma") % (usado or t("em armas"),
                                                      sugerida["neste_tipo"])
                elif sugerida["tipos"]:
                    usado = "%s%s" % (usado + ", " if usado else "",
                                      ", ".join(sugerida["tipos"][:2]).lower())
                fonte.append({"caminho": sugerida["caminho"],
                              "usado": usado,
                              "emissores": dele.get("emissores") or {},
                              "sugerida": sugerida})
            total = len(self.sugeridas)
        else:
            fonte = [{"caminho": e["caminho"], "usado": "",
                      "emissores": e["emissores"], "sugerida": None}
                     for e in self.efeitos]
            total = len(self.efeitos)

        self.efeitos_mostrados = [e for e in fonte
                                  if not procurado
                                  or procurado in e["caminho"].lower()]
        self.lista_fx.delete(*self.lista_fx.get_children())
        for i, e in enumerate(self.efeitos_mostrados):
            emissores = ", ".join("%s x%d" % (k.replace("Emitter", ""), v)
                                  for k, v in sorted((e["emissores"] or {}).items()))
            self.lista_fx.insert("", "end", iid=str(i),
                                 values=(e["caminho"], e["usado"], emissores))
        self.conta_fx.config(text=t("%d de %d")
                             % (len(self.efeitos_mostrados), total))

    # ---- escolher --------------------------------------------------------
    def ao_escolher(self, _evento=None):
        escolhida = self.tabela.selection()
        if not escolhida:
            return
        arma = self.mostradas[int(escolhida[0])]
        self.base = arma
        self.rotulo_arma.config(text=t("Arma: %s, id %s")
                                % (arma["nome"] or t("sem nome"), arma["id"]))
        # Mexer no glow de uma arma do jogo muda aquela arma para todo mundo
        # que a equipar. Quem quer uma arma com brilho proprio quer id proprio,
        # e o botao ao lado faz isso.
        do_jogo = str(arma["id"]).isdigit() and int(arma["id"]) < l2item.PRIMEIRO_ID_LIVRE
        self.aviso_arma.config(
            text=t("Esta é uma arma do jogo: Gerar muda o brilho dela para "
                   "todo mundo. Para uma arma só sua, use Criar arma nova.")
            if do_jogo else "")
        self.mostrar_icone(arma.get("icone") or "")

        glow = l2glow.ler(self.itens, arma["id"])
        self.efeito.set((glow["a"] or {}).get("efeito") or "")
        for chave in l2glow.NOMES:
            valor = (glow["a"] or {}).get(chave) or ""
            self.valores[chave].set(self._curto(valor))

        self.refazer_sugestoes()
        if self.so_sugeridos.get():
            self.filtrar_efeitos()

        self.malha_atual = self._malha_da_arma(arma)
        self.medida = None
        self.desenhar_regua()
        if self.malha_atual:
            threading.Thread(target=self._medir_thread,
                             args=(self.malha_atual,), daemon=True).start()
        self.atualizar_botoes()

    @staticmethod
    def _curto(valor):
        """`0.80000001` na tabela vira `0.8` na tela; o arquivo continua igual."""
        try:
            return "%g" % float(valor)
        except (TypeError, ValueError):
            return valor or "0"

    def _malha_da_arma(self, arma):
        """
        A malha que o boneco segura -- e nao a que cai no chao.

        Sao colunas diferentes: `wpn_mesh[0]` e a arma na mao, `drop_mesh1` e o
        pacote largado no chao. O glow acompanha a que esta na mao. Nas armas
        deste cliente as duas costumam apontar para o mesmo lugar, mas nas de
        duas pecas nao, e e a da mao que interessa.
        """
        tabela = self.itens.tabelas["weapon"]
        for coluna in ("wpn_mesh[0]", "drop_mesh1", "drop_mesh2"):
            try:
                valor = tabela.campo(arma["linha"], coluna).strip()
            except Exception:                       # noqa: BLE001
                continue
            if valor:
                return valor
        return ""

    def _medir_thread(self, malha):
        """
        Mede a malha fora da thread da tela, e diz em voz alta se nao deu.

        Medir chama o umodel, que pode faltar, falhar ou nao achar o pacote.
        Engolir isso deixaria a regua em branco sem explicacao -- o usuario
        ficaria olhando para "sem medida da malha" sem saber o que fazer.
        """
        motivo = ""
        try:
            medida = l2npc.dados_da_malha(
                self.T, self.cliente.get(), malha, self.trabalho() / "malhas",
                cache=Path(motor.BASE) / "malhas.json")
            if medida is None:
                motivo = t("a malha %s não foi encontrada nos pacotes do "
                           "cliente.") % malha
        except Exception as e:                      # noqa: BLE001
            medida, motivo = None, str(e)
        self.raiz.after(0, self._medida_chegou, malha, medida, motivo)

    def _medida_chegou(self, malha, medida, motivo=""):
        if malha != self.malha_atual:
            return                                  # trocou de arma no meio
        self.medida = medida
        self.medida_falhou = motivo
        if motivo:
            self.log(t("Sem a régua: %s") % motivo)
        self.desenhar_regua()

    def usar_efeito(self):
        marcado = self.lista_fx.selection()
        if not marcado or self.base is None:
            return
        escolhido = self.efeitos_mostrados[int(marcado[0])]
        self.efeito.set(escolhido["caminho"])

        # Uma arma sem glow nao tem numeros. Se o efeito veio da sugestao, os
        # numeros do jogo vem junto -- e o efeito nasce enquadrado, em vez de
        # no cabo e encolhido.
        vazia = all(not self.valores[c].get().strip()
                    or self.valores[c].get().strip() == "0"
                    for c in l2glow.NOMES)
        sugerida = escolhido.get("sugerida")
        if sugerida and sugerida.get("ajustes"):
            for chave, valor in sugerida["ajustes"].items():
                if valor:
                    self.valores[chave].set(self._curto(valor))
            self.log(t("  os cinco números vieram do que o jogo usa neste "
                       "efeito."))
        elif vazia:
            for chave, padrao in (("longitudinal", "0"), ("vertical", "0"),
                                  ("lateral", "0"), ("tamanho", "1"),
                                  ("intensidade", "1")):
                self.valores[chave].set(padrao)
            self.log(t("  tamanho e intensidade começaram em 1 -- zero deixaria "
                       "o efeito invisível."))
        self.desenhar_regua()

    def copiar_de_outra_arma(self):
        """
        Traz o efeito e os cinco números de uma arma que já funciona.

        Acertar os cinco no palpite não dá: o efeito sai do lugar e não há como
        saber por quê. Se uma arma do jogo já tem o glow enquadrado, os números
        dela são a resposta -- e são do MESMO formato, então valem direto.

        A janela é a mesma da aba de NPC, que já lista as armas do cliente com
        ícone e filtro.
        """
        if self.itens is None:
            messagebox.showinfo(t("Abra as tabelas primeiro"),
                                t("Abra as tabelas do cliente para começar."))
            return
        import gui_arma

        # A janela guarda a lista numa gaveta por grupo. A desta aba já está
        # carregada, então entregá-la evita reler as tabelas do cliente.
        if not getattr(self, "itens_do_cliente_weapon", None):
            self.itens_do_cliente_weapon = self.lista

        escolha = gui_arma.EscolherArma(self.raiz, self,
                                        atual=(self.base or {}).get("id", ""))
        arma = escolha.resposta
        if not arma or not str(arma.get("id", "")).isdigit():
            return

        try:
            glow = l2glow.ler(self.itens, arma["id"])
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para ler"), str(erro))
            return

        de_la = glow["a"] or {}
        if not de_la.get("efeito"):
            messagebox.showinfo(
                t("Essa arma não tem glow"),
                t("A %s não tem efeito nenhum, então não há números para "
                  "copiar.") % (arma.get("nome") or arma["id"]))
            return

        self.efeito.set(de_la["efeito"])
        for chave in l2glow.NOMES:
            self.valores[chave].set(self._curto(de_la.get(chave) or "0"))
        self.desenhar_regua()
        self.log(t("\nCopiado da arma %s — %s:") % (arma["id"],
                                                     arma.get("nome") or ""))
        self.log("  " + l2glow.descrever(glow))
        if self.base is not None:
            try:
                daqui = l2glow.tipo_da_arma(self.itens, self.base["linha"])
                de_onde = l2glow.tipo_da_arma(self.itens,
                                              self.itens.por_id("weapon",
                                                                arma["id"]))
            except Exception:                       # noqa: BLE001
                daqui = de_onde = ""
            if daqui and de_onde and daqui != de_onde:
                # A malha de uma adaga nao tem o tamanho da de um arco: os
                # numeros valem, mas o enquadramento pode nao valer.
                self.log(t("  atenção: aquela é %s e esta é %s — os números "
                           "vieram de uma arma de outro tipo.")
                         % (de_onde, daqui))

    def tirar_glow(self):
        self.efeito.set("")
        for chave in l2glow.NOMES:
            self.valores[chave].set("0")
        self.desenhar_regua()

    # ---- o icone ---------------------------------------------------------
    def carregar_icone(self, referencia):
        """
        A imagem do ícone no tamanho em que o jogo a desenha.

        É o que o painel de ícones pede ao dono dele. Mesma função da aba de
        Itens, e pelo mesmo motivo: redimensionar de 32 para 32 passaria a arte
        por um reamostrador à toa e a borraria.
        """
        try:
            arquivo = l2item.extrair_icone(self.T, self.cliente.get(),
                                           referencia,
                                           self.trabalho() / "icones",
                                           dizer=self._avisar_do_icone)
            if not arquivo:
                return None
            bruta = motor.abrir_imagem(arquivo, self.T)
            if bruta.size != (LADO_DO_ICONE, LADO_DO_ICONE):
                bruta = bruta.resize((LADO_DO_ICONE, LADO_DO_ICONE),
                                     Image.LANCZOS)
            return bruta
        except Exception:                           # noqa: BLE001
            return None

    def mostrar_icone(self, referencia):
        if Image is None or not referencia:
            self._desenhar_icone(None)
            return
        if referencia in self.icones:
            self._desenhar_icone(self.icones[referencia])
            return
        threading.Thread(target=self._icone_thread, args=(referencia,),
                         daemon=True).start()

    def _icone_thread(self, referencia):
        try:
            arquivo = l2item.extrair_icone(self.T, self.cliente.get(),
                                           referencia,
                                           self.trabalho() / "icones",
                                           dizer=self._avisar_do_icone)
            imagem = motor.abrir_imagem(arquivo, self.T) if arquivo else None
        except Exception:                           # noqa: BLE001
            imagem = None
        self.raiz.after(0, self._guardar_icone, referencia, imagem)

    def _guardar_icone(self, referencia, imagem):
        foto = ImageTk.PhotoImage(imagem) if imagem is not None else None
        self.icones[referencia] = foto
        if self.base and (self.base.get("icone") or "") == referencia:
            self._desenhar_icone(foto)

    def _desenhar_icone(self, foto):
        if foto is None:
            self.tela_icone.config(image="", text="—")
        else:
            self.tela_icone.config(image=foto, text="")
        self.tela_icone.imagem = foto

    # ---- a regua ---------------------------------------------------------
    def desenhar_regua(self, *_a):
        """
        A lamina deitada, medida da malha, e onde o glow cai nela.

        Sem a medida nao se desenha regua nenhuma: uma escala inventada e pior
        do que escala nenhuma, porque parece informacao.
        """
        tela = self.regua
        tela.delete("all")
        eixo = l2glow.eixo_da_arma(self.medida)
        if eixo is None:
            tela.create_text(LARGURA_REGUA // 2, ALTURA_REGUA // 2,
                             width=LARGURA_REGUA - 20, justify="center",
                             text=(self.medida_falhou
                                   or t("medindo a malha…")),
                             fill=tema.TEXTO_FRACO, font=("Segoe UI", 8))
            return

        nome_eixo, menor, maior = eixo
        margem = 26
        largura = LARGURA_REGUA - margem * 2
        meio = ALTURA_REGUA // 2

        def em_pixels(valor):
            fatia = (valor - menor) / float(maior - menor or 1)
            return margem + max(0.0, min(1.0, fatia)) * largura

        tela.create_text(margem, 12, anchor="w", fill=tema.TEXTO_FRACO,
                         font=("Segoe UI", 8),
                         text=t("%s -- eixo %s, de %.1f a %.1f")
                         % (self.malha_atual.split(".")[-1], nome_eixo.upper(),
                            menor, maior))

        tela.create_line(margem, meio, margem + largura, meio,
                         fill=tema.TEXTO_FRACO, width=3)
        for valor, rotulo in ((menor, t("cabo")), (0.0, "0"),
                              (maior, t("ponta"))):
            if not (menor <= valor <= maior):
                continue
            x = em_pixels(valor)
            tela.create_line(x, meio - 6, x, meio + 6, fill=tema.TEXTO_FRACO)
            tela.create_text(x, meio + 16, text=rotulo, fill=tema.TEXTO_FRACO,
                             font=("Segoe UI", 8))

        if not self.efeito.get().strip():
            tela.create_text(LARGURA_REGUA // 2, ALTURA_REGUA - 12,
                             text=t("sem glow"), fill=tema.TEXTO_FRACO,
                             font=("Segoe UI", 8))
            return

        try:
            ao_longo = float((self.valores["longitudinal"].get() or "0")
                             .replace(",", "."))
            tamanho = float((self.valores["tamanho"].get() or "1")
                            .replace(",", "."))
        except ValueError:
            return                                  # numero pela metade

        x = em_pixels(ao_longo)
        raio = max(3, min(22, 6 * abs(tamanho)))
        cor = tema.ATENCAO
        tela.create_oval(x - raio, meio - raio, x + raio, meio + raio,
                         outline=cor, width=2)
        tela.create_text(x, meio - raio - 8, text="%g" % ao_longo, fill=cor,
                         font=("Segoe UI", 8))
        fora = "" if menor <= ao_longo <= maior else t("  (fora da lâmina)")
        tela.create_text(LARGURA_REGUA // 2, ALTURA_REGUA - 12,
                         text=t("o glow fica aqui%s") % fora, fill=tema.TEXTO_FRACO,
                         font=("Segoe UI", 8))

    def ver_malha(self):
        if not self.malha_atual:
            return
        try:
            pacote = l2npc.abrir_visualizador(self.T, self.cliente.get(),
                                              self.malha_atual)
        except Exception as e:                      # noqa: BLE001
            messagebox.showerror(t("Não deu"), str(e))
            return
        self.log(t("\nAbrindo a malha %s (%s) no visualizador do umodel.")
                 % (self.malha_atual, Path(pacote).name))
        self.log(t("  o glow NÃO aparece ali: partícula só o jogo desenha."))

    # ---- criar uma arma nova ---------------------------------------------
    def criar_arma(self):
        """
        Copia a arma escolhida para um id novo, já com este glow.

        A cópia é a mesma da aba de Itens -- `Itens.clonar`, o nome no
        `itemname-e`, o XML por `l2item.xml_servidor`. Dano, status e skills
        continuam sendo assunto daquela aba: duplicá-los aqui seria manter a
        mesma coisa em dois lugares.
        """
        if self.rodando or self.itens is None or self.base is None:
            return
        janela = NovaArma(self)
        if janela.resposta is None:
            return
        self._criar(janela.resposta)

    def _criar(self, dados):
        glow = self.glow_da_tela()
        if glow is None:
            return

        trocas = {}
        if dados["icone"] and dados["icone"] != (self.base.get("icone") or ""):
            trocas["icon[0]"] = dados["icone"]

        try:
            self.itens.clonar("weapon", self.base["id"], dados["id"],
                              nome=dados["nome"], descricao=dados["descricao"],
                              destaque=dados.get("destaque"),
                              trocas=trocas, substituir=dados["substituir"])
            l2glow.aplicar(self.itens, dados["id"], glow)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para criar"), str(erro))
            return

        self.icone_pendente = dados.get("pendente")
        self.log(t("\n=== arma %s — %s, cópia da %s ===")
                 % (dados["id"], dados["nome"] or t("sem nome"),
                    self.base["id"]))
        self.log(t("  glow: %s") % l2glow.descrever(glow))

        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("gravando…"))
        threading.Thread(target=self._criar_thread, args=(dados,),
                         daemon=True).start()

    def _criar_thread(self, dados):
        def anotar(texto):
            self.raiz.after(0, self.log, "  " + texto)

        try:
            gravados = self.itens.gravar(self.saida(), aolog=anotar)
            xml = self._xml_da_arma(dados)
            erro = None
        except Exception as e:                      # noqa: BLE001
            gravados, xml, erro = [], None, e
        self.raiz.after(0, self._fim_criacao, dados, gravados, xml, erro)

    def _xml_da_arma(self, dados):
        """
        O XML do servidor, ao lado das tabelas. Devolve o caminho.

        Marcada a caixa, ele é copiado direto para a pasta de itens do
        servidor. Falhar ali não derruba a criação: a arma foi criada, o que
        não deu foi a entrega, e isso se diz e se refaz pelo botão da outra
        página.
        """
        linha = self.itens.por_id("weapon", dados["id"])
        campos = l2item.campos_do_servidor(self.itens, "weapon", linha)
        texto = l2item.xml_servidor(dados["id"], dados["nome"], "weapon",
                                    self.base["id"], campos=campos,
                                    tipo=campos.get("tipo"))
        alvo = self.saida() / ("%s-item.xml" % dados["id"])
        alvo.write_text(texto, encoding="utf-8")

        if self.gravar_no_servidor.get():
            pasta = self.pasta_de_itens_do_servidor()
            if pasta is None:
                self.raiz.after(0, self.log, t(
                    "  não descobri onde os itens moram no servidor; a XML "
                    "ficou só na pasta de saída."))
            else:
                try:
                    pasta.mkdir(parents=True, exist_ok=True)
                    no_servidor = pasta / alvo.name
                    no_servidor.write_text(texto, encoding="utf-8")
                    self.raiz.after(0, self.log,
                                    t("  XML gravada em %s") % no_servidor)
                except OSError as erro:
                    self.raiz.after(0, self.log, t(
                        "  não consegui gravar na pasta do servidor: %s")
                        % erro)
        return alvo

    def _fim_criacao(self, dados, gravados, xml, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            # A arma ja estava na memoria quando a gravacao falhou. Deixa-la
            # la faria a proxima tentativa esbarrar num "id ja existe" que o
            # usuario nao criou.
            try:
                self.itens.remover(dados["id"])
            except Exception:                       # noqa: BLE001
                pass
            self.log(t("A criação parou: %s") % erro)
            messagebox.showerror(t("A criação parou"), str(erro))
            self.atualizar_botoes()
            return

        self.gravados = gravados
        self.lista = [i for i in self.itens.listar() if i["grupo"] == "weapon"]
        self.resumo_do_glow()
        self.filtro.set(str(dados["id"]))
        self.preencher()
        self.refazer_criadas()
        self.estado.config(text=t("gerado em %s") % self.saida())
        self.atualizar_botoes()
        messagebox.showinfo(
            t("Arma criada"),
            t("A arma %s foi gerada em:\n\n%s\n\nO XML do servidor saiu "
              "junto, em %s.\n\nNada foi alterado no cliente ainda — use "
              "Instalar no cliente.\n\nDano, status e skills ficam na aba "
              "Itens, na janela Novo item.")
            % (dados["id"], self.saida(), xml.name if xml else "—"))

    def glow_da_tela(self):
        """O que está nos campos, pronto para gravar. None se algum não vale."""
        glow = {"a": {"efeito": self.efeito.get().strip()}, "b": {}}
        for chave in l2glow.NOMES:
            glow["a"][chave] = self.valores[chave].get().strip() or "0"
        try:
            l2glow._numero(glow["a"]["tamanho"], "tamanho")
        except l2glow.ErroDeGlow as erro:
            messagebox.showerror(t("Valor inválido"), str(erro))
            return None
        return glow

    # ---- gerar e instalar ------------------------------------------------
    def gerar(self):
        if self.rodando or self.itens is None or self.base is None:
            return
        glow = self.glow_da_tela()
        if glow is None:
            return

        try:
            l2glow.aplicar(self.itens, self.base["id"], glow)
        except l2glow.ErroDeGlow as erro:
            messagebox.showerror(t("Valor inválido"), str(erro))
            return

        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("gravando…"))
        self.log(t("\n=== glow da arma %s: %s ===")
                 % (self.base["id"], l2glow.descrever(glow)))
        threading.Thread(target=self._gerar_thread, daemon=True).start()

    def _gerar_thread(self):
        def anotar(texto):
            self.raiz.after(0, self.log, "  " + texto)

        try:
            gravados = self.itens.gravar(self.saida(), aolog=anotar)
            erro = None
        except Exception as e:                      # noqa: BLE001
            gravados, erro = [], e
        self.raiz.after(0, self._fim_geracao, gravados, erro)

    def _fim_geracao(self, gravados, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            self.log(t("A geração parou: %s") % erro)
            messagebox.showerror(t("A geração parou"), str(erro))
            self.atualizar_botoes()
            return
        self.gravados = gravados
        self.preencher()
        self.estado.config(text=t("gerado em %s") % self.saida())
        self.log(t("  pronto. Nada foi copiado para o cliente ainda."))
        self.atualizar_botoes()

    def instalar(self):
        if self.rodando or not self.gravados:
            return
        system = self.system()
        if not messagebox.askyesno(
                t("Instalar no cliente"),
                t("%d tabelas vão ser copiadas para:\n\n%s\n\nOs originais são "
                  "guardados em %s na primeira vez. Continuar?")
                % (len(self.gravados), system, l2item.PASTA_GUARDA)):
            return
        try:
            postos = l2item.instalar(self.gravados, system,
                                     aolog=lambda s: self.log("  " + s))
            icone = self.instalar_icone_pendente()
        except Exception as e:                      # noqa: BLE001
            self.log(t("A instalação parou: %s") % e)
            messagebox.showerror(t("A instalação parou"), str(e))
            return
        messagebox.showinfo(
            t("Instalação terminada"),
            (t("%d tabelas instaladas, e o pacote de ícone %s.\n\nFeche e "
               "abra o cliente: o weapongrp.dat só é lido no arranque.")
             % (len(postos), icone.name) if icone else
             t("%d tabelas instaladas.\n\nFeche e abra o cliente: o "
               "weapongrp.dat só é lido no arranque.") % len(postos)))
        self.atualizar_botoes()

    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "glow",
                        t("Manual — o brilho da arma")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))

    def instalar_icone_pendente(self):
        """
        Põe no cliente o pacote do ícone próprio, se houver um esperando.

        Depois de posto a marca sai: instalar duas vezes copiaria o mesmo
        arquivo sobre si mesmo.
        """
        pendente = getattr(self, "icone_pendente", None)
        if not pendente or not Path(pendente).is_file():
            return None
        import l2icone

        posto = l2icone.instalar(pendente, self.cliente.get(),
                                 aolog=lambda s: self.log("  " + s))
        self.icone_pendente = None
        return Path(posto) if posto else Path(pendente)

    def restaurar(self):
        system = self.system()
        if not messagebox.askyesno(
                t("Restaurar originais"),
                t("As tabelas guardadas em %s voltam para o cliente, "
                  "desfazendo o que foi instalado. Continuar?")
                % l2item.PASTA_GUARDA):
            return
        voltaram = l2item.restaurar(system,
                                    aolog=lambda s: self.log("  " + s))
        messagebox.showinfo(t("Pronto"),
                            t("%d tabelas restauradas.") % len(voltaram))


class NovaArma(tk.Toplevel):
    """
    Pergunta o que é preciso para copiar a arma sob um id novo.

    Irmã da janela Novo item, mas mais curta de propósito: aqui só se pergunta
    quem a arma é. Dano, status e skills ficam na aba de Itens, onde já existe
    a janela de quatro páginas para isso -- ter dois lugares que fazem a mesma
    coisa é ter dois lugares para consertar quando ela mudar.
    """

    def __init__(self, dono):
        tk.Toplevel.__init__(self, dono.raiz)
        self.dono = dono
        self.resposta = None
        base = dono.base

        self.title(t("Nova arma"))
        self.transient(dono.raiz)
        ajuda.por_icone(self)

        quadro = ttk.Frame(self, padding=12)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, font=("Segoe UI", 10, "bold"),
                  text=t("Copiando a arma %s — %s")
                  % (base["id"], base["nome"] or t("sem nome"))).pack(
            anchor="w")
        ttk.Label(quadro, foreground=COR_TEXTO_FRACO, wraplength=700,
                  justify="left",
                  text=t("A cópia leva a linha inteira: malha, textura, som e "
                         "os números do cliente vêm da base. O glow que está "
                         "na tela entra na cópia, e a arma original não é "
                         "tocada.")).pack(anchor="w", pady=(2, 10))

        corpo = ttk.Frame(quadro)
        corpo.pack(fill="both", expand=True)

        campos = ttk.Frame(corpo)
        campos.pack(side="left", fill="y")

        ttk.Label(campos, text=t("id:")).grid(row=0, column=0, sticky="w")
        self.ident = tk.StringVar(value=str(dono.itens.proximo_id_livre()))
        ttk.Entry(campos, textvariable=self.ident, width=12).grid(
            row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Button(campos, text=t("Sugerir"), command=self.sugerir).grid(
            row=0, column=2, sticky="w", padx=(6, 0))

        ttk.Label(campos, text=t("nome:")).grid(row=1, column=0, sticky="w",
                                                pady=(6, 0))
        self.nome = tk.StringVar(value=base["nome"])
        ttk.Entry(campos, textvariable=self.nome, width=32).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(campos, text=t("destaque:")).grid(row=2, column=0,
                                                    sticky="w", pady=(6, 0))
        # O destaque da base ja vem preenchido: a copia herda a linha inteira
        # do item original, e esta e a palavra que o jogo mostra ao lado do
        # nome. Apagar o campo tira a palavra da copia, sem tocar no original.
        self.destaque = tk.StringVar(value=base.get("destaque", ""))
        # Onde a cronica nao tem a coluna `add_name` -- C1 e C2 -- o campo
        # nasce desligado: escrever nele seria escrever para lugar nenhum.
        tem_destaque = True
        try:
            tem_destaque = dono.itens.tem_destaque() if dono.itens else True
        except Exception:                           # noqa: BLE001
            tem_destaque = True
        ttk.Entry(campos, textvariable=self.destaque, width=32,
                  state="normal" if tem_destaque else "disabled").grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        ttk.Label(campos, text=t("descrição:")).grid(row=3, column=0,
                                                     sticky="w", pady=(6, 0))
        self.descricao = tk.StringVar(value=base.get("descricao", ""))
        ttk.Entry(campos, textvariable=self.descricao).grid(
            row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0),
            pady=(6, 0))

        self.substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(campos, variable=self.substituir,
                        text=t("substituir se o id já existir")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        canto = ttk.Frame(campos)
        canto.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ajuda.ajuda(canto, lambda: t(
            "O id é o que amarra o cliente ao servidor. Use um acima de "
            "%d, longe da faixa do jogo original.@@"
            "Depois de criar, o XML do servidor sai junto das tabelas -- mas "
            "ele vem só com o que dá para ler do cliente. Dano, status e "
            "skills se preenchem na aba Itens, marcando a arma nova na lista.")
            .replace("@@", chr(10) + chr(10)) % l2item.PRIMEIRO_ID_LIVRE)

        direita = ttk.LabelFrame(corpo, text=t("Ícone"), padding=6)
        direita.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.icone = gui_icone.PainelDeIcone(
            direita, dono,
            sorted({i["icone"] for i in dono.lista if i.get("icone")}),
            atual=base.get("icone") or "", saida=dono.saida())
        self.icone.pack(fill="both", expand=True)

        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(14, 0))
        ttk.Button(rodape, text=t("Cancelar"),
                   command=self.destroy).pack(side="right")
        ttk.Button(rodape, text=t("Criar"), command=self.criar).pack(
            side="right", padx=(0, 6))

        self.bind("<Escape>", lambda _e: self.destroy())
        ajuda.centralizar(self)
        self.grab_set()
        self.focus_set()
        self._fixar_tamanho()
        dono.raiz.wait_window(self)

    def _fixar_tamanho(self):
        """
        Trava o tamanho depois de medido.

        A grade de ícones muda de altura conforme o filtro, e a janela seguia
        essa medida: filtrar fazia a janela crescer e encolher na frente de
        quem estava escolhendo.
        """
        try:
            self.update_idletasks()
            self.geometry("%dx%d" % (max(self.winfo_reqwidth(), 760),
                                     max(self.winfo_reqheight(), 480)))
            self.minsize(700, 440)
        except tk.TclError:
            pass

    def sugerir(self):
        self.ident.set(str(self.dono.itens.proximo_id_livre()))

    def criar(self):
        texto = self.ident.get().strip()
        if not texto.isdigit() or int(texto) <= 0:
            messagebox.showerror(t("id inválido"),
                                 t("O id tem de ser um número maior que "
                                   "zero."), parent=self)
            return
        ident = int(texto)
        # A lista da aba ja tem as armas do cliente, mas o id pode existir
        # noutro grupo -- uma armadura, um item comum. `onde_esta` olha os tres.
        ja_em = self.dono.itens.onde_esta(texto)
        if ja_em and not self.substituir.get():
            messagebox.showerror(
                t("Esse id já existe"),
                t("O id %s já está no cliente, em %s.\n\nEscolha outro, ou "
                  "marque \"substituir se o id já existir\".")
                % (texto, ja_em), parent=self)
            return
        if ident < l2item.PRIMEIRO_ID_LIVRE and not messagebox.askyesno(
                t("Id baixo"),
                t("O %d está na faixa do jogo. Os ids a partir de %d ficam "
                  "longe dela.\n\nUsar o %d assim mesmo?")
                % (ident, l2item.PRIMEIRO_ID_LIVRE, ident), parent=self):
            return

        self.resposta = {"id": texto,
                         "nome": self.nome.get().strip(),
                         "destaque": self.destaque.get().strip(),
                         "descricao": self.descricao.get().strip(),
                         "icone": self.icone.referencia,
                         "substituir": self.substituir.get(),
                         "pendente": self.icone.pendente}
        self.destroy()
