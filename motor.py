#!/usr/bin/env python3
"""
L2PackTool -- upscale de texturas .utx do Lineage 2 (Interlude e afins).

Ciclo completo, sem interface grafica:

    .utx criptografado
      -> l2encdec -l        descriptografa
      -> umodel -export     extrai as texturas
      -> Pillow             TGA -> PNG
      -> upscayl-bin        amplia
      -> texconv            comprime em DXT5 com mipmaps (.dds)
      -> ucc make           remonta o pacote
      -> l2encdec -e 121    criptografa de volta

Escrito e validado contra um cliente Interlude real. Ver LEIA-ME.md para as
ressalvas -- em especial o custo de memoria, que e a razao mais comum de isto
dar errado na pratica.
"""

import argparse
import configparser
import os
import re
import shutil
import tempfile
import time
import subprocess
import sys
from pathlib import Path

import versao

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow nao instalado. Rode: pip install Pillow")

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
AQUI = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG = BASE / "config.ini"

# Nome do executavel (ou marca, no caso da pasta de modelos) de cada
# ferramenta. A busca e por NOME dentro de ferramentas/, recursivamente: assim
# nao importa como as subpastas foram nomeadas nem quantos niveis tem, e
# atualizar uma ferramenta e so trocar a pasta dela de lugar.
ALVOS = {
    "l2encdec": ["l2encdec_old.exe", "l2encdec.exe"],
    "umodel":   ["umodel.exe", "umodel_64.exe"],
    "upscayl":  ["upscayl-bin.exe"],
    "texconv":  ["texconv.exe"],
    "ucc":      ["UCC.exe"],
    "l2asm":    ["l2asm.exe"],
    "l2disasm": ["l2disasm.exe"],
    # So para video: GIF e animacao o Pillow le sozinho.
    "ffmpeg":   ["ffmpeg.exe"],
}

# A pasta de modelos nao tem executavel: e reconhecida pelos arquivos .param
# que o upscayl carrega.
MARCA_MODELOS = "*.param"

FERRAMENTAS_DIR = "ferramentas"


def descobrir(raiz):
    """
    Localiza as ferramentas dentro de ferramentas/, por nome de arquivo.

    Devolve so o que encontrar. O que faltar sera buscado no config.ini, e o
    que faltar dos dois e reportado ao usuario com o nome.
    """
    achados = {}
    if not raiz.is_dir():
        return achados

    # Um unico rglob por chave seria O(n) por ferramenta; percorremos a arvore
    # uma vez so e casamos pelo nome, que e barato.
    por_nome = {}
    for caminho in raiz.rglob("*"):
        if caminho.is_file():
            por_nome.setdefault(caminho.name.lower(), caminho)

    for chave, nomes in ALVOS.items():
        for nome in nomes:
            achado = por_nome.get(nome.lower())
            if achado:
                achados[chave] = achado
                break

    for param in raiz.rglob(MARCA_MODELOS):
        achados["modelos"] = param.parent
        break

    return achados



# ---------------------------------------------------------------------------
# Com que metodo cada tipo de arquivo volta a ser fechado.
#
# Nao da para perguntar ao arquivo: um arquivo aberto nao guarda de onde veio.
# Entao quem decide e a extensao, e por isso o nome do arquivo de saida importa
# tanto -- na versao 121 a chave ainda por cima deriva dele.
VERSAO_POR_EXTENSAO = {
    ".utx": "121",
    ".u": "111", ".unr": "111", ".usx": "111", ".ukx": "111",
    ".uax": "111", ".umx": "111",
    ".dat": "413", ".ini": "413",
}
VERSAO_PADRAO = "121"

NOME_DO_METODO = {
    "111": "Blowfish (Ver111)",
    "121": "XOR pelo nome (Ver121)",
    "413": "RSA (Ver413)",
}


def versao_de(caminho):
    """O metodo com que este arquivo volta a ser fechado."""
    return VERSAO_POR_EXTENSAO.get(Path(caminho).suffix.lower(), VERSAO_PADRAO)


def carregar_config():
    """
    Resolve os caminhos em tres camadas, nesta ordem:

      1. o que estiver dentro de ferramentas/  (dinamico, o caso normal)
      2. o que o config.ini apontar             (sobreposicao manual)
      3. nada -- reportado como ausente

    Com isso a pasta funciona ao ser copiada para qualquer lugar, e quem
    preferir apontar para instalacoes proprias ainda pode.
    """
    # Duas camadas, nesta ordem de prioridade:
    #
    #   1. ferramentas/ ao lado do executavel  -- permite atualizar uma
    #      ferramenta sem reconstruir nada
    #   2. ferramentas/ EMBUTIDA no executavel -- rede de seguranca: apagar a
    #      pasta externa por engano nao quebra o programa
    #
    # Na versao empacotada as duas existem; na enxuta, so a externa.
    resolvidos = descobrir(AQUI / FERRAMENTAS_DIR)
    resolvidos.update(descobrir(BASE / FERRAMENTAS_DIR))

    cfg = _ler_config()
    for chave, valor in cfg.items("ferramentas") if cfg.has_section("ferramentas") else []:
        if not valor.strip():
            continue
        caminho = Path(valor)
        if not caminho.is_absolute():
            caminho = BASE / caminho
        # O config.ini so entra onde a busca automatica nao achou nada, ou
        # onde ele aponta para algo que existe de fato.
        if chave not in resolvidos or caminho.exists():
            resolvidos[chave] = caminho

    for chave in list(ALVOS) + ["modelos"]:
        resolvidos.setdefault(chave, BASE / FERRAMENTAS_DIR / chave)

    return resolvidos


# Impede que cada subprocesso abra um console proprio no Windows.
#
# umodel, upscayl, texconv, ucc e l2encdec sao aplicativos de console: sem
# isto, a interface grafica pisca uma janela preta por ferramenta e por
# arquivo -- com dezenas de pacotes vira um desfile de janelas roubando o foco.
# CREATE_NO_WINDOW cobre o caso normal; o STARTUPINFO cobre os que criam
# console por conta propria, ignorando a flag.
_SEM_JANELA = {}
if os.name == "nt":
    _info = subprocess.STARTUPINFO()
    _info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _info.wShowWindow = 0            # SW_HIDE
    _SEM_JANELA = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        "startupinfo": _info,
    }


def _ler_config():
    """
    O config.ini, lido sem nunca levantar excecao.

    Arquivo torto -- secao faltando, linha solta, o BOM do Bloco de Notas --
    devolve um config vazio em vez de derrubar a janela: o que esta ali dentro
    e preferencia, e preferencia perdida se recompoe, programa fechado no
    arranque nao.
    """
    cfg = configparser.ConfigParser()
    if CONFIG.exists():
        try:
            cfg.read(CONFIG, encoding="utf-8-sig")
        except (configparser.Error, OSError, UnicodeDecodeError):
            return configparser.ConfigParser()
    return cfg


def ler_preferencias(padrao="upscayl-standard-4x"):
    """
    Escala e modelo escolhidos da ultima vez.

    Ficam no mesmo config.ini das ferramentas, em secao propria. Sao
    preferencia do usuario, nao configuracao de instalacao -- por isso o
    arquivo e opcional e a ausencia dele nao e problema.
    """
    cfg = _ler_config()
    if cfg.has_section("preferencias"):
        return (cfg.get("preferencias", "modelo", fallback=padrao),
                cfg.getint("preferencias", "escala", fallback=2))
    return padrao, 2


def gravar_preferencias(modelo, escala):
    """Guarda a escolha para a proxima abertura, preservando o resto do arquivo."""
    cfg = _ler_config()
    if not cfg.has_section("preferencias"):
        cfg.add_section("preferencias")
    cfg.set("preferencias", "modelo", str(modelo))
    cfg.set("preferencias", "escala", str(escala))
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            cfg.write(f)
    except Exception:
        pass    # sem permissao de escrita a interface segue funcionando


def ler_opcao(secao, chave, padrao=""):
    """Um valor guardado no config.ini. Ausencia nunca e erro."""
    cfg = _ler_config()
    return cfg.get(secao, chave, fallback=padrao)


def gravar_opcao(secao, chave, valor):
    """Guarda um valor preservando o resto do arquivo."""
    cfg = _ler_config()
    if not cfg.has_section(secao):
        cfg.add_section(secao)
    cfg.set(secao, chave, str(valor))
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            cfg.write(f)
    except OSError:
        pass    # sem permissao de escrita a interface segue funcionando


# Os programas de janela que este aqui abre e NAO espera: o visualizador do
# umodel e o UnrealEd. Ficam anotados para poderem ser fechados junto com a
# janela principal -- deixar um UnrealEd orfao consumindo meio giga de memoria
# depois que o programa sumiu da tela e o tipo de coisa que ninguem associa ao
# programa que fechou.
#
# As ferramentas de console nao entram aqui: `executar` espera cada uma
# terminar, entao nao ha o que fechar depois.
_FILHOS = []


def registrar_filho(processo, nome=""):
    """Anota um programa de janela que ficou aberto por nossa conta."""
    _FILHOS.append((processo, nome or "processo"))
    return processo


def filhos_vivos():
    """Os nomes dos que ainda estao de pe."""
    return [nome for processo, nome in _FILHOS if processo.poll() is None]


def encerrar_filhos(aolog=None):
    """
    Fecha o que continua aberto. Devolve quantos foram fechados.

    Pede educadamente (terminate) e, se em tres segundos o programa nao sair,
    insiste (kill). So mexe em processo que ESTE programa abriu e guardou --
    nunca procura por nome, que pegaria janelas do usuario.
    """
    fechados = 0
    for processo, nome in list(_FILHOS):
        if processo.poll() is not None:
            continue
        try:
            processo.terminate()
            for _ in range(30):
                if processo.poll() is not None:
                    break
                time.sleep(0.1)
            if processo.poll() is None:
                processo.kill()
            fechados += 1
            if aolog:
                aolog("%s fechado." % nome)
        except Exception as e:
            if aolog:
                aolog("nao consegui fechar %s: %s" % (nome, e))
    del _FILHOS[:]
    return fechados


def executar(cmd, cwd=None, mostrar=False, limite=3600):
    """
    Roda um comando. Devolve (codigo, saida). Nunca lanca.

    `limite` existe porque nem toda ferramenta desiste sozinha. O l2encdec, por
    exemplo, leva cento e nove segundos tentando adivinhar a chave de um
    LineageCreature.u de doze kilobytes antes de dizer que nao conseguiu --
    numa varredura de quarenta pacotes, um caso desses sozinho passa do tempo
    que o usuario aceita esperar.
    """
    try:
        r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                           capture_output=True, text=True, errors="replace", timeout=limite,
                           # Sem isto o subprocesso herda a entrada padrao e,
                           # se algum dia pedir uma tecla, fica parado para
                           # sempre esperando alguem que nao esta olhando. Foi
                           # o que o l2encdec fez com quatro pacotes do
                           # cliente: dez minutos de espera com 0,2 s de CPU.
                           # Com a entrada fechada ele le fim de arquivo e sai.
                           stdin=subprocess.DEVNULL,
                           **_SEM_JANELA)
        saida = (r.stdout or "") + (r.stderr or "")
        if mostrar and saida.strip():
            print("    " + saida.strip()[:1200].replace("\n", "\n    "))
        return r.returncode, saida
    except Exception as e:
        return -1, str(e)


def executar_fluxo(cmd, aoprogresso=None, cwd=None):
    """
    Como executar(), mas LENDO A SAIDA ENQUANTO O PROCESSO RODA.

    O upscayl-bin imprime o andamento em porcentagem a cada tile terminado
    ("0,00%", "11,11%", ...), separado por retorno de carro e nao por quebra de
    linha. Com capture_output nada disso aparece ate o fim -- e como uma
    textura de 1024 leva minutos numa GPU integrada, o programa inteiro parecia
    congelado. Lendo byte a byte cada porcentagem chega na hora.

    Detalhe: o numero sai com o separador decimal DO SISTEMA, entao em maquina
    brasileira vem "11,11%" e nao "11.11%". Trocar a virgula por ponto antes de
    converter e o que faz isto funcionar fora do ingles.

    `aoprogresso` recebe a fracao ja pronta, de 0.0 a 1.0.
    """
    import re
    padrao = re.compile(r"^(\d+[.,]?\d*)\s*%$")
    linhas = []
    try:
        p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, bufsize=0, **_SEM_JANELA)
    except Exception as e:
        return -1, str(e)

    pedaco = b""
    while True:
        c = p.stdout.read(1)
        if not c:
            break
        if c in (b"\r", b"\n"):
            texto = pedaco.decode("utf-8", "replace").strip()
            pedaco = b""
            if not texto:
                continue
            achado = padrao.match(texto)
            if achado and aoprogresso:
                try:
                    aoprogresso(min(1.0, float(achado.group(1).replace(",", ".")) / 100.0))
                except ValueError:
                    pass
            elif not achado:
                linhas.append(texto)
        else:
            pedaco += c

    p.wait()
    return p.returncode, "\n".join(linhas[-40:])


def versao_pacote(caminho):
    """Assinatura, versao e licensee de um pacote Unreal JA descriptografado."""
    import struct
    try:
        with open(caminho, "rb") as f:
            dados = f.read(8)
        sig, ver, lic = struct.unpack("<IHH", dados)
        return (sig, ver, lic) if sig == 0x9E2A83C1 else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Etapas
# ---------------------------------------------------------------------------
def descriptografar(T, utx, destino):
    """
    ATENCAO: na versao 121 a chave XOR deriva do NOME DO ARQUIVO. Renomear no
    meio do processo nao da erro -- produz lixo em silencio. Por isso o nome
    original e preservado em todas as etapas.
    """
    destino.mkdir(parents=True, exist_ok=True)
    aberto = destino / "aberto"
    aberto.mkdir(parents=True, exist_ok=True)
    saida_direta = aberto / utx.name

    # Nem todo arquivo do cliente esta criptografado -- varios .u e alguns
    # .utx vem com a assinatura Unreal crua. Passar um desses pelo l2encdec
    # produz lixo, e o sintoma e um "assinatura invalida" que parece erro de
    # chave quando na verdade nao havia nada para decifrar.
    if versao_pacote(utx) is not None:
        shutil.copy2(utx, saida_direta)
        info = versao_pacote(saida_direta)
        return saida_direta, "ja aberto, versao=%d licensee=%d" % (info[1], info[2])

    copia = destino / utx.name
    shutil.copy2(utx, copia)
    rel = os.path.join("aberto", utx.name)

    executar([T["l2encdec"], "-l", copia.name, rel], cwd=destino)
    saida = aberto / utx.name

    if versao_pacote(saida) is None:
        executar([T["l2encdec"], "-s", copia.name, rel], cwd=destino)

    # A copia criptografada so existia para dar ao l2encdec um arquivo com o
    # nome certo no diretorio de trabalho (a chave da versao 121 deriva do
    # nome). Cumprido o papel, ela e uma duplicata exata do .utx de origem.
    copia.unlink(missing_ok=True)

    info = versao_pacote(saida)
    return (saida, "versao=%d licensee=%d" % (info[1], info[2])) if info else (None, "assinatura invalida")


def extrair(T, pacote, saida_dir):
    """
    O umodel decide sozinho entre TGA e PNG conforme a textura tenha alfa, e
    nao ha opcao de formato -- por isso a coleta aceita os dois.
    """
    saida_dir.mkdir(parents=True, exist_ok=True)
    _, log = executar([T["umodel"], "-export", "-game=l2", "-out=" + str(saida_dir), str(pacote)])
    return list(saida_dir.rglob("*.tga")) + list(saida_dir.rglob("*.png")), log


# Acima deste numero de texturas, exportar o pacote inteiro de uma vez sai mais
# barato do que uma chamada por textura. Medido no umodel: cada chamada custa a
# abertura do pacote (~0,3 s no cliente tipico), enquanto a exportacao em si e
# copia de bytes.
LIMITE_POR_OBJETO = 12


def extensao_de_exportacao(info):
    """
    Em que arquivo esta textura vai sair.

    Formato comprimido vira .dds, que e o unico recipiente que guarda bloco DXT
    sem descomprimir. O resto sai .tga, que e o que o umodel escreve quando nao
    ha o que comprimir -- pixel cru, sem perda.
    """
    formato = (info or {}).get("formato", "")
    return ".dds" if formato in FORMATO_TEXCONV and formato != "TEXF_RGBA8" else ".tga"


def exportar(T, pacote, nomes, destino, progresso=None, aolog=None):
    """
    Tira texturas do pacote COMO ELAS ESTAO, sem passar por conversao nenhuma.

    E o que o L2Tool faz e o que o resto deste programa nao fazia: as outras
    etapas descomprimem para PNG porque precisam de pixel para ampliar. Aqui
    nao -- quem exporta quer o arquivo original, para abrir no Photoshop, guardar
    antes de mexer, ou levar para outro pacote.

    O umodel copia os blocos DXT para dentro de um .dds sem tocar neles: os bytes
    do arquivo exportado sao os mesmos bytes que estao dentro do .utx. Textura
    sem compressao (RGBA8, P8, L8) sai em .tga, que tambem e o pixel como esta.

    `nomes` sao os nomes das texturas (o mesmo que aparece na miniatura). Devolve
    a lista de arquivos gravados em `destino`.
    """
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    nomes = list(nomes)
    if not nomes:
        return []

    with tempfile.TemporaryDirectory(prefix="l2pack_exp_") as tmp:
        tmp = Path(tmp)
        base = [T["umodel"], "-export", "-dds", "-game=l2", "-out=" + str(tmp)]

        if len(nomes) <= LIMITE_POR_OBJETO:
            for i, nome in enumerate(nomes, 1):
                executar(base + ["-obj=" + nome, str(pacote)], limite=300)
                if progresso:
                    progresso(i, len(nomes))
        else:
            # Uma chamada so, o pacote inteiro; depois se escolhe o que levar.
            executar(base + [str(pacote)], limite=1800)
            if progresso:
                progresso(len(nomes), len(nomes))

        # O umodel exporta em <pacote>/Texture/, e o nome do arquivo mantem a
        # caixa do objeto -- que nem sempre e a que o chamador tem em maos.
        achados = {}
        for arquivo in tmp.rglob("*"):
            if arquivo.is_file():
                achados.setdefault(arquivo.stem.lower(), arquivo)

        gravados = []
        for nome in nomes:
            origem = achados.get(nome.lower())
            if origem is None:
                if aolog:
                    aolog("%s: o umodel nao exportou nada" % nome)
                continue
            alvo = destino / origem.name
            shutil.copy2(origem, alvo)
            gravados.append(alvo)

    return gravados


def converter(imagens, destino, extensao):
    """
    Converte e ACHATA a arvore.

    Duas razoes: o upscayl so le jpg/png/webp -- alimentado com TGA ele
    responde "Couldn't read the image" e ainda assim devolve codigo zero, ou
    seja, falha em silencio; e em modo diretorio ele nao desce em subpastas,
    enquanto o umodel exporta em <pacote>/Texture/.
    """
    destino.mkdir(parents=True, exist_ok=True)
    saidas = []
    for img in sorted(imagens):
        alvo = destino / (img.stem + extensao)
        try:
            with Image.open(img) as im:
                im.convert("RGBA").save(alvo)
            saidas.append(alvo)
        except Exception as e:
            print("    aviso: %s nao convertida (%s)" % (img.name, e))
    return saidas


def limpar_gama(png):
    """
    Remove do PNG os marcadores de espaco de cor: sRGB, gAMA, iCCP e cHRM.

    O upscayl grava "sRGB" e "gAMA=0,45455" na saida. O texconv respeita esses
    campos: le a imagem como sRGB e, ao gravar em BC3_UNORM (que e linear),
    converte -- e a textura sai com menos da metade do brilho. Uma media de
    (113,99,99) virava (51,43,43), visivel no jogo como um pacote inteiro
    escurecido.

    O ciclo antigo escapava disso por acaso: convertia PNG -> TGA antes de
    comprimir, e o TGA nao tem onde guardar esses campos. Trocar o TGA por PNG
    direto -- que poupa uma copia de cada textura em disco -- so e seguro
    apagando os campos aqui.

    Apagar chunk de PNG nao exige recalcular nada: cada um leva o proprio CRC,
    entao basta nao copiar os indesejados. Textura de jogo e amostrada crua
    pelo cliente; nao ha espaco de cor a preservar.
    """
    import struct
    ASSINATURA = b"\x89PNG\r\n\x1a\n"
    FORA = {b"sRGB", b"gAMA", b"iCCP", b"cHRM"}
    try:
        dados = png.read_bytes()
    except OSError:
        return False
    if not dados.startswith(ASSINATURA):
        return False    # nao e PNG (o upscayl tambem grava jpg/webp se pedirem)

    saida = bytearray(ASSINATURA)
    i, mexeu = len(ASSINATURA), False
    while i + 8 <= len(dados):
        tamanho = struct.unpack(">I", dados[i:i + 4])[0]
        tipo = dados[i + 4:i + 8]
        fim = i + 12 + tamanho
        if fim > len(dados):
            return False    # arquivo truncado: melhor nao reescrever nada
        if tipo in FORA:
            mexeu = True
        else:
            saida += dados[i:fim]
        i = fim
        if tipo == b"IEND":
            break

    if mexeu:
        png.write_bytes(bytes(saida))
    return mexeu


def ampliar(T, entrada, saida, escala, modelo, progresso=None):
    """
    Amplia UMA IMAGEM POR VEZ, e nao o diretorio inteiro numa chamada.

    O modo diretorio do upscayl e um pouco mais rapido, porque carrega o modelo
    uma vez so, mas nao devolve nada ate terminar tudo. Chamando por imagem,
    cada uma reporta ao terminar -- e, com executar_fluxo, tambem reporta o
    andamento DENTRO da imagem, tile a tile. Isso importa: numa GPU integrada
    uma textura de 1024 leva minutos sozinha, e sem o andamento interno a barra
    ficava parada esse tempo todo, na primeira imagem, sem nada na tela
    provando que o trabalho estava andando.

    `entrada` aceita uma pasta ou uma lista de imagens. A lista evita ter de
    copiar as marcadas para uma pasta a parte so para poder passar um diretorio.

    `progresso` recebe (indice, total, nome, fracao), com fracao de 0.0 a 1.0
    dentro da imagem atual.
    """
    saida.mkdir(parents=True, exist_ok=True)
    if isinstance(entrada, Path):
        entrada = entrada.glob("*.png")
    imagens = sorted(entrada, key=lambda p: p.name.lower())
    total = len(imagens)
    feitas = []

    for i, img in enumerate(imagens, 1):
        alvo = saida / img.name
        if progresso:
            progresso(i, total, img.name, 0.0)

        dentro = None
        if progresso:
            def dentro(f, _i=i, _n=img.name):
                progresso(_i, total, _n, f)

        executar_fluxo([T["upscayl"], "-i", str(img), "-o", str(alvo),
                        "-s", str(escala), "-n", modelo,
                        "-m", str(T["modelos"]), "-f", "png"], dentro)

        if alvo.exists():
            limpar_gama(alvo)
            feitas.append(alvo)
        if progresso:
            progresso(i, total, img.name, 1.0)

    return feitas


# Como cada formato do Unreal se escreve num DDS que o texconv produz e o
# editor reimporta. So estes quatro tem correspondencia exata; o que nao estiver
# aqui nao tem como voltar ao formato de origem -- ver `formato_alvo`.
FORMATO_TEXCONV = {
    "TEXF_DXT1":  "BC1_UNORM",
    "TEXF_DXT3":  "BC2_UNORM",
    "TEXF_DXT5":  "BC3_UNORM",
    "TEXF_RGBA8": "B8G8R8A8_UNORM",
}

# Campos que o painel mostra alem dos quatro que o programa usa para decidir a
# compressao. Sao os mesmos que o l2tool exibe.
PROPRIEDADES_EXTRA = (
    "UBits", "VBits", "UClamp", "VClamp", "UClampMode", "VClampMode",
    "LODSet", "NormalLOD", "MinLOD", "StrippedNumMips", "HasBeenStripped",
    "bTwoSided", "bHighColorQuality", "bHighTextureQuality", "bRealtime",
    "DetailScale", "Detail", "Palette", "AnimNext", "SurfaceType",
)

_CABECA_DUMP = re.compile(r"^ClassName:\s+(\S+)\s+ObjectName:\s+(.+?)\s*$")
_CAMPO_DUMP = re.compile(r"^\s+(\w+)\s+=\s+(.+?)\s*$")


def inventario(T, pacote):
    """
    O formato, o tamanho e o uso de alfa de cada textura do pacote.

    Devolve {nome em minusculas: {formato, largura, altura, alfa, mascarado}}.

    Sem isto o programa comprimia tudo em BC3, o que erra de duas formas ao
    mesmo tempo: uma textura opaca que era DXT1 dobrava de tamanho sem ganhar
    nada, e o pacote inteiro passava a ter um formato que nao era o do jogo. O
    umodel responde isso para um pacote inteiro em menos de um segundo, e le
    direto do .utx criptografado -- nem precisa descriptografar antes.
    """
    codigo, texto = executar([T["umodel"], "-dump", "-game=l2", str(pacote)])

    achados = {}
    atual = None
    for linha in texto.split("\n"):
        cabeca = _CABECA_DUMP.match(linha)
        if cabeca:
            atual = {"classe": cabeca.group(1), "nome": cabeca.group(2)}
            continue

        if atual is None:
            continue

        campo = _CAMPO_DUMP.match(linha)
        if not campo:
            continue

        chave, valor = campo.group(1), campo.group(2)
        if chave == "Format":
            atual["formato"] = valor.split()[0]
        elif chave == "USize":
            atual["largura"] = int(valor)
        elif chave == "VSize":
            atual["altura"] = int(valor)
        elif chave == "bAlphaTexture":
            atual["alfa"] = (valor == "true")
        elif chave == "bMasked":
            atual["mascarado"] = (valor == "true")
        # O resto nao entra em nenhuma decisao do programa: e para o painel de
        # propriedades, que existe para quem vai trocar a textura saber o que
        # esta trocando.
        elif chave in PROPRIEDADES_EXTRA:
            atual[chave] = valor

        # O nome so entra no inventario quando ja se sabe formato E tamanho,
        # que sao os ultimos campos do bloco. Assim um bloco truncado nao vira
        # uma entrada pela metade.
        if atual.get("classe") == "Texture" and "formato" in atual and "altura" in atual:
            achados[atual["nome"].lower()] = atual

    return achados


def abrir_imagem(caminho, T=None):
    """
    Abre qualquer imagem que o usuario escolher, inclusive DDS exotico.

    O Pillow le PNG, JPG, TGA, BMP, WEBP e a maior parte dos DDS (BC1 a BC7).
    O que ele ainda recusa sao os DDS de nicho -- BC6H, mapas de normal em
    ATI2/3Dc, cabecalho DX10 com formato incomum, cubemap. Nesses casos o
    texconv converte para PNG num temporario e o Pillow le o PNG: a ferramenta
    que ja comprime na saida tambem sabe descomprimir na entrada.

    Devolve uma imagem RGBA carregada na memoria -- nenhum arquivo temporario
    fica para tras.
    """
    caminho = Path(caminho)
    try:
        with Image.open(caminho) as im:
            im.load()
            return im.convert("RGBA")
    except Exception as erro_pillow:
        texconv = (T or {}).get("texconv")
        if not texconv or not Path(texconv).exists():
            raise

        import tempfile
        with tempfile.TemporaryDirectory(prefix="l2pack_") as tmp:
            executar([texconv, "-nologo", "-y", "-ft", "png", "-f",
                      "R8G8B8A8_UNORM", "-m", "1", "-o", tmp, str(caminho)],
                     limite=120)
            saidas = list(Path(tmp).glob("*.png"))
            if not saidas:
                raise erro_pillow
            with Image.open(saidas[0]) as im:
                im.load()
                return im.convert("RGBA")


def medir_imagem(caminho, T=None):
    """Tamanho e alfa de uma imagem, sem carregar o que nao precisa."""
    try:
        with Image.open(caminho) as im:
            tem = im.mode in ("RGBA", "LA", "PA") and                 im.convert("RGBA").getchannel("A").getextrema()[0] < 255
            return im.size, tem, (im.format or "")
    except Exception:
        pass
    # Formato que o Pillow recusa: vale o desvio pelo texconv.
    im = abrir_imagem(caminho, T)
    return im.size, im.getchannel("A").getextrema()[0] < 255, "DDS"


def notas_da_substituta(origem, info, largura, altura, T=None):
    """
    O que vai ser ajustado nesta imagem para ela caber no lugar da textura.

    Serve para dizer ANTES de processar, e nao depois: o usuario escolhe um
    arquivo e ja ve o que o programa vai fazer com ele -- redimensionar,
    recortar, herdar o alfa, gravar em outro formato. Devolve uma lista de
    frases curtas, vazia quando a imagem ja chega do jeito que o pacote quer.

    Cada frase e um par (chave, valores) e nao um texto pronto, porque quem
    monta a frase e a interface, que sabe o idioma.
    """
    notas = []
    try:
        (l, a), alfa_nova, formato = medir_imagem(origem, T)
    except Exception as e:
        return [("erro", (str(e),))]

    largura, altura = int(largura), int(altura)
    if (l, a) != (largura, altura):
        notas.append(("tamanho", (l, a, largura, altura)))
        if abs((float(l) / a) - (float(largura) / altura)) > 0.01:
            notas.append(("proporcao", ()))

    if (info or {}).get("alfa") and not alfa_nova:
        notas.append(("alfa", ()))

    # O formato de saida e sempre o que o PACOTE pede para aquela textura, e
    # nao o do arquivo escolhido: DDS entrando nao quer dizer DDS do mesmo tipo,
    # e PNG entrando nao vira PNG no pacote. Por isso a nota aparece sempre.
    rotulo, observacao = formato_alvo(info, origem)
    original = (info or {}).get("formato", "").replace("TEXF_", "")
    notas.append(("formato", (formato or "?", original or "?", rotulo)))
    if observacao:
        notas.append(("aviso", (observacao,)))

    return notas


def tem_alfa(imagem):
    """True se a imagem tiver algum pixel que nao seja totalmente opaco."""
    try:
        with Image.open(imagem) as im:
            if im.mode not in ("RGBA", "LA", "PA"):
                return False
            return im.convert("RGBA").getchannel("A").getextrema()[0] < 255
    except Exception:
        return False


def formato_alvo(info, imagem):
    """
    O formato em que esta textura deve ser regravada, e o porque.

    Devolve (rotulo do texconv, observacao ou vazio). A regra e simples: se o
    formato original tem equivalente exato, usa-se ele -- a textura sai do
    programa como entrou, so com mais pixels. Formatos sem equivalente (P8, L8,
    G16, RGBA7) sao os legados: nao ha como voltar a uma paleta depois de
    ampliar, entao escolhe-se pelo alfa e a troca fica registrada, porque uma
    substituicao silenciosa e a que ninguem descobre.
    """
    original = (info or {}).get("formato", "")
    exato = FORMATO_TEXCONV.get(original)
    if exato:
        return exato, ""

    escolhido = "BC3_UNORM" if tem_alfa(imagem) else "BC1_UNORM"
    if not original:
        return escolhido, "nao estava no inventario; escolhi %s pelo alfa" % escolhido

    return escolhido, "%s nao tem equivalente em DDS; escolhi %s" % (original, escolhido)


def comprimir(T, entrada, saida_dir, formatos=None, progresso=None, aviso=None):
    """
    Comprime para DDS com mipmaps, via texconv, NO FORMATO DE CADA TEXTURA.

    `formatos` e o inventario devolvido por `inventario()`. Sem ele cada imagem
    e julgada so pelo alfa, que e o melhor palpite possivel mas continua sendo
    palpite -- passe o inventario sempre que o pacote de origem estiver a mao.

    O editor chamaria xDxTex.exe para comprimir na importacao, mas esse
    executavel nao vem nos builds de L2Editor que circulam -- o sintoma sao
    linhas "Error spawning xDxTex.exe" e texturas entrando CRUAS, quatro vezes
    maiores. Comprimindo antes e importando DDS, ele nao precisa ser chamado.

    Le PNG direto: o texconv aceita PNG e produz o mesmo DDS que produziria a
    partir de um TGA, entao a conversao intermediaria so gastava disco.
    """
    saida_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(entrada, Path):
        entrada = list(entrada.glob("*.png")) + list(entrada.glob("*.tga"))

    imagens = sorted(entrada, key=lambda p: p.name.lower())
    if not imagens:
        return []

    # Uma chamada por formato, e nao uma por textura: o texconv aceita varios
    # arquivos de uma vez, e sao tres ou quatro grupos no pacote tipico.
    grupos = {}
    for img in imagens:
        rotulo, observacao = formato_alvo((formatos or {}).get(img.stem.lower()), img)
        grupos.setdefault(rotulo, []).append(img)
        if observacao and aviso:
            aviso("%s: %s" % (img.stem, observacao))

    feitas = 0
    for rotulo, lista in sorted(grupos.items()):
        arquivos = [str(p) for p in lista]
        # Em lotes: a linha de comando do Windows para em 32 KB, e um pacote
        # com centenas de texturas e caminhos longos passa disso.
        LOTE = 48
        for k in range(0, len(arquivos), LOTE):
            executar([T["texconv"], "-f", rotulo, "-m", "0", "-y",
                      "-o", str(saida_dir)] + arquivos[k:k + LOTE])
            feitas += len(arquivos[k:k + LOTE])
            if progresso:
                progresso(feitas, len(imagens))

    return sorted(saida_dir.glob("*.dds"))


def resumo_formatos(imagens, formatos):
    """Quantas texturas foram para cada formato. Serve so para o registro."""
    contagem = {}
    for img in imagens:
        rotulo, _ = formato_alvo((formatos or {}).get(img.stem.lower()), img)
        contagem[rotulo] = contagem.get(rotulo, 0) + 1
    return ", ".join("%s: %d" % (k, v) for k, v in sorted(contagem.items()))


def preparar_substituta(origem, destino, largura, altura, alfa_de=None, T=None):
    """
    Encaixa uma imagem escolhida pelo usuario no lugar de uma textura do pacote.

    Tres coisas precisam continuar como estavam, ou o cliente reclama ou o
    desenho quebra:

      TAMANHO   o cliente usa potencias de dois, com UBits/VBits gravados no
                pacote; entregar uma imagem de outro tamanho e pedir problema.
                A imagem nova e reamostrada para o tamanho exato da antiga.

      PROPORCAO reamostrar para uma proporcao diferente esticaria o desenho. A
                imagem e cortada no centro ate a proporcao certa antes de ser
                reduzida -- cortar tira conteudo das bordas, mas esticar
                estraga tudo o que sobrou.

      ALFA      se a textura original tinha alfa e a nova nao tem, o alfa
                antigo e reaproveitado. Uma placa que era recortada nao pode
                virar um retangulo opaco so porque o arquivo novo veio sem
                canal de transparencia.

    FORMATO    nao e decidido aqui: quem cuida disso e `comprimir`, com o
               inventario do pacote, exatamente como faz com as ampliadas. O
               que vale e o que AQUELA textura era no pacote -- DXT1, DXT3,
               DXT5, RGBA8 ou um legado sem equivalente. O arquivo escolhido
               so entra como pixel: um DDS BC7 vira DXT1 se a textura antiga
               era DXT1, e um PNG vira DXT5 se ela era DXT5.

    A imagem de entrada pode ser qualquer coisa que o Pillow ou o texconv
    leiam, DDS incluso -- ver `abrir_imagem`.
    """
    nova = abrir_imagem(origem, T)

    largura, altura = int(largura), int(altura)
    alvo = float(largura) / float(altura)
    atual = float(nova.width) / float(nova.height)
    if abs(alvo - atual) > 0.01:
        if atual > alvo:                    # sobra largura
            corte = int(round(nova.height * alvo))
            esquerda = (nova.width - corte) // 2
            nova = nova.crop((esquerda, 0, esquerda + corte, nova.height))
        else:                               # sobra altura
            corte = int(round(nova.width / alvo))
            topo = (nova.height - corte) // 2
            nova = nova.crop((0, topo, nova.width, topo + corte))

    nova = nova.resize((largura, altura), Image.LANCZOS)

    observacao = ""
    if alfa_de and Path(alfa_de).exists() and nova.getchannel("A").getextrema()[0] == 255:
        with Image.open(alfa_de) as antiga:
            if antiga.mode in ("RGBA", "LA", "PA"):
                canal = antiga.convert("RGBA").getchannel("A")
                if canal.getextrema()[0] < 255:
                    nova.putalpha(canal.resize((largura, altura), Image.LANCZOS))
                    observacao = "alfa herdado da textura original"

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    nova.save(destino)
    return destino, observacao


def montar(T, nome, dds, raiz_editor, nomes_extras=(), grupos=None):
    """
    Gera o .uc e roda `ucc make`.

    MIPS=Off porque o DDS ja traz os mipmaps prontos; deixar On faria o editor
    regera-los e perder a compressao. O Build.ini isolado existe porque o
    UT2003.ini lista pacotes cujo codigo-fonte nao acompanha os builds, e o
    `ucc make` para no primeiro deles.

    `nomes_extras` sao nomes que precisam existir na TABELA DE NOMES do pacote
    mesmo sem serem usados por textura nenhuma. A tabela de nomes so guarda o
    que o pacote cita, e uma propriedade marcada e identificada pelo indice do
    nome dela ali dentro -- entao um nome ausente e uma propriedade que nao ha
    como escrever depois. Declarar uma variavel com aquele nome poe o nome na
    tabela; a variavel em si nao faz nada.
    """
    system = T["ucc"].parent
    pasta = raiz_editor / nome
    shutil.rmtree(pasta, ignore_errors=True)
    (pasta / "Classes").mkdir(parents=True)

    linhas = ["// Gerado por L2PackTool -- nao editar a mao.",
              "class %s extends Object;" % nome, ""]
    for extra in nomes_extras:
        linhas.append("var Texture %s;   // so para o nome entrar na tabela"
                      % extra)
    if nomes_extras:
        linhas.append("")
    # O GRUPO importa. Uma textura mora em `pacote.grupo.nome`, e e por esse
    # caminho inteiro que o mapa e a interface a pedem. Jogar tudo num grupo
    # novo funciona quando o pacote e nosso, mas quebra quando estamos
    # refazendo um pacote do cliente: o mapa continua pedindo o grupo antigo.
    # Por isso `grupos` manda, e "Upscaled" e so o padrao de quem nao informa.
    grupos = grupos or {}
    for d in dds:
        grupo = grupos.get(d.stem, grupos.get(d.stem.lower(), "Upscaled"))
        # Grupo vazio nao e "Upscaled": e textura que mora na raiz do pacote, e
        # ai a clausula GROUP nao entra. Escrever `GROUP=` sem valor faz o ucc
        # engasgar sem dizer onde.
        linhas.append('#exec TEXTURE IMPORT NAME=%s FILE="%s"%s MIPS=Off'
                      % (d.stem, d.resolve(),
                         (" GROUP=" + grupo) if grupo else ""))
    (pasta / "Classes" / (nome + ".uc")).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # Build.ini: so os pacotes ja compilados, mais o nosso.
    origem = system / "UT2003.ini"
    build = system / "Build.ini"
    manter = {"Core", "Engine", "Editor", "UnrealEd"}
    linhas_ini, inserido = [], False
    for l in origem.read_text(encoding="utf-8", errors="replace").split("\n"):
        if l.startswith("EditPackages="):
            alvo = l.split("=", 1)[1].strip()
            if alvo in manter:
                linhas_ini.append(l)
            elif not inserido:
                inserido = True
                linhas_ini.append("EditPackages=" + nome)
            continue
        linhas_ini.append(l)
    if not inserido:
        linhas_ini.append("EditPackages=" + nome)
    build.write_text("\n".join(linhas_ini), encoding="utf-8", errors="replace")

    destino_u = system / (nome + ".u")
    destino_u.unlink(missing_ok=True)
    _, log = executar([T["ucc"], "make", "-ini=Build.ini"], cwd=system)
    shutil.rmtree(pasta, ignore_errors=True)
    build.unlink(missing_ok=True)   # gerado a cada execucao; nao serve depois
    return (destino_u if destino_u.exists() else None), log


def criptografar(T, pacote, nome_final, destino, cifrar=True, versao="121"):
    """
    Criptografa com o NOME FINAL, nunca com um temporario: a chave da versao
    121 deriva do nome do arquivo de saida.

    Com cifrar=False apenas copia: o arquivo de entrada nao estava
    criptografado, e devolver criptografado mudaria o formato em relacao ao
    original sem que ninguem tivesse pedido.

    `versao` tem de ser a mesma do arquivo que veio. O cliente escolhe como
    decifrar pelo cabecalho, nao pela extensao, mas um .usx que saiu como 111 e
    voltou como 121 e um arquivo diferente do que o resto do jogo espera --
    entao quem chama informa o que leu com l2npc.metodo_do_arquivo().
    """
    destino.mkdir(parents=True, exist_ok=True)

    if not cifrar:
        alvo = destino / nome_final
        shutil.copy2(pacote, alvo)
        return alvo, True

    plano = destino / "_plano.bin"
    shutil.copy2(pacote, plano)
    alvo = destino / nome_final

    executar([T["l2encdec"], "-e", str(versao), plano.name, alvo.name],
             cwd=destino)
    plano.unlink(missing_ok=True)

    # Prova de integridade: descriptografa de volta e compara.
    if alvo.exists():
        volta = destino / "_volta.bin"
        executar([T["l2encdec"], "-l", alvo.name, volta.name], cwd=destino)
        ok = volta.exists() and volta.read_bytes() == pacote.read_bytes()
        volta.unlink(missing_ok=True)
        return alvo, ok
    return None, False


# ---------------------------------------------------------------------------
def processar(T, utx, trabalho, saida_final, escala, modelo, parar_em):
    print("\n=== %s ===" % utx.name)
    base = trabalho / utx.stem
    shutil.rmtree(base, ignore_errors=True)

    estava_cifrado = versao_pacote(utx) is None

    dec, detalhe = descriptografar(T, utx, base / "dec")
    if dec is None:
        print("  ERRO ao descriptografar: %s" % detalhe)
        return False
    print("  descriptografado (%s)" % detalhe)
    if parar_em == "descriptografar":
        return True

    formatos = inventario(T, utx)
    print("  inventario: %d texturas com formato conhecido" % len(formatos))

    imagens, log = extrair(T, dec, base / "extraido")
    if not imagens:
        print("  ERRO: nenhuma textura extraida")
        print("    " + log.strip()[-300:].replace("\n", "\n    "))
        return False
    print("  extraidas: %d texturas" % len(imagens))
    if parar_em == "extrair":
        return True

    converter(imagens, base / "png", ".png")
    # O que o umodel cuspiu ja virou PNG; manter as duas arvores so duplicava
    # cada textura em disco.
    shutil.rmtree(base / "extraido", ignore_errors=True)
    shutil.rmtree(base / "dec", ignore_errors=True)

    ultimo = [""]

    def andamento(i, total, nome, fracao):
        marca = "  %d/%d  %s  %3d%%" % (i, total, nome, round(fracao * 100))
        if marca != ultimo[0]:
            ultimo[0] = marca
            print(marca + "        ", end="\r", flush=True)

    ampliadas = ampliar(T, base / "png", base / "ampliado", escala, modelo, andamento)
    print()
    if not ampliadas:
        print("  ERRO: upscayl nao gerou nada")
        return False
    print("  ampliadas: %d (%dx, %s)" % (len(ampliadas), escala, modelo))

    dds = comprimir(T, ampliadas, base / "dds", formatos=formatos,
                    aviso=lambda m: print("    " + m))
    if not dds:
        print("  ERRO: texconv nao gerou DDS")
        return False
    print("  comprimidas: %d  (%s)"
          % (len(dds), resumo_formatos(ampliadas, formatos)))
    if parar_em == "comprimir":
        return True

    pacote, log = montar(T, utx.stem, dds, T["ucc"].parent.parent)
    if pacote is None:
        print("  ERRO no ucc make")
        print("    " + log.strip()[-400:].replace("\n", "\n    "))
        return False
    info = versao_pacote(pacote)
    print("  pacote montado: %d bytes (versao=%d licensee=%d)"
          % (pacote.stat().st_size, info[1], info[2]))

    final, integro = criptografar(T, pacote, utx.name, saida_final, estava_cifrado)
    pacote.unlink(missing_ok=True)      # copia do ucc, dentro do System do editor
    if final is None:
        print("  ERRO ao criptografar")
        return False
    print("  %s: %s (%d bytes)%s"
          % ("criptografado" if estava_cifrado else "gravado",
             final.name, final.stat().st_size,
             "" if integro else "  [AVISO: ida e volta nao confere]"))

    # O .utx final ja esta em saida/. Tudo em trabalho/ e intermediario: cada
    # textura existia ali como PNG original, PNG ampliado e DDS.
    if integro and not parar_em:
        shutil.rmtree(base, ignore_errors=True)
        try:
            trabalho.rmdir()    # so sai se estiver vazia; com lote, a ultima apaga
        except OSError:
            pass
    return integro


# ---------------------------------------------------------------------------
# A linha de comando
#
# Ela serve ao que se faz em lote e sem escolher na tela: abrir e fechar
# arquivo do cliente, ampliar textura, conferir o que falta. Editar mob,
# multisell, item e skill continua na interface, que e onde se ve o que se
# esta mudando antes de gravar.
#
# O texto daqui sai sem acento: o console do Windows abre em cp1252, e um
# acento em canal redirecionado vira erro de codificacao no meio de um lote.
# ---------------------------------------------------------------------------

COMANDOS = (
    ("upscale", "amplia as texturas de um .utx e remonta o pacote"),
    ("abrir", "descriptografa arquivo do cliente (.dat .utx .u .unr .ini)"),
    ("fechar", "criptografa de volta, com o nome que o jogo espera"),
    ("extrair", "tira as texturas de um pacote, como imagens"),
    ("listar", "mostra a versao e os objetos de um pacote"),
    ("conferir", "confere o cliente e diz que arquivo falta"),
    ("lobby", "poe o video na tela de login de um lobby, com camera fixa"),
    ("ferramentas", "diz quais ferramentas foram encontradas, e onde"),
    ("ajuda", "esta lista; `ajuda <comando>` detalha um deles"),
)

EXEMPLOS = """exemplos

  L2PackTool-cli upscale Fantasy.utx -s 2
  L2PackTool-cli upscale C:\\texturas -s 2 -o C:\\saida
  L2PackTool-cli abrir "C:\\Lineage II\\system\\itemname-e.dat" -o .\\aberto
  L2PackTool-cli fechar .\\aberto\\itemname-e.dat -o .\\fechado
  L2PackTool-cli extrair Fantasy.utx -o .\\texturas
  L2PackTool-cli listar Fantasy.utx
  L2PackTool-cli conferir "C:\\Lineage II" -o relatorio.txt
  L2PackTool-cli lobby "C:\\Lineage II"

o que a interface faz e a linha de comando nao

  editar mob, multisell, item, skill e criar NPC. Sao trabalhos de escolher
  na tela e ver o efeito antes de gravar; em parametro de comando eles
  virariam uma lista longa sem conferencia possivel.
"""


def texto_da_ajuda():
    largura = max(len(nome) for nome, _ in COMANDOS)
    linhas = ["", "L2PackTool-cli <comando> [opcoes]", "", "comandos"]
    for nome, resumo in COMANDOS:
        linhas.append("  %-*s  %s" % (largura, nome, resumo))
    linhas += ["",
               "`<comando> -h` mostra as opcoes daquele comando.",
               "",
               EXEMPLOS]
    return "\n".join(linhas)


def _alvos(entrada, extensoes=None):
    """Um arquivo, ou os arquivos de uma pasta. Ordenados, para o lote repetir."""
    caminho = Path(entrada)
    if caminho.is_file():
        return [caminho]
    if not caminho.is_dir():
        return []
    achados = sorted(p for p in caminho.iterdir() if p.is_file())
    if extensoes:
        achados = [p for p in achados if p.suffix.lower() in extensoes]
    return achados


def _ferramentas(exigidas=()):
    """Carrega os caminhos e cobra o que falta. Devolve None se faltar algo."""
    T = carregar_config()
    faltando = [k for k in (exigidas or T) if k not in T or not T[k].exists()]
    if faltando:
        print("Ferramentas nao encontradas: %s" % ", ".join(sorted(faltando)))
        print("Ponha a pasta ferramentas/ ao lado deste programa, ou aponte o")
        print("caminho em %s." % CONFIG)
        return None
    return T


def _cmd_ferramentas(_args):
    T = carregar_config()
    print("\nferramentas, como este programa as encontra:\n")
    esperadas = set(ALVOS) | {"modelos"}
    for chave in sorted(esperadas | set(T)):
        caminho = T.get(chave)
        if caminho and Path(caminho).exists():
            print("  %-10s  %s" % (chave, caminho))
        else:
            print("  %-10s  NAO ENCONTRADA" % chave)
    print("\nA busca e por nome dentro de ferramentas/, ao lado do programa.")
    print("O %s sobrepoe, quando aponta para algo que existe." % CONFIG)
    return 0


def _cmd_upscale(args):
    T = _ferramentas()
    if T is None:
        return 1

    alvos = _alvos(args.entrada, {".utx"})
    if not alvos:
        print("Nenhum .utx em %s" % args.entrada)
        return 1

    print("%d pacote(s), upscale %dx, modelo %s"
          % (len(alvos), args.escala, args.modelo))
    ok = sum(1 for u in alvos
             if processar(T, u, Path(args.trabalho), Path(args.saida),
                          args.escala, args.modelo, args.parar_em))
    print("\n%d de %d concluidos. Saida em %s"
          % (ok, len(alvos), Path(args.saida).resolve()))
    return 0 if ok == len(alvos) else 1


def _metodo_do_arquivo(caminho):
    """A versao escrita no cabecalho, ou None se o arquivo ja esta aberto."""
    import l2npc
    return l2npc.metodo_do_arquivo(caminho)


def _cmd_abrir(args):
    T = _ferramentas(("l2encdec",))
    if T is None:
        return 1

    alvos = _alvos(args.entrada)
    if not alvos:
        print("Nada para abrir em %s" % args.entrada)
        return 1

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    print("\n=== abrindo %d arquivo(s) em %s ===" % (len(alvos), destino))

    feitos = 0
    for origem in alvos:
        alvo = destino / origem.name
        try:
            metodo = _metodo_do_arquivo(origem)
            if metodo:
                executar([T["l2encdec"], "-d", origem, alvo], limite=1800)
                if not alvo.exists():
                    raise RuntimeError("o l2encdec nao gravou nada")
                marca = "aberto (%s)" % NOME_DO_METODO.get(metodo, metodo)
            else:
                shutil.copy2(origem, alvo)
                marca = "copiado, ja estava aberto"
            print("  %-34s %s  (%s bytes)"
                  % (origem.name, marca, "{:,}".format(alvo.stat().st_size)))
            feitos += 1
        except Exception as e:                      # noqa: BLE001
            print("  %-34s ERRO: %s" % (origem.name, e))

    print("\n%d de %d abertos. Saida em %s"
          % (feitos, len(alvos), destino.resolve()))
    return 0 if feitos == len(alvos) else 1


def _ida_e_volta(T, entrada, saida, destino):
    """
    Abre de volta o que acabou de ser fechado e compara com o que entrou.

    A conferencia de dentro do `criptografar` usa o caminho do .utx, que nao
    serve a um .dat. Esta usa o mesmo `-d` de sempre, e quem valida nao e o
    mesmo caminho que gravou.
    """
    volta = destino / ("_conferindo_" + saida.name)
    try:
        executar([T["l2encdec"], "-d", saida, volta], limite=1800)
        if not volta.exists():
            return False
        return volta.read_bytes() == entrada.read_bytes()
    except Exception:                               # noqa: BLE001
        return False
    finally:
        volta.unlink(missing_ok=True)


def _cmd_fechar(args):
    T = _ferramentas(("l2encdec",))
    if T is None:
        return 1

    alvos = _alvos(args.entrada)
    if not alvos:
        print("Nada para fechar em %s" % args.entrada)
        return 1

    destino = Path(args.saida)
    destino.mkdir(parents=True, exist_ok=True)
    print("\n=== fechando %d arquivo(s) em %s ===" % (len(alvos), destino))

    feitos = 0
    for origem in alvos:
        try:
            if _metodo_do_arquivo(origem):
                # Fechar duas vezes produz arquivo que o cliente nao le.
                alvo = destino / origem.name
                shutil.copy2(origem, alvo)
                print("  %-34s copiado, ja estava criptografado" % origem.name)
                feitos += 1
                continue

            versao = args.versao or versao_de(origem)
            alvo, integro = criptografar(T, origem, origem.name, destino,
                                         True, versao=versao)
            if alvo is None:
                print("  %-34s ERRO: o l2encdec nao gravou nada" % origem.name)
                continue
            if not integro:
                integro = _ida_e_volta(T, origem, alvo, destino)
            print("  %-34s fechado em %s%s  (%s bytes)"
                  % (origem.name,
                     NOME_DO_METODO.get(versao, versao),
                     "" if integro else "  [a ida e volta nao confere]",
                     "{:,}".format(alvo.stat().st_size)))
            feitos += 1
        except Exception as e:                      # noqa: BLE001
            print("  %-34s ERRO: %s" % (origem.name, e))

    print("\n%d de %d fechados. Saida em %s"
          % (feitos, len(alvos), destino.resolve()))
    print("O nome importa: a chave da versao 121 deriva dele. Para devolver ao")
    print("cliente, o arquivo tem de manter o nome que tinha.")
    return 0 if feitos == len(alvos) else 1


def _cmd_extrair(args):
    T = _ferramentas(("umodel",))
    if T is None:
        return 1

    alvos = _alvos(args.entrada, {".utx", ".ukx", ".usx", ".u"})
    if not alvos:
        print("Nenhum pacote em %s" % args.entrada)
        return 1

    destino = Path(args.saida)
    total = 0
    for pacote in alvos:
        print("\n=== %s ===" % pacote.name)
        saidas, _log = extrair(T, pacote, destino / pacote.stem)
        print("  %d imagem(ns) em %s" % (len(saidas), destino / pacote.stem))
        total += len(saidas)
    print("\n%d imagem(ns) no total. Saida em %s" % (total, destino.resolve()))
    return 0 if total else 1


def _cmd_listar(args):
    import l2conferir

    alvos = _alvos(args.entrada, {".utx", ".ukx", ".usx", ".u", ".unr", ".uax"})
    if not alvos:
        print("Nenhum pacote em %s" % args.entrada)
        return 1

    lidos = 0
    for pacote in alvos:
        print("\n=== %s ===" % pacote.name)

        metodo = _metodo_do_arquivo(pacote)
        if metodo:
            print("  criptografado em %s" % NOME_DO_METODO.get(metodo, metodo))
        else:
            info = versao_pacote(pacote)
            if info is None:
                print("  nao e um pacote Unreal, nem tem cabecalho conhecido")
                continue
            print("  pacote Unreal aberto, versao=%d licensee=%d"
                  % (info[1], info[2]))

        # A leitura decifra a versao 121 na memoria, entao vale tentar mesmo
        # com o arquivo fechado. A 111 so abre por inteiro, e ai nao sai.
        try:
            objetos = l2conferir.objetos_do_pacote(pacote)
        except Exception as e:                      # noqa: BLE001
            print("  nao deu para ler os objetos: %s" % e)
            print("  abra antes com `abrir`, e liste o que sair.")
            continue

        print("  %d objeto(s):" % len(objetos))
        for nome in objetos:
            print("    %s" % nome)
        lidos += 1

    return 0 if lidos else 1


def _cmd_conferir(args):
    import l2conferir

    T = _ferramentas(("l2encdec",))
    if T is None:
        return 1

    ultimo = [""]

    def andando(fracao, texto):
        if texto != ultimo[0]:
            ultimo[0] = texto
            print("  %3d%%  %s" % (int(fracao * 100), texto))

    print("\n=== conferindo %s ===" % args.cliente)
    resultado = l2conferir.conferir(args.cliente, T, aoprogresso=andando)
    relatorio = l2conferir.texto_do_relatorio(resultado)

    if args.saida:
        Path(args.saida).write_text(relatorio, encoding="utf-8")
        print("\nRelatorio em %s" % Path(args.saida).resolve())
    else:
        print()
        print(relatorio)
    return 1 if l2conferir.problemas(resultado) else 0


def _original_do_lobby(mapa):
    """
    O mapa como veio do cliente.

    A primeira instalacao guarda uma copia; as seguintes partem dela. Sem
    isso, instalar duas vezes deixaria duas telas no mesmo lugar, e a
    segunda so pioraria a primeira.
    """
    pasta = mapa.parent / "backup_lobby"
    pasta.mkdir(exist_ok=True)
    copias = sorted(pasta.glob("*_%s" % mapa.name))
    if copias:
        return copias[0]
    copia = pasta / ("%s_%s" % (time.strftime("%Y%m%d_%H%M%S"), mapa.name))
    shutil.copy2(mapa, copia)
    return copia


def _achar_o_lobby(entrada):
    """O arquivo do lobby, dado ele mesmo, a pasta do cliente ou a maps."""
    caminho = Path(entrada)
    if caminho.is_file():
        return caminho
    for tentativa in (caminho / "maps" / "Lobby.unr", caminho / "Lobby.unr"):
        if tentativa.exists():
            return tentativa
    mapas = caminho / "maps"
    if mapas.is_dir():
        achados = sorted(mapas.glob("*obby*.unr"))
        if achados:
            return achados[0]
    return None


def _camera_pedida(texto):
    """`x,y,z` ou `x,y,z,giro` -- o giro em unidades do Unreal, 0 a 65535."""
    if not texto:
        return None
    partes = [p for p in texto.replace(";", ",").split(",") if p.strip()]
    if len(partes) not in (3, 4):
        raise ValueError("a camera precisa de x,y,z ou x,y,z,giro")
    return tuple(float(p) for p in partes)


def _cmd_lobby(args):
    import l2mapa

    alvo = _achar_o_lobby(args.entrada)
    if alvo is None or not alvo.exists():
        print("Nao achei o mapa do lobby em %s" % args.entrada)
        return 1

    try:
        camera = _camera_pedida(args.camera)
    except ValueError as erro:
        print("Camera invalida: %s" % erro)
        return 2

    original = _original_do_lobby(alvo)
    if original != alvo:
        print("original guardado em %s" % original.parent.name)

    try:
        mapa = l2mapa.ler(original)
        resumo = l2mapa.instalar_video_no_login(
            mapa, args.pacote, camera=camera, formato=args.formato,
            escala=args.escala)
        saida = Path(args.saida) if args.saida else alvo
        l2mapa.gravar(mapa, saida)
    except l2mapa.ErroDeMapa as erro:
        print("Nao deu: %s" % erro)
        return 1
    except OSError as erro:
        print("Nao consegui gravar: %s" % erro)
        print("Se o jogo estiver aberto, feche-o antes.")
        return 1

    print("cena de login: %s" % (resumo["marca"] or "sem marca"))
    print("camera fixa em (%.0f, %.0f, %.0f), sem movimento"
          % resumo["camera"])
    print("tela escala %.2f, fundo preto escala %.2f"
          % (resumo["escala"], resumo["escala"] * l2mapa.PAINEL_SOBRE_A_TELA))
    print("cobertura da altura da janela:")
    for formato, nome_da_tela in ((2.39, "ultralarga"), (1.78, "16 por 9"),
                                  (1.60, "16 por 10"), (1.33, "4 por 3"),
                                  (1.25, "5 por 4")):
        # a janela pode faltar pela altura ou pela largura -- vale a pior
        quanto = min(l2mapa.cobertura_da_altura(resumo["escala"], formato),
                     l2mapa.cobertura_da_largura(resumo["escala"]))
        print("   %-12s %s" % (nome_da_tela,
                               "cobre" if quanto >= 1.0 else
                               "falta %d%%" % round((1 - quanto) * 100)))
    print("gravado em %s" % saida)
    return 0


def _cmd_ajuda(args):
    if getattr(args, "sobre", None):
        alvo = args.sobre
        if alvo not in dict(COMANDOS):
            print("Nao conheco o comando `%s`." % alvo)
            print(texto_da_ajuda())
            return 1
        montar().parse_args([alvo, "-h"])
        return 0
    print(texto_da_ajuda())
    return 0


def montar():
    p = argparse.ArgumentParser(
        prog="L2PackTool-cli",
        description="Ferramentas de cliente do Lineage 2, pela linha de comando.",
        epilog="`L2PackTool-cli ajuda` lista tudo com exemplos.")
    sub = p.add_subparsers(dest="comando")

    up = sub.add_parser("upscale", help=dict(COMANDOS)["upscale"])
    up.add_argument("entrada", help="arquivo .utx ou pasta com varios")
    up.add_argument("-o", "--saida", default="./saida",
                    help="onde gravar os .utx finais (padrao ./saida)")
    up.add_argument("-t", "--trabalho", default="./trabalho",
                    help="pasta de trabalho (padrao ./trabalho)")
    up.add_argument("-s", "--escala", type=int, default=2, choices=[2, 3, 4],
                    help="fator de upscale (padrao 2). Ver o aviso de memoria.")
    up.add_argument("-n", "--modelo", default="upscayl-standard-4x",
                    help="modelo do upscayl (padrao upscayl-standard-4x)")
    up.add_argument("--parar-em",
                    choices=["descriptografar", "extrair", "comprimir"],
                    help="interrompe apos a etapa indicada, para inspecao")
    up.set_defaults(funcao=_cmd_upscale)

    ab = sub.add_parser("abrir", help=dict(COMANDOS)["abrir"])
    ab.add_argument("entrada", help="arquivo do cliente, ou pasta com varios")
    ab.add_argument("-o", "--saida", default="./aberto",
                    help="onde gravar (padrao ./aberto)")
    ab.set_defaults(funcao=_cmd_abrir)

    fe = sub.add_parser("fechar", help=dict(COMANDOS)["fechar"])
    fe.add_argument("entrada", help="arquivo aberto, ou pasta com varios")
    fe.add_argument("-o", "--saida", default="./fechado",
                    help="onde gravar (padrao ./fechado)")
    fe.add_argument("--versao", choices=["111", "121", "413"],
                    help="forca o metodo; sem isto vem da extensao")
    fe.set_defaults(funcao=_cmd_fechar)

    ex = sub.add_parser("extrair", help=dict(COMANDOS)["extrair"])
    ex.add_argument("entrada", help="pacote, ou pasta com varios")
    ex.add_argument("-o", "--saida", default="./texturas",
                    help="onde gravar as imagens (padrao ./texturas)")
    ex.set_defaults(funcao=_cmd_extrair)

    li = sub.add_parser("listar", help=dict(COMANDOS)["listar"])
    li.add_argument("entrada", help="pacote, ou pasta com varios")
    li.set_defaults(funcao=_cmd_listar)

    co = sub.add_parser("conferir", help=dict(COMANDOS)["conferir"])
    co.add_argument("cliente", help="a pasta do cliente, ou a system dentro dela")
    co.add_argument("-o", "--saida",
                    help="grava o relatorio num arquivo, em vez de na tela")
    co.set_defaults(funcao=_cmd_conferir)

    lo = sub.add_parser("lobby", help=dict(COMANDOS)["lobby"])
    lo.add_argument("entrada",
                    help="o Lobby.unr, ou a pasta do cliente")
    lo.add_argument("-p", "--pacote", default=versao.NOME,
                    help="nome do pacote de video instalado, sem .usx "
                         "(padrao %s)" % versao.NOME)
    lo.add_argument("--formato", type=float, default=1.25,
                    help="a janela mais alta a cobrir, largura/altura "
                         "(padrao 1.25, que e 5 por 4 e cobre todas as "
                         "telas comuns)")
    lo.add_argument("--escala", type=float,
                    help="escala da tela a mao, em vez da calculada")
    lo.add_argument("--camera",
                    help="x,y,z ou x,y,z,giro -- muda o ponto da camera")
    lo.add_argument("-o", "--saida",
                    help="grava noutro arquivo, em vez de no do cliente")
    lo.set_defaults(funcao=_cmd_lobby)

    fr = sub.add_parser("ferramentas", help=dict(COMANDOS)["ferramentas"])
    fr.set_defaults(funcao=_cmd_ferramentas)

    aj = sub.add_parser("ajuda", help=dict(COMANDOS)["ajuda"])
    aj.add_argument("sobre", nargs="?", help="o comando a detalhar")
    aj.set_defaults(funcao=_cmd_ajuda)

    return p


def main(argumentos=None):
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)

    # Quem chamava `L2PackTool-cli pasta -s 2` continua chamando assim: sem
    # comando reconhecido na frente, o pedido e de upscale, como sempre foi.
    conhecidos = set(dict(COMANDOS)) | {"help", "-h", "--help"}
    if argumentos and argumentos[0] not in conhecidos:
        # Nao e comando e nao e caminho: foi comando escrito errado. Dizer
        # "nenhum .utx aqui" mandaria procurar o erro no lugar errado.
        if not argumentos[0].startswith("-") \
                and not Path(argumentos[0]).exists():
            print("Nao conheco o comando `%s`, e nao existe caminho com"
                  " esse nome." % argumentos[0])
            print(texto_da_ajuda())
            return 2
        argumentos.insert(0, "upscale")
    if argumentos and argumentos[0] == "help":
        argumentos[0] = "ajuda"

    if not argumentos:
        print(texto_da_ajuda())
        return 0

    args = montar().parse_args(argumentos)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
