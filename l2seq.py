# -*- coding: utf-8 -*-
"""
Lobby de video: trocar os quadros de um `MaterialSequence`.

Este modulo existe por causa de uma descoberta que custou caro. Havia uma
hipotese razoavel -- animar a textura do lobby com a corrente `AnimNext`, que e
como a propria NCSoft anima fogo e agua -- e ela funciona no papel: a
propriedade e escrita, o umodel le a corrente inteira, o cliente carrega o
pacote sem reclamar. So que na tela nao acontece nada.

O lobby de video de verdade e montado de outro jeito, e um pacote pronto
mostrou qual:

    demev  (MaterialSequence)  592 itens {Material=<quadro>, Time=0.02}
    Shg1   (Shader)            Diffuse = demev, SelfIllumination = demev
    seq    (StaticMesh)        Materials[0] = Shg1        <- a tela
    592 texturas 2048x2048 DXT1, um mipmap so, nomeadas 10000..10591

`MaterialSequence` e o material feito para tocar uma lista de materiais no
tempo; `AnimNext` anima textura de particula. Era a ferramenta errada para o
servico.

O que este modulo faz e, por isso, bem menos ambicioso do que o que veio antes
-- e bem mais seguro. Nenhuma tabela e reescrita, nenhum objeto muda de
tamanho, nada anda de lugar: os bytes dos pixeis de cada quadro sao
sobrescritos onde estao, um a um. Um arquivo de 1,2 GB e tratado com `seek` e
`write`, sem passar pela memoria.
"""
import math
import re
import shutil
import struct
from pathlib import Path

import l2anim
import l2npc
import l2upscale as motor

# O quadro do pacote de referencia: 2048x2048 com o video em 16:9 no meio e
# faixa preta em cima e embaixo. Medido, nao chutado.
ASPECTO_PADRAO = 16.0 / 9.0


class ErroSequencia(Exception):
    pass


# ---------------------------------------------------------------------------
# Ler o pacote
# ---------------------------------------------------------------------------
def _tabelas(dados):
    (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
     qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(
        l2anim.CABECALHO, dados)
    if assinatura != 0x9E2A83C1:
        raise ErroSequencia("nao e um pacote Unreal.")
    nomes, _fim = l2anim._ler_nomes_cru(dados, off_nomes, qtd_nomes)
    lista_nomes = [n for n, _f in nomes]

    imports, pos = [], off_imp
    for _ in range(qtd_imp):
        campos, pos = l2anim._ler_import(dados, pos)
        imports.append(campos)
    exports, pos = [], off_exp
    for _ in range(qtd_exp):
        campos, pos = l2anim._ler_export(dados, pos)
        exports.append(campos)
    return lista_nomes, imports, exports


def _decodificar(cru, nomes):
    """(nome, tipo, indice do array, corpo, deslocamento do corpo no `cru`)."""
    pos = 0
    i_nome, pos = l2anim._descompacto(cru, pos)
    nome = nomes[i_nome] if 0 <= i_nome < len(nomes) else "?"
    info = cru[pos]
    pos += 1
    tipo, codigo = info & 0x0F, (info >> 4) & 0x07
    if tipo == 10:
        _i, pos = l2anim._descompacto(cru, pos)
    if codigo < 5:
        tamanho = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}[codigo]
    elif codigo == 5:
        tamanho = cru[pos]; pos += 1
    elif codigo == 6:
        tamanho = int.from_bytes(cru[pos:pos + 2], "little"); pos += 2
    else:
        tamanho = int.from_bytes(cru[pos:pos + 4], "little"); pos += 4
    indice = None
    if (info & 0x80) and tipo != 3:
        indice, pos = l2anim._descompacto(cru, pos)
    return nome, tipo, indice, cru[pos:pos + tamanho], pos


def _classe(campos, nomes, imports, exports):
    indice = campos["classe"]
    if indice < 0:
        return nomes[imports[-indice - 1]["nome"]]
    if indice > 0:
        return nomes[exports[indice - 1]["nome"]]
    return ""


def ler_sequencia(caminho):
    """
    Descreve o lobby de video de um pacote, ou devolve None se nao houver um.

    O que volta e o suficiente para trocar o filme sem abrir o arquivo de novo:
    onde ficam os pixeis de cada quadro, quantos bytes cabem ali, e onde estao
    os `Time` que mandam na velocidade.
    """
    caminho = Path(caminho)
    pacote = l2npc.Pacote(caminho)
    try:
        dados = pacote.dados
        nomes, imports, exports = _tabelas(dados)

        sequencias = [(i, c) for i, c in enumerate(exports, 1)
                      if _classe(c, nomes, imports, exports) == "MaterialSequence"
                      and c["tamanho"]]
        if not sequencias:
            return None
        indice_seq, campos_seq = sequencias[0]

        props, _fim = l2anim.ler_propriedades(
            dados, campos_seq["inicio"], nomes,
            campos_seq["inicio"] + campos_seq["tamanho"])

        ordem, tempos, tempo_total, laco = [], [], None, None
        for _n, cru in props:
            nome, tipo, _ind, corpo, desloc = _decodificar(cru, nomes)
            if nome == "TotalTime" and tipo == 4:
                tempo_total = struct.unpack_from("<f", corpo, 0)[0]
                continue
            if nome == "Loop" and tipo == 3:
                # Propriedade booleana nao gasta byte de valor: ela mora no bit
                # mais alto do proprio byte de tipo.
                pos_info = 0
                _i, pos_info = l2anim._descompacto(cru, pos_info)
                laco = bool((cru[pos_info] >> 7) & 1)
                continue
            if nome != "SequenceItems" or tipo != 9:
                continue
            # base absoluta do corpo do vetor dentro do arquivo
            base = campos_seq["inicio"] + (len(cru) - len(corpo)) + 0
            base = campos_seq["inicio"] + cru.find(bytes(corpo[:16]))
            quantos, p = l2anim._descompacto(corpo, 0)
            for _k in range(quantos):
                interna, p = l2anim.ler_propriedades(corpo, p, nomes,
                                                     len(corpo))
                for _n2, c2 in interna:
                    n2, t2, _i2, corpo2, desloc2 = _decodificar(c2, nomes)
                    if n2 == "Material" and t2 == 5:
                        alvo, _ = l2anim._descompacto(corpo2, 0)
                        ordem.append(alvo)
                    elif n2 == "Time" and t2 == 4:
                        # posicao absoluta do float, para poder ajusta-lo
                        dentro = corpo.find(bytes(c2)) + desloc2
                        tempos.append(base + dentro)

        if not ordem:
            return None

        quadros = []
        for alvo in ordem:
            if alvo <= 0 or alvo > len(exports):
                continue
            campos = exports[alvo - 1]
            if not campos["tamanho"]:
                continue
            _p, fim = l2anim.ler_propriedades(
                dados, campos["inicio"], nomes,
                campos["inicio"] + campos["tamanho"])
            saltos = l2anim.posicoes_de_mipmap(dados, campos["inicio"],
                                               campos["tamanho"], fim)
            if not saltos or len(saltos) != 1:
                # Os quadros do pacote de referencia tem um mipmap so. Mais de
                # um significa outro arranjo, e trocar por cima seria chute.
                continue
            quantidade, onde = l2anim._descompacto(dados, saltos[0] + 4)
            largura, altura = _medidas(dados, campos, nomes)
            quadros.append({
                "nome": nomes[campos["nome"]],
                "onde": onde,
                "bytes": quantidade,
                "largura": largura,
                "altura": altura,
            })

        return {
            "arquivo": caminho,
            "sequencia": nomes[campos_seq["nome"]],
            "indice": indice_seq,
            "quadros": quadros,
            "tempos": tempos,
            "tempo_total": tempo_total,
            "laco": laco,
            "posicao_total": _posicao_do_total(dados, campos_seq, nomes),
        }
    finally:
        pacote.fechar()


def _medidas(dados, campos, nomes):
    props, _fim = l2anim.ler_propriedades(
        dados, campos["inicio"], nomes, campos["inicio"] + campos["tamanho"])
    largura = altura = 0
    for _n, cru in props:
        nome, tipo, _i, corpo, _d = _decodificar(cru, nomes)
        if nome == "USize":
            largura = int.from_bytes(corpo[:4], "little")
        elif nome == "VSize":
            altura = int.from_bytes(corpo[:4], "little")
    return largura, altura


def _posicao_do_total(dados, campos_seq, nomes):
    """Onde no arquivo esta o float TotalTime, para poder ajusta-lo."""
    props, _fim = l2anim.ler_propriedades(
        dados, campos_seq["inicio"], nomes,
        campos_seq["inicio"] + campos_seq["tamanho"])
    pos = campos_seq["inicio"]
    for _n, cru in props:
        nome, tipo, _i, _corpo, desloc = _decodificar(cru, nomes)
        if nome == "TotalTime" and tipo == 4:
            return pos + desloc
        pos += len(cru)
    return None


# ---------------------------------------------------------------------------
# Trocar o filme
# ---------------------------------------------------------------------------
def extrair_quadros(T, origem, destino, quantos, largura, altura,
                    aspecto=ASPECTO_PADRAO, aolog=None, faixa=True,
                    comeco=None, fim=None, logo=None):
    """
    Tira `quantos` quadros do video, no tamanho do quadro do pacote.

    O video entra centralizado, com faixa preta em cima e embaixo -- que e como
    o pacote de referencia faz: quadro de 2048x2048 com a imagem 16:9 de
    2048x1152 no meio. A faixa existe porque o Unreal 2 quer textura em
    potencia de dois, e 2048x1152 nao e; a malha da tela amostra so a faixa do
    meio, entao no jogo ela nao aparece.

    Com `faixa=False` o quadro sai so com a parte util, do tamanho que a malha
    mostra. E o que a previa usa: assim o que se ve na tela do programa e o
    mesmo enquadramento que vai aparecer no jogo.

    `comeco` e `fim`, em segundos, recortam um trecho. O `-ss` vem ANTES do
    `-i` de proposito: assim o ffmpeg salta direto para o ponto em vez de
    decodificar o video inteiro ate chegar la, o que num arquivo longo e a
    diferenca entre segundos e minutos.

    `logo` poe uma imagem por cima: {"arquivo", "x", "y", "largura"}, com os
    tres numeros em FRACAO da parte visivel do quadro, e nao em pixeis. E o que
    faz a previa e o quadro final concordarem -- a previa sai a 640 de largura e
    o quadro a 2048, e a mesma fracao cai no mesmo lugar nos dois.

    Com "entra" e "sai" em segundos, a logo aparece so nesse intervalo. A
    contagem e do trecho recortado, nao do video inteiro: o `-ss` ja zerou o
    relogio no comeco do trecho.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    origem, destino = Path(origem), Path(destino)
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)

    exe = l2anim.ffmpeg(T)
    if exe is None:
        raise ErroSequencia("nao achei o ffmpeg.")

    duracao = duracao_do_video(T, origem) or 0.0
    if duracao <= 0:
        raise ErroSequencia("nao consegui medir a duracao de %s." % origem.name)

    comeco = max(0.0, float(comeco or 0.0))
    fim = min(duracao, float(fim) if fim else duracao)
    if fim - comeco < 0.05:
        raise ErroSequencia("o trecho escolhido tem menos de um vigesimo de "
                            "segundo.")
    duracao = fim - comeco

    util = int(round(largura / float(aspecto)))
    util -= util % 2
    alvo_altura = altura if faixa else util
    filtro = ("fps=%.6f,scale=%d:%d:force_original_aspect_ratio=decrease,"
              "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black"
              % (quantos / duracao, largura, util, largura, alvo_altura))
    padrao = str(destino / "q%05d.png")
    anotar("tirando %d quadros de %.2fs%s (%s)..."
           % (quantos, duracao,
              (" a partir de %.2fs" % comeco) if comeco else "", origem.name))
    recorte = []
    if comeco > 0:
        recorte += ["-ss", "%.3f" % comeco]
    recorte += ["-i", str(origem), "-t", "%.3f" % duracao]

    if logo and Path(logo.get("arquivo", "")).is_file():
        # A faixa util comeca em (altura - util)/2 quando ha borda preta; sem
        # borda, o quadro inteiro E a faixa.
        topo = (alvo_altura - util) // 2 if faixa else 0
        larga = max(8, int(round(largura * float(logo.get("largura", 0.2)))))
        x = int(round(largura * float(logo.get("x", 0.05))))
        y = topo + int(round(util * float(logo.get("y", 0.05))))
        quando = ""
        if logo.get("entra") is not None and logo.get("sai") is not None:
            quando = (":enable='between(t,%.3f,%.3f)'"
                      % (float(logo["entra"]), float(logo["sai"])))
        complexo = ("[0:v]%s[base];[1:v]scale=%d:-1[marca];"
                    "[base][marca]overlay=%d:%d%s"
                    % (filtro, larga, x, y, quando))
        linha = ([str(exe), "-y"] + recorte + ["-i", str(logo["arquivo"]),
                 "-filter_complex", complexo, "-frames:v", str(quantos),
                 padrao])
    else:
        linha = ([str(exe), "-y"] + recorte + ["-vf", filtro,
                 "-frames:v", str(quantos), padrao])
    _codigo, texto = motor.executar(linha, limite=7200)
    saidas = sorted(destino.glob("q*.png"))
    if not saidas:
        ultimas = [l.strip() for l in texto.strip().split("\n")[-3:]]
        raise ErroSequencia("o ffmpeg nao extraiu quadro nenhum: %s"
                            % " / ".join(ultimas))

    # Video curto demais devolve menos quadros do que o pedido; o ultimo se
    # repete ate fechar a conta, que e melhor do que a sequencia encurtar e
    # deixar quadro velho no meio do filme novo.
    while len(saidas) < quantos:
        copia = destino / ("q%05d.png" % (len(saidas) + 1))
        shutil.copy2(saidas[-1], copia)
        saidas.append(copia)
    anotar("%d quadros prontos." % len(saidas))
    return saidas[:quantos]


def dados_do_video(T, origem):
    """
    Duracao e cadencia do video, perguntadas ao ffmpeg.

    Devolve {"duracao": segundos, "fps": quadros por segundo}, com None no que
    nao der para ler. Sao os dois numeros de que o programa precisa para
    preencher sozinho quantos quadros tirar: na cadencia do proprio video, o
    filme no lobby fica com o mesmo ritmo do arquivo de origem.
    """
    exe = l2anim.ffmpeg(T)
    if exe is None:
        return {"duracao": None, "fps": None}
    _codigo, texto = motor.executar([str(exe), "-i", str(origem)], limite=120)

    duracao = None
    achado = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", texto)
    if achado:
        h, m, s = achado.groups()
        duracao = int(h) * 3600 + int(m) * 60 + float(s)

    # O ffmpeg escreve "25 fps" na linha do fluxo de video; quando nao escreve
    # -- acontece com alguns GIF --, o "tbr" serve de aproximacao.
    fps = None
    achado = re.search(r"(\d+(?:\.\d+)?)\s*fps", texto)
    if not achado:
        achado = re.search(r"(\d+(?:\.\d+)?)\s*tbr", texto)
    if achado:
        try:
            fps = float(achado.group(1))
        except ValueError:
            fps = None
    if fps is not None and not 0.5 <= fps <= 240:
        fps = None
    return {"duracao": duracao, "fps": fps}


def duracao_do_video(T, origem):
    """Segundos do video. Atalho para quem so quer a duracao."""
    return dados_do_video(T, origem)["duracao"]


def distribuir(imagens, capacidade):
    """
    Espalha `imagens` pelos `capacidade` lugares da sequencia.

    A sequencia tem um numero fixo de lugares -- 592, no pacote de referencia --
    e todos tem de ser preenchidos: deixar lugar sobrando e deixar quadro do
    filme antigo no meio do filme novo. Com menos imagens do que lugares, cada
    uma ocupa varios lugares seguidos, o que da um filme com menos quadros por
    segundo sem mudar a duracao.
    """
    imagens = list(imagens)
    if not imagens:
        return []
    return [imagens[i * len(imagens) // capacidade] for i in range(capacidade)]


def trocar_filme(T, info, imagens, trabalho, aolog=None, aoprogresso=None,
                 lote=24, amostras=8):
    """
    Poe as imagens no lugar dos quadros, dentro do arquivo, sem mexer em mais
    nada.

    Trabalha em lotes: comprimir 592 imagens de 2048x2048 de uma vez pediria
    uns tres gigabytes de disco so de intermediario. Cada lote e comprimido,
    gravado e apagado antes do seguinte.

    No fim, `amostras` quadros espalhados sao lidos de volta do arquivo e
    comparados byte a byte com o que foi gravado. E a mesma regra do resto do
    programa: quem confere nao e quem escreveu.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    quadros = info["quadros"]
    imagens = list(imagens)
    if len(imagens) != len(quadros):
        raise ErroSequencia("recebi %d imagens para %d quadros."
                            % (len(imagens), len(quadros)))

    trabalho = Path(trabalho)
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True)

    quais = set()
    if amostras and len(quadros) > 1:
        passo = max(1, len(quadros) // amostras)
        quais = set(range(0, len(quadros), passo))
    guardados = {}

    with open(info["arquivo"], "r+b") as arquivo:
        for comeco in range(0, len(imagens), lote):
            pedaco = imagens[comeco:comeco + lote]
            pasta = trabalho / ("lote%04d" % comeco)
            dds = motor.comprimir(
                T, pedaco, pasta,
                formatos={p.stem.lower(): {"formato": "TEXF_DXT1"}
                          for p in pedaco})
            por_nome = {d.stem.lower(): d for d in dds}
            for k, imagem in enumerate(pedaco):
                quadro = quadros[comeco + k]
                origem = por_nome.get(imagem.stem.lower())
                if origem is None:
                    raise ErroSequencia("o texconv nao gerou o DDS de %s."
                                        % imagem.name)
                # O DDS traz 128 bytes de cabecalho; o quadro so tem um nivel,
                # entao o que interessa e o comeco dos dados.
                bruto = origem.read_bytes()[128:]
                if len(bruto) < quadro["bytes"]:
                    raise ErroSequencia(
                        "%s comprimiu em %d bytes e o quadro tem %d."
                        % (imagem.name, len(bruto), quadro["bytes"]))
                arquivo.seek(quadro["onde"])
                arquivo.write(bruto[:quadro["bytes"]])
                if (comeco + k) in quais:
                    guardados[comeco + k] = bruto[:quadro["bytes"]]
            shutil.rmtree(pasta, ignore_errors=True)
            if aoprogresso:
                aoprogresso(min(comeco + lote, len(imagens)), len(imagens))
            anotar("  %d de %d quadros gravados"
                   % (min(comeco + lote, len(imagens)), len(imagens)))

    if guardados:
        with open(info["arquivo"], "rb") as arquivo:
            erradas = []
            for indice, esperado in sorted(guardados.items()):
                quadro = quadros[indice]
                arquivo.seek(quadro["onde"])
                if arquivo.read(quadro["bytes"]) != esperado:
                    erradas.append(quadro["nome"])
        if erradas:
            raise ErroSequencia(
                "%d quadro(s) nao conferem depois de gravados (%s) -- o "
                "arquivo pode ter ficado inconsistente."
                % (len(erradas), ", ".join(erradas[:4])))
        anotar("conferido: %d quadros lidos de volta batem byte a byte."
               % len(guardados))
    return len(imagens)


def ajustar_tempo(info, segundos):
    """
    Faz a sequencia durar `segundos`, mexendo so nos floats que ja estao la.

    Cada item tem o seu `Time`, e o material tem o `TotalTime`. Sao quatro
    bytes cada um, entao mudar o valor nao muda o tamanho de nada -- e por isso
    da para gravar por cima com seguranca.
    """
    if not info["tempos"]:
        return None
    por_quadro = float(segundos) / len(info["tempos"])
    # O tempo de cada item e gravado em float de quatro bytes, entao o valor
    # que fica no arquivo nao e exatamente o que a divisao deu. O TotalTime tem
    # de ser a soma DESSES valores, e nao o numero pedido: sobrando tempo no
    # fim, a sequencia fica parada no ultimo quadro esperando o relogio virar.
    gravado = struct.unpack("<f", struct.pack("<f", por_quadro))[0]
    total = gravado * len(info["tempos"])
    with open(info["arquivo"], "r+b") as arquivo:
        for posicao in info["tempos"]:
            arquivo.seek(posicao)
            arquivo.write(struct.pack("<f", por_quadro))
        if info.get("posicao_total") is not None:
            arquivo.seek(info["posicao_total"])
            arquivo.write(struct.pack("<f", total))
    return gravado


# ---------------------------------------------------------------------------
# Ler de volta o que esta gravado
# ---------------------------------------------------------------------------
# Serve para a previa poder mostrar o pacote, e nao a intencao. Os bytes saem do
# arquivo, ganham um cabecalho DDS e viram imagem -- o Pillow decodifica DXT1
# sozinho, entao nao e preciso chamar ferramenta nenhuma e da para montar dezenas
# de quadros em segundos.
CABECALHO_DDS = struct.Struct("<4sIIIIIII44sII4sIIIIIIIIII")


def cabecalho_dds(largura, altura, tamanho, marca=b"DXT1"):
    """Os 128 bytes de cabecalho de um DDS comprimido, de um mipmap so."""
    return CABECALHO_DDS.pack(
        b"DDS ", 124,
        0x1 | 0x2 | 0x4 | 0x1000 | 0x80000,     # CAPS HEIGHT WIDTH PIXELFORMAT LINEARSIZE
        altura, largura, tamanho, 0, 1,
        b"\x00" * 44,                            # reservado
        32, 0x4,                                 # ddspf: tamanho e FOURCC
        marca, 0, 0, 0, 0, 0,
        0x1000, 0, 0, 0, 0)                      # caps e o resto


def quadro_em_dds(info, indice):
    """O quadro `indice` da sequencia, lido do arquivo, como um DDS na memoria."""
    quadro = info["quadros"][indice]
    with open(info["arquivo"], "rb") as arquivo:
        arquivo.seek(quadro["onde"])
        bruto = arquivo.read(quadro["bytes"])
    return (cabecalho_dds(quadro["largura"], quadro["altura"], len(bruto))
            + bruto)


def amostrar_do_pacote(info, quantos):
    """
    `quantos` quadros espalhados pela sequencia, em DDS, lidos do arquivo.

    Devolve [(indice, bytes)]. Sao os pixeis que o cliente vai desenhar -- nada
    aqui e recalculado a partir do video.
    """
    total = len(info["quadros"])
    quantos = max(1, min(quantos, total))
    passo = total / float(quantos)
    indices = sorted({int(i * passo) for i in range(quantos)})
    return [(i, quadro_em_dds(info, i)) for i in indices]


def ajustar_laco(info, repetir=True, aolog=None):
    """
    Grava `Loop` no MaterialSequence, para o filme repetir sozinho.

    O sintoma que trouxe esta funcao: o filme toca uma vez, para no ultimo
    quadro e so recomeca quando o proprio lobby reinicia. O pacote nao guarda
    `Loop` nenhum -- fica no padrao da classe --, e pacotes do proprio jogo
    mostram que a propriedade existe e e gravavel (o lineagemonsterstex.utx
    guarda `Loop = False` nos materiais do Zaken).

    Como o objeto cresce, ele nao pode ficar onde esta. Nada e reescrito no
    lugar: o objeto novo, a tabela de nomes maior e as tabelas de import e
    export vao para o FIM do arquivo, e o cabecalho passa a apontar para la. O
    que ficou para tras vira peso morto de algumas dezenas de kilobytes -- num
    arquivo de 1,2 GB, e o preco de nao mover 1,2 GB de lugar.

    Devolve o novo tamanho do arquivo, ou None se nao havia o que mudar.
    """
    def anotar(texto):
        if aolog:
            aolog(texto)

    if info.get("laco") == bool(repetir):
        return None

    caminho = Path(info["arquivo"])
    pacote = l2npc.Pacote(caminho)
    try:
        dados = pacote.dados
        (assinatura, versao, licenciado, flags, qtd_nomes, off_nomes,
         qtd_exp, off_exp, qtd_imp, off_imp) = struct.unpack_from(
            l2anim.CABECALHO, dados)
        nomes_crus, _fim_nomes = l2anim._ler_nomes_cru(dados, off_nomes,
                                                       qtd_nomes)
        nomes = [n for n, _f in nomes_crus]

        imports, pos = [], off_imp
        for _ in range(qtd_imp):
            campos, pos = l2anim._ler_import(dados, pos)
            imports.append(campos)
        exports, pos = [], off_exp
        for _ in range(qtd_exp):
            campos, pos = l2anim._ler_export(dados, pos)
            exports.append(campos)

        alvo = exports[info["indice"] - 1]
        props, fim_props = l2anim.ler_propriedades(
            dados, alvo["inicio"], nomes, alvo["inicio"] + alvo["tamanho"])
        corpo = bytearray(dados[alvo["inicio"]:
                                alvo["inicio"] + alvo["tamanho"]])
    finally:
        pacote.fechar()

    if "Loop" in nomes:
        i_laco = nomes.index("Loop")
        nomes_novos = nomes_crus
    else:
        i_laco = len(nomes)
        nomes_novos = list(nomes_crus) + [("Loop", nomes_crus[1][1])]

    # BOOL nao gasta byte de VALOR -- ele mora no bit mais alto do byte de
    # tipo --, mas gasta o byte de TAMANHO: o jogo grava `53 00`, ou seja,
    # codigo 5 ("o tamanho vem a seguir") com tamanho zero. Escrevendo sem esse
    # zero, quem le entende que ha um byte de valor e come o `None` da lista.
    pedaco = (l2anim.compacto(i_laco)
              + bytes([3 | (5 << 4) | (0x80 if repetir else 0)])
              + b"\x00")
    ja_tinha = [n for n, _c in props if n == "Loop"]
    if ja_tinha:
        # trocar o valor no lugar: mesmo tamanho, nada se move
        procurado = l2anim.compacto(i_laco)
        onde = -1
        for info in (3 | (5 << 4), 3 | (5 << 4) | 0x80, 3, 3 | 0x80):
            onde = bytes(corpo).find(procurado + bytes([info]))
            if onde >= 0:
                break
        if onde >= 0:
            corpo[onde:onde + len(pedaco)] = pedaco
            with open(caminho, "r+b") as arquivo:
                arquivo.seek(alvo["inicio"] + onde)
                arquivo.write(pedaco)
            anotar("Loop = %s (trocado no lugar)" % bool(repetir))
            return caminho.stat().st_size

    dentro = fim_props - 1 - alvo["inicio"]      # antes do None que fecha
    corpo[dentro:dentro] = pedaco

    with open(caminho, "r+b") as arquivo:
        arquivo.seek(0, 2)
        fim = arquivo.tell()

        alvo["inicio"], alvo["tamanho"] = fim, len(corpo)
        arquivo.write(bytes(corpo))

        novo_off_nomes = arquivo.tell()
        for texto, f in nomes_novos:
            arquivo.write(l2anim._escrever_nome(texto, f))

        novo_off_imp = arquivo.tell()
        for campos in imports:
            arquivo.write(l2anim._escrever_import(campos))

        novo_off_exp = arquivo.tell()
        for campos in exports:
            arquivo.write(l2anim._escrever_export(campos))

        cabecalho = bytearray(struct.calcsize(l2anim.CABECALHO))
        struct.pack_into(l2anim.CABECALHO, cabecalho, 0, assinatura, versao,
                         licenciado, flags, len(nomes_novos), novo_off_nomes,
                         qtd_exp, novo_off_exp, qtd_imp, novo_off_imp)
        arquivo.seek(0)
        arquivo.write(bytes(cabecalho))
        tamanho = arquivo.seek(0, 2)

    anotar("Loop = %s escrito; o arquivo cresceu %d bytes"
           % (bool(repetir), tamanho - fim))
    return tamanho


def achar_lobby_de_video(raiz):
    """Os pacotes do cliente que tem um MaterialSequence dentro."""
    raiz = Path(raiz)
    achados = []
    for pasta in raiz.iterdir():
        if not pasta.is_dir() or pasta.name.lower() not in ("staticmeshes",
                                                            "textures"):
            continue
        for arquivo in sorted(pasta.iterdir()):
            if arquivo.suffix.lower() not in (".usx", ".utx"):
                continue
            try:
                if not _tem_nome(arquivo, "MaterialSequence"):
                    continue
                info = ler_sequencia(arquivo)
            except Exception:
                continue
            if info and info["quadros"]:
                achados.append(info)
    return achados


def _tem_nome(caminho, procurado):
    """
    A tabela de nomes diz, em milissegundos, se vale a pena abrir o pacote.

    Varrer a pasta inteira lendo objeto por objeto custaria minutos; a tabela
    de nomes fica logo no comeco do arquivo e ja responde.
    """
    pacote = l2npc.Pacote(caminho)
    try:
        return procurado in pacote.nomes
    finally:
        pacote.fechar()
