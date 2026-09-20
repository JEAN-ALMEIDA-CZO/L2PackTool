#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conferencia do cliente: o que as tabelas pedem contra o que existe nas pastas.

O sintoma que isto resolve nao aparece como erro. Uma arma cujo modelo nao
esta instalado vira uma mao vazia; um icone que falta vira um quadrado em
branco; uma armadura sem textura vira um boneco branco. O cliente nao reclama
-- ele desenha o que conseguiu e segue.

O metodo tem duas metades:

  1. AS REFERENCIAS. As tabelas .dat do cliente guardam os caminhos dos
     modelos, texturas, icones e sons no formato "Pacote.Objeto". Elas sao
     lidas por varredura de texto, e nao por definicao .ddf: o que interessa
     aqui e achar as referencias, nao interpretar as colunas. Uma varredura
     nao depende de o .ddf descrever aquele cliente -- e cliente modificado
     sempre tem coluna a mais ou a menos -- e nao corre o risco de ler campo
     deslocado, porque nada e gravado de volta.

  2. O QUE EXISTE. Cada pacote instalado e aberto so nas tabelas de nome e de
     exportacao, sem descriptografar o arquivo inteiro. Os .utx do L2 usam
     Lineage2Ver121, que e um XOR de um byte so derivado do nome do arquivo:
     da para ler qualquer pedaco do arquivo direto do disco. Um cliente com
     12 GB de pacotes e catalogado em segundos, e nao em horas.

     Os .usx, .ukx e .u usam Blowfish, que nao permite esse acesso por pedaco.
     Desses o programa confere que o pacote existe, e diz no relatorio que o
     conteudo nao foi aberto -- em vez de calar ou de dar por bom o que nao
     conferiu.
"""

import re
import shutil
import struct
import time
from pathlib import Path

import l2upscale as motor

# Tudo que e pacote Unreal e pode ser referenciado por uma tabela.
EXTENSOES = (".utx", ".usx", ".ukx", ".uax", ".u", ".unr", ".umx")

# As pastas do cliente, e a que tipo de pacote cada uma serve. A ordem importa
# na hora de instalar: um .utx que veio de systextures volta para systextures.
PASTAS_DO_CLIENTE = ("system", "systextures", "textures", "staticmeshes",
                     "animations", "maps", "sounds", "voice", "music")

PASTA_POR_EXTENSAO = {
    ".utx": "textures",
    ".usx": "staticmeshes",
    ".ukx": "animations",
    ".uax": "sounds",
    ".unr": "maps",
    ".u": "system",
    ".umx": "music",
}

# As tabelas que citam arquivos. Sao lidas nesta ordem; a que nao existir e
# simplesmente pulada, porque cliente nenhum tem todas.
TABELAS = ("npcgrp.dat", "weapongrp.dat", "armorgrp.dat", "etcitemgrp.dat",
           "itemgrp.dat", "skillgrp.dat", "pledgegrp.dat", "doorgrp.dat")

ASSINATURA = 0x9E2A83C1

# Uma cadeia de texto UTF-16 legivel, de quatro caracteres para cima. E assim
# que os .dat guardam os caminhos.
_CORRIDA = re.compile(rb"(?:[\x20-\x7E]\x00){4,}")

# "Pacote.Objeto": duas partes de identificador separadas por ponto. O filtro e
# apertado de proposito -- numero com virgula decimal, versao e nome de arquivo
# nao passam por aqui.
_REFERENCIA = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{1,63}"
                         r"(?:\.[A-Za-z0-9_\-]{1,63})+$")

# Nomes de pacote que nao sao pacote: aparecem no texto das tabelas mas o
# cliente nunca vai procurar um arquivo com esse nome.
_NAO_SAO_PACOTES = {"core", "engine", "editor", "unrealed", "ipdrv", "uweb",
                    "uwindow", "fire", "ifc", "window", "xinterface",
                    "xgame", "gameplay"}

# Objeto do Unreal nao se chama "100". Texto como "skill.at.100", que o
# skillgrp guarda as centenas, passa pelo formato de referencia sem ser uma --
# e entraria no relatorio como 257 arquivos perdidos que nunca existiram.
_SO_NUMERO = re.compile(r"^\d+$")


class ErroDeLeitura(Exception):
    pass


# ---------------------------------------------------------------------------
# Leitura por pedaco de um pacote
# ---------------------------------------------------------------------------
def chave_xor(nome_do_arquivo):
    """
    A chave do Lineage2Ver121: um byte, a soma dos caracteres do nome.

    E por isso que renomear um .utx o corrompe -- a chave passa a ser outra.
    """
    return sum(ord(c) for c in nome_do_arquivo.lower()) & 0xFF


def _indice(dados, pos):
    """O inteiro compacto do Unreal: 6 bits uteis no primeiro byte, 7 nos outros."""
    valor = dados[pos]
    pos += 1
    negativo = valor & 0x80
    n = valor & 0x3F
    if valor & 0x40:
        desloc = 6
        while True:
            c = dados[pos]
            pos += 1
            n |= (c & 0x7F) << desloc
            desloc += 7
            if not (c & 0x80):
                break
    return (-n if negativo else n), pos


class LeitorDePacote:
    """
    Um pacote aberto por acesso aleatorio, sem copia e sem descriptografar
    tudo.

    Serve para uma pergunta so: que objetos moram aqui dentro. Por isso le
    apenas a tabela de nomes, na frente do arquivo, e a de exportacao, no fim.
    Um .utx de 200 MB responde isso lendo alguns kilobytes.
    """

    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.arquivo = open(self.caminho, "rb")
        try:
            cabeca = self.arquivo.read(28)
            marca = cabeca.replace(b"\x00", b"")
            if marca.startswith(b"Lineage2Ver"):
                metodo = marca[11:14].decode("latin-1")
                if metodo != "121":
                    raise ErroDeLeitura(
                        "%s usa Lineage2Ver%s, que so abre por inteiro."
                        % (self.caminho.name, metodo))
                self.inicio = 28
                chave = chave_xor(self.caminho.name)
                self.tabela = bytes(b ^ chave for b in range(256))
            else:
                self.inicio = 0
                self.tabela = None

            assinatura = struct.unpack_from("<I", self._ler(0, 4), 0)[0]
            if assinatura != ASSINATURA:
                raise ErroDeLeitura("%s nao e um pacote Unreal." % self.caminho.name)
        except Exception:
            self.fechar()
            raise

        cabecalho = self._ler(0, 36)
        self.versao, self.licenca = struct.unpack_from("<HH", cabecalho, 4)
        (_flags, self.qtd_nomes, self.off_nomes, self.qtd_exp, self.off_exp,
         self.qtd_imp, self.off_imp) = struct.unpack_from("<IIIIIII", cabecalho, 8)
        self.tamanho = self.caminho.stat().st_size - self.inicio

    def _ler(self, posicao, quantos):
        self.arquivo.seek(self.inicio + posicao)
        dados = self.arquivo.read(quantos)
        return dados.translate(self.tabela) if self.tabela else dados

    def fechar(self):
        if getattr(self, "arquivo", None) is not None:
            self.arquivo.close()
            self.arquivo = None

    def __enter__(self):
        return self

    def __exit__(self, *_erro):
        self.fechar()
        return False

    def nomes(self):
        """
        A tabela de nomes. O tamanho dela nao esta escrito em lugar nenhum --
        so o fim, que e o inicio da proxima tabela. Le-se um pedaco generoso e,
        se nao bastar, o pedaco dobra.
        """
        limite = min(self.off_exp or self.tamanho, self.off_imp or self.tamanho,
                     self.tamanho) - self.off_nomes
        if limite <= 0:
            raise ErroDeLeitura("tabela de nomes fora do arquivo")

        pedido = min(self.qtd_nomes * 80 + 8192, limite)
        while True:
            bruto = self._ler(self.off_nomes, pedido)
            try:
                nomes, pos = [], 0
                for _ in range(self.qtd_nomes):
                    tam, pos = _indice(bruto, pos)
                    if tam < 0:
                        # Tamanho negativo quer dizer UTF-16, e conta
                        # caracteres em vez de bytes. Aparece em pacotes
                        # gerados por editor, misturado com os latin-1 no
                        # mesmo arquivo -- ignorar o sinal faz a leitura
                        # andar para tras e perder a tabela inteira dali.
                        bytes_ = -tam * 2
                        texto = bruto[pos:pos + bytes_ - 2].decode("utf-16-le",
                                                                   "replace")
                    else:
                        bytes_ = tam
                        texto = bruto[pos:pos + tam - 1].decode("latin-1")
                    if not texto and bytes_ <= 0:
                        raise ErroDeLeitura("tabela de nomes fora de passo")
                    nomes.append(texto)
                    pos += bytes_ + 4       # a string, mais quatro de flags
                return nomes
            except IndexError:
                if pedido >= limite:
                    raise ErroDeLeitura("tabela de nomes incompleta")
                pedido = min(pedido * 2, limite)

    def objetos(self):
        """Os nomes dos objetos exportados -- o que o cliente pode carregar daqui."""
        nomes = self.nomes()
        bruto = self._ler(self.off_exp, self.tamanho - self.off_exp)
        saida, pos = [], 0
        for _ in range(self.qtd_exp):
            try:
                _classe, pos = _indice(bruto, pos)
                _mae, pos = _indice(bruto, pos)
                pos += 4                            # dono
                nome, pos = _indice(bruto, pos)
                pos += 4                            # flags
                tamanho, pos = _indice(bruto, pos)
                if tamanho > 0:
                    _inicio, pos = _indice(bruto, pos)
            except IndexError:
                # A tabela fica no fim do arquivo e alguns pacotes chegam com
                # os ultimos bytes truncados. Perder os dois ultimos de mil
                # objetos nao muda a resposta; abortar a leitura mudaria.
                break
            saida.append(nomes[nome] if 0 <= nome < len(nomes) else "")
        return saida


def objetos_do_pacote(caminho):
    """
    Os objetos de um pacote, ou levanta ErroDeLeitura se ele nao abre assim.

    Uma leitura que sai pela metade e pior do que nenhuma: ela viraria uma
    lista de objetos inexistentes no relatorio, com nome e tudo, e mandaria o
    usuario reinstalar um pacote que estava inteiro. Por isso a leitura so
    vale se quase todos os nomes sairem preenchidos.
    """
    with LeitorDePacote(caminho) as pacote:
        objetos = pacote.objetos()

    if not objetos:
        return []
    vazios = sum(1 for o in objetos if not o)
    if vazios > len(objetos) // 20:
        raise ErroDeLeitura("%s: %d de %d nomes nao foram lidos"
                            % (Path(caminho).name, vazios, len(objetos)))
    return objetos


# ---------------------------------------------------------------------------
# O cliente
# ---------------------------------------------------------------------------
def raiz_do_cliente(caminho):
    """Aceita tanto a pasta do cliente quanto a system dentro dela."""
    raiz = Path(caminho)
    return raiz.parent if raiz.name.lower() == "system" else raiz


class Cliente:
    """
    O indice dos pacotes instalados, e o que ha dentro de cada um.

    O conteudo e lido sob demanda e guardado: um mesmo pacote e citado por
    centenas de itens, e abri-lo uma vez por citacao seria o grosso do tempo.
    """

    def __init__(self, caminho):
        self.raiz = raiz_do_cliente(caminho)
        self.pacotes = {}
        self._conteudo = {}
        self._indexar()

    def _indexar(self):
        for pasta in PASTAS_DO_CLIENTE:
            diretorio = self.raiz / pasta
            if not diretorio.is_dir():
                continue
            for item in diretorio.rglob("*"):
                if item.is_file() and item.suffix.lower() in EXTENSOES:
                    self.pacotes.setdefault(item.stem.lower(), []).append(item)

    @property
    def system(self):
        return self.raiz / "system"

    def tem(self, nome_do_pacote):
        return nome_do_pacote.lower() in self.pacotes

    def caminho_de(self, nome_do_pacote):
        achados = self.pacotes.get(nome_do_pacote.lower())
        return achados[0] if achados else None

    def conteudo_de(self, nome_do_pacote):
        """
        {objetos em minusculas} -- ou None quando o pacote existe mas nao pode
        ser aberto por pedaco (Blowfish). None nao e "vazio": e "nao conferi".

        Quando o mesmo nome aparece em mais de uma pasta, o conteudo de todos
        e somado. Nao e um detalhe: os icones deste cliente estao repartidos
        entre system/Icon.u, com 14.621 objetos, e systextures/Icon.utx, com
        4.019. Olhar so o primeiro daria quatro mil icones por perdidos.
        """
        chave = nome_do_pacote.lower()
        if chave in self._conteudo:
            return self._conteudo[chave]

        resposta = None
        for caminho in self.pacotes.get(chave, []):
            try:
                objetos = set(o.lower() for o in objetos_do_pacote(caminho))
            except (ErroDeLeitura, OSError, struct.error, ValueError):
                continue
            resposta = objetos if resposta is None else (resposta | objetos)
        self._conteudo[chave] = resposta
        return resposta


# ---------------------------------------------------------------------------
# As referencias
# ---------------------------------------------------------------------------
def referencias_do_arquivo(dados):
    """
    Todo 'Pacote.Objeto' que aparece como texto nestes bytes.

    A varredura por si so erra por um caractere, e o erro nao e inofensivo. Um
    campo de texto e gravado como o tamanho em quatro bytes seguido dos
    caracteres; quando o tamanho do campo SEGUINTE cai entre 32 e 126, os dois
    primeiros bytes dele -- por exemplo 58 00, que e o numero 88 -- passam por
    um 'X' em UTF-16 e entram no fim do texto anterior. O efeito e uma
    referencia a mais no relatorio para cada item do cliente.

    Por isso o tamanho declarado antes do texto tem a ultima palavra sobre
    onde ele acaba.
    """
    achadas = set()
    for corrida in _CORRIDA.finditer(dados):
        inicio, fim = corrida.span()
        if inicio >= 4:
            declarado = struct.unpack_from("<i", dados, inicio - 4)[0]
            if 0 < declarado <= fim - inicio and not declarado % 2:
                fim = inicio + declarado
        texto = dados[inicio:fim].decode("utf-16-le", "ignore")
        if not _REFERENCIA.match(texto):
            continue
        partes = texto.split(".")
        if partes[0].lower() in _NAO_SAO_PACOTES or _SO_NUMERO.match(partes[-1]):
            continue
        achadas.add(texto)
    return achadas


def _abrir_dat(caminho, T, trabalho):
    """Devolve os bytes decifrados da tabela."""
    import l2npc

    metodo = l2npc.metodo_do_arquivo(caminho)
    if not metodo:
        return caminho.read_bytes()

    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    puro = trabalho / (caminho.stem + ".dec")
    if (not puro.exists()
            or puro.stat().st_mtime < caminho.stat().st_mtime):
        puro.unlink(missing_ok=True)
        codigo, saida = motor.executar([T["l2encdec"], "-d", caminho, puro],
                                       limite=300)
        if not puro.exists():
            raise ErroDeLeitura("o l2encdec nao abriu %s: %s"
                                % (caminho.name, saida.strip()[:160]))
    return puro.read_bytes()


def referencias_do_cliente(cliente, T, trabalho, aoprogresso=None):
    """
    {referencia: {tabelas que a citam}} e a lista do que cada tabela rendeu.
    """
    cliente = cliente if isinstance(cliente, Cliente) else Cliente(cliente)
    achadas = {}
    tabelas = []

    presentes = [nome for nome in TABELAS if (cliente.system / nome).is_file()]
    for i, nome in enumerate(presentes):
        if aoprogresso:
            aoprogresso(0.05 + 0.35 * i / max(1, len(presentes)),
                        "lendo %s" % nome)
        caminho = cliente.system / nome
        try:
            dados = _abrir_dat(caminho, T, trabalho)
        except (ErroDeLeitura, OSError) as erro:
            tabelas.append({"nome": nome, "referencias": 0, "erro": str(erro)})
            continue

        daqui = referencias_do_arquivo(dados)
        for referencia in daqui:
            achadas.setdefault(referencia, set()).add(nome)
        tabelas.append({"nome": nome, "referencias": len(daqui), "erro": ""})

    return achadas, tabelas


# ---------------------------------------------------------------------------
# A conferencia
# ---------------------------------------------------------------------------
def conferir(caminho_do_cliente, T=None, trabalho=None, aoprogresso=None):
    """
    Confere o cliente inteiro e devolve o relatorio.

    Nada e escrito: a conferencia so le. O que ela responde e onde o cliente
    vai desenhar um buraco.
    """
    comeco = time.time()
    T = T or motor.carregar_config()
    trabalho = Path(trabalho or (motor.BASE / "trabalho" / "conferir"))
    trabalho.mkdir(parents=True, exist_ok=True)

    if aoprogresso:
        aoprogresso(0.02, "catalogando os pacotes instalados")
    cliente = Cliente(caminho_do_cliente)

    achadas, tabelas = referencias_do_cliente(cliente, T, trabalho, aoprogresso)

    pacotes_ausentes = {}
    objetos_ausentes = {}
    nao_conferidos = {}
    resolvidas = 0

    total = max(1, len(achadas))
    for i, (referencia, origens) in enumerate(sorted(achadas.items())):
        if aoprogresso and i % 250 == 0:
            aoprogresso(0.4 + 0.55 * i / total,
                        "conferindo %d de %d referencias" % (i, total))

        # "Pacote.Objeto", mas tambem "Pacote.Grupo.Objeto" -- o Unreal agrupa
        # objetos dentro do pacote, e o cliente escreve o caminho inteiro. O
        # que se procura na tabela de exportacao e sempre a ultima parte.
        partes = referencia.split(".")
        nome_do_pacote, objeto = partes[0], partes[-1]
        chave = nome_do_pacote.lower()

        if not cliente.tem(chave):
            entrada = pacotes_ausentes.setdefault(
                chave, {"nome": nome_do_pacote, "referencias": [], "origens": set()})
            entrada["referencias"].append(referencia)
            entrada["origens"].update(origens)
            continue

        conteudo = cliente.conteudo_de(chave)
        if conteudo is None:
            entrada = nao_conferidos.setdefault(
                chave, {"nome": nome_do_pacote, "referencias": [],
                        "caminho": cliente.caminho_de(chave)})
            entrada["referencias"].append(referencia)
        elif objeto.lower() not in conteudo:
            entrada = objetos_ausentes.setdefault(
                chave, {"nome": nome_do_pacote, "referencias": [],
                        "caminho": cliente.caminho_de(chave), "origens": set()})
            entrada["referencias"].append(referencia)
            entrada["origens"].update(origens)
        else:
            resolvidas += 1

    if aoprogresso:
        aoprogresso(1.0, "pronto")

    return {
        "cliente": cliente,
        "raiz": cliente.raiz,
        "tabelas": tabelas,
        "pacotes_instalados": len(cliente.pacotes),
        "total": len(achadas),
        "resolvidas": resolvidas,
        "pacotes_ausentes": pacotes_ausentes,
        "objetos_ausentes": objetos_ausentes,
        "nao_conferidos": nao_conferidos,
        "segundos": time.time() - comeco,
    }


def problemas(resultado):
    """Uma lista plana para a tela, do mais grave para o menos."""
    lista = []
    for entrada in sorted(resultado["pacotes_ausentes"].values(),
                          key=lambda e: -len(e["referencias"])):
        lista.append({
            "gravidade": "pacote",
            "pacote": entrada["nome"],
            "quantos": len(entrada["referencias"]),
            "origens": sorted(entrada["origens"]),
            "exemplos": sorted(entrada["referencias"])[:5],
            "caminho": None,
        })
    for entrada in sorted(resultado["objetos_ausentes"].values(),
                          key=lambda e: -len(e["referencias"])):
        lista.append({
            "gravidade": "objeto",
            "pacote": entrada["nome"],
            "quantos": len(entrada["referencias"]),
            "origens": sorted(entrada["origens"]),
            "exemplos": sorted(entrada["referencias"])[:5],
            "caminho": entrada["caminho"],
        })
    return lista


def texto_do_relatorio(resultado):
    """O relatorio em texto, para guardar ou mandar para alguem."""
    linhas = []
    escrever = linhas.append

    escrever("CONFERENCIA DO CLIENTE")
    escrever("=" * 66)
    escrever("cliente: %s" % resultado["raiz"])
    escrever("data:    %s" % time.strftime("%d/%m/%Y %H:%M"))
    escrever("")

    escrever("TABELAS LIDAS")
    for tabela in resultado["tabelas"]:
        if tabela["erro"]:
            escrever("  %-18s nao abriu: %s" % (tabela["nome"], tabela["erro"]))
        else:
            escrever("  %-18s %6d referencias" % (tabela["nome"],
                                                  tabela["referencias"]))
    escrever("")

    faltando = sum(len(e["referencias"])
                   for e in resultado["pacotes_ausentes"].values())
    quebradas = sum(len(e["referencias"])
                    for e in resultado["objetos_ausentes"].values())
    sem_conferir = sum(len(e["referencias"])
                       for e in resultado["nao_conferidos"].values())

    escrever("RESUMO")
    escrever("  pacotes instalados no cliente: %d" % resultado["pacotes_instalados"])
    escrever("  referencias encontradas:       %d" % resultado["total"])
    escrever("  resolvidas:                    %d" % resultado["resolvidas"])
    escrever("  pacote ausente:                %d  (%d pacotes)"
             % (faltando, len(resultado["pacotes_ausentes"])))
    escrever("  objeto ausente:                %d  (%d pacotes)"
             % (quebradas, len(resultado["objetos_ausentes"])))
    escrever("  nao conferidas:                %d  (%d pacotes Blowfish)"
             % (sem_conferir, len(resultado["nao_conferidos"])))
    escrever("  tempo:                         %.1f s" % resultado["segundos"])
    escrever("")

    if resultado["pacotes_ausentes"]:
        escrever("PACOTES QUE FALTAM")
        escrever("O cliente pede estes arquivos e eles nao estao em pasta nenhuma.")
        escrever("-" * 66)
        for entrada in sorted(resultado["pacotes_ausentes"].values(),
                              key=lambda e: -len(e["referencias"])):
            escrever("  %-34s %5d referencias   (%s)"
                     % (entrada["nome"], len(entrada["referencias"]),
                        ", ".join(sorted(entrada["origens"]))))
            # Sem corte: a lista existe para ser conferida, e quem precisa
            # dela precisa dela inteira -- para procurar um nome, copiar para
            # um script, comparar com o que o pack instalou.
            for referencia in sorted(entrada["referencias"]):
                escrever("      %s" % referencia)
        escrever("")

    if resultado["objetos_ausentes"]:
        escrever("OBJETOS QUE FALTAM DENTRO DE PACOTES INSTALADOS")
        escrever("O arquivo esta la, mas nao tem dentro o que a tabela pede.")
        escrever("-" * 66)
        for entrada in sorted(resultado["objetos_ausentes"].values(),
                              key=lambda e: -len(e["referencias"])):
            escrever("  %-34s %5d referencias" % (entrada["nome"],
                                                  len(entrada["referencias"])))
            escrever("      arquivo: %s" % entrada["caminho"])
            # Sem corte: a lista existe para ser conferida, e quem precisa
            # dela precisa dela inteira -- para procurar um nome, copiar para
            # um script, comparar com o que o pack instalou.
            for referencia in sorted(entrada["referencias"]):
                escrever("      %s" % referencia)
        escrever("")

    if resultado["nao_conferidos"]:
        escrever("PRESENTES, CONTEUDO NAO ABERTO")
        escrever("Pacotes com Lineage2Ver111 (Blowfish), que so abrem por inteiro.")
        escrever("A conferencia confirma que o arquivo existe e para por ai.")
        escrever("-" * 66)
        for entrada in sorted(resultado["nao_conferidos"].values(),
                              key=lambda e: -len(e["referencias"])):
            escrever("  %-34s %5d referencias" % (entrada["nome"],
                                                  len(entrada["referencias"])))
        escrever("")

    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Procurar noutros clientes e instalar
# ---------------------------------------------------------------------------
def procurar(pastas, nomes, aoprogresso=None, limite_por_nome=6):
    """
    Varre as pastas atras dos pacotes que faltam.

    `pastas` costuma ser uma pasta com varios clientes dentro. A varredura
    desce ate o fim e olha o nome do arquivo, porque o mesmo pacote muda de
    lugar de cliente para cliente.

    Devolve {nome em minusculas: [{caminho, tamanho, origem, pasta}]}.
    """
    procurados = {n.lower() for n in nomes}
    encontrados = {}
    if not procurados:
        return encontrados

    vistos = 0
    for pasta in ([pastas] if isinstance(pastas, (str, Path)) else pastas):
        raiz = Path(pasta)
        if not raiz.is_dir():
            continue
        for item in raiz.rglob("*"):
            vistos += 1
            if aoprogresso and vistos % 2000 == 0:
                aoprogresso(None, "%d arquivos vistos, %d pacotes achados"
                            % (vistos, len(encontrados)))
            if not item.is_file() or item.suffix.lower() not in EXTENSOES:
                continue
            chave = item.stem.lower()
            if chave not in procurados:
                continue
            lista = encontrados.setdefault(chave, [])
            if len(lista) >= limite_por_nome:
                continue
            if any(c["caminho"] == item for c in lista):
                continue
            lista.append({
                "caminho": item,
                "tamanho": item.stat().st_size,
                "pasta": item.parent.name,
                "origem": _origem_de(item),
            })

    for lista in encontrados.values():
        lista.sort(key=lambda c: -c["tamanho"])
    if aoprogresso:
        aoprogresso(1.0, "%d arquivos vistos, %d pacotes achados"
                    % (vistos, len(encontrados)))
    return encontrados


def _origem_de(caminho):
    """De que cliente veio o arquivo, pelo nome da pasta acima da conhecida."""
    pai = caminho.parent
    if pai.name.lower() in PASTAS_DO_CLIENTE and pai.parent.name:
        return pai.parent.name
    return pai.name


def destino_no_cliente(cliente, caminho_de_origem):
    """
    Onde o pacote deve cair no cliente.

    Preferencia pela pasta de onde ele veio -- systextures e textures guardam
    os dois .utx, e a diferenca importa para o cliente. Sem essa pista, vale a
    extensao.
    """
    raiz = cliente.raiz if isinstance(cliente, Cliente) else raiz_do_cliente(cliente)
    origem = Path(caminho_de_origem)
    pasta = origem.parent.name.lower()
    if pasta not in PASTAS_DO_CLIENTE:
        pasta = PASTA_POR_EXTENSAO.get(origem.suffix.lower(), "textures")
    return raiz / pasta / origem.name


def instalar(cliente, escolhidos, aolog=None):
    """
    Copia os pacotes escolhidos para dentro do cliente.

    `escolhidos` e uma lista de caminhos de origem. Nada e sobrescrito: se ja
    existe um arquivo com aquele nome no cliente, ele nao era o que faltava, e
    a copia e recusada.

    A copia vai primeiro para um nome provisorio na propria pasta de destino e
    so depois e renomeada. Um cliente com metade de um .utx nao abre.
    """
    raiz = cliente.raiz if isinstance(cliente, Cliente) else raiz_do_cliente(cliente)
    resultados = []

    for origem in escolhidos:
        origem = Path(origem)
        destino = destino_no_cliente(raiz, origem)
        registro = {"origem": origem, "destino": destino, "ok": False, "motivo": ""}

        try:
            if destino.exists():
                registro["motivo"] = "ja existe no cliente"
            else:
                destino.parent.mkdir(parents=True, exist_ok=True)
                provisorio = destino.with_suffix(destino.suffix + ".parcial")
                provisorio.unlink(missing_ok=True)
                shutil.copy2(origem, provisorio)
                if provisorio.stat().st_size != origem.stat().st_size:
                    provisorio.unlink(missing_ok=True)
                    registro["motivo"] = "a copia saiu com tamanho diferente"
                else:
                    provisorio.replace(destino)
                    registro["ok"] = True
                    registro["motivo"] = conferir_instalado(destino)
        except OSError as erro:
            registro["motivo"] = str(erro)

        resultados.append(registro)
        if aolog:
            aolog("%s %s -> %s%s"
                  % ("instalado:" if registro["ok"] else "nao instalado:",
                     origem.name, destino.parent.name,
                     "  (%s)" % registro["motivo"] if registro["motivo"] else ""))

    return resultados


def conferir_instalado(caminho):
    """
    Abre o que acabou de ser copiado, para saber se o cliente vai conseguir.

    Num .utx isto e uma prova de verdade: a chave do Ver121 deriva do nome do
    arquivo, entao um pacote que chegou com outro nome nao decifra, e a
    assinatura nao bate. O erro aparece aqui, e nao na tela de carregamento.
    """
    try:
        with LeitorDePacote(caminho) as pacote:
            return "%d objetos" % pacote.qtd_exp
    except ErroDeLeitura:
        return "conteudo nao aberto (Blowfish)"
    except (OSError, struct.error, ValueError) as erro:
        return "atencao: %s" % erro
