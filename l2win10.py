#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fazer as crônicas antigas (C1 a C4) abrirem no Windows 10 e 11.

São duas correções, cada uma num arquivo da `system`. Nenhuma tem posição
fixa: cada uma procura no arquivo a forma exata do código que conserta, e só
mexe se a forma bater inteira. O original vai para `system/backup_win10/`
antes, e desfazer é copiar de volta.

## Core.dll -- o jogo trava antes de abrir

O `Core.dll` tem um construtor global -- código que roda sozinho quando a DLL
é carregada -- que faz isto:

    CoInitializeEx(0, 0)
    CoCreateInstance({53e96b9b-3784-4edc-a80d-268cb5b5ec0d}, CLSCTX_ALL, ...)
    se falhar: OutputDebugString(...) e segue

A classe não existe em Windows nenhum, e o jogo foi feito para seguir sem
ela. No XP a resposta "classe não registrada" vinha na hora. No Windows 10 o
`CLSCTX_ALL` faz o COM consultar o serviço do sistema por RPC -- e isso
acontece DENTRO do carregamento das DLLs, com o carregador travado. A
resposta nunca chega: o `L2.exe` fica parado em 14 MB, sem janela e sem log.

Medido no C2: pilha da thread principal `Core.dll+0x7C780` (o retorno do
CoCreateInstance) -> combase -> RPC. O mesmo código aparece TRÊS vezes em
cada `Core.dll` de C1 a C4 (dois construtores e um método), e as três são
trocadas: o `test eax,eax / jl fim` depois do CoInitializeEx vira
`jmp fim`, que é o caminho que o jogo já tinha para "classe não registrada".

A comunidade resolvia isto com um `vista7.dll` acoplado ao `Core.dll` de cada
pack; a troca do byte faz o mesmo sem DLL de terceiros.

## D3DDrv.dll -- a caixa "AGP is deactivated"

O renderizador pergunta à placa se ela tem memória AGP
(`D3DDEVCAPS_TEXTURENONLOCALVIDMEM`). Placa e driver de hoje não declaram
isso, e o jogo para numa caixa "Warning" esperando o clique -- depois segue
exatamente pelo mesmo caminho de quem tem AGP. A correção mantém a linha
`WARNING : no AGP support detected` no log e pula só a caixa: a instrução
seguinte ao registro vira um salto para depois do `MessageBoxW`.
"""

import shutil
import struct
import uuid
from pathlib import Path

PASTA_DE_COPIAS = "backup_win10"


class ErroWin10(Exception):
    pass


# ---------------------------------------------------------------------------
# PE: o minimo para converter entre arquivo e memoria
# ---------------------------------------------------------------------------
def _pe(dados):
    """(ImageBase, secoes [(va, tam_virtual, raw, tam_raw)], importacoes)."""
    pe = struct.unpack_from("<I", dados, 0x3C)[0]
    if dados[pe:pe + 4] != b"PE\0\0":
        raise ErroWin10("não é um executável do Windows")
    n = struct.unpack_from("<H", dados, pe + 6)[0]
    opt = pe + 24
    tam_opt = struct.unpack_from("<H", dados, pe + 20)[0]
    base = struct.unpack_from("<I", dados, opt + 28)[0]
    secoes = []
    for i in range(n):
        _nome, vs, va, rs, raw = struct.unpack_from("<8sIIII", dados, opt + tam_opt + i * 40)
        secoes.append((va, vs, raw, rs))
    return base, secoes, opt


def _rva(secoes, deslocamento):
    for va, _vs, raw, rs in secoes:
        if raw <= deslocamento < raw + rs:
            return va + deslocamento - raw
    return None


def _desloc(secoes, rva):
    for va, vs, raw, rs in secoes:
        if va <= rva < va + max(vs, rs):
            return raw + rva - va
    return None


def _endereco_da_importacao(dados, nome_da_funcao):
    """O VA da entrada da IAT de uma funcao importada (por nome), ou None."""
    base, secoes, opt = _pe(dados)
    rva_imp = struct.unpack_from("<I", dados, opt + 104)[0]
    off = _desloc(secoes, rva_imp)
    if off is None:
        return None
    while True:
        ilt, _t, _f, nome, iat = struct.unpack_from("<IIIII", dados, off)
        if not nome:
            return None
        o = _desloc(secoes, ilt or iat)
        k = 0
        while o is not None:
            v = struct.unpack_from("<I", dados, o)[0]
            if not v:
                break
            if not v & 0x80000000:
                p = _desloc(secoes, v + 2)
                if p is not None and dados[p:p + len(nome_da_funcao) + 1] == nome_da_funcao + b"\0":
                    return base + iat + 4 * k
            o += 4
            k += 1
        off += 20


def _push_da_string(dados, texto):
    """Os deslocamentos de cada `push <endereco da string>` (utf-16 ou ascii)."""
    base, secoes, _opt = _pe(dados)
    saida = []
    for forma in (texto.encode("utf-16-le") + b"\0\0", texto.encode("latin-1") + b"\0"):
        i = dados.find(forma)
        if i < 0:
            continue
        rva = _rva(secoes, i)
        if rva is None:
            continue
        empurra = b"\x68" + struct.pack("<I", base + rva)
        j = dados.find(empurra)
        while j >= 0:
            saida.append(j)
            j = dados.find(empurra, j + 1)
    return saida


# ---------------------------------------------------------------------------
# As correcoes
# ---------------------------------------------------------------------------
class Correcao:
    """Uma troca de bytes num arquivo da system."""
    arquivo = ""
    titulo = ""

    def pontos(self, dados):
        """[(deslocamento, bytes_originais, bytes_novos, ja_aplicado)]."""
        raise NotImplementedError


class TravaDoCom(Correcao):
    arquivo = "Core.dll"
    titulo = "o jogo trava antes de abrir"
    CLSID = uuid.UUID("53e96b9b-3784-4edc-a80d-268cb5b5ec0d").bytes_le

    def pontos(self, dados):
        i = dados.find(self.CLSID)
        if i < 0:
            return []
        base, secoes, _opt = _pe(dados)
        rva = _rva(secoes, i)
        if rva is None:
            return []
        empurra = b"\x68" + struct.pack("<I", base + rva)
        achados = []
        j = dados.find(empurra)
        while j >= 0:
            trecho = dados[max(0, j - 48):j]
            for valor, feito in ((0x7C, False), (0xEB, True)):
                k = trecho.rfind(b"\x85\xc0" + bytes([valor]))
                # salto curto e para frente, logo antes do push da classe
                if k >= 0 and 0 < trecho[k + 3] < 0x80:
                    pos = max(0, j - 48) + k + 2
                    achados.append((pos, b"\x7c", b"\xeb", feito))
                    break
            j = dados.find(empurra, j + 1)
        return achados


class AvisoDeAgp(Correcao):
    """
    O trecho, no C3 (as outras cronicas mudam so os enderecos):

        test ah, 0x10                  ; D3DDEVCAPS_TEXTURENONLOCALVIDMEM
        je   sem_agp                   ; 74 22
        ... log "AGP support detected"
        jmp  depois_da_caixa           ; EB 76
      sem_agp:
        ... log "WARNING : no AGP support detected"
        ... MessageBoxW("AGP is deactivated")
      depois_da_caixa:

    O `je` passa a cair no `jmp depois_da_caixa`: um byte de deslocamento
    relativo. A primeira versao trocava um `mov eax,[endereco]` por um salto,
    e o endereco absoluto daquele mov tem relocacao -- carregado fora do
    endereco preferido, o Windows "corrigia" o salto e o jogo caia num GPF.
    """
    arquivo = "D3DDrv.dll"
    titulo = 'a caixa "AGP is deactivated"'
    DETECTADO = "D3D Driver: AGP support detected"
    TESTE = b"\xf6\xc4\x10"                             # test ah, 0x10

    def pontos(self, dados):
        achados = []
        for p in _push_da_string(dados, self.DETECTADO):
            k = dados.rfind(self.TESTE, max(0, p - 0x20), p)
            if k < 0:
                continue
            # o je vem logo depois do test -- o compilador pode ter posto
            # uma instrucao no meio (no C3, `mov [ebx+0x60], ecx`)
            for je in range(k + 3, min(k + 12, p)):
                if dados[je] != 0x74:
                    continue
                fim_do_je = je + 2
                destino = fim_do_je + dados[je + 1]
                if not p < destino < p + 0x60:
                    continue
                if dados[destino] == 0xEB:
                    # ja adaptado: o je cai direto no jmp que pula a caixa
                    achados.append((je + 1, b"", bytes([dados[je + 1]]), True))
                elif dados[destino - 2] == 0xEB:
                    # original: o je cai no bloco "sem AGP", logo depois do jmp
                    novo = (destino - 2) - fim_do_je
                    achados.append((je + 1, bytes([dados[je + 1]]), bytes([novo]), False))
                break
        return achados


CORRECOES = (TravaDoCom(), AvisoDeAgp())


# ---------------------------------------------------------------------------
# O que a tela e a linha de comando usam
# ---------------------------------------------------------------------------
def _arquivo(system, nome):
    system = Path(system)
    if not system.is_dir():
        return None
    for p in system.iterdir():
        if p.name.lower() == nome.lower() and p.is_file():
            return p
    return None


def diagnostico(system):
    """
    [(correcao, caminho, estado)] para cada correcao que se aplica.

    estado: "precisa", "adaptado" ou "nao_se_aplica".
    """
    saida = []
    for c in CORRECOES:
        caminho = _arquivo(system, c.arquivo)
        if caminho is None:
            saida.append((c, None, "nao_se_aplica"))
            continue
        pts = c.pontos(caminho.read_bytes())
        if not pts:
            estado = "nao_se_aplica"
        elif all(p[3] for p in pts):
            estado = "adaptado"
        else:
            estado = "precisa"
        saida.append((c, caminho, estado))
    return saida


def estado(system):
    """O resumo para a tela: (estado geral, frase)."""
    diag = diagnostico(system)
    if not any(c[1] for c in diag):
        return "sem_core", "não achei o Core.dll em %s" % system
    precisam = [c.titulo for c, _p, e in diag if e == "precisa"]
    feitas = [c.titulo for c, _p, e in diag if e == "adaptado"]
    if precisam:
        return "precisa", ("Este cliente precisa de adaptação para o Windows "
                           "10/11: %s." % "; ".join(precisam))
    if feitas:
        return "adaptado", "Este cliente já está adaptado para o Windows 10/11."
    return "nao_se_aplica", ("Este cliente não tem os defeitos conhecidos do "
                             "Windows 10/11 -- nada a fazer.")


def adaptar(system, aolog=None):
    """Aplica o que faltar. Devolve a lista de arquivos alterados."""
    def diga(t):
        if aolog:
            aolog(t)

    alterados = []
    for correcao, caminho, situacao in diagnostico(system):
        if situacao != "precisa":
            continue
        dados = bytearray(caminho.read_bytes())
        pts = [p for p in correcao.pontos(bytes(dados)) if not p[3]]
        guarda = Path(system) / PASTA_DE_COPIAS
        guarda.mkdir(exist_ok=True)
        copia = guarda / (caminho.name + ".original")
        if not copia.exists():
            shutil.copy2(caminho, copia)
            diga("Original guardado em %s" % copia)
        for pos, antes, depois, _feito in pts:
            if dados[pos:pos + len(antes)] != antes:
                raise ErroWin10("%s mudou durante a leitura -- nada foi gravado"
                                % caminho.name)
            dados[pos:pos + len(depois)] = depois
        temporario = caminho.with_name(caminho.name + ".win10")
        temporario.write_bytes(bytes(dados))
        # Conferencia: do mesmo tamanho, e agora todos os pontos aplicados.
        novo = temporario.read_bytes()
        if len(novo) != len(caminho.read_bytes()) or \
                not all(p[3] for p in correcao.pontos(novo)):
            temporario.unlink(missing_ok=True)
            raise ErroWin10("a conferência de %s falhou -- nada foi gravado"
                            % caminho.name)
        temporario.replace(caminho)
        alterados.append(caminho)
        diga("%s adaptado (%s): %s." % (caminho.name, correcao.titulo,
                                        ", ".join("0x%X" % p[0] for p in pts)))
    if not alterados:
        diga("Nada a fazer: o cliente já está como precisa.")
    return alterados


def desfazer(system, aolog=None):
    """Devolve os originais guardados em backup_win10."""
    guarda = Path(system) / PASTA_DE_COPIAS
    if not guarda.is_dir():
        raise ErroWin10("não há cópias em %s" % guarda)
    devolvidos = []
    for copia in sorted(guarda.glob("*.original")):
        destino = Path(system) / copia.name[:-len(".original")]
        shutil.copy2(copia, destino)
        devolvidos.append(destino)
        if aolog:
            aolog("%s original devolvido." % destino.name)
    return devolvidos
