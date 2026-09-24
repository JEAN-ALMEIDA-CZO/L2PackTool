#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A aba de Mob: o status, as skills e a lista de drop de um NPC do servidor.

Sao as tres coisas que se mexe num mob e que, no XML, ficam a mil linhas uma da
outra dentro de um arquivo com mil NPCs. Editar aquilo no bloco de notas e
onde nasce a maioria dos "o servidor nao sobe": um `<ai>` sem `seedable`, um
drop de item que nao existe, uma chance escrita como `5` querendo dizer 5%
quando `5` e 0,0005%.

## O que esta tela protege

- **A chance e por milhao.** `DropData.MAX_CHANCE` e 1.000.000, entao 7,9637%
  se escreve `79637`. Aqui os dois aparecem lado a lado, e mexer num muda o
  outro.
- **A skill 4416 nao e uma skill.** O core le o `level` dela como a RACA do mob
  e sai fora sem registrar golpe nenhum. Ela aparece num campo proprio, e nao
  na lista de golpes, para ninguem apagar a raca achando que tirou um ataque.
- **Drop de item que o cliente nao tem** e descartado pelo core com um aviso no
  log. A conferencia acha isso antes de ir para o jogo.
- **O que esta tela nao edita, ela nao toca.** `<petdata>` com a tabela de
  niveis do pet e `<teachTo>` voltam byte a byte -- e a tela diz que eles estao
  la, para ninguem desconfiar que sumiram.

O trabalho de ler e gravar e do `l2mob`, que faz cirurgia no texto em vez de
reescrever o arquivo: editar um mob nao mexe nos outros mil.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import ajuda
import gui_arma
import gui_projeto
import l2conferir
import l2item
import l2mob
import l2skill
import l2servidor
import motor
from idioma import t, N_

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

import tema

COR_TEXTO_FRACO = tema.TEXTO_FRACO
COR_FUNDO_ICONE = tema.COR_FUNDO_ICONE
COR_ALERTA = tema.ATENCAO
LADO_DO_ICONE = 32
TODOS = N_("todos")

# Os grupos do cliente que o seletor de item mostra num drop: qualquer coisa
# pode cair de um mob.
GRUPOS_DE_ITEM = ("weapon", "armor", "etc")


class JanelaMob:
    def __init__(self, raiz, pai):
        self.raiz = raiz
        self.rodando = False
        self.T = motor.carregar_config()
        self.lista = []                 # os mobs do servidor, leves
        self.mostrados = []
        self.mob = None                 # o mob aberto agora
        self.nomes = {}                 # {id do item: nome}
        self.descricoes = {}
        self.icones = {}
        self.icones_de_item = {}
        self.campos = {}                # {nome do set: StringVar}
        self.campos_ai = {}

        try:
            estilo = ttk.Style()
            estilo.configure("Mob.Treeview", rowheight=36)
        except tk.TclError:
            pass

        quadro = ttk.Frame(pai, padding=10)
        self.quadro = quadro    # a ancora dos `after` desta aba
        quadro.bind("<Destroy>", self._ao_morrer)
        quadro.pack(fill="both", expand=True)

        ttk.Label(quadro, justify="left", wraplength=980,
                  foreground=COR_TEXTO_FRACO,
                  text=t("O status, as skills e a lista de drop de um mob do "
                         "servidor. Abra as pastas, escolha o mob na lista e "
                         "edite; só o mob editado é reescrito no "
                         "arquivo.")).pack(anchor="w")

        self._montar_pastas(quadro)

        painel = ttk.Panedwindow(quadro, orient="horizontal")
        painel.pack(fill="both", expand=True, pady=(8, 0))
        painel.add(self._montar_lista(painel), weight=1)
        painel.add(self._montar_edicao(painel), weight=3)

        self._montar_rodape(quadro)
        self.atualizar_botoes()

    # =====================================================================
    # as pastas
    # =====================================================================
    def _montar_pastas(self, pai):
        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(10, 0))
        self.servidor = tk.StringVar(
            value=motor.ler_opcao("servidor", "pasta", "") or "")
        self.botao_abrir = ttk.Button(linha, text=t("Carregar"),
                                      style="Primario.TButton",
                                      command=self.carregar_tudo)
        self.botao_abrir.pack(side="left")
        ttk.Button(linha, text=t("Manual"),
                   command=self.abrir_manual).pack(side="left", padx=(6, 0))
        ajuda.ajuda(linha, lambda: t(
            "Carrega tudo o que esta aba usa: os mobs do servidor e as "
            "tabelas do cliente.@@"
            "Os mobs moram em `data/xml/npcs`, e o core lê essa pasta mais as "
            "subpastas raidboss, grandboss, farmzone, custom e events — nessa "
            "ordem; id repetido faz valer o último a carregar. Do cliente vêm "
            "o nome e o desenho de cada item do drop e de cada skill."))

        linha = ttk.Frame(pai)
        linha.pack(fill="x", pady=(6, 0))
        self.cliente = tk.StringVar(
            value=str(l2conferir.raiz_do_cliente(
                motor.ler_opcao("cliente", "system", "") or "")))


    def abrir_manual(self):
        import manual

        if manual.abrir(self.raiz, "mob", t("Manual — mob")) is None:
            messagebox.showinfo(
                t("Manual não encontrado"),
                t("O texto do manual não veio junto com o programa."))

    # =====================================================================
    # a lista de mobs
    # =====================================================================
    def _montar_lista(self, pai):
        caixa = ttk.LabelFrame(pai, text=t("Os mobs do servidor"), padding=6)

        linha = ttk.Frame(caixa)
        linha.pack(fill="x")
        ttk.Label(linha, text=t("Procurar:")).pack(side="left")
        self.procura = tk.StringVar()
        campo = ttk.Entry(linha, textvariable=self.procura, width=16)
        campo.pack(side="left", padx=(6, 0))
        campo.bind("<KeyRelease>", lambda _e: self._filtrar_daqui_a_pouco())
        self.conta = ttk.Label(linha, text="", foreground=COR_TEXTO_FRACO)
        self.conta.pack(side="right")

        linha = ttk.Frame(caixa)
        linha.pack(fill="x", pady=(4, 0))
        ttk.Label(linha, text=t("Tipo:")).pack(side="left")
        self.tipo = tk.StringVar(value=t(TODOS))
        self.caixa_tipo = ttk.Combobox(linha, textvariable=self.tipo, width=13,
                                       state="readonly", values=(t(TODOS),))
        self.caixa_tipo.pack(side="left", padx=(6, 0))
        self.caixa_tipo.bind("<<ComboboxSelected>>", lambda _e: self.preencher())
        ttk.Label(linha, text=t("nível")).pack(side="left", padx=(8, 0))
        self.nivel_de = tk.StringVar()
        self.nivel_ate = tk.StringVar()
        for variavel in (self.nivel_de, self.nivel_ate):
            c = ttk.Entry(linha, textvariable=variavel, width=5)
            c.pack(side="left", padx=(4, 0))
            c.bind("<KeyRelease>", lambda _e: self._filtrar_daqui_a_pouco())
            if variavel is self.nivel_de:
                ttk.Label(linha, text=t("a")).pack(side="left", padx=(2, 0))
        ttk.Button(linha, text=t("Limpar"),
                   command=self.limpar_filtros).pack(side="left", padx=(8, 0))

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("nome"), N_("nv"), N_("tipo"),
                   N_("drops"), N_("skills"))
        self.tabela = ttk.Treeview(dentro, columns=colunas, show="headings",
                                   height=20, selectmode="browse")
        for nome, largura, alinhamento in zip(
                colunas, (56, 150, 34, 90, 44, 44),
                ("e", "w", "e", "w", "e", "e")):
            self.tabela.heading(nome, text=t(nome))
            self.tabela.column(nome, width=largura, anchor=alinhamento,
                               stretch=(nome == "nome"))
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.tabela.yview)
        self.tabela.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.tabela.pack(side="left", fill="both", expand=True)
        self.tabela.bind("<<TreeviewSelect>>", lambda _e: self.abrir_o_marcado())
        return caixa

    def _filtrar_daqui_a_pouco(self):
        """
        Espera a digitação parar antes de refazer a lista.

        São 6.532 mobs; refazer a tabela a cada tecla faz a digitação engasgar.
        """
        marcado = getattr(self, "_marcado", None)
        if marcado is not None:
            try:
                self.quadro.after_cancel(marcado)
            except tk.TclError:
                pass
        self._marcado = self.quadro.after(220, self.preencher)

    def limpar_filtros(self):
        self.procura.set("")
        self.tipo.set(t(TODOS))
        self.nivel_de.set("")
        self.nivel_ate.set("")
        self.preencher()

    def preencher(self):
        procurado = self.procura.get().strip().lower()
        tipo = self.tipo.get()
        tipo = None if not tipo or tipo == t(TODOS) else tipo

        def numero(variavel):
            try:
                return int(variavel.get().strip())
            except ValueError:
                return None
        de, ate = numero(self.nivel_de), numero(self.nivel_ate)

        self.mostrados = []
        for m in self.lista:
            if procurado and (procurado not in m["nome"].lower()
                              and procurado not in m["id"]):
                continue
            if tipo and m["tipo"] != tipo:
                continue
            if de is not None or ate is not None:
                try:
                    nivel = int(m["nivel"])
                except (TypeError, ValueError):
                    continue
                if de is not None and nivel < de:
                    continue
                if ate is not None and nivel > ate:
                    continue
            self.mostrados.append(m)

        self.tabela.delete(*self.tabela.get_children())
        for i, m in enumerate(self.mostrados[:4000]):
            self.tabela.insert("", "end", iid=str(i),
                               values=(m["id"], m["nome"] or t("sem nome"),
                                       m["nivel"], m["tipo"],
                                       m["drops"] or "", m["skills"] or ""))
        sobra = len(self.mostrados) - 4000
        self.conta.config(
            text=(t("%d de %d  (mostrando 4.000)") % (len(self.mostrados),
                                                      len(self.lista))
                  if sobra > 0 else
                  t("%d de %d") % (len(self.mostrados), len(self.lista))))

    # =====================================================================
    # a edição
    # =====================================================================
    def _montar_edicao(self, pai):
        caixa = ttk.Frame(pai, padding=(10, 0, 0, 0))

        cabeca = ttk.Frame(caixa)
        cabeca.pack(fill="x")
        self.titulo = ttk.Label(cabeca, text=t("Nenhum mob aberto."),
                                font=("Segoe UI", 10, "bold"))
        self.titulo.pack(side="left")
        self.preservados = ttk.Label(cabeca, text="",
                                     foreground=COR_TEXTO_FRACO)
        self.preservados.pack(side="right")

        self.abas = ttk.Notebook(caixa)
        self.abas.pack(fill="both", expand=True, pady=(6, 0))
        self.abas.add(self._montar_status(self.abas), text=t("  Status  "))
        self.abas.add(self._montar_skills(self.abas), text=t("  Skills  "))
        self.abas.add(self._montar_drops(self.abas), text=t("  Drop  "))
        self.abas.add(self._montar_minions(self.abas), text=t("  Minions  "))
        return caixa

    # ---- status ---------------------------------------------------------
    def _montar_status(self, pai):
        import rolagem

        area = rolagem.Area(pai)
        dentro = ttk.Frame(area.dentro, padding=8)
        dentro.pack(fill="both", expand=True)

        nome_e_titulo = ttk.LabelFrame(dentro, text=t("Identidade"), padding=6)
        nome_e_titulo.pack(fill="x")
        self.campo_nome = tk.StringVar()
        self.campo_titulo = tk.StringVar()
        for coluna, (rotulo, variavel) in enumerate(
                ((t("nome"), self.campo_nome), (t("título"), self.campo_titulo))):
            ttk.Label(nome_e_titulo, text=rotulo).grid(
                row=0, column=coluna * 2, sticky="w", padx=(0 if not coluna else 12, 4))
            campo = ttk.Entry(nome_e_titulo, textvariable=variavel, width=26)
            campo.grid(row=0, column=coluna * 2 + 1, sticky="w")
            variavel.trace_add("write", lambda *_a: self._mexeu("atributos"))
        ajuda.ajuda(nome_e_titulo, lambda: t(
            "O core lê `name` e `title` sem conferir se existem.@@"
            "Deixar o nome vazio não é o mesmo que não ter nome: o atributo "
            "continua no XML, vazio, que é o que o pack faz nos mobs sem "
            "título."), grid=True, row=0, column=4, padx=(12, 0))

        self.quadro_status = ttk.LabelFrame(dentro, text=t("Status"), padding=6)
        self.quadro_status.pack(fill="x", pady=(8, 0))

        self.quadro_ai = ttk.LabelFrame(dentro, text=t("IA"), padding=6)
        self.quadro_ai.pack(fill="x", pady=(8, 0))
        return area

    def _encher_status(self):
        for quadro in (self.quadro_status, self.quadro_ai):
            for filho in quadro.winfo_children():
                filho.destroy()
        self.campos, self.campos_ai = {}, {}
        if not self.mob:
            return

        # A ordem da tela e a do `l2mob.STATUS`; o que o mob tiver alem disso
        # entra no fim, para nao sumir de vista nem mudar de lugar no arquivo.
        conhecidos = dict(l2mob.STATUS)
        tinha = dict(self.mob["sets"])
        ordem = [c for c, _ in l2mob.STATUS if c in tinha]
        ordem += [c for c, _ in self.mob["sets"] if c not in conhecidos]

        for posicao, chave in enumerate(ordem):
            linha, coluna = divmod(posicao, 4)
            ttk.Label(self.quadro_status,
                      text=t(conhecidos.get(chave, chave))).grid(
                row=linha, column=coluna * 2, sticky="e", padx=(0, 4), pady=2)
            variavel = tk.StringVar(value=tinha.get(chave, ""))
            if chave == "type":
                campo = ttk.Combobox(self.quadro_status, width=14,
                                     textvariable=variavel,
                                     values=l2mob.TIPOS_DE_NPC)
            else:
                campo = ttk.Entry(self.quadro_status, textvariable=variavel,
                                  width=12)
            campo.grid(row=linha, column=coluna * 2 + 1, sticky="w",
                       padx=(0, 12), pady=2)
            variavel.trace_add("write", lambda *_a: self._mexeu("sets"))
            self.campos[chave] = variavel

        ai = self.mob.get("ai") or {}
        if not ai:
            ttk.Label(self.quadro_ai, foreground=COR_TEXTO_FRACO,
                      text=t("Este mob não tem bloco <ai>.")).grid(
                row=0, column=0, sticky="w")
            return
        chaves = list(l2mob.AI_OBRIGATORIOS)
        chaves += [c for c in ai if c not in chaves]
        for posicao, chave in enumerate(chaves):
            linha, coluna = divmod(posicao, 4)
            ttk.Label(self.quadro_ai, text=chave).grid(
                row=linha, column=coluna * 2, sticky="e", padx=(0, 4), pady=2)
            variavel = tk.StringVar(value=ai.get(chave, ""))
            if chave == "type":
                campo = ttk.Combobox(self.quadro_ai, width=12,
                                     textvariable=variavel,
                                     values=l2mob.TIPOS_DE_AI)
            else:
                campo = ttk.Entry(self.quadro_ai, textvariable=variavel,
                                  width=10)
            campo.grid(row=linha, column=coluna * 2 + 1, sticky="w",
                       padx=(0, 12), pady=2)
            variavel.trace_add("write", lambda *_a: self._mexeu("ai"))
            self.campos_ai[chave] = variavel

    # ---- skills ---------------------------------------------------------
    def _montar_skills(self, pai):
        caixa = ttk.Frame(pai, padding=8)

        raca = ttk.LabelFrame(caixa, text=t("Raça"), padding=6)
        raca.pack(fill="x")
        self.raca = tk.StringVar()
        self.caixa_raca = ttk.Combobox(
            raca, textvariable=self.raca, width=24, state="readonly",
            values=[""] + ["%s — %s" % (k, v)
                           for k, v in sorted(l2mob.RACAS.items(),
                                              key=lambda p: int(p[0]))])
        self.caixa_raca.pack(side="left")
        self.caixa_raca.bind("<<ComboboxSelected>>",
                             lambda _e: self._mexeu("skills"))
        ajuda.ajuda(raca, lambda: t(
            "A raça é escrita como se fosse a skill 4416, mas não é uma "
            "skill.@@"
            "O core lê o `level` daquela linha como a raça do mob e sai fora "
            "sem registrar golpe nenhum. Por isso ela fica aqui, e não na "
            "lista abaixo: na lista, alguém apagaria a raça achando que "
            "estava tirando um ataque."))

        lista = ttk.LabelFrame(caixa, text=t("Os golpes"), padding=6)
        lista.pack(fill="both", expand=True, pady=(8, 0))
        colunas = (N_("id"), N_("nível"))
        self.lista_skills = ttk.Treeview(lista, columns=colunas,
                                         show="tree headings", height=12,
                                         selectmode="browse",
                                         style="Mob.Treeview")
        self.lista_skills.heading("#0", text=t("skill"))
        self.lista_skills.column("#0", width=260, minwidth=150, stretch=True)
        for nome, largura in zip(colunas, (80, 70)):
            self.lista_skills.heading(nome, text=t(nome))
            self.lista_skills.column(nome, width=largura, anchor="e",
                                     stretch=False)
        self.lista_skills.pack(fill="both", expand=True)
        self.lista_skills.bind("<Double-1>", lambda _e: self.mudar_skill())
        # A descrição é longa demais para uma coluna e curta demais para uma
        # janela: ela sai no ponteiro, na linha sob ele.
        gui_arma.DicaDaLinha(self.lista_skills, self._descricao_da_skill)

        botoes = ttk.Frame(lista)
        botoes.pack(fill="x", pady=(6, 0))
        ttk.Button(botoes, text=t("+ skill"),
                   command=self.por_skill).pack(side="left")
        ttk.Button(botoes, text=t("Sugerir…"),
                   command=self.sugerir_skill).pack(side="left", padx=(4, 0))
        ttk.Button(botoes, text=t("Mudar…"),
                   command=self.mudar_skill).pack(side="left", padx=(4, 0))
        ttk.Button(botoes, text=t("Tirar"),
                   command=self.tirar_skill).pack(side="left", padx=(4, 0))
        ajuda.ajuda(botoes, lambda: t(
            "Sugerir mostra o que os mobs PARECIDOS com este usam.@@"
            "Parecido é do mesmo tipo e de nível próximo, contado no seu "
            "próprio pack — não é lista escrita à mão. O número ao lado de "
            "cada skill é quantos mobs parecidos a usam."))
        return caixa

    # ---- o que o cliente sabe sobre cada skill -------------------------
    def skill_do_cliente(self, ident):
        """O registro daquela skill, ou None se as tabelas não foram abertas."""
        gaveta = getattr(self, "_por_id_de_skill", None)
        if gaveta is None:
            gaveta = self._por_id_de_skill = {}
            for s in getattr(self, "skills_do_cliente", []) or []:
                gaveta[str(s["id"])] = s
        return gaveta.get(str(ident))

    def _esquecer_skills_do_cliente(self):
        """A gaveta de busca é refeita quando a lista do cliente muda."""
        self._por_id_de_skill = None

    def _descricao_da_skill(self, linha):
        try:
            golpe = l2mob.golpes_de(self.mob)[int(linha)]
        except (ValueError, IndexError, TypeError):
            return ""
        s = self.skill_do_cliente(golpe.get("id"))
        if s is None:
            return t("A skill %s não está nas tabelas do cliente.\n"
                     "Abra as tabelas para ver o nome e o que ela faz.") \
                % golpe.get("id")
        partes = ["%s   (id %s, nível %s)" % (s["nome"] or t("sem nome"),
                                              s["id"], golpe.get("level", ""))]
        if (s.get("descricao") or "").strip():
            partes.append("")
            partes.append(s["descricao"].strip())
        return "\n".join(partes)

    def icone_da_skill(self, referencia):
        """O desenho da skill, pedido uma vez e guardado."""
        if not referencia or Image is None:
            return ""
        if referencia in self.icones:
            return self.icones[referencia] or ""
        self.icones[referencia] = None
        threading.Thread(target=self._icone_de_skill_thread,
                         args=(referencia,), daemon=True).start()
        return ""

    def _icone_de_skill_thread(self, referencia):
        imagem = self.carregar_icone(referencia)
        try:
            self.raiz.after(0, self._icone_de_skill_chegou, referencia, imagem)
        except tk.TclError:
            pass

    def _icone_de_skill_chegou(self, referencia, imagem):
        if imagem is None:
            return
        self.icones[referencia] = ImageTk.PhotoImage(imagem)
        self._encher_skills()

    def _encher_skills(self):
        self.lista_skills.delete(*self.lista_skills.get_children())
        if not self.mob:
            self.raca.set("")
            return
        numero = l2mob.raca_de(self.mob)
        self.raca.set("%s — %s" % (numero, l2mob.RACAS[numero])
                      if numero in l2mob.RACAS else numero)
        for i, golpe in enumerate(l2mob.golpes_de(self.mob)):
            do_cliente = self.skill_do_cliente(golpe.get("id"))
            self.lista_skills.insert(
                "", "end", iid=str(i),
                image=(self.icone_da_skill((do_cliente or {}).get("icone") or "")
                       or self.marca_de_espera()),
                text=" " + ((do_cliente or {}).get("nome")
                            or t("(não está no cliente)")),
                values=(golpe.get("id", ""), golpe.get("level", "")))

    def _skill_marcada(self):
        marcada = self.lista_skills.selection()
        return int(marcada[0]) if marcada else None

    def _abrir_seletor(self, atual="", titulo=None, sugeridas=None):
        escolha = gui_arma.EscolherSkill(self.raiz, self, atual=atual,
                                         titulo=titulo, sugeridas=sugeridas)
        # O seletor guarda a lista lida na aba; a gaveta de busca reflete isso.
        self._esquecer_skills_do_cliente()
        return escolha.resposta

    def por_skill(self):
        if not self.mob:
            return
        escolhida = self._abrir_seletor(titulo=t("A skill do mob"))
        if not escolhida:
            self._encher_skills()
            return
        self.mob["skills"].append({"id": escolhida["id"],
                                   "level": escolhida["level"]})
        self._mexeu("skills")
        self._encher_skills()

    def sugerir_skill(self):
        """Abre o seletor já filtrado pelo que os mobs parecidos usam."""
        if not self.mob:
            return
        pasta = l2mob.pasta_de_npcs(self.servidor.get().strip())
        if not pasta.is_dir():
            messagebox.showinfo(
                t("Sem servidor"),
                t("A sugestão sai dos mobs do seu próprio servidor. "
                  "Aponte a pasta dele no projeto, no cabeçalho."))
            return
        self.estado.config(text=t("procurando mobs parecidos…"))
        self.raiz.update_idletasks()
        try:
            sugeridas = l2mob.sugerir_skills(pasta, self.mob)
        except Exception as erro:                   # noqa: BLE001
            self.estado.config(text="")
            messagebox.showerror(t("Não deu para sugerir"), str(erro))
            return
        self.estado.config(text="")
        if not sugeridas:
            messagebox.showinfo(
                t("Nada a sugerir"),
                t("Nenhum mob parecido com este usa uma skill que ele ainda "
                  "não tem."))
            return
        escolhida = self._abrir_seletor(titulo=t("Skills de mobs parecidos"),
                                        sugeridas=sugeridas)
        if not escolhida:
            self._encher_skills()
            return
        self.mob["skills"].append({"id": escolhida["id"],
                                   "level": escolhida["level"]})
        self._mexeu("skills")
        self._encher_skills()

    def mudar_skill(self):
        indice = self._skill_marcada()
        if indice is None or not self.mob:
            return
        atual = l2mob.golpes_de(self.mob)[indice]
        escolhida = self._abrir_seletor(atual=atual.get("id", ""),
                                        titulo=t("Mudar a skill"))
        if not escolhida:
            self._encher_skills()
            return
        atual["id"], atual["level"] = escolhida["id"], escolhida["level"]
        self._mexeu("skills")
        self._encher_skills()

    def tirar_skill(self):
        indice = self._skill_marcada()
        if indice is None or not self.mob:
            return
        alvo = l2mob.golpes_de(self.mob)[indice]
        self.mob["skills"] = [s for s in self.mob["skills"] if s is not alvo]
        self._mexeu("skills")
        self._encher_skills()

    # ---- drops ----------------------------------------------------------
    def _montar_drops(self, pai):
        caixa = ttk.Frame(pai, padding=8)

        recado = ttk.Label(
            caixa, foreground=COR_TEXTO_FRACO, justify="left", wraplength=620,
            text=t("A chance vai de 1 a 1.000.000, onde 1.000.000 é 100%. "
                   "Categoria -1 é spoil; de 0 para cima são grupos de drop "
                   "comum, e o core sorteia um item por grupo."))
        recado.pack(anchor="w")

        dentro = ttk.Frame(caixa)
        dentro.pack(fill="both", expand=True, pady=(6, 0))
        colunas = (N_("id"), N_("min"), N_("max"), N_("chance"), N_("%"))
        self.lista_drops = ttk.Treeview(dentro, columns=colunas,
                                        show="tree headings", height=12,
                                        selectmode="browse",
                                        style="Mob.Treeview")
        self.lista_drops.heading("#0", text=t("item"))
        self.lista_drops.column("#0", width=250, minwidth=150, stretch=True)
        for nome, largura in zip(colunas, (60, 50, 50, 80, 74)):
            self.lista_drops.heading(nome, text=t(nome))
            self.lista_drops.column(nome, width=largura, anchor="e",
                                    stretch=False)
        barra = ttk.Scrollbar(dentro, orient="vertical",
                              command=self.lista_drops.yview)
        self.lista_drops.config(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.lista_drops.pack(side="left", fill="both", expand=True)
        self.lista_drops.bind("<Double-1>", lambda _e: self.mudar_drop())

        botoes = ttk.Frame(caixa)
        botoes.pack(fill="x", pady=(6, 0))
        ttk.Button(botoes, text=t("+ item"),
                   command=self.por_drop).pack(side="left")
        ttk.Button(botoes, text=t("Mudar…"),
                   command=self.mudar_drop).pack(side="left", padx=(4, 0))
        ttk.Button(botoes, text=t("Tirar"),
                   command=self.tirar_drop).pack(side="left", padx=(4, 0))
        ttk.Button(botoes, text=t("+ categoria"),
                   command=self.por_categoria).pack(side="left", padx=(16, 0))
        return caixa

    def _encher_drops(self):
        self.lista_drops.delete(*self.lista_drops.get_children())
        if not self.mob:
            return
        for c, categoria in enumerate(self.mob["drops"]):
            rotulo = (t("spoil")
                      if str(categoria["id"]) == str(l2mob.CATEGORIA_SPOIL)
                      else t("categoria %s") % categoria["id"])
            pai = self.lista_drops.insert(
                "", "end", iid="c%d" % c, open=True,
                text=" %s  (%d)" % (rotulo, len(categoria["itens"])))
            for i, item in enumerate(categoria["itens"]):
                ident = str(item.get("itemid", ""))
                chance = item.get("chance", "")
                self.lista_drops.insert(
                    pai, "end", iid="c%d.%d" % (c, i),
                    image=self.icone_de(ident) or self.marca_de_espera(),
                    text=" " + (self.nomes.get(ident)
                                or t("(não está no cliente)")),
                    values=(ident, item.get("min", ""), item.get("max", ""),
                            chance,
                            "%.4f%%" % l2mob.porcentagem(chance)))

    def _drop_marcado(self):
        """(categoria, item) do que está marcado, ou (categoria, None)."""
        marcado = self.lista_drops.selection()
        if not marcado:
            return None, None
        partes = marcado[0].lstrip("c").split(".")
        categoria = int(partes[0])
        return categoria, (int(partes[1]) if len(partes) > 1 else None)

    def por_categoria(self):
        if not self.mob:
            return
        valor = PedirUmNumero(self.raiz, t("Nova categoria"),
                              t("número da categoria (-1 é spoil)"), "0")
        if valor.resposta is None:
            return
        self.mob["drops"].append({"id": valor.resposta, "itens": []})
        self._mexeu("drops")
        self._encher_drops()

    def por_drop(self):
        if not self.mob:
            return
        categoria, _item = self._drop_marcado()
        if categoria is None:
            if not self.mob["drops"]:
                self.por_categoria()
                categoria = 0 if self.mob["drops"] else None
            else:
                categoria = 0
        if categoria is None:
            return
        escolha = gui_arma.EscolherArma(
            self.raiz, self, grupos=GRUPOS_DE_ITEM,
            titulo=t("O que o mob dropa"))
        if not escolha.resposta:
            return
        self.mob["drops"][categoria]["itens"].append(
            {"itemid": str(escolha.resposta["id"]), "min": "1", "max": "1",
             "chance": "10000"})
        self._mexeu("drops")
        self._encher_drops()

    def mudar_drop(self):
        categoria, item = self._drop_marcado()
        if categoria is None or item is None or not self.mob:
            return
        alvo = self.mob["drops"][categoria]["itens"][item]
        janela = gui_arma.MudarDrop(
            self.raiz, self.nomes.get(str(alvo.get("itemid", ""))) or "",
            alvo.get("itemid", ""), alvo.get("min", "1"),
            alvo.get("max", "1"), alvo.get("chance", "1"))
        if janela.resposta is None:
            return
        alvo["min"] = janela.resposta["minimo"]
        alvo["max"] = janela.resposta["maximo"]
        alvo["chance"] = janela.resposta["chance"]
        self._mexeu("drops")
        self._encher_drops()

    def tirar_drop(self):
        categoria, item = self._drop_marcado()
        if categoria is None or not self.mob:
            return
        if item is None:
            del self.mob["drops"][categoria]
        else:
            del self.mob["drops"][categoria]["itens"][item]
        self._mexeu("drops")
        self._encher_drops()

    # ---- minions --------------------------------------------------------
    def _montar_minions(self, pai):
        caixa = ttk.Frame(pai, padding=8)
        ttk.Label(caixa, foreground=COR_TEXTO_FRACO, justify="left",
                  wraplength=620,
                  text=t("Os mobs que nascem junto com este. O id é de outro "
                         "NPC; min e max são quantos vêm.")).pack(anchor="w")
        colunas = (N_("id"), N_("min"), N_("max"))
        self.lista_minions = ttk.Treeview(caixa, columns=colunas,
                                          show="headings", height=10,
                                          selectmode="browse")
        for nome, largura in zip(colunas, (90, 60, 60)):
            self.lista_minions.heading(nome, text=t(nome))
            self.lista_minions.column(nome, width=largura, anchor="e")
        self.lista_minions.pack(fill="both", expand=True, pady=(6, 0))

        botoes = ttk.Frame(caixa)
        botoes.pack(fill="x", pady=(6, 0))
        ttk.Button(botoes, text=t("+ minion"),
                   command=self.por_minion).pack(side="left")
        ttk.Button(botoes, text=t("Tirar"),
                   command=self.tirar_minion).pack(side="left", padx=(4, 0))
        return caixa

    def _encher_minions(self):
        self.lista_minions.delete(*self.lista_minions.get_children())
        if not self.mob:
            return
        for i, m in enumerate(self.mob.get("minions") or []):
            self.lista_minions.insert("", "end", iid=str(i),
                                      values=(m.get("id", ""), m.get("min", ""),
                                              m.get("max", "")))

    def por_minion(self):
        if not self.mob:
            return
        valores = PedirDoisNumeros(self.raiz, t("Novo minion"), t("id do NPC"),
                                   "", t("quantos"), "1")
        if valores.resposta is None:
            return
        ident, quantos = valores.resposta
        self.mob.setdefault("minions", []).append(
            {"id": ident, "min": quantos, "max": quantos})
        self._mexeu("minions")
        self._encher_minions()

    def tirar_minion(self):
        marcado = self.lista_minions.selection()
        if not marcado or not self.mob:
            return
        del self.mob["minions"][int(marcado[0])]
        self._mexeu("minions")
        self._encher_minions()

    # =====================================================================
    # o rodapé
    # =====================================================================

    def ver_malha(self):
        """
        Abre a malha deste mob no visualizador do umodel.

        O mob e do servidor e a malha e do cliente -- quem liga os dois e o
        `npcgrp.dat`, pelo id. Sem o cliente apontado nao ha o que abrir, e
        dizer isso e melhor do que abrir uma janela vazia.
        """
        import l2npc

        mob = self._da_tela() or self.mob
        ident = str((mob or {}).get("id") or "").strip()
        if not ident:
            messagebox.showinfo(t("Escolha o mob"),
                                t("Marque um mob na lista primeiro."))
            return

        cliente = self.cliente.get().strip()
        if not cliente:
            messagebox.showinfo(t("Falta o cliente"),
                                t("Aponte a pasta do cliente em Projetos: a "
                                  "malha vem de lá, não do servidor."))
            return

        try:
            grp = l2npc.abrir_npcgrp(self.system(), self.T, self.trabalho())
            malha, texturas = "", []
            for linha in grp.linhas:
                if linha[0] == ident:
                    malha = grp.campo(linha, "mesh")
                    # O cliente aplica estas por cima do material da malha; o
                    # visualizador nao, e a diferenca parece textura faltando.
                    texturas = l2npc.texturas_do_npc(grp, linha)
                    break
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu para ler o npcgrp.dat"), str(erro))
            return

        if not malha:
            messagebox.showinfo(
                t("Sem malha no cliente"),
                t("O id %s não está no npcgrp.dat deste cliente, ou não tem "
                  "modelo apontado. Ele existe no servidor, mas o cliente "
                  "não sabe desenhá-lo.") % ident)
            return

        try:
            pacote = l2npc.abrir_visualizador(
                self.T, l2conferir.raiz_do_cliente(cliente), malha)
        except Exception as erro:                   # noqa: BLE001
            messagebox.showerror(t("Não deu"), str(erro))
            return

        self.log(t("\nAbrindo a malha %s (%s) no visualizador do umodel.")
                 % (malha, Path(pacote).name))
        recado = l2npc.recado_das_texturas(texturas)
        if recado:
            self.log("\n" + recado)
            messagebox.showinfo(t("Sobre as texturas deste NPC"), recado)

    def _montar_rodape(self, pai):
        acao = ttk.Frame(pai)
        acao.pack(fill="x", pady=(8, 0))
        self.botao_conferir = ttk.Button(acao, text=t("Conferir"),
                                         command=self.conferir)
        self.botao_conferir.pack(side="left")
        self.botao_xml = ttk.Button(acao, text=t("Ver a XML"),
                                    command=self.ver_xml)
        self.botao_xml.pack(side="left", padx=(6, 0))
        self.botao_gravar = ttk.Button(acao, text=t("Gravar no servidor"),
                                       command=self.gravar)
        self.botao_gravar.pack(side="left", padx=(6, 0))
        self.botao_malha = ttk.Button(acao, text=t("Ver a malha em 3D"),
                                      command=self.ver_malha)
        self.botao_malha.pack(side="left", padx=(6, 0))
        ajuda.ajuda(acao, lambda: t(
            "Abre a malha deste mob no visualizador do umodel, para girar e "
            "ver as animações.\n\n"
            "O mob vem do servidor, mas o modelo é do cliente: o id é "
            "procurado no npcgrp.dat, que diz qual malha ele usa."))
        self.estado = ttk.Label(acao, text="", foreground=COR_TEXTO_FRACO)
        self.estado.pack(side="left", padx=(12, 0))

        self.texto = tk.Text(pai, height=7, wrap="word")
        self.texto.pack(fill="both", expand=False, pady=(8, 0))

    def log(self, texto):
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")

    def _avisar_do_icone(self, recado):
        """O ícone veio de outro pacote -- dizer isso, da thread para cá."""
        try:
            self.raiz.after(0, self.log, recado)
        except Exception:                           # noqa: BLE001
            pass

    def trabalho(self):
        pasta = Path(motor.BASE) / "trabalho" / "mob"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def system(self):
        return l2conferir.raiz_do_cliente(self.cliente.get().strip()) / "system"

    def atualizar_botoes(self):
        parado = not self.rodando
        # O botao so fica cinza enquanto algo roda. Faltando pasta ele
        # continua clicavel e DIZ o que falta -- botao cinza nao ensina nada.
        self.botao_abrir.config(state="normal" if parado else "disabled")
        tem = self.mob is not None
        for botao in (self.botao_conferir, self.botao_xml):
            botao.config(state="normal" if tem else "disabled")
        self.botao_gravar.config(
            state="normal" if tem and self.mob.get("mexidos") else "disabled")

    # =====================================================================
    # abrir
    # =====================================================================
    def carregar_tudo(self):
        """
        Carrega o que esta aba usa: as tabelas do cliente e os mobs.

        Na ordem: primeiro o cliente, depois o servidor. É o cliente que dá o
        nome e o desenho de item e skill, então carregá-lo antes faz a lista
        de mobs já nascer com tudo no lugar, em vez de preencher na frente de
        quem olha.
        """
        gui_projeto.limpar_aviso(self)
        faltas = gui_projeto.conferir_pastas()
        if faltas:
            gui_projeto.avisar_falta(self, faltas)
            return
        self._depois_das_tabelas = self.abrir
        self.abrir_tabelas()

    def abrir(self):
        pasta = l2mob.pasta_de_npcs(self.servidor.get().strip())
        if not pasta.is_dir():
            messagebox.showerror(t("Pasta não encontrada"),
                                 t("Não achei a pasta `npcs` a partir de %s.")
                                 % self.servidor.get())
            return
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("lendo os mobs do servidor…"))
        threading.Thread(target=self._abrir_thread, args=(pasta,),
                         daemon=True).start()

    def _abrir_thread(self, pasta):
        try:
            lista = l2mob.listar(pasta)
            erro = None
        except Exception as e:                      # noqa: BLE001
            lista, erro = [], e
        try:
            self.raiz.after(0, self._fim_abrir, pasta, lista, erro)
        except tk.TclError:
            pass

    def _fim_abrir(self, pasta, lista, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            messagebox.showerror(t("Não deu para ler os mobs"), str(erro))
            self.atualizar_botoes()
            return
        self.lista = lista
        tipos = []
        for m in lista:
            if m["tipo"] and m["tipo"] not in tipos:
                tipos.append(m["tipo"])
        self.caixa_tipo.config(values=tuple([t(TODOS)] + sorted(tipos)))
        self.log(t("%d mobs em %s.") % (len(lista), pasta))
        repetidos = self._ids_repetidos(lista)
        if repetidos:
            self.log(t("Atenção: %d id(s) aparecem em mais de um arquivo — o "
                       "core carrega na ordem npcs, raidboss, grandboss, "
                       "farmzone, custom, events, e o último apaga os "
                       "anteriores: %s")
                     % (len(repetidos), ", ".join(repetidos[:12])))
        self.preencher()
        self.atualizar_botoes()

    def _ids_repetidos(self, lista):
        vistos, repetidos = set(), []
        for m in lista:
            if m["id"] in vistos and m["id"] not in repetidos:
                repetidos.append(m["id"])
            vistos.add(m["id"])
        return repetidos

    def abrir_tabelas(self):
        self.rodando = True
        self.atualizar_botoes()
        self.estado.config(text=t("lendo as tabelas do cliente…"))
        threading.Thread(target=self._tabelas_thread, daemon=True).start()

    def _tabelas_thread(self):
        try:
            itens = l2item.Itens(self.T, self.system(),
                                 self.trabalho() / "itens")
            lidos = itens.listar()
            # As skills vem junto: a lista de drop precisa do item, e a de
            # golpes precisa da skill. Pedir as duas em botoes separados faria
            # a aba abrir pela metade sem dizer qual metade falta.
            try:
                skills = l2skill.Skills(self.T, self.system(),
                                        self.trabalho() / "skills").listar()
            except Exception:                       # noqa: BLE001
                skills = []        # cliente sem tabela de skill legivel
            erro = None
        except Exception as e:                      # noqa: BLE001
            lidos, skills, erro = [], [], e
        try:
            self.raiz.after(0, self._fim_tabelas, lidos, skills, erro)
        except tk.TclError:
            pass

    def _fim_tabelas(self, lidos, skills, erro):
        self.rodando = False
        self.estado.config(text="")
        if erro is not None:
            messagebox.showerror(t("Não deu para ler as tabelas"), str(erro))
            self.atualizar_botoes()
            return
        self.nomes = dict((str(i["id"]), i["nome"]) for i in lidos)
        self.descricoes = dict((str(i["id"]), i.get("descricao") or "")
                               for i in lidos)
        self.icones_de_item = dict((str(i["id"]), i.get("icone") or "")
                                   for i in lidos)
        self.skills_do_cliente = skills
        self._esquecer_skills_do_cliente()
        self.log(t("%d itens e %d skills do cliente.")
                 % (len(lidos), len(skills)))
        self._encher_drops()
        self._encher_skills()
        self.atualizar_botoes()
        # O `Carregar` encadeia: terminadas as tabelas, vêm os mobs.
        seguinte = getattr(self, "_depois_das_tabelas", None)
        self._depois_das_tabelas = None
        if seguinte is not None:
            seguinte()

    def abrir_o_marcado(self):
        marcado = self.tabela.selection()
        if not marcado:
            return
        indice = int(marcado[0])
        if indice >= len(self.mostrados):
            return
        registro = self.mostrados[indice]
        if (self.mob and self.mob.get("mexidos")
                and self.mob["id"] != registro["id"]):
            if not messagebox.askyesno(
                    t("Largar as mudanças?"),
                    t("O mob %s tem mudanças que ainda não foram gravadas. "
                      "Abrir outro perde essas mudanças. Continuar?")
                    % self.mob["id"]):
                return
        mob = l2mob.ler(registro["arquivo"], registro["id"])
        if mob is None:
            messagebox.showerror(t("Não achei"),
                                 t("O mob %s sumiu do arquivo %s.")
                                 % (registro["id"], registro["arquivo"].name))
            return
        self.mob = mob
        self.campo_nome.set(mob["name"])
        self.campo_titulo.set(mob["title"])
        mob["mexidos"].clear()          # preencher os campos nao e editar
        self.titulo.config(text=t("%s — %s   (%s)")
                           % (mob["id"], mob["name"] or t("sem nome"),
                              Path(mob["arquivo"]).name))
        guardados = l2mob.blocos_preservados(mob)
        self.preservados.config(
            text=t("preservado sem tocar: %s") % ", ".join(guardados)
            if guardados else "")
        self._encher_status()
        self._encher_skills()
        self._encher_drops()
        self._encher_minions()
        self.atualizar_botoes()

    # =====================================================================
    # editar, conferir, gravar
    # =====================================================================
    def _mexeu(self, o_que):
        if self.mob is None:
            return
        self.mob["mexidos"].add(o_que)
        self.atualizar_botoes()

    def _da_tela(self):
        """O mob com o que está nos campos agora."""
        if self.mob is None:
            return None
        mob = self.mob
        if "atributos" in mob["mexidos"]:
            mob["atributos"]["name"] = self.campo_nome.get()
            mob["atributos"]["title"] = self.campo_titulo.get()
            mob["name"] = self.campo_nome.get()
            mob["title"] = self.campo_titulo.get()
        if "sets" in mob["mexidos"]:
            mob["sets"] = [(c, self.campos[c].get()) if c in self.campos
                           else (c, v) for c, v in mob["sets"]]
        if "ai" in mob["mexidos"]:
            for chave, variavel in self.campos_ai.items():
                mob["ai"][chave] = variavel.get()
        if "skills" in mob["mexidos"]:
            golpes = l2mob.golpes_de(mob)
            escolhida = (self.raca.get() or "").split("—")[0].strip()
            mob["skills"] = ([{"id": str(l2mob.SKILL_DA_RACA),
                               "level": escolhida}] if escolhida else []) + golpes
        return mob

    def conferir(self):
        mob = self._da_tela()
        if mob is None:
            return
        problemas = l2mob.conferir(mob, self.nomes or None)
        if not problemas:
            self.log(t("\nO mob %s está consistente.") % mob["id"])
            return
        self.log(t("\nA conferência achou %d coisas no mob %s:")
                 % (len(problemas), mob["id"]))
        for p in problemas:
            self.log("  - " + p)

    def ver_xml(self):
        mob = self._da_tela()
        if mob is None:
            return
        janela = tk.Toplevel(self.raiz)
        janela.title(t("A XML do mob %s") % mob["id"])
        ajuda.por_icone(janela)
        caixa = tk.Text(janela, wrap="none", width=100, height=32)
        caixa.pack(fill="both", expand=True)
        caixa.insert("1.0", l2mob.xml(mob))
        caixa.config(state="disabled")
        ttk.Button(janela, text=t("Fechar"),
                   command=janela.destroy).pack(pady=6)

    def gravar(self):
        mob = self._da_tela()
        if mob is None:
            return
        problemas = l2mob.conferir(mob, self.nomes or None)
        if problemas:
            if not messagebox.askyesno(
                    t("Gravar mesmo assim?"),
                    t("A conferência achou %d coisas. Gravar mesmo assim?\n\n%s")
                    % (len(problemas), "\n".join("- " + p
                                                 for p in problemas[:8]))):
                self.conferir()
                return
        try:
            copia = l2mob.gravar(mob)
        except Exception as e:                      # noqa: BLE001
            messagebox.showerror(t("Não deu para gravar"), str(e))
            return
        self.log(t("Gravado o mob %s em %s.")
                 % (mob["id"], Path(mob["arquivo"]).name))
        if copia:
            self.log(t("  cópia do arquivo antigo: %s") % Path(copia).name)
        self.log(t("  falta recarregar no jogo:  //reload npc"))
        # Reler: o texto cru mudou, e gravar de novo por cima do antigo daria
        # "o npc mudou no arquivo desde que foi lido".
        self.mob = l2mob.ler(mob["arquivo"], mob["id"])
        self.atualizar_botoes()

    # =====================================================================
    # os ícones
    # =====================================================================
    def marca_de_espera(self):
        """
        O quadrado vazio que ocupa o lugar do ícone enquanto ele não chega.

        Os ícones saem do cliente numa thread por item, e demoram uns dois
        segundos para a lista inteira. Sem nada no lugar, a linha parece ter
        perdido o desenho -- e dois segundos são tempo de sobra para alguém
        concluir que está quebrado. Com a marca, ela parece o que é: ainda
        carregando.
        """
        marca = getattr(self, "_marca_de_espera", None)
        if marca is not None or Image is None:
            return marca or ""
        try:
            arte = Image.new("RGBA", (LADO_DO_ICONE, LADO_DO_ICONE),
                             (0, 0, 0, 0))
            desenho = __import__("PIL.ImageDraw", fromlist=["ImageDraw"])
            caneta = desenho.Draw(arte)
            caneta.rectangle([6, 6, LADO_DO_ICONE - 7, LADO_DO_ICONE - 7],
                             outline=(110, 122, 138, 170))
            marca = ImageTk.PhotoImage(arte)
        except Exception:                           # noqa: BLE001
            marca = ""
        self._marca_de_espera = marca
        return marca

    def icone_de(self, ident):
        ident = str(ident)
        if ident in self.icones:
            return self.icones[ident] or ""
        referencia = (self.icones_de_item or {}).get(ident)
        if not referencia or Image is None:
            self.icones[ident] = None
            return ""
        self.icones[ident] = None
        threading.Thread(target=self._icone_thread, args=(ident, referencia),
                         daemon=True).start()
        return ""

    def _icone_thread(self, ident, referencia):
        imagem = self.carregar_icone(referencia)
        try:
            self.raiz.after(0, self._icone_chegou, ident, imagem)
        except tk.TclError:
            pass

    def _icone_chegou(self, ident, imagem):
        if imagem is None:
            return
        self.icones[ident] = ImageTk.PhotoImage(imagem)
        if getattr(self, "_redesenho_pedido", False):
            return
        self._redesenho_pedido = True
        try:
            self._redesenho_marcado = self.quadro.after(
                120, self._redesenhar)
        except tk.TclError:
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

    def _redesenhar(self):
        self._redesenho_pedido = False
        self._redesenho_marcado = None
        self._encher_drops()

    def carregar_icone(self, referencia):
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


# =========================================================================
# janelinhas
# =========================================================================
class PedirUmNumero:
    """Um campo e dois botões. Devolve o texto em `.resposta`, ou None."""

    def __init__(self, raiz, titulo, rotulo, valor=""):
        self.resposta = None
        self.janela = tk.Toplevel(raiz)
        self.janela.title(titulo)
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)
        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text=rotulo).pack(anchor="w")
        self.valor = tk.StringVar(value=valor)
        campo = ttk.Entry(quadro, textvariable=self.valor, width=18)
        campo.pack(anchor="w", pady=(4, 0))
        campo.focus_set()
        campo.bind("<Return>", lambda _e: self.aceitar())
        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(10, 0))
        ttk.Button(botoes, text=t("Usar"),
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")
        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        raiz.wait_window(self.janela)

    def aceitar(self):
        self.resposta = self.valor.get().strip()
        self.janela.destroy()


class PedirDoisNumeros:
    """Dois campos. Devolve (a, b) em `.resposta`, ou None."""

    def __init__(self, raiz, titulo, r1, v1, r2, v2):
        self.resposta = None
        self.janela = tk.Toplevel(raiz)
        self.janela.title(titulo)
        self.janela.transient(raiz)
        ajuda.por_icone(self.janela)
        quadro = ttk.Frame(self.janela, padding=12)
        quadro.pack(fill="both", expand=True)
        self.a = tk.StringVar(value=v1)
        self.b = tk.StringVar(value=v2)
        for linha, (rotulo, variavel) in enumerate(((r1, self.a), (r2, self.b))):
            ttk.Label(quadro, text=rotulo).grid(row=linha, column=0,
                                                sticky="e", padx=(0, 6), pady=3)
            campo = ttk.Entry(quadro, textvariable=variavel, width=14)
            campo.grid(row=linha, column=1, sticky="w", pady=3)
            campo.bind("<Return>", lambda _e: self.aceitar())
            if not linha:
                campo.focus_set()
        botoes = ttk.Frame(quadro)
        botoes.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(botoes, text=t("Usar"),
                   command=self.aceitar).pack(side="left")
        ttk.Button(botoes, text=t("Cancelar"),
                   command=self.janela.destroy).pack(side="right")
        self.janela.bind("<Escape>", lambda _e: self.janela.destroy())
        ajuda.centralizar(self.janela)
        self.janela.grab_set()
        raiz.wait_window(self.janela)

    def aceitar(self):
        self.resposta = (self.a.get().strip(), self.b.get().strip())
        self.janela.destroy()
