#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Atualizar o programa a partir das releases do GitHub.

Publicar uma release no repositório com o instalador anexado
(`L2PackTool-Setup-X.Y.Z.exe`) é tudo o que precisa para a versão nova chegar
a quem usa: o programa pergunta à API do GitHub qual é a última, mostra o que
mudou (o texto da release), baixa o instalador e roda.

## Por que o instalador, e não trocar o .exe

O executável em uso está aberto -- o Windows não deixa sobrescrever. O
instalador já sabe fechar o programa (`CloseApplications`), instala na mesma
pasta (o `AppId` não muda) e, com `/REABRIR`, abre a versão nova no fim. É o
mesmo caminho de quem baixa à mão, sem um segundo jeito de instalar para dar
defeito só no dia da atualização.

## A conferência

O GitHub publica o tamanho e, desde 2025, o SHA-256 de cada anexo. O arquivo
baixado é conferido contra os dois antes de rodar: um download cortado no meio
ou trocado no caminho não chega a ser executado.

Sem dependência nova: `urllib` e `json` da biblioteca padrão.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

import versao

REPOSITORIO = "JEAN-ALMEIDA-CZO/L2PackTool"
API = "https://api.github.com/repos/%s/releases?per_page=30" % REPOSITORIO
PAGINA = "https://github.com/%s/releases" % REPOSITORIO

# O anexo que é o instalador. Os outros (prints, zips) não interessam aqui.
INSTALADOR = re.compile(r"^L2PackTool-Setup-(\d+(?:\.\d+)*)\.exe$", re.I)

# Onde o instalador baixado espera. Fora da pasta do programa de propósito: o
# instalador vai escrever lá dentro, e não pode estar rodando de dentro dela.
PASTA_DE_DOWNLOAD = Path(tempfile.gettempdir()) / "L2PackTool-atualizacao"

BLOCO = 256 * 1024


class ErroDeAtualizacao(Exception):
    pass


class Cancelado(ErroDeAtualizacao):
    pass


# ---------------------------------------------------------------------------
# versões
# ---------------------------------------------------------------------------
def numero(texto):
    """`v1.10.0` -> (1, 10, 0). Sem número nenhum, (0, 0, 0)."""
    partes = [int(p) for p in re.findall(r"\d+", str(texto or ""))[:3]]
    return tuple(partes + [0] * (3 - len(partes)))


def versao_atual():
    return tuple(versao.VERSAO[:3])


def texto_da_versao(tupla):
    return ".".join(str(n) for n in tupla)


# ---------------------------------------------------------------------------
# a consulta
# ---------------------------------------------------------------------------
def _cabecalhos():
    return {"User-Agent": "L2PackTool/%s" % versao.TEXTO,
            "Accept": "application/vnd.github+json"}


def _pedir(url, timeout=20):
    pedido = urllib.request.Request(url, headers=_cabecalhos())
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return resposta.read()
    except urllib.error.HTTPError as e:
        if e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0":
            raise ErroDeAtualizacao(
                "o GitHub limitou as consultas deste endereço por uma hora; "
                "tente mais tarde")
        raise ErroDeAtualizacao("o GitHub respondeu %d (%s)" % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise ErroDeAtualizacao("sem conexão com o GitHub (%s)" % e.reason)
    except OSError as e:                            # timeout, socket
        raise ErroDeAtualizacao("sem conexão com o GitHub (%s)" % e)


def _release(bruta):
    """Uma release da API, só com o que o programa usa."""
    anexo = None
    for a in bruta.get("assets") or []:
        if INSTALADOR.match(a.get("name") or ""):
            digest = a.get("digest") or ""
            anexo = {"nome": a["name"],
                     "url": a.get("browser_download_url") or "",
                     "tamanho": int(a.get("size") or 0),
                     "sha256": (digest.split(":", 1)[1].lower()
                                if digest.lower().startswith("sha256:") else "")}
            break
    tag = bruta.get("tag_name") or bruta.get("name") or ""
    return {"versao": numero(tag),
            "texto": texto_da_versao(numero(tag)),
            "tag": tag,
            "titulo": bruta.get("name") or tag,
            "notas": (bruta.get("body") or "").replace("\r\n", "\n").strip(),
            "data": (bruta.get("published_at") or "")[:10],
            "pagina": bruta.get("html_url") or PAGINA,
            "instalador": anexo}


def procurar(timeout=20):
    """
    O que há no GitHub, comparado com esta versão.

    Devolve {"atual", "ultima", "novas", "alvo"}: `novas` são as releases
    mais novas que esta, da mais nova para a mais velha (quem pula duas
    versões lê o que mudou nas duas); `alvo` é a mais nova que já tem o
    instalador anexado -- release recém-criada, com o anexo ainda subindo,
    não é oferecida pela metade.
    """
    try:
        dados = json.loads(_pedir(API, timeout).decode("utf-8"))
    except ValueError:
        raise ErroDeAtualizacao("o GitHub mandou uma resposta que não é JSON")
    releases = [_release(r) for r in dados
                if not r.get("draft") and not r.get("prerelease")]
    releases.sort(key=lambda r: r["versao"], reverse=True)
    atual = versao_atual()
    novas = [r for r in releases if r["versao"] > atual]
    alvo = next((r for r in novas if r["instalador"]), None)
    return {"atual": atual,
            "ultima": releases[0] if releases else None,
            "novas": novas,
            "alvo": alvo}


# ---------------------------------------------------------------------------
# o download
# ---------------------------------------------------------------------------
def _sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(BLOCO), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(anexo, ao_progresso=None, cancelado=None, pasta=None):
    """
    Baixa o instalador e confere tamanho e SHA-256. Devolve o caminho.

    `ao_progresso(baixados, total, bytes_por_segundo)` é chamado umas dez
    vezes por segundo. A velocidade é a dos últimos três segundos, e não a
    média desde o começo: é ela que diz quanto falta de verdade quando a rede
    oscila. `cancelado` é um `threading.Event`.
    """
    pasta = Path(pasta or PASTA_DE_DOWNLOAD)
    pasta.mkdir(parents=True, exist_ok=True)
    final = pasta / anexo["nome"]
    total = int(anexo.get("tamanho") or 0)
    esperado = anexo.get("sha256") or ""

    # Já baixado numa tentativa anterior, e inteiro: não baixa de novo.
    if final.is_file() and (not total or final.stat().st_size == total) and \
            (not esperado or _sha256(final) == esperado):
        if ao_progresso:
            ao_progresso(final.stat().st_size, final.stat().st_size, 0.0)
        return final

    parcial = pasta / (anexo["nome"] + ".part")
    pedido = urllib.request.Request(anexo["url"], headers={
        "User-Agent": _cabecalhos()["User-Agent"],
        "Accept": "application/octet-stream"})
    h = hashlib.sha256()
    baixados = 0
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta, \
                open(parcial, "wb") as saida:
            total = int(resposta.headers.get("Content-Length") or total or 0)
            janela = deque([(time.monotonic(), 0)])
            ultimo_aviso = 0.0
            while True:
                if cancelado is not None and cancelado.is_set():
                    raise Cancelado("download cancelado")
                bloco = resposta.read(BLOCO)
                if not bloco:
                    break
                saida.write(bloco)
                h.update(bloco)
                baixados += len(bloco)
                agora = time.monotonic()
                janela.append((agora, baixados))
                while len(janela) > 2 and janela[0][0] < agora - 3.0:
                    janela.popleft()
                if ao_progresso and agora - ultimo_aviso >= 0.1:
                    ultimo_aviso = agora
                    passado = max(0.001, agora - janela[0][0])
                    ao_progresso(baixados, total,
                                 (baixados - janela[0][1]) / passado)
    except Cancelado:
        _apagar(parcial)
        raise
    except urllib.error.URLError as e:
        _apagar(parcial)
        raise ErroDeAtualizacao("o download parou: %s" % getattr(e, "reason", e))
    except OSError as e:
        _apagar(parcial)
        raise ErroDeAtualizacao("o download parou: %s" % e)

    if total and baixados != total:
        _apagar(parcial)
        raise ErroDeAtualizacao("o download veio incompleto (%d de %d bytes)"
                                % (baixados, total))
    if esperado and h.hexdigest() != esperado:
        _apagar(parcial)
        raise ErroDeAtualizacao("o arquivo baixado não é o que foi publicado "
                                "(SHA-256 diferente) -- não vou executá-lo")
    if ao_progresso:
        ao_progresso(baixados, total or baixados, 0.0)
    os.replace(parcial, final)
    return final


def _apagar(caminho):
    try:
        Path(caminho).unlink()
    except OSError:
        pass


def limpar_baixados():
    """Apaga instaladores de versões que já estão instaladas."""
    if not PASTA_DE_DOWNLOAD.is_dir():
        return
    atual = versao_atual()
    for arquivo in PASTA_DE_DOWNLOAD.iterdir():
        achado = INSTALADOR.match(arquivo.name.replace(".part", ""))
        if arquivo.name.endswith(".part") or (achado and
                                              numero(achado.group(1)) <= atual):
            _apagar(arquivo)


# ---------------------------------------------------------------------------
# a instalação
# ---------------------------------------------------------------------------
def empacotado():
    return bool(getattr(sys, "frozen", False))


def pasta_instalada():
    """
    A pasta onde o instalador pôs este programa, ou None.

    Só a cópia instalada tem o desinstalador ao lado. Uma cópia solta -- o
    `dist` de quem compila, um pendrive -- não é atualizada no lugar: a versão
    nova vai para a pasta padrão do instalador.
    """
    if not empacotado():
        return None
    pasta = Path(sys.executable).parent
    return pasta if any(pasta.glob("unins*.exe")) else None


def instalar(instalador):
    """
    Roda o instalador. Empacotado, sem perguntas e reabrindo no fim -- quem
    chama fecha o programa logo depois, para liberar o .exe.
    """
    argumentos = [str(instalador)]
    if empacotado():
        argumentos += ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                       "/CLOSEAPPLICATIONS", "/REABRIR"]
        pasta = pasta_instalada()
        if pasta is not None:
            argumentos.append("/DIR=%s" % pasta)
    bandeiras = 0
    if os.name == "nt":
        bandeiras = (getattr(subprocess, "DETACHED_PROCESS", 0)
                     | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    subprocess.Popen(argumentos, close_fds=True, creationflags=bandeiras,
                     cwd=str(Path(instalador).parent))


# ---------------------------------------------------------------------------
# texto para a tela
# ---------------------------------------------------------------------------
def tamanho(n):
    """Bytes em KB/MB/GB, com uma casa."""
    n = float(n or 0)
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return ("%d %s" % (n, unidade) if unidade == "B"
                    else "%.1f %s" % (n, unidade))
        n /= 1024.0
    return "%.1f GB" % n


def duracao(segundos):
    segundos = int(max(0, segundos))
    if segundos < 60:
        return "%d s" % segundos
    if segundos < 3600:
        return "%d min %02d s" % divmod(segundos, 60)
    horas, resto = divmod(segundos, 3600)
    return "%d h %02d min" % (horas, resto // 60)


if __name__ == "__main__":
    # `python l2atualizar.py` diz o que o programa veria, sem baixar nada.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    achado = procurar()
    print("instalada:", texto_da_versao(achado["atual"]))
    ultima = achado["ultima"]
    print("última no GitHub:", ultima and ultima["texto"],
          ultima and ultima["instalador"] and tamanho(ultima["instalador"]["tamanho"]))
    print("oferecer:", achado["alvo"] and achado["alvo"]["texto"])
