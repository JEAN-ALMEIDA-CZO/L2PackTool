#!/usr/bin/env python3
"""
Criador de NPC com efeito visual -- o motor.

O que o cliente precisa para um NPC brilhar
-------------------------------------------
Um NPC, para o cliente, e uma linha do `npcgrp.dat`. A linha diz qual malha
usar, quais texturas, quais sons -- e, na coluna `class`, qual classe
UnrealScript governa aquele boneco. Quase todos apontam para uma classe
generica (`LineageNPC.xxx`); um NPC com efeito aponta para uma classe PROPRIA,
que ao nascer cria um emissor de particulas e o gruda no esqueleto.

Ha dois caminhos, e este modulo faz os dois:

  RAPIDO   A propria linha do npcgrp tem tres colunas de efeito --
           `rb_effect_on`, `rb_effect` e `rb_effect_fl`. O cliente as usa para
           a aura dos raid bosses: 25 NPCs do cliente original as preenchem,
           sempre com `LineageEffect.ra_boss_halo_a_ca` e uma escala. Sao uma
           referencia de classe e um numero: nao ha compilacao nenhuma, so
           reescrever o .dat.

  SCRIPT   Gera a classe .uc, compila com o UCC e aponta a linha do npcgrp para
           ela. E o metodo classico, e o unico com controle fino -- altura,
           osso de encaixe, rotacao, escala, varios emissores no mesmo NPC.

Por que o caminho SCRIPT e o confiavel
--------------------------------------
Este cliente ja tem 25 NPCs feitos assim, por quem mexeu nele antes: 18 usam
`SGERfjsEffects.SGERfjs_Effect_Ice` e 7 usam `LineageNPCs6Script.effectnpc_f`.
O modelo de codigo em MODELO_UC nao foi inventado -- foi lido de dentro do
`SGERfjsEffects.u` desse cliente. Pacotes Unreal guardam o fonte original num
objeto `TextBuffer` ao lado da classe, e `Pacote.fonte()` sabe extrai-lo; o
desenho aqui e o mesmo, com os mesmos dois ganchos: `PostSetPawnResource` para
nascer e `ClearL2Game` para morrer.

O caminho RAPIDO esta documentado pelo formato do arquivo, mas nao ha neste
cliente um so exemplo dele com efeito que nao seja a aura de boss. Deve valer
para qualquer emissor -- e uma referencia de classe como outra qualquer -- mas
isso e deducao, nao observacao. Quem decide e o jogo.

Ferramentas usadas (todas ja em ferramentas/)
---------------------------------------------
    l2encdec   descriptografa e recriptografa .dat e .u do cliente
    l2disasm   .dat binario -> texto tabulado, guiado por um .ddf
    l2asm      o caminho de volta
    UCC.exe    compilador UnrealScript, do L2Editor
"""

import json
import mmap
import os
import re
import shutil
import struct
import time
from pathlib import Path

import motor
import projeto


# ---------------------------------------------------------------------------
# Definicoes .dat
# ---------------------------------------------------------------------------
# Ficam embutidas, e nao em arquivo solto, por dois motivos. Sem elas nada
# funciona -- um arquivo a mais para se perder numa copia seria um modo de
# falha novo e silencioso. E a definicao que circula (a do L2FileEdit) NAO
# monta de volta: ela chama as duas listas de textura de `tex1`, o que o
# l2disasm tolera e o l2asm recusa com "Field 'tex1' has no soft limit but is
# cntby". Aqui a segunda virou `tex2` e cada tabela dinamica ganhou o SOFT que
# o montador exige.
#
# Com esta definicao o ciclo descriptografar -> texto -> binario ->
# criptografar devolve o npcgrp.dat byte a byte igual ao original. Isso foi
# conferido antes de qualquer coisa ser escrita, e `conferir_ciclo()` refaz a
# conferencia no cliente do usuario antes da primeira gravacao.
DDF_NPCGRP = '''FS = "\\t";
RECCNT = OFF;
HEADER = YES;
MTXCNT_OUT = YES;
MATCNT_OUT = YES;
MAGIC = 0;
ORD_IGNORE = NO;

{
\tUINT tag;
\tUNICODE class;
\tUNICODE mesh;
\tUINT cnt_tex1;
\tUNICODE tex1[cnt_tex1];
\t\tSOFT = 5;
\tUINT cnt_tex2;
\tUNICODE tex2[cnt_tex2];
\t\tSOFT = 2;
\tCNTR cnt_dtab1;
\tUINT dtab1[cnt_dtab1];
\t\tSOFT = 26;
\tFLOAT npc_speed;
\tUINT unk0_cnt;
\tUNICODE unk0_tab[unk0_cnt];
\t\tSOFT = 1;
\tUINT cnt_snd1;
\tUNICODE snd1[cnt_snd1];
\t\tSOFT = 3;
\tUINT cnt_snd2;
\tUNICODE snd2[cnt_snd2];
\t\tSOFT = 5;
\tUINT cnt_snd3;
\tUNICODE snd3[cnt_snd3];
\t\tSOFT = 3;
\tUINT rb_effect_on;
\tUNICODE rb_effect;
\t\tENBBY = [(rb_effect_on: -1, 1)];
\tFLOAT rb_effect_fl;
\t\tENBBY = [(rb_effect_on: -1, 1)];
\tCNTR unk1_cnt;
\tUINT unk1_tab[unk1_cnt];
\t\tSOFT = 5;
\tUNICODE effect;
\tUINT UNK_2;
\tFLOAT sound_rad;
\tFLOAT sound_vol;
\tFLOAT sound_rnd;
\tUINT quest_be;
\tUINT class_lim;
}
'''

DDF_NPCNAME = '''FS = "\\t";
HEADER = YES;
RECCNT = OFF;
MTXCNT_OUT = YES;
MATCNT_OUT = YES;
MAGIC = 0;
ORD_IGNORE = NO;

{
\tUINT id;
\tASCF name;
\tASCF description;
\tCHEX rgb[3];
\tCHAR reserved1;
}
'''

# O metodo de criptografia esta escrito no comeco do proprio arquivo, em
# UTF-16: "Lineage2Ver413" nos .dat do Interlude, "Lineage2Ver111" nos .u. Nao
# ha o que adivinhar -- le-se e devolve-se o mesmo na hora de regravar.
_CABECALHO = re.compile(rb"^L\x00i\x00n\x00e\x00a\x00g\x00e\x002\x00V\x00e\x00r\x00"
                        rb"(\d\x00\d\x00\d\x00)")


def metodo_do_arquivo(caminho):
    """'413', '111'... ou None se o arquivo nao estiver criptografado."""
    try:
        with open(caminho, "rb") as f:
            cabeca = f.read(28)
    except OSError:
        return None

    achado = _CABECALHO.match(cabeca)
    return achado.group(1).decode("utf-16-le") if achado else None


# ---------------------------------------------------------------------------
# Pacotes Unreal (.u / .utx)
# ---------------------------------------------------------------------------
def _indice(dados, pos):
    """
    Le o inteiro compacto do Unreal: seis bits uteis no primeiro byte (mais o
    sinal e o "continua"), sete nos seguintes. Aparece em toda tabela do
    formato, entao vale a funcao propria.
    """
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


# Tipos de propriedade do UnrealScript 2, na ordem em que o formato os numera.
_TIPOS = {1: "Byte", 2: "Int", 3: "Bool", 4: "Float", 5: "Object", 6: "Name",
          7: "String", 8: "Class", 9: "Array", 10: "Struct", 11: "Vector",
          12: "Rotator", 13: "Str", 14: "Map", 15: "FixedArray"}

# Classes de emissor de particulas do motor. A presenca de um destes DENTRO de
# uma classe e o que distingue um efeito de qualquer outra classe do pacote:
# nao da para consultar a ancestralidade (a classe-mae mora noutro arquivo),
# mas os emissores sao filhos diretos e estao ali, no mesmo pacote.
EMISSORES = ("SpriteEmitter", "MeshEmitter", "BeamEmitter", "VertMeshEmitter",
             "TrailEmitter", "SparkEmitter", "ParticleEmitter")


class Pacote:
    """
    Um pacote Unreal lido o suficiente para tres perguntas: que classes existem,
    quais delas sao efeitos, e qual era o fonte delas.

    So as tabelas de nome, importacao e exportacao sao interpretadas -- nunca os
    objetos inteiros. O LineageEffect.u tem 5.495 objetos em 2 MB; ler as
    tabelas leva milissegundos e ja responde tudo o que interessa aqui.

    O arquivo e acessado por mmap, e nao lido para a memoria. A pasta system de
    um cliente tem 787 MB de pacotes, e um so deles -- L2UI_CH3.u -- tem 228.
    Ler cada um por inteiro para consultar tres tabelas que somam alguns
    kilobytes custaria minutos e gigabytes; com mmap o sistema traz do disco
    apenas as paginas efetivamente tocadas.
    """

    # Os quatro bytes C1 83 2A 9E lidos em little endian. Escrever a constante
    # na ordem em que aparece no hexdump faria todo pacote nao criptografado
    # ser recusado como "nao e um pacote Unreal" -- e os criptografados
    # tambem, logo depois de descriptografados.
    ASSINATURA = 0x9E2A83C1

    def __init__(self, caminho, ferramentas=None, temporario=None):
        self.caminho = Path(caminho)
        self.nome = self.caminho.stem
        self.puro = None
        self._fh = None
        self.dados = None

        self._abrir(ferramentas, temporario)
        try:
            dados = self.dados
            assinatura, self.versao, self.licenca = struct.unpack_from("<IHH", dados, 0)
            if assinatura != self.ASSINATURA:
                raise ValueError("%s nao e um pacote Unreal." % self.caminho.name)

            (_flags, qtd_nomes, off_nomes, qtd_exp, off_exp,
             qtd_imp, off_imp) = struct.unpack_from("<IIIIIII", dados, 8)

            self.nomes = self._ler_nomes(dados, off_nomes, qtd_nomes)
            self.imports = self._ler_imports(dados, off_imp, qtd_imp)
            self.exports = self._ler_exports(dados, off_exp, qtd_exp)
        except Exception:
            self.fechar()
            raise

    # -- leitura bruta ------------------------------------------------------
    def _abrir(self, ferramentas, temporario):
        """
        Deixa `self.dados` apontando para os bytes puros do pacote.

        Boa parte dos .u do cliente vem com cabecalho Lineage2Ver111. O
        l2encdec resolve, mas so trabalha arquivo inteiro, entao o resultado
        vai para um temporario reaproveitado enquanto o original nao mudar.
        """
        alvo = self.caminho
        metodo = metodo_do_arquivo(self.caminho)

        if metodo is not None:
            if ferramentas is None or temporario is None:
                raise ValueError("%s esta criptografado e o l2encdec nao foi informado."
                                 % self.caminho.name)

            destino = Path(temporario) / ("puro_" + self.caminho.name)
            if (not destino.exists()
                    or destino.stat().st_mtime < self.caminho.stat().st_mtime):
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.unlink(missing_ok=True)
                # Limite curto de proposito: aqui a resposta interessante e
                # "abriu ou nao abriu". Um pacote que o l2encdec nao decifra em
                # meio minuto nao vai decifrar, e a varredura tem mais quarenta
                # arquivos pela frente.
                codigo, saida = motor.executar([ferramentas["l2encdec"], "-d",
                                                self.caminho, destino], limite=30)
                # O l2encdec devolve zero mesmo quando desiste -- ele so
                # imprime o motivo. Quem diz se deu certo e o arquivo existir.
                if not destino.exists() or destino.stat().st_size == 0:
                    raise ValueError("nao consegui descriptografar %s: %s"
                                     % (self.caminho.name, saida.strip()[:160]))

            self.puro = destino
            alvo = destino

        self._fh = open(alvo, "rb")
        self.dados = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)

    def fechar(self, apagar_temporario=False):
        """Solta o arquivo. Sem isto o Windows recusa apagar o temporario."""
        if self.dados is not None:
            try:
                self.dados.close()
            except (BufferError, ValueError):
                pass
            self.dados = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        if apagar_temporario and self.puro:
            Path(self.puro).unlink(missing_ok=True)
            self.puro = None

    def __enter__(self):
        return self

    def __exit__(self, *_erro):
        self.fechar()
        return False

    @staticmethod
    def _ler_nomes(dados, pos, quantos):
        nomes = []
        for _ in range(quantos):
            tam, pos = _indice(dados, pos)
            nomes.append(dados[pos:pos + tam - 1].decode("latin-1"))
            pos += tam + 4              # a string, mais quatro bytes de flags
        # O primeiro nome e sempre "None" e vem com o primeiro byte zerado
        # neste formato. Nao adianta decodificar: e uma constante.
        if nomes:
            nomes[0] = "None"
        return nomes

    def _ler_imports(self, dados, pos, quantos):
        itens = []
        for _ in range(quantos):
            _pacote, pos = _indice(dados, pos)
            classe, pos = _indice(dados, pos)
            dono = struct.unpack_from("<i", dados, pos)[0]
            pos += 4
            nome, pos = _indice(dados, pos)
            itens.append({"classe": self.nomes[classe], "dono": dono,
                          "nome": self.nomes[nome]})
        return itens

    def _ler_exports(self, dados, pos, quantos):
        itens = []
        for _ in range(quantos):
            try:
                classe, pos = _indice(dados, pos)
                _mae, pos = _indice(dados, pos)
                dono = struct.unpack_from("<i", dados, pos)[0]
                pos += 4
                nome, pos = _indice(dados, pos)
                pos += 4                            # flags do objeto
                tamanho, pos = _indice(dados, pos)
                inicio = 0
                if tamanho > 0:
                    inicio, pos = _indice(dados, pos)
            except (IndexError, struct.error):
                # A tabela de exportacao fica no fim do arquivo, e alguns
                # pacotes perdem os ultimos bytes na descriptografia. Perder os
                # dois ultimos de 5.495 objetos nao muda um catalogo; abortar a
                # leitura inteira mudaria.
                break

            itens.append({"classe": classe, "dono": dono, "nome": self.nomes[nome],
                          "tamanho": tamanho, "inicio": inicio})
        return itens

    # -- consultas ----------------------------------------------------------
    def referencia(self, ref):
        """Resolve referencia de objeto: positiva e export, negativa e import."""
        if ref == 0:
            return None
        if ref < 0:
            indice = -ref - 1
            return self.imports[indice]["nome"] if indice < len(self.imports) else None
        return self.exports[ref - 1]["nome"] if ref - 1 < len(self.exports) else None

    def classe_de(self, exportado):
        """Nome da classe de um objeto. Referencia zero significa 'e uma Class'."""
        return self.referencia(exportado["classe"]) or "Class"

    def classes(self):
        return [e["nome"] for e in self.exports if self.classe_de(e) == "Class"]

    def pacotes_citados(self):
        """
        Os nomes de pacote que este arquivo importa, na grafia do compilador.

        E a unica fonte confiavel de como um pacote se chama de verdade: o
        nome do arquivo em disco pode estar todo em minusculas, e o pacote nao
        guarda o proprio nome em lugar nenhum.
        """
        return [i["nome"] for i in self.imports if i["classe"] == "Package"]

    def efeitos(self):
        """
        Classes do pacote que contem emissores de particula, com a contagem
        deles por tipo. Sao os efeitos utilizaveis.
        """
        achados = {}
        for e in self.exports:
            classe = self.classe_de(e)
            if classe not in EMISSORES:
                continue

            dono = self.referencia(e["dono"])
            if dono:
                achados.setdefault(dono, {})
                achados[dono][classe] = achados[dono].get(classe, 0) + 1

        validas = set(self.classes())
        return {k: v for k, v in achados.items() if k in validas}

    def propriedades(self, exportado):
        """
        As propriedades gravadas num objeto: (nome, tipo, valor).

        So os valores baratos saem preenchidos -- objeto, nome, float, inteiro
        e byte. Aqui a pergunta e sempre "que textura este emissor usa", e nada
        alem disso justifica decodificar struct por struct.
        """
        dados = self.dados
        pos = exportado["inicio"]
        fim = pos + exportado["tamanho"]
        saida = []

        while pos < fim:
            try:
                indice, pos = _indice(dados, pos)
                nome = self.nomes[indice]
                if nome == "None":
                    break

                info = dados[pos]
                pos += 1
                tipo = info & 0x0F
                codigo = (info >> 4) & 0x07

                if tipo == 10:                      # Struct: o nome dela vem antes
                    _st, pos = _indice(dados, pos)

                if codigo <= 4:
                    tamanho = (1, 2, 4, 12, 16)[codigo]
                elif codigo == 5:
                    tamanho = dados[pos]
                    pos += 1
                elif codigo == 6:
                    tamanho = struct.unpack_from("<H", dados, pos)[0]
                    pos += 2
                else:
                    tamanho = struct.unpack_from("<I", dados, pos)[0]
                    pos += 4

                if (info & 0x80) and tipo != 3:     # elemento de vetor
                    _i, pos = _indice(dados, pos)

                valor = None
                if tipo in (5, 8):
                    ref, _ = _indice(dados, pos)
                    valor = self.referencia(ref)
                elif tipo == 6:
                    ref, _ = _indice(dados, pos)
                    valor = self.nomes[ref] if ref < len(self.nomes) else None
                elif tipo == 4:
                    valor = struct.unpack_from("<f", dados, pos)[0]
                elif tipo == 2:
                    valor = struct.unpack_from("<i", dados, pos)[0]
                elif tipo == 1:
                    valor = dados[pos]

                saida.append((nome, _TIPOS.get(tipo, str(tipo)), valor))
                pos += tamanho
            except (IndexError, struct.error):
                break

        return saida

    def texturas_de(self, classe):
        """As texturas que os emissores de uma classe usam, sem repetir."""
        vistas = []
        for e in self.exports:
            if self.classe_de(e) not in EMISSORES:
                continue
            if self.referencia(e["dono"]) != classe:
                continue

            for nome, tipo, valor in self.propriedades(e):
                if tipo == "Object" and valor and nome in ("Texture", "Skin", "StaticMesh"):
                    if valor not in vistas:
                        vistas.append(valor)

        return vistas

    def fonte(self, classe):
        """
        O .uc original da classe, se o pacote ainda o guardar.

        O UCC grava o fonte num TextBuffer ao lado da classe, e os pacotes do
        Lineage 2 mantiveram esse buffer. E por isso que o modelo de codigo
        deste modulo pode ser lido de um NPC com efeito que ja funciona, em vez
        de adivinhado.
        """
        for e in self.exports:
            if self.classe_de(e) != "TextBuffer":
                continue
            if self.referencia(e["dono"]) != classe:
                continue

            pos = e["inicio"]
            marca, pos = _indice(self.dados, pos)   # fim da lista de propriedades
            if self.nomes[marca] != "None":
                continue
            pos += 8                                # Pos e Top, dois inteiros
            tam, pos = _indice(self.dados, pos)
            return self.dados[pos:pos + tam - 1].decode("latin-1")

        return None


# ---------------------------------------------------------------------------
# Catalogo de efeitos
# ---------------------------------------------------------------------------
# Pacotes do motor e da interface. Sao lidos sem erro, mas nunca tem emissor
# de particula, e alguns sao enormes -- so o L2UI_CH3.u tem 228 MB. Pular por
# prefixo, e nao por nome exato, cobre as variantes (L2UI, L2UI_VK,
# InterfaceTextures2...) que aparecem em cliente mexido.
_PREFIXOS_IGNORADOS = ("core", "engine", "editor", "unrealed", "ipdrv", "uweb",
                       "fire", "window", "uwindow", "gameplay", "l2ui",
                       "interface", "interfacetex", "udebugmenu", "nwindow",
                       "icon", "npclogotex", "drp", "anim")


def catalogar_efeitos(system, T, temporario, cache=None, aoprogresso=None):
    """
    Varre os .u da pasta system e devolve (efeitos, recusados).

    Cada efeito e {pacote, classe, caminho, emissores, total}. `caminho` ja vem
    no formato que tanto o npcgrp quanto o Spawn esperam: "Pacote.Classe".
    `recusados` e a lista de (arquivo, motivo) -- pacotes que nao abriram. Ela
    e devolvida em vez de engolida porque um efeito que o usuario procura pode
    estar justamente num deles, e um catalogo silenciosamente incompleto e pior
    do que um catalogo que admite o que faltou.

    O resultado vai para um cache em disco com o tamanho e a data de cada
    arquivo: pacote de cliente so muda quando alguem o troca, e refazer a
    varredura a cada abertura da janela seria cobrar o tempo dela sem motivo.
    """
    system = Path(system)
    arquivos = sorted(p for p in system.glob("*.u")
                      if not p.stem.lower().startswith(_PREFIXOS_IGNORADOS))

    assinatura = {p.name: [p.stat().st_size, int(p.stat().st_mtime)] for p in arquivos}

    if cache:
        cache = Path(cache)
        if cache.exists():
            try:
                guardado = json.loads(cache.read_text(encoding="utf-8"))
                if guardado.get("assinatura") == assinatura:
                    return guardado["efeitos"], guardado.get("recusados", [])
            except (ValueError, KeyError, OSError):
                pass                    # cache ilegivel nao e erro: refaz

    efeitos = []
    recusados = []
    # {nome em minusculas: grafia como os outros pacotes o escrevem}
    grafias = {}

    for i, arquivo in enumerate(arquivos):
        if aoprogresso:
            aoprogresso(i, len(arquivos), arquivo.name)

        pacote = None
        try:
            pacote = Pacote(arquivo, T, temporario)
            for citado in pacote.pacotes_citados():
                grafias.setdefault(citado.lower(), citado)

            for classe, emissores in sorted(pacote.efeitos().items()):
                efeitos.append({
                    "pacote": pacote.nome,
                    "classe": classe,
                    "emissores": emissores,
                    "total": sum(emissores.values()),
                })
        except (ValueError, OSError, struct.error, IndexError) as e:
            recusados.append([arquivo.name, str(e)[:160]])
        finally:
            if pacote:
                # O temporario descriptografado morre aqui: guardar uma copia
                # pura de 787 MB de pacotes para um catalogo de alguns
                # kilobytes seria encher o disco do usuario por nada.
                pacote.fechar(apagar_temporario=True)

    # O caminho so e montado agora, ja com a grafia certa: ela pode ter vindo
    # de um pacote lido depois daquele que define o efeito.
    for e in efeitos:
        e["pacote"] = grafias.get(e["pacote"].lower(), e["pacote"])
        e["caminho"] = "%s.%s" % (e["pacote"], e["classe"])

    efeitos.sort(key=lambda e: (e["pacote"].lower(), e["classe"].lower()))

    if cache:
        try:
            cache.write_text(json.dumps({"assinatura": assinatura, "efeitos": efeitos,
                                         "recusados": recusados}), encoding="utf-8")
        except OSError:
            pass                        # sem permissao de escrita nao impede nada

    if aoprogresso:
        aoprogresso(len(arquivos), len(arquivos), "")
    return efeitos, recusados


# ---------------------------------------------------------------------------
# npcgrp.dat
# ---------------------------------------------------------------------------
class ErroDat(Exception):
    pass



# Ate quanto um float pode mudar na ida e volta e ainda ser o mesmo numero.
# Uma parte em um milhao: o erro medido e de oito centesimos de milionesimo, e
# qualquer coisa maior do que isto nao e arredondamento de texto.
FOLGA_DO_FLOAT = 1e-6

# Quantos valores podem mudar assim antes de a coisa virar suspeita. E um
# limite de bom senso: no npcgrp de 5,4 MB do C4 mudam 43.
QUANTOS_FLOATS_CABEM = 500


def _e_o_ultimo_bit(antes, depois, posicao):
    """
    A diferenca neste byte e o ultimo bit de um float?

    O byte pode ser qualquer um dos quatro de um float, e a tabela nao e
    alinhada -- entao tenta-se ler o float comecando em cada uma das quatro
    posicoes possiveis. Basta uma delas dar dois numeros praticamente iguais.
    """
    for base in range(max(0, posicao - 3), posicao + 1):
        if base + 4 > len(antes):
            continue
        try:
            a = struct.unpack_from("<f", antes, base)[0]
            b = struct.unpack_from("<f", depois, base)[0]
        except struct.error:
            continue
        if a == b or not a:
            continue
        if abs(a - b) / abs(a) < FOLGA_DO_FLOAT:
            return True
    return False


def _comparar(antes, depois):
    """
    (passou, motivo) entre o binario original e o remontado.

    Tamanho diferente reprova na hora: ai nao e arredondamento, e estrutura.
    """
    if antes == depois:
        return True, "identico ao original"
    if len(antes) != len(depois):
        return False, ("a volta nao reproduz o original (mudou de %d para %d "
                       "bytes)" % (len(antes), len(depois)))

    diferentes = [i for i in range(len(antes)) if antes[i] != depois[i]]
    if len(diferentes) > QUANTOS_FLOATS_CABEM:
        return False, ("a volta nao reproduz o original (%d bytes diferentes)"
                       % len(diferentes))

    if all(_e_o_ultimo_bit(antes, depois, i) for i in diferentes):
        return True, ("igual, menos o ultimo bit de %d valores de ponto "
                      "flutuante -- diferenca na oitava casa decimal, que o "
                      "jogo nao distingue" % len(diferentes))

    return False, ("a volta nao reproduz o original (%d bytes diferentes, e "
                   "nem todos sao arredondamento)" % len(diferentes))


class Tabela:
    """
    Um .dat do cliente em forma de tabela: cabecalho com os nomes das colunas e
    uma lista de linhas, cada uma uma lista de strings.

    A ida e a volta passam pelo l2encdec e pelo l2disasm/l2asm, que sao os
    programas que a comunidade usa ha mais de dez anos para isso. Reimplementar
    RSA, zlib e o formato tabular em Python daria mais codigo e menos
    confianca.
    """

    def __init__(self, origem, ddf, T, trabalho, cronica=None):
        self.origem = Path(origem)
        self.ddf_texto = ddf
        self.T = T
        self.trabalho = Path(trabalho)
        self.trabalho.mkdir(parents=True, exist_ok=True)
        self.metodo = metodo_do_arquivo(self.origem)

        # `ddf_base` descreve os campos; `ddf` passa a ser a versao medida
        # neste arquivo, escrita pelo `_ler`.
        # De que cronica veio a definicao, para a mensagem de erro saber o
        # que comparar. Quem constroi a Tabela direto nao informa, e ai vale
        # a do projeto.
        self.cronica_em_uso = cronica
        self.ddf_base = self.trabalho / (self.origem.stem + "_base.ddf")
        self.ddf_base.write_text(ddf, encoding="latin-1", newline="")
        self.ddf = self.ddf_base

        self.cabecalho = []
        self.linhas = []
        self._ler()

    # -- ida ----------------------------------------------------------------
    def _ler(self):
        puro = self.trabalho / (self.origem.stem + ".dec")
        if self.metodo:
            try:
                motor.abrir_dat(self.T, self.origem, puro)
            except OSError as erro:
                raise ErroDat(str(erro))
        else:
            shutil.copy2(self.origem, puro)

        # Mede os limites NESTE arquivo antes de qualquer coisa: sem eles a
        # leitura ate sai, mas o montador recusa a definicao na hora de
        # gravar -- tabela que se le e nao se grava.
        try:
            self.ddf = motor.completar_definicao(self.T, self.ddf_base, puro,
                                                 self.trabalho)
        except OSError as erro:
            # Definicao que nao mede quase sempre e cronica errada, e o
            # programa sabe medir qual e a certa -- dizer isso aqui poupa o
            # usuario de tentar uma por uma.
            try:
                import l2item
                raise ErroDat(l2item.com_a_cronica_certa(
                    self.T, self.origem.parent, self.cronica_em_uso,
                    self.origem, self.trabalho, erro))
            except ImportError:
                raise ErroDat(str(erro))

        texto = self.trabalho / (self.origem.stem + ".txt")
        codigo, saida = motor.executar([self.T["l2disasm"], "-d", self.ddf, puro, texto])
        if not texto.exists():
            raise ErroDat(motor.explicar_saida(
                saida, "não consegui ler %s." % self.origem.name))

        conteudo = texto.read_text(encoding="utf-8", errors="replace").split("\n")
        self.cabecalho = conteudo[0].split("\t")
        self.linhas = [l.split("\t") for l in conteudo[1:] if l.strip()]
        self._puro = puro

    # -- volta --------------------------------------------------------------
    def gravar(self, destino):
        """
        Monta e criptografa de volta, com o mesmo metodo do arquivo de origem.

        Escreve primeiro num temporario e so depois move para o destino: uma
        falha no meio do caminho nao pode deixar o cliente com um npcgrp.dat
        pela metade, que e a diferenca entre "nao funcionou" e "o jogo nao
        abre mais".
        """
        destino = Path(destino)
        texto = self.trabalho / (self.origem.stem + "_novo.txt")
        linhas = ["\t".join(self.cabecalho)]
        linhas += ["\t".join(l) for l in self.linhas]
        texto.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="")

        puro = self.trabalho / (self.origem.stem + "_novo.dec")
        puro.unlink(missing_ok=True)
        codigo, saida = motor.executar([self.T["l2asm"], "-d", self.ddf, texto, puro])
        if not puro.exists():
            raise ErroDat(motor.explicar_saida(
                saida, "não consegui montar %s de volta." % self.origem.name))

        provisorio = self.trabalho / (self.origem.stem + "_novo.dat")
        provisorio.unlink(missing_ok=True)
        if self.metodo:
            codigo, saida = motor.executar([self.T["l2encdec"], "-h", self.metodo,
                                            puro, provisorio])
            if not provisorio.exists():
                raise ErroDat("l2encdec nao criptografou: %s" % saida.strip()[:200])
        else:
            shutil.copy2(puro, provisorio)

        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(provisorio), str(destino))
        return destino

    # Resultado da conferencia por arquivo ja visto nesta sessao:
    # {(caminho, tamanho, data): (deu certo, motivo)}. A conferencia remonta
    # 5,7 MB para comparar com o original; repeti-la a cada NPC criado
    # dobrava a espera para responder sempre a mesma coisa.
    _conferidos = {}

    def conferir_ciclo(self):
        """
        Monta o que foi lido, sem mudar nada, e compara com o binario original.

        E a unica prova de que a definicao .ddf descreve este arquivo
        corretamente. Se a volta nao reproduz a ida byte a byte, gravar
        qualquer alteracao seria escrever um arquivo com campos deslocados --
        e o sintoma disso nao e um erro, e o cliente carregando NPCs errados.

        So roda de fato uma vez por arquivo: o veredito nao pode mudar
        enquanto o arquivo for o mesmo.
        """
        try:
            marca = (str(self.origem), self.origem.stat().st_size,
                     int(self.origem.stat().st_mtime))
        except OSError:
            marca = None

        if marca and marca in Tabela._conferidos:
            deu, motivo = Tabela._conferidos[marca]
            return deu, motivo + " (conferido nesta sessao)"

        texto = self.trabalho / (self.origem.stem + "_conf.txt")
        linhas = ["\t".join(self.cabecalho)]
        linhas += ["\t".join(l) for l in self.linhas]
        texto.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="")

        puro = self.trabalho / (self.origem.stem + "_conf.dec")
        puro.unlink(missing_ok=True)
        motor.executar([self.T["l2asm"], "-d", self.ddf, texto, puro])
        if not puro.exists():
            if marca:
                Tabela._conferidos[marca] = (False, "o montador recusou o arquivo")
            return False, "o montador recusou o arquivo"

        resposta = _comparar(self._puro.read_bytes(), puro.read_bytes())
        if marca:
            Tabela._conferidos[marca] = resposta
        return resposta

    # -- acesso por nome de coluna -----------------------------------------
    def coluna(self, nome):
        return self.cabecalho.index(nome)

    def campo(self, linha, nome):
        try:
            return linha[self.coluna(nome)]
        except (ValueError, IndexError):
            return ""

    def definir(self, linha, nome, valor):
        linha[self.coluna(nome)] = str(valor)

    def remover_linha(self, valor, coluna=0):
        """Tira a linha daquela chave. Devolve True se achou alguma."""
        alvo = str(valor)
        antes = len(self.linhas)
        self.linhas = [l for l in self.linhas if l[coluna] != alvo]
        return len(self.linhas) != antes

    def por_chave(self, valor, coluna=0):
        alvo = str(valor)
        for linha in self.linhas:
            if linha[coluna] == alvo:
                return linha
        return None


def definicao_da_cronica(arquivo, embutida, cronica=None):
    """
    O texto .ddf daquela tabela, na cronica em uso.

    A definicao vem da pasta da cronica; a embutida no codigo fica como
    reserva, para o caso de a pasta nao ter aquele arquivo. Sem cronica dita,
    vale a do projeto -- cliente e cronica andam juntos.
    """
    if cronica is None:
        try:
            cronica = projeto.cronica()
        except Exception:                           # noqa: BLE001
            cronica = None
    caminho = motor.definicoes(cronica) / (arquivo + ".ddf")
    if caminho.is_file():
        try:
            return caminho.read_text(encoding="latin-1")
        except OSError:
            pass
    return embutida


def exigir_provada(tabela, cronica=None):
    """
    Recusa abrir tabela que a cronica declara nao provada.

    Ler com definicao que nao fecha na volta nao da erro: da campo
    deslocado. No npcgrp isso e malha e classe trocadas de NPC, e o sintoma
    aparece no jogo, nao aqui.
    """
    if cronica is None:
        try:
            cronica = projeto.cronica()
        except Exception:                           # noqa: BLE001
            cronica = None
    if motor.tabela_provada(cronica, tabela):
        return
    raise ErroDat(
        "a definicao de %s ainda nao foi provada na cronica %s: ela le o "
        "arquivo mas nao o reproduz na volta, e ler assim desloca campo sem "
        "avisar. As outras abas continuam funcionando nesta cronica."
        % (tabela, cronica or "?"))


class Npcgrp(Tabela):
    """O npcgrp.dat, com os atalhos que este programa usa."""

    def __init__(self, system, T, trabalho, cronica=None):
        exigir_provada("npcgrp", cronica)
        Tabela.__init__(self, Path(system) / "npcgrp.dat",
                        definicao_da_cronica("npcgrp", DDF_NPCGRP, cronica),
                        T, trabalho, cronica)

    def resumo(self):
        """Uma linha por NPC, so com o que a tela mostra."""
        saida = []
        for linha in self.linhas:
            efeito = ""
            if self.campo(linha, "rb_effect_on") == "1":
                efeito = self.campo(linha, "rb_effect")
            saida.append({
                "tag": linha[0],
                "classe": self.campo(linha, "class"),
                "malha": self.campo(linha, "mesh"),
                "efeito": efeito,
                "escala": self.campo(linha, "rb_effect_fl"),
            })
        return saida

    def clonar(self, tag_base, tag_novo, substituir=False):
        """
        Copia uma linha inteira sob outro id e devolve a copia, ja inserida.

        Clonar em vez de montar do zero e deliberado: uma linha do npcgrp tem
        72 colunas, e as que nao tem a ver com aparencia -- sons, raio de
        audicao, limites de classe -- precisam de valores plausiveis. Herda-las
        de um NPC que ja funciona e mais seguro do que inventa-las.
        """
        base = self.por_chave(tag_base)
        if base is None:
            raise ErroDat("o NPC base %s nao existe no npcgrp." % tag_base)

        if self.por_chave(tag_novo) is not None:
            if not substituir:
                raise ErroDat("o id %s ja existe no npcgrp. Escolha outro, ou "
                              "mande substituir." % tag_novo)
            # Substituir e tirar a linha antiga e por a nova no lugar: deixar
            # as duas faria o cliente ficar com o que viesse primeiro, sem
            # dizer qual foi.
            self.remover_linha(tag_novo)

        novo = list(base)
        novo[0] = str(tag_novo)
        self.linhas.append(novo)
        return novo

    def aplicar_efeito_rapido(self, linha, caminho_efeito, escala):
        """Preenche as tres colunas de aura que o cliente ja sabe ler."""
        self.definir(linha, "rb_effect_on", 1)
        self.definir(linha, "rb_effect", caminho_efeito)
        self.definir(linha, "rb_effect_fl", "%.8f" % float(escala))

    def limpar_efeito_rapido(self, linha):
        # Com rb_effect_on em zero as duas colunas seguintes sao desativadas
        # pela regra ENBBY da definicao, e precisam sair VAZIAS -- deixar o
        # texto la faria o montador gravar campos que o cliente nao vai ler.
        self.definir(linha, "rb_effect_on", 0)
        self.definir(linha, "rb_effect", "")
        self.definir(linha, "rb_effect_fl", "")


class Npcname(Tabela):
    """O npcname-e.dat, so para dar nome ao NPC novo."""

    def __init__(self, system, T, trabalho, cronica=None):
        Tabela.__init__(self, Path(system) / "npcname-e.dat",
                        definicao_da_cronica("npcname-e", DDF_NPCNAME, cronica),
                        T, trabalho, cronica)

    def nomes(self):
        """{id: nome} com o marcador de formato e o \\0 final removidos."""
        saida = {}
        for linha in self.linhas:
            texto = self.campo(linha, "name")
            if texto.startswith(("a,", "u,")):
                texto = texto[2:]
            saida[linha[0]] = texto.replace("\\0", "")
        return saida

    def titulos(self):
        """
        {id: titulo}. O titulo mora na coluna `description` da mesma linha.

        E o texto que aparece acima do nome do NPC em jogo -- "Gatekeeper",
        "Blacksmith". Sem ele, editar um NPC criado perdia metade da
        identificacao dele.
        """
        saida = {}
        for linha in self.linhas:
            texto = self.campo(linha, "description")
            if texto.startswith(("a,", "u,")):
                texto = texto[2:]
            saida[linha[0]] = texto.replace("\\0", "")
        return saida

    def definir_nome(self, tag, nome, titulo=""):
        """Cria ou atualiza a entrada. Devolve True se criou."""
        linha = self.por_chave(tag)
        novo = linha is None
        if novo:
            # A entrada nova e uma copia da primeira, so trocando id e nome:
            # as colunas de cor e a reservada precisam de valores plausiveis, e
            # copiar quem ja funciona e mais seguro do que inventa-los.
            if not self.linhas:
                raise ErroDat("o npcname-e.dat esta vazio; nao tenho de onde "
                              "copiar o formato de uma entrada.")
            linha = list(self.linhas[0])
            linha[0] = str(tag)
            self.linhas.append(linha)

        self.definir(linha, "name", "a,%s\\0" % nome)
        self.definir(linha, "description", "a,%s%s" % (titulo, "\\0" if titulo else ""))
        return novo


# ---------------------------------------------------------------------------
# Geracao do script
# ---------------------------------------------------------------------------
# O molde. A estrutura -- estender LineagePawn, acender em PostSetPawnResource,
# apagar em ClearL2Game -- foi lida do SGERfjsEffects.u deste cliente, que ja
# governa 18 NPCs nele.
#
# A diferenca esta em como o emissor e encontrado. O original escrevia
# Spawn(Class'SGERfjs_Effect', ...), com o efeito definido no proprio pacote;
# aqui usa-se DynamicLoadObject, que resolve o nome em tempo de execucao. Assim
# o pacote gerado nao depende, na compilacao, do arquivo que contem o efeito --
# e o que permite escolher entre os milhares de efeitos ja instalados no
# cliente sem ter que carregar nenhum deles no compilador.
# O molde e UnrealScript: tabulacao de verdade, e nao espacos.
TAB = chr(9)
NL = chr(10)

MODELO_UC = '''//=============================================================================
// %(classe)s
//
// Gerado pelo L2PackTool -- aba "NPC com efeito".
// NPC base: %(base)s
// Efeito(s): %(lista)s
//
// A receita abaixo e o que a tela le para reabrir este NPC. Sao os valores
// COMO FORAM DIGITADOS -- a altura aqui e a que o usuario pediu, e nao o
// deslocamento medido do osso que o codigo usa.
%(receita)s%(receita_npc)s
//
// Nao editar a mao: regerar pela janela e mais rapido e nao esquece nada.
//=============================================================================

class %(classe)s extends %(mae)s
\tConfig(User);

%(declaracoes)s
var Rotator SemGiro;

// PostSetPawnResource, e nao PostBeginPlay: a engine chama esta DEPOIS de por
// os recursos do boneco no lugar, e e nela que o SGERfjsEffects.u deste
// cliente acende os efeitos dos 19 NPCs que funcionam aqui. PostBeginPlay roda
// antes disso.
//
// A engine a chama por nome, entao declara-la basta -- nenhum pai precisa
// te-la, e NAO se chama Super aqui. Chamar derrubou o cliente com General
// protection fault: o Super so compilava porque a funcao tinha sido declarada
// no talo, e em jogo a classe de verdade pode nao ter uma para responder.
simulated function PostSetPawnResource()
{
%(tamanho)s
\tSemGiro.Pitch = 0;
\tSemGiro.Roll = 0;
\tSemGiro.Yaw = 0;

%(acendimentos)s}

simulated function Destroyed()
{
\tClearL2Game();
\tSuper.Destroyed();
}

// Chamado pelo cliente quando o boneco e desmontado. Sem isto o emissor fica
// orfao na cena: o NPC some e o brilho continua no lugar onde ele estava.
simulated event ClearL2Game()
{
%(apagamentos)s}

// Um Emitter nao guarda particula: guarda uma lista de ParticleEmitter, e
// cada uma decide em que sistema de coordenadas vive. PTCS_Absolute ignora o
// ator por completo; PTCS_Independent solta a particula no mundo depois de
// nascer; e o StartLocationOffset desloca o nascimento por conta propria --
// um efeito de marcador de quest ja vem feito para pairar sobre a cabeca.
//
// Com PTCS_Relative, esse sistema e o ator -- preso ao osso --, e o
// StartLocationOffset carrega a altura pedida. E o mecanismo do proprio motor.
simulated function ObedecerPosicao(Emitter Alvo, vector Desloca, float Escala)
{
	local int i;

	if ( Alvo == None )
		return;

	for ( i = 0; i < Alvo.Emitters.Length; i++ )
	{
		if ( Alvo.Emitters[i] == None )
			continue;
		Alvo.Emitters[i].CoordinateSystem = PTCS_Relative;
		Alvo.Emitters[i].StartLocationOffset = Desloca;

		// O tamanho tambem e da particula, e nao do ator: o
		// SetDrawScale do Emitter nao engorda o que o ParticleEmitter
		// desenha. A faixa onde elas nascem escala junto, senao o
		// efeito fica gordo e apertado em vez de maior.
		if ( Escala != 1.0 )
		{
			Alvo.Emitters[i].StartSizeRange.X.Min *= Escala;
			Alvo.Emitters[i].StartSizeRange.X.Max *= Escala;
			Alvo.Emitters[i].StartSizeRange.Y.Min *= Escala;
			Alvo.Emitters[i].StartSizeRange.Y.Max *= Escala;
			Alvo.Emitters[i].StartSizeRange.Z.Min *= Escala;
			Alvo.Emitters[i].StartSizeRange.Z.Max *= Escala;
			Alvo.Emitters[i].StartLocationRange.X.Min *= Escala;
			Alvo.Emitters[i].StartLocationRange.X.Max *= Escala;
			Alvo.Emitters[i].StartLocationRange.Y.Min *= Escala;
			Alvo.Emitters[i].StartLocationRange.Y.Max *= Escala;
			Alvo.Emitters[i].StartLocationRange.Z.Min *= Escala;
			Alvo.Emitters[i].StartLocationRange.Z.Max *= Escala;
		}
	}
}

simulated function Emitter Acender(string Caminho, name Osso, float Dx, float Dy, float Dz, float Escala)
{
\tlocal class<Actor> Molde;
\tlocal Emitter Novo;
\tlocal vector Ponto;

\tMolde = class<Actor>(DynamicLoadObject(Caminho, class'Class'));
\tif ( Molde == None )
\t\treturn None;

\tNovo = Emitter(Spawn(Molde, self, 'None', Location, Rotation));
\tif ( Novo == None )
\t\treturn None;

\tNovo.SetDrawScale(Escala);

\t// O SetRelativeLocation fica: ha efeito que o respeita. O que
\t// NAO da para contar com ele -- num ator preso a osso o motor
\t// recalcula a posicao a cada quadro --, e por isso quem carrega
\t// a altura de verdade e o StartLocationOffset da particula.
\tAttachToBone(Novo, Osso);
\tNovo.SetRelativeRotation(SemGiro);

\t// Os tres eixos, e nao so o Z: preso a um osso, o deslocamento vale
\t// no sistema de coordenadas DAQUELE osso, que esta girado.
\tPonto.X = Dx;
\tPonto.Y = Dy;
\tPonto.Z = Dz;
\tNovo.SetRelativeLocation(Ponto);

\treturn Novo;
}
'''

# A classe-mae de mentira, so o bastante para o compilador aceitar a heranca.
#
# O LineageWarrior.u de verdade nao serve aqui: ele foi compilado contra a
# Engine do cliente, e a Engine que acompanha o L2Editor e outra compilacao --
# recompilar o original falha em GetWalkAnimName e em meia duzia de funcoes que
# so existem numa das duas. O declarado abaixo e o que o pacote gerado
# referencia POR NOME; em jogo, quem responde e o LineagePawn de verdade.
#
# PostBeginPlay e declarado aqui de proposito: sem isso, o `Super.PostBeginPlay()`
# da classe gerada seria resolvido no Pawn do motor e pularia justamente a
# versao do LineagePawn, que e a que monta as animacoes. Declarar e seguro
# porque o LineagePawn real TEM essa funcao -- esta no fonte que o proprio
# LineageWarrior.u do cliente guarda.
#
# PostSetPawnResource NAO entra aqui, e a tentativa custou um cliente fechado.
# Declara-la no talo fez o `Super.PostSetPawnResource()` compilar; em jogo o
# pacote e ligado a classe de VERDADE, que pode nao ter essa funcao, e a
# chamada apontou para o nada:
#
#   General protection fault!
#   History: UObject::ProcessEvent <- (Npc_60000_FX ...,
#     Function FX_60000.Npc_60000_FX.PostSetPawnResource)
#     <- APawn::PostLoadProcess <- TickAllActors <- ...
#
# Quem chama PostSetPawnResource e a engine, por nome: declarar basta, e e o
# que a classe de referencia deste cliente faz -- sem Super nenhum.
TALO_LINEAGEPAWN = '''class LineagePawn extends Pawn;

simulated function PostBeginPlay()
{
\tSuper.PostBeginPlay();
}

simulated function Destroyed()
{
\tSuper.Destroyed();
}
'''

# A classe do NPC copiado, tambem de mentira. Em jogo, quem responde e a de
# verdade, com o comportamento que aquele NPC tiver.
TALO_MAE = '''class %(classe)s extends LineagePawn;
'''


def nome_de_classe(texto):
    """Transforma um texto qualquer num identificador UnrealScript valido."""
    limpo = re.sub(r"[^A-Za-z0-9_]", "_", texto.strip())
    limpo = re.sub(r"_+", "_", limpo).strip("_")
    if not limpo or limpo[0].isdigit():
        limpo = "N" + limpo
    return limpo


def fonte_uc(classe, mae, base, efeitos, esqueleto=None, tamanho=1.0):
    """
    Monta o .uc.

    `efeitos` e uma lista de dicionarios {caminho, osso, altura, escala} -- um
    por emissor a acender no mesmo NPC. `altura` e a altura DESEJADA na malha,
    contada do chao; quem a converte para o sistema de coordenadas do osso e
    esta funcao, com o `esqueleto` que veio do .psk.

    Cada emissor ganha uma variavel propria em vez de uma posicao num vetor.
    Vetor seria mais curto, mas o UnrealScript recusa vetor estatico de um
    elemento so -- "Illegal array size 1" -- e um efeito so e exatamente o caso
    mais comum. Gerar variaveis numeradas funciona para qualquer quantidade.
    """
    declaracoes, apagamentos, acendimentos = [], [], []
    receitas = []
    por_nome = {o["nome"].lower(): o for o in (esqueleto or [])}

    for i, e in enumerate(efeitos):
        var = "Aceso%d" % i
        declaracoes.append("var Emitter %s;" % var)
        apagamentos.append(
            "\tif ( %s != None )\n"
            "\t{\n"
            "\t\t%s.NDestroy();\n"
            "\t\t%s = None;\n"
            "\t}" % (var, var, var))
        osso = e.get("osso") or "Bip01"
        altura = float(e.get("altura", 0.0))
        dados = por_nome.get(osso.lower())
        if dados:
            dx, dy, dz = deslocamento_no_osso(dados, altura)
        else:
            dx, dy, dz = 0.0, 0.0, altura
        # Prende SEMPRE ao osso: o efeito acompanha o boneco, e o
        # deslocamento nao vem de mexer no ator -- vem de onde a
        # particula nasce.
        acendimentos.append(
            "\t%s = Acender(\"%s\", '%s', %.2f, %.2f, %.2f, %.2f);"
            % (var, e["caminho"], osso, dx, dy, dz,
               float(e.get("escala", 1.0))))
        obedece = bool(e.get("obedece", True))
        receitas.append('// L2PackTool-efeito: caminho="%s" osso="%s" '
                        'altura=%s escala=%s obedece=%s'
                        % (e["caminho"], osso, altura,
                           float(e.get("escala", 1.0)),
                           "1" if obedece else "0"))
        if obedece:
            acendimentos.append(
                "\tObedecerPosicao(%s, vect(%.2f,%.2f,%.2f), %.2f);"
                % (var, dx, dy, dz, float(e.get("escala", 1.0))))

    return MODELO_UC % {
        "classe": classe,
        "mae": mae,
        "base": base,
        "lista": ", ".join(e["caminho"] for e in efeitos),
        # DrawScale so entra quando ha o que mudar: uma linha a toa num
        # arquivo gerado e uma linha que alguem vai ler e se perguntar por que.
        "tamanho": ((TAB + "SetDrawScale(%.2f);" + NL) % float(tamanho)
                    if abs(float(tamanho) - 1.0) > 0.001 else ""),
        "receita_npc": ((NL + "// L2PackTool-npc: tamanho=%s" % tamanho)
                        if abs(float(tamanho) - 1.0) > 0.001 else ""),
        "receita": "\n".join(receitas),
        "declaracoes": "\n".join(declaracoes),
        "apagamentos": "\n".join(apagamentos) + "\n",
        "acendimentos": "\n".join(acendimentos) + "\n",
    }


def compilar(T, pacote, fontes, mae=None, aolog=None):
    """
    Compila um pacote UnrealScript com o UCC do L2Editor e devolve o .u.

    `mae` e o "Pacote.Classe" do NPC copiado -- a classe que a gerada estende.
    Ela nao existe no compilador (mora no cliente), entao e criado um talo com
    o nome certo: o pacote gerado passa a referencia-la POR NOME, e em jogo
    quem responde e a classe de verdade, com o comportamento dela.

    O trabalho acontece DENTRO de ferramentas/L2Editor, e nao numa copia: o
    UCC precisa dos seus dll e .u ao lado, e sao 79 MB que nao faz sentido
    duplicar a cada compilacao. Em compensacao, tudo o que e criado ali e
    apagado no fim, e os .u que a compilacao sobrescreve sao guardados e
    repostos -- a pasta termina como comecou.
    """
    system = Path(T["ucc"]).parent
    raiz = system.parent
    registro = []

    def anotar(texto):
        registro.append(texto)
        if aolog:
            aolog(texto)

    # Os talos, na ordem de compilacao: cada um so depende do anterior.
    talos = [("LineageWarrior", {"LineagePawn": TALO_LINEAGEPAWN})]

    classe_mae = "LineagePawn"
    if mae and "." in mae:
        pacote_mae, classe_mae = mae.split(".", 1)
        classe_mae = nome_de_classe(classe_mae)
        if pacote_mae.lower() != "lineagewarrior":
            talos.append((nome_de_classe(pacote_mae),
                          {classe_mae: TALO_MAE % {"classe": classe_mae}}))
        elif classe_mae != "LineagePawn":
            # A mae mora no proprio LineageWarrior: entra junto do LineagePawn.
            talos[0][1][classe_mae] = TALO_MAE % {"classe": classe_mae}

    pastas = []
    guardados = []
    try:
        for nome_talo, classes in talos:
            destino = raiz / nome_talo / "Classes"
            shutil.rmtree(raiz / nome_talo, ignore_errors=True)
            destino.mkdir(parents=True)
            for nome_classe, texto in classes.items():
                (destino / (nome_classe + ".uc")).write_text(texto, encoding="latin-1",
                                                             newline="")
            pastas.append(raiz / nome_talo)

            # Se ja existe um .u com esse nome na pasta do editor, ele e do
            # editor e nao pode ser perdido: sai da frente e volta no fim.
            antigo = system / (nome_talo + ".u")
            if antigo.exists():
                guardado = system / (nome_talo + ".u.guardado")
                guardado.unlink(missing_ok=True)
                shutil.move(str(antigo), str(guardado))
                guardados.append((guardado, antigo))

        # O pacote do usuario.
        destino = raiz / pacote / "Classes"
        shutil.rmtree(raiz / pacote, ignore_errors=True)
        destino.mkdir(parents=True)
        for nome, texto in fontes.items():
            (destino / (nome + ".uc")).write_text(texto, encoding="latin-1", newline="")
        pastas.append(raiz / pacote)

        # Um .ini so com o que vamos compilar.
        #
        # O UT2003.ini do editor lista pacotes cujo fonte nao acompanha o
        # build; o `ucc make` para no primeiro deles. Core e Engine ficam
        # porque tem dll ao lado e sao apenas carregados, nunca recompilados.
        ini = system / "BuildNpc.ini"
        modelo = (system / "UT2003.ini").read_text(encoding="latin-1", errors="replace")
        modelo = re.sub(r"(?m)^EditPackages=.*\n", "", modelo)
        lista = ["Core", "Engine"] + [n for n, _ in talos] + [pacote]
        modelo = modelo.replace(
            "[Editor.EditorEngine]",
            "[Editor.EditorEngine]\n"
            + "\n".join("EditPackages=" + n for n in lista))
        ini.write_text(modelo, encoding="latin-1", newline="")

        saida = system / (pacote + ".u")
        saida.unlink(missing_ok=True)

        anotar("compilando %s (estende %s) com o UCC..." % (pacote, mae or "LineagePawn"))
        codigo, texto = motor.executar([T["ucc"], "make", "-ini=BuildNpc.ini"], cwd=system)
        for l in texto.strip().split("\n")[-16:]:
            if l.strip():
                anotar("    " + l.strip())

        ini.unlink(missing_ok=True)
        for nome_talo, _ in talos:
            (system / (nome_talo + ".u")).unlink(missing_ok=True)

        if not saida.exists():
            raise ErroDat("o UCC nao gerou %s.u -- veja o registro acima." % pacote)

        return saida, registro
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
        for guardado, original in guardados:
            if guardado.exists():
                original.unlink(missing_ok=True)
                shutil.move(str(guardado), str(original))


# ---------------------------------------------------------------------------
# O que este programa criou
# ---------------------------------------------------------------------------
# A assinatura do programa na coluna `class` do npcgrp. Os dois numeros tem de
# ser o mesmo id -- e isso que distingue um NPC criado aqui de um pacote
# qualquer que por acaso comece com FX_.
MARCA = re.compile(r"^FX_(\d+)\.Npc_(\d+)_FX$", re.IGNORECASE)


def listar_criados(T, system, trabalho):
    """
    Os NPCs que este programa criou e instalou neste cliente.

    Le do proprio npcgrp.dat, e nao de um registro a parte, de proposito: um
    registro pode ficar desatualizado -- o usuario troca de cliente, restaura
    um backup, copia a pasta para outra maquina -- e entao a tela mostraria
    NPCs que nao existem e esconderia os que existem. O npcgrp e a verdade.
    """
    system = Path(system)
    grp = Npcgrp(system, T, trabalho)

    try:
        nomes = Npcname(system, T, trabalho).nomes()
    except ErroDat:
        nomes = {}

    achados = []
    for linha in grp.linhas:
        classe = grp.campo(linha, "class")
        marca = MARCA.match(classe)
        if not marca or marca.group(1) != marca.group(2):
            continue

        tag = linha[0]
        if marca.group(1) != tag:
            continue                    # nome de classe de outro id: nao e nosso

        pacote = system / ("FX_%s.u" % tag)
        achados.append({
            "tag": tag,
            "nome": nomes.get(tag, ""),
            "classe": classe,
            "malha": grp.campo(linha, "mesh"),
            "pacote": pacote,
            "pacote_existe": pacote.exists(),
        })

    achados.sort(key=lambda a: int(a["tag"]))
    return achados


def guardar(system, nomes, aolog=None):
    """
    Copia os arquivos citados para system/backup_npc, com data no nome.

    As copias nunca se sobrescrevem: e o que permite voltar atras depois da
    terceira ou quarta tentativa, quando ninguem lembra mais qual era o
    arquivo bom.
    """
    system = Path(system)
    destino = system / "backup_npc"
    destino.mkdir(exist_ok=True)
    carimbo = time.strftime("%Y%m%d_%H%M%S")

    for nome in nomes:
        origem = system / nome
        if not origem.exists():
            continue
        copia = destino / ("%s.%s" % (nome, carimbo))
        shutil.copy2(origem, copia)
        if aolog:
            aolog("  guardado: backup_npc/%s" % copia.name)


# As duas marcas que o proprio programa deixou no .uc gerado.
_BASE_NO_FONTE = re.compile(r"^//\s*NPC base:\s*(\d+)", re.M)
# A receita escrita pelo gerador: valores como o usuario os digitou.
_RECEITA_NPC = re.compile(r"//\s*L2PackTool-npc:\s*tamanho=([-\d.]+)")
_RECEITA = re.compile(
    r'//\s*L2PackTool-efeito:\s*caminho="([^"]*)"\s+osso="([^"]*)"\s+'
    r'altura=([-\d.]+)\s+escala=([-\d.]+)(?:\s+obedece=([01]))?')

# Reserva 1, para os NPCs criados antes de a receita existir: os argumentos da
# assinatura ANTIGA do Acender, em que os dois ultimos numeros eram altura e
# escala.
_ACENDER = re.compile(
    r"""Acender\(\s*"([^"]+)"\s*,\s*'([^']*)'\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)""")

# Reserva 2, para os gerados com a assinatura de seis numeros: caminho, osso e
# escala saem daqui, e a altura do Seguir correspondente -- casados pelo nome
# da variavel.
_ACENDER_NOVO = re.compile(
    r"""(\w+)\s*=\s*Acender\(\s*"([^"]+)"\s*,\s*'([^']*)'\s*,"""
    r"""\s*[-\d.]+\s*,\s*[-\d.]+\s*,\s*[-\d.]+\s*,\s*([-\d.]+)""")
_SEGUIR = re.compile(r"""Seguir\(\s*(\w+)\s*,\s*'[^']*'\s*,\s*([-\d.]+)""")


def _efeitos_do_fonte_novo(fonte):
    """
    As escolhas repartidas entre o Acender e o Seguir, casadas pela variavel.

    Sem `Seguir` a altura e zero: e o que "preso ao osso" quer dizer.
    """
    alturas = dict((var, valor) for var, valor in _SEGUIR.findall(fonte))
    achados = []
    for var, caminho, osso, escala in _ACENDER_NOVO.findall(fonte):
        achados.append((caminho, osso, alturas.get(var, "0"), escala))
    return achados


def ler_receita(system, tag, classe=None):
    """
    As escolhas que criaram o NPC: base, efeitos, osso, altura e escala.

    Sai do fonte que o pacote instalado guarda. Devolve None se o pacote nao
    estiver la ou se o fonte tiver sido removido dele -- caso em que so da para
    editar recomecando.
    """
    system = Path(system)
    tag = str(tag)
    pacote = system / ("FX_%s.u" % tag)
    if not pacote.exists():
        return None

    try:
        lido = Pacote(pacote)
    except (ValueError, OSError, struct.error, IndexError):
        return None

    try:
        fonte = lido.fonte(classe or ("Npc_%s_FX" % tag))
        if not fonte:
            # O nome da classe pode ter sido outro: tenta a unica que houver.
            classes = lido.classes()
            fonte = lido.fonte(classes[0]) if len(classes) == 1 else None
    finally:
        lido.fechar()

    if not fonte:
        return None

    achado = _BASE_NO_FONTE.search(fonte)
    crus = (_RECEITA.findall(fonte)
            or _efeitos_do_fonte_novo(fonte)
            or _ACENDER.findall(fonte))
    efeitos = []
    for cru in crus:
        c, o, a, e = cru[:4]
        # As receitas antigas nao tem o campo; ausente quer dizer "obedece",
        # que e o padrao de hoje.
        obedece = (cru[4] != "0") if len(cru) > 4 and cru[4] != "" else True
        try:
            efeitos.append({"caminho": c, "osso": o or "Bip01",
                            "altura": float(a), "escala": float(e),
                            "obedece": obedece})
        except ValueError:
            continue                # numero torto no fonte nao derruba a volta

    do_npc = _RECEITA_NPC.search(fonte)
    try:
        tamanho = float(do_npc.group(1)) if do_npc else 1.0
    except ValueError:
        tamanho = 1.0

    return {"base": achado.group(1) if achado else "",
            "efeitos": efeitos,
            "tamanho": tamanho,
            "fonte": fonte}


def efeitos_dos_gerados(system, npcs, aolog=None):
    """
    O efeito que cada NPC GERADO por este programa acende.

    A coluna `rb_effect` do npcgrp so serve ao modo rapido -- 25 chefes deste
    cliente a usam, e mais ninguem. Um NPC feito em modo script nao poe nada
    ali: o efeito esta dentro do pacote dele, escrito no fonte do .u. Sem ler
    o pacote, a tela mostra a coluna vazia para um NPC que tem efeito sim, o
    que parece defeito e nao e.

    Devolve {id: "caminho1, caminho2"}. So abre o pacote dos NPCs cuja classe
    tem a marca deste programa; os outros ficam de fora sem custo nenhum.
    """
    system = Path(system)
    achados = {}
    for n in npcs:
        classe = n.get("classe") or ""
        marca = MARCA.match(classe)
        if not marca or marca.group(1) != str(n.get("tag")):
            continue

        try:
            receita = ler_receita(system, n["tag"], classe.split(".")[-1])
        except Exception as e:          # pacote torto nao pode parar a leitura
            if aolog:
                aolog("%s: nao consegui ler o pacote (%s)" % (n["tag"], e))
            continue

        if receita and receita["efeitos"]:
            achados[str(n["tag"])] = ", ".join(e["caminho"]
                                               for e in receita["efeitos"])
    return achados


def remover_npc(T, system, trabalho, tag, saida=None, aolog=None):
    """
    Desfaz um NPC criado: tira as linhas dos .dat e apaga o pacote dele.

    Nao restaura copia de seguranca. Restaurar traria de volta o npcgrp inteiro
    como estava antes daquele NPC, e junto levaria embora todos os outros
    criados depois -- a remocao tem de valer so para o id pedido.
    """
    system = Path(system)
    registro = []

    def anotar(texto):
        registro.append(texto)
        if aolog:
            aolog(texto)

    tag = str(tag)
    anotar("removendo o NPC %s..." % tag)

    grp = Npcgrp(system, T, trabalho)
    ok, motivo = grp.conferir_ciclo()
    anotar("conferencia do npcgrp: %s" % motivo)
    if not ok:
        raise ErroDat("o npcgrp.dat deste cliente nao volta identico pela "
                      "definicao embutida. Gravar seria arriscado, entao parei.")

    linha = grp.por_chave(tag)
    if linha is None:
        raise ErroDat("o id %s nao esta no npcgrp deste cliente." % tag)

    classe = grp.campo(linha, "class")
    marca = MARCA.match(classe)
    if not marca:
        raise ErroDat("o NPC %s nao foi criado por este programa (classe %s). "
                      "Nao vou mexer nele." % (tag, classe))

    # Copia antes de escrever: esta e a unica operacao do programa que mexe
    # direto no cliente sem passar por uma pasta de saida, e desfazer uma
    # remocao errada sem copia significaria refazer o NPC do zero.
    guardar(system, ["npcgrp.dat", "npcname-e.dat"], anotar)

    grp.remover_linha(tag)
    grp.gravar(system / "npcgrp.dat")
    anotar("  npcgrp.dat: linha do %s removida (%d NPCs restantes)."
           % (tag, len(grp.linhas)))

    try:
        nomes = Npcname(system, T, trabalho)
        if nomes.remover_linha(tag):
            nomes.gravar(system / "npcname-e.dat")
            anotar("  npcname-e.dat: nome removido.")
        else:
            anotar("  npcname-e.dat: nao havia nome para este id.")
    except ErroDat as e:
        anotar("  aviso: nao consegui mexer no npcname-e.dat (%s)." % e)

    pacote = system / ("%s.u" % classe.split(".")[0])
    if pacote.exists():
        pacote.unlink()
        anotar("  apagado do cliente: %s" % pacote.name)
    else:
        anotar("  %s nao estava no cliente." % pacote.name)

    # Os arquivos que sobraram na pasta de saida daquela geracao.
    if saida:
        saida = Path(saida)
        sufixos = ("FX_%s.u" % tag, "Npc_%s_FX.uc" % tag, "npc_%s.xml" % tag)
        for nome in sufixos:
            alvo = saida / nome
            if alvo.exists():
                alvo.unlink()
                anotar("  apagado da saida: %s" % nome)

    anotar("pronto. Falta so apagar o XML do servidor: "
           "data/xml/npcs/custom/npc_%s.xml, e //reload npc." % tag)
    return registro


# ---------------------------------------------------------------------------
# A malha do NPC
# ---------------------------------------------------------------------------
# Onde procurar o pacote de uma malha, na ordem em que costuma estar. O npcgrp
# da o nome como "Pacote.malha" e nunca diz em que pasta o pacote mora.
_PASTAS_DE_MALHA = ("animations", "staticmeshes", "systextures", "textures")


def pacote_da_malha(cliente, malha):
    """
    O arquivo que contem a malha, e a pasta dele.

    `malha` vem do npcgrp no formato "LineageMonsters.orc_m00". Devolve
    (caminho do pacote, nome da malha) ou (None, nome).
    """
    if not malha or "." not in malha:
        return None, malha

    # O cliente pode ter sido apontado pela pasta system; a raiz e a mae dela.
    raiz = Path(cliente)
    if raiz.name.lower() == "system":
        raiz = raiz.parent

    nome_pacote, nome_malha = malha.split(".", 1)
    for pasta in _PASTAS_DE_MALHA:
        diretorio = raiz / pasta
        if not diretorio.is_dir():
            continue
        for extensao in (".ukx", ".usx", ".utx"):
            # O Windows nao diferencia maiusculas, mas o glob do Python sim.
            achados = list(diretorio.glob(nome_pacote + extensao))
            if not achados:
                achados = [q for q in diretorio.iterdir()
                           if q.name.lower() == (nome_pacote + extensao).lower()]
            if achados:
                return achados[0], nome_malha

    return None, nome_malha


def dados_da_malha(T, cliente, malha, trabalho, cache=None):
    """
    A altura do boneco e a lista de ossos dele.

    Devolve {"altura": float, "ossos": [nomes]} -- ou None se a malha nao for
    encontrada. As duas coisas saem do mesmo .psk, entao sai tudo de uma
    exportacao so.

    A altura vem do alcance em Z da nuvem de vertices, que e exatamente a
    unidade que o SetRelativeLocation usa. Nao ha jeito mais direto: o npcgrp
    nao guarda tamanho, e a altura do XML do servidor e a caixa de colisao,
    que e outra coisa.

    Os ossos importam porque e neles que o efeito se prende. O primeiro da
    lista e a raiz do esqueleto.

    O resultado vai para um cache: exportar leva um decimo de segundo e a
    resposta nao muda enquanto o cliente for o mesmo.
    """
    if not malha:
        return None

    guardado = {}
    if cache:
        cache = Path(cache)
        if cache.exists():
            try:
                guardado = json.loads(cache.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                guardado = {}
        anotado = guardado.get(malha)
        # Cache antigo guardava so o numero, depois so a altura e os ossos, e
        # depois ainda sem o alcance por eixo. Faltando qualquer um dos dois,
        # refaz: sem o esqueleto o efeito nao vai para a altura certa, e sem o
        # alcance por eixo a regua da arma nao tem o que medir.
        if (isinstance(anotado, dict) and anotado.get("esqueleto")
                and anotado.get("x_min") is not None):
            return anotado

    pacote, nome = pacote_da_malha(cliente, malha)
    if pacote is None:
        return None

    destino = Path(trabalho) / "psk"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)

    motor.executar([T["umodel"], "-export", "-game=l2",
                    "-path=" + str(pacote.parent), "-out=" + str(destino),
                    pacote.name, nome], limite=120)

    achado = None
    for arquivo in destino.rglob("*.psk"):
        achado = _ler_psk(arquivo.read_bytes())
        if achado and achado.get("altura") is not None:
            break

    shutil.rmtree(destino, ignore_errors=True)

    if cache and achado:
        guardado[malha] = achado
        try:
            cache.write_text(json.dumps(guardado), encoding="utf-8")
        except OSError:
            pass

    return achado


def _quat_vezes(a, b):
    """Produto de dois quaternions no formato (x, y, z, w)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _quat_gira(q, v):
    """Aplica o quaternion ao vetor."""
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx))


def _quat_inverso(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def _resolver_ossos(crus):
    """
    Percorre a cadeia e devolve a posicao e a rotacao de cada osso na malha.

    O `.psk` guarda cada osso em relacao ao pai. Somar so as posicoes daria
    errado: a do filho esta no sistema de coordenadas girado do pai, entao a
    rotacao tem de ser acumulada junto.

    O quaternion da raiz vem direto; os demais vem conjugados, que e como o
    formato foi escrito desde sempre.
    """
    resolvidos = []
    for i, osso in enumerate(crus):
        q = osso["quat"]
        if i > 0:
            q = _quat_inverso(q)
        if i == 0 or osso["pai"] >= len(resolvidos):
            mundo_q, mundo_p = q, osso["pos"]
        else:
            pai = resolvidos[osso["pai"]]
            mundo_q = _quat_vezes(pai["quat"], q)
            girado = _quat_gira(pai["quat"], osso["pos"])
            mundo_p = tuple(pai["pos"][k] + girado[k] for k in range(3))
        # De todos os eixos locais, qual sobe mais no mundo? E por ele que o
        # deslocamento tem de ir, e ele muda de osso para osso.
        eixos = {"X": _quat_gira(mundo_q, (1.0, 0.0, 0.0)),
                 "Y": _quat_gira(mundo_q, (0.0, 1.0, 0.0)),
                 "Z": _quat_gira(mundo_q, (0.0, 0.0, 1.0))}
        eixo, direcao = max(eixos.items(), key=lambda par: par[1][2])
        resolvidos.append({"nome": osso["nome"], "pai": osso["pai"],
                           "quat": mundo_q, "pos": mundo_p,
                           "eixo": eixo, "subida": direcao[2]})
    return resolvidos


def deslocamento_no_osso(osso, altura_desejada):
    """
    O vetor local que leva o efeito ate `altura_desejada` na malha.

    O `SetRelativeLocation` de um ator preso a um osso trabalha no sistema de
    coordenadas DAQUELE osso, que esta girado. Pedir "para cima" e, portanto,
    girar o vetor do mundo para dentro desse sistema -- e nao escrever a altura
    no Z e torcer.
    """
    subir = float(altura_desejada) - float(osso["pos"][2])
    return _quat_gira(_quat_inverso(osso["quat"]), (0.0, 0.0, subir))


def _ler_psk(dados):
    """
    Altura e ossos de um .psk.

    O formato e uma sequencia de blocos, cada um com cabecalho de 32 bytes:
    nome, sinalizadores, tamanho do registro e quantidade. PNTS0000 traz as
    posicoes dos vertices, tres floats cada; REFSKELT traz os ossos, com o nome
    nos primeiros 64 bytes de cada registro.
    """
    saida = {"altura": None, "raio": None, "ossos": [], "chao": None,
             "topo": None, "esqueleto": []}
    crus = []
    pos = 0

    while pos + 32 <= len(dados):
        try:
            nome = dados[pos:pos + 20].split(b"\0")[0].decode("latin-1")
            _flags, tamanho, quantos = struct.unpack_from("<iii", dados, pos + 20)
        except (struct.error, UnicodeDecodeError):
            break

        pos += 32
        if quantos < 0 or tamanho < 0:
            break

        try:
            if nome == "PNTS0000" and quantos > 0 and tamanho >= 12:
                pontos = [struct.unpack_from("<fff", dados, pos + i * tamanho)
                          for i in range(quantos)]
                zs = [p[2] for p in pontos]
                saida["altura"] = round(max(zs) - min(zs), 1)
                # O chao nao e o zero: a origem da malha fica na cintura, e os
                # pes ficam abaixo dela.
                saida["chao"] = round(min(zs), 2)
                saida["topo"] = round(max(zs), 2)
                # A largura sai da mesma nuvem: o maior alcance horizontal a
                # partir do eixo. Serve para o raio de colisao, que hoje vinha
                # de um numero fixo.
                largura = max(abs(p[0]) for p in pontos)
                fundura = max(abs(p[1]) for p in pontos)
                saida["raio"] = round(max(largura, fundura), 1)
                # Cada eixo por si: a arma deita no eixo do comprimento, e e
                # nele que o glow anda. Juntos, os dois so dizem "o maior".
                for eixo, k in (("x", 0), ("y", 1), ("z", 2)):
                    valores = [p[k] for p in pontos]
                    saida[eixo + "_min"] = round(min(valores), 2)
                    saida[eixo + "_max"] = round(max(valores), 2)
            elif nome == "REFSKELT" and quantos > 0 and tamanho >= 120:
                for i in range(quantos):
                    base = pos + i * tamanho
                    crus.append({
                        "nome": dados[base:base + 64].split(b"\0")[0]
                                .decode("latin-1").strip(),
                        "pai": struct.unpack_from("<i", dados, base + 72)[0],
                        "quat": struct.unpack_from("<ffff", dados, base + 76),
                        "pos": struct.unpack_from("<fff", dados, base + 92),
                    })
                saida["ossos"] = [o["nome"] for o in crus]
            elif nome == "REFSKELT" and quantos > 0 and tamanho >= 64:
                saida["ossos"] = [
                    dados[pos + i * tamanho:pos + i * tamanho + 64]
                    .split(b"\0")[0].decode("latin-1").strip()
                    for i in range(quantos)]
        except (struct.error, UnicodeDecodeError):
            pass

        pos += tamanho * quantos

    if crus:
        try:
            saida["esqueleto"] = _resolver_ossos(crus)
        except Exception:
            saida["esqueleto"] = []
    return saida if (saida["altura"] is not None or saida["ossos"]) else None



def texturas_do_npc(grp, linha):
    """
    As texturas que o npcgrp manda aplicar neste NPC.

    Sao as colunas `tex1[*]`, e ha clientes com dois conjuntos (o segundo
    entra em NPC que troca de aparencia). Devolve a lista sem repetir e sem
    vazio, na ordem em que aparecem.
    """
    achadas = []
    for coluna in grp.cabecalho:
        if not coluna.lower().startswith("tex"):
            continue
        if coluna.lower().startswith("cnt_"):
            continue
        valor = (grp.campo(linha, coluna) or "").strip()
        if valor and valor not in achadas:
            achadas.append(valor)
    return achadas


def recado_das_texturas(texturas):
    """
    O que dizer ao abrir o visualizador, quando ha mais de uma textura.

    Uma textura so: a malha ja a traz, e a janela sai certa -- nao ha o que
    explicar. Mais de uma: o cliente aplica as outras por cima, o umodel nao,
    e a diferenca aparece como parte sem textura.
    """
    if len(texturas) <= 1:
        return ""
    return ("Este NPC usa %d texturas, que o cliente aplica sobre a malha:\n"
            "  %s\n\n"
            "O visualizador mostra só a que está embutida no material da "
            "malha -- as partes em xadrez ou em cor chapada são as outras. "
            "Não é textura faltando no cliente: nenhum visualizador de fora "
            "do jogo faz essa troca, que o motor faz ao criar o boneco."
            % (len(texturas), "\n  ".join(texturas)))


# A coluna que diz se o NPC tem efeito. Nao existe nas cronicas de texto, e e
# por ela que se sabe se vale oferecer a funcao.
COLUNA_DO_EFEITO = "rb_effect_on"


class NpcgrpTexto(object):
    """
    O npcgrp de C1 e C2, com os atalhos que as telas usam.

    Herdaria da TabelaCompativel se o l2compat pudesse ser importado no topo
    -- mas ele importa o l2texto, que importa este modulo. Composicao resolve
    sem ciclo: tudo o que nao esta aqui e perguntado a tabela de dentro.
    """

    def __init__(self, system, T, trabalho, cronica=None):
        import l2compat
        alvo = l2compat.caminho_de_texto(system, "npcgrp.dat")
        if not alvo.is_file():
            raise ErroDat("nao achei o npcgrp desta cronica em %s" % system)
        self.tabela = l2compat.TabelaCompativel(alvo, T, trabalho, "npcgrp")
        self.cronica_em_uso = cronica

    def __getattr__(self, nome):
        return getattr(self.tabela, nome)

    def tem_efeito(self):
        """Esta cronica prende efeito ao NPC pelo npcgrp?"""
        try:
            self.tabela.coluna(COLUNA_DO_EFEITO)
            return True
        except ValueError:
            return False

    def resumo(self):
        """Uma linha por NPC, com o que a tela mostra. Sem efeito, que nao ha."""
        saida = []
        for linha in self.tabela.linhas:
            saida.append({
                "tag": self.tabela.campo(linha, "id"),
                "classe": self.tabela.campo(linha, "class"),
                "malha": self.tabela.campo(linha, "mesh"),
                "efeito": "",
                "escala": "",
            })
        return saida


def abrir_npcgrp(system, T, trabalho, cronica=None):
    """
    O npcgrp desta cronica, binario ou de texto.

    Quem chama nao precisa saber qual e: os dois respondem `linhas`, `campo`
    e `resumo`.
    """
    if cronica is None:
        try:
            cronica = projeto.cronica()
        except Exception:                           # noqa: BLE001
            cronica = None
    if motor.formato_da_cronica(cronica) == "texto":
        return NpcgrpTexto(system, T, trabalho, cronica)
    return Npcgrp(system, T, trabalho, cronica)

def abrir_visualizador(T, cliente, malha):
    """
    Abre o visualizador 3D do umodel na malha do NPC.

    Ele mostra o boneco com textura e roda as animacoes. NAO mostra o efeito:
    emissor de particula nao esta entre os recursos que o umodel abre, e
    nenhum visualizador de Lineage 2 desenha particula do Unreal Engine 2 --
    isso so o motor do jogo faz.

    A janela e um processo a parte, que segue vivo depois desta chamada: quem
    fecha e o usuario.
    """
    pacote, nome = pacote_da_malha(cliente, malha)
    if pacote is None:
        raise ErroDat("nao achei o pacote da malha %s nas pastas %s do cliente."
                      % (malha, ", ".join(_PASTAS_DE_MALHA)))

    # O `-path` e a RAIZ do cliente, e nao a pasta do pacote.
    #
    # A malha mora em `animations`, mas a textura dela mora em `systextures`, e
    # o umodel so acha o que estiver sob o `-path`. Apontando so para a pasta
    # do pacote, ele carregava a geometria e nao achava material nenhum -- 58
    # avisos de import perdido -- e a janela abria com o boneco sem textura,
    # que na pratica e uma tela clara e vazia.
    #
    # Com a raiz ele acha as duas: a mesma malha exporta junto com os shaders
    # `lilim_knight_t00/t01` e as texturas delas. Varrer o cliente inteiro
    # custa a fracao de segundo do scan, e e o que faz o visualizador mostrar
    # o boneco em vez de um vulto branco.
    raiz_do_cliente = Path(cliente)
    if raiz_do_cliente.name.lower() == "system":
        raiz_do_cliente = raiz_do_cliente.parent

    # So o CREATE_NO_WINDOW, e nao o motor._SEM_JANELA inteiro.
    #
    # Aquele carrega tambem STARTF_USESHOWWINDOW com SW_HIDE, que serve para as
    # ferramentas de console nao piscarem uma janela preta -- mas escondia
    # tambem a janela do visualizador, que e o que se quer ver. Sem flag
    # nenhuma, por outro lado, o console do umodel aparece cheio de avisos de
    # som que nao interessam a ninguem. O CREATE_NO_WINDOW sozinho faz o certo:
    # suprime o console e deixa o programa abrir as janelas dele.
    import subprocess
    motor.registrar_filho(subprocess.Popen(
        [str(T["umodel"]), "-view", "-game=l2",
         "-path=" + str(raiz_do_cliente), pacote.name, nome],
        cwd=str(Path(T["umodel"]).parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)),
        "umodel (%s)" % nome)
    return pacote


# Os comandos de console que o Engine.dll do cliente reconhece em modo de
# desenvolvimento. Foram lidos do proprio binario, onde ficam em PARES -- o
# nome por extenso seguido do atalho curto --, que e como o ParseCommand os
# compara. Os nomes sao certos; os argumentos marcados com "=" sao o que os
# literais vizinhos indicam.
COMANDOS_DEVMODE = (
    ("nv", "NpcViewer -- o visualizador de NPC"),
    ("pv", "PawnViewer -- o visualizador de personagem"),
    ("sv", "SkillViewer -- o visualizador de skill"),
    ("SPAWNACTOR Class=FX_<id>.Npc_<id>_FX", "faz nascer a classe gerada aqui"),
    ("SPAWNNPCS", "faz nascer NPCs do npcgrp"),
    ("MESHCHANGE MESHNAME=<Pacote.malha>", "troca a malha do boneco"),
    ("CHANGEANIM ANIM=WAIT|WALK|RUN", "troca a animacao"),
    ("DEFAULTCAMERA DISTANCE=200 PITCH=0 YAW=0", "posiciona a camera"),
    ("AddEffect / DeleteEffect", "poe e tira efeito no alvo"),
    ("BONESCALE / BS", "escala de osso, para conferir encaixe"),
    ("DeleteSelectedActor", "apaga o que estiver selecionado"),
    ("CheckGrp", "confere os .dat e aponta os erros deles"),
)


# Os .ini que o jogo em DevMode reescreve em texto puro, e que no cliente sao
# CRIPTOGRAFADOS. Depois de um DevMode sem protecao, o jogo normal abre com
# erro porque nao consegue mais le-los.
INIS_PROTEGIDOS = ("l2.ini", "user.ini")

# Onde as copias ficam esperando a volta do jogo.
PASTA_GUARDA = "backup_devmode"


def _system_do_cliente(cliente):
    system = Path(cliente)
    return system if system.name.lower() == "system" else system / "system"


def ini_criptografado(caminho):
    """True se o arquivo tem o cabecalho Lineage2Ver, como os .dat."""
    return metodo_do_arquivo(caminho) is not None


def guardar_inis(cliente, aolog=None):
    """
    Copia os .ini protegidos antes de abrir o DevMode.

    Devolve a lista do que foi guardado. Se ja houver copias pendentes de uma
    sessao anterior, elas NAO sao sobrescritas: a copia antiga e a boa, e a
    atual pode ja ser a versao estragada.
    """
    system = _system_do_cliente(cliente)
    guarda = system / PASTA_GUARDA
    guarda.mkdir(exist_ok=True)
    feitos = []

    for nome in INIS_PROTEGIDOS:
        origem = system / nome
        if not origem.exists():
            continue

        destino = guarda / nome
        if destino.exists():
            if aolog:
                aolog("  ja havia copia de %s guardada; mantida a antiga." % nome)
            feitos.append(nome)
            continue

        shutil.copy2(origem, destino)
        feitos.append(nome)
        if aolog:
            aolog("  guardado: %s (%s)"
                  % (nome, "criptografado" if ini_criptografado(origem)
                     else "texto puro"))

    return feitos


def restaurar_inis(cliente, aolog=None):
    """
    Devolve os .ini guardados e apaga as copias.

    Tem de ser chamado DEPOIS que o jogo fechou: e ao sair que o Unreal grava a
    configuracao, entao restaurar com ele aberto seria escrever para ser
    sobrescrito.
    """
    system = _system_do_cliente(cliente)
    guarda = system / PASTA_GUARDA
    if not guarda.is_dir():
        return []

    feitos = []
    for nome in INIS_PROTEGIDOS:
        copia = guarda / nome
        if not copia.exists():
            continue

        destino = system / nome
        estragado = destino.exists() and not ini_criptografado(destino)
        shutil.copy2(copia, destino)
        copia.unlink()
        feitos.append(nome)
        if aolog:
            aolog("  %s devolvido%s." % (nome,
                  " (o DevMode tinha deixado texto puro no lugar)" if estragado
                  else ""))

    try:
        guarda.rmdir()
    except OSError:
        pass        # sobrou alguma coisa la dentro; nao e problema

    return feitos


def tem_inis_guardados(cliente):
    """Se sobrou copia de uma sessao que nao chegou a ser devolvida."""
    guarda = _system_do_cliente(cliente) / PASTA_GUARDA
    return guarda.is_dir() and any((guarda / n).exists() for n in INIS_PROTEGIDOS)


def jogo_aberto():
    """True se ha um L2.exe rodando. Por nome, porque o processo e elevado."""
    codigo, saida = motor.executar(
        ["tasklist", "/FI", "IMAGENAME eq L2.exe", "/NH"], limite=20)
    return "L2.exe" in saida


def abrir_devmode(cliente, aolog=None):
    """
    Abre o cliente em modo de desenvolvimento, sem servidor.

    E a linha que o proprio start_devmode.cmd do cliente ja usa:
    `L2.exe -INI=devmode.ini -ng`. O devmode.ini manda carregar um mapa local
    (LocalMap) em vez de entrar num servidor, e liga o menu de depuracao.

    Antes de abrir, guarda os .ini que o DevMode reescreve. Devolver as copias
    e tarefa de quem chamou, depois que o jogo fechar -- ver `restaurar_inis`.

    Devolve o caminho do L2.exe. Nao espera o jogo fechar.
    """
    system = _system_do_cliente(cliente)

    exe = system / "L2.exe"
    if not exe.exists():
        raise ErroDat("nao achei o L2.exe em %s." % system)

    ini = system / "devmode.ini"
    if not ini.exists():
        raise ErroDat("este cliente nao tem devmode.ini em %s. Sem ele o jogo "
                      "tenta entrar num servidor em vez de abrir um mapa local."
                      % system)

    guardar_inis(cliente, aolog)

    # Pelo shell, e nao por CreateProcess direto: o L2.exe tem manifesto de
    # administrador, e um Popen comum falha com "a operacao solicitada requer
    # elevacao" (WinError 740). O os.startfile passa pelo ShellExecute, que
    # sabe pedir a elevacao ao usuario -- e e o mesmo caminho do
    # start_devmode.cmd que acompanha o cliente.
    os.startfile(str(exe), arguments="-INI=devmode.ini -ng", cwd=str(system))
    return exe


# ---------------------------------------------------------------------------
# Lado do servidor
# ---------------------------------------------------------------------------
def xml_servidor(tag, nome, titulo, base_tag, social=1):
    """
    O trecho de XML para o L2J, no formato do aCis/L2JMega.

    O cliente sozinho nao faz NPC nenhum aparecer: ele so sabe desenhar o que o
    servidor mandar nascer. `idTemplate` e o que amarra os dois -- e o id que o
    cliente procura no npcgrp.

    `social` e a animacao que o NPC toca quando o jogador clica nele -- e o que
    faz o jogador perceber que o NPC notou. Uma malha tem no maximo tres slots
    sociais (SpWait01, spwait02, spwait03) e varias tem so um, por isso o
    padrao e 1: e o unico que praticamente toda malha possui. Zero devolve o
    NPC ao sorteio de sempre.

    A estrutura tem de ser exatamente esta, e nao ha margem: o NpcTable pega
    `doc.getFirstChild()` e varre os filhos DELE atras de elementos "npc".
    Sem o <list> em volta, ele varre os <set> de um <npc> solitario, nao acha
    nada, e termina sem carregar nem reclamar -- o erro so aparece depois, em
    jogo, quando o //spawn responde que o id nao existe.
    """
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<list>\n'
        '\t<!-- Gerado pelo L2PackTool.\n'
        '\t     Coloque em data/xml/npcs/custom/ e reinicie o gameserver.\n'
        '\t     NPC base copiado no cliente: %(base)s -->\n'
        '\t<npc id="%(tag)s" idTemplate="%(tag)s" name="%(nome)s" title="%(titulo)s">\n'
        '\t\t<set name="usingServerSideName" val="true"/>\n'
        '\t\t<set name="usingServerSideTitle" val="%(usa_titulo)s"/>\n'
        '%(social)s'
        '\t\t<set name="level" val="70"/>\n'
        '\t\t<set name="radius" val="8"/>\n'
        '\t\t<set name="height" val="24"/>\n'
        '\t\t<set name="type" val="Folk"/>\n'
        '\t\t<set name="hp" val="2444"/>\n'
        '\t\t<set name="mp" val="1345"/>\n'
        '\t\t<set name="hpRegen" val="7.5"/>\n'
        '\t\t<set name="mpRegen" val="2.7"/>\n'
        '\t\t<set name="pAtk" val="688"/>\n'
        '\t\t<set name="pDef" val="295"/>\n'
        '\t\t<set name="mAtk" val="470"/>\n'
        '\t\t<set name="mDef" val="216"/>\n'
        '\t\t<set name="crit" val="4"/>\n'
        '\t\t<set name="atkSpd" val="253"/>\n'
        '\t\t<set name="str" val="40"/>\n'
        '\t\t<set name="int" val="21"/>\n'
        '\t\t<set name="dex" val="30"/>\n'
        '\t\t<set name="wit" val="20"/>\n'
        '\t\t<set name="con" val="43"/>\n'
        '\t\t<set name="men" val="20"/>\n'
        '\t\t<set name="exp" val="0"/>\n'
        '\t\t<set name="sp" val="0"/>\n'
        '\t\t<set name="corpseTime" val="7"/>\n'
        '\t\t<set name="aggroRange" val="0"/>\n'
        '\t\t<set name="rHand" val="0"/>\n'
        '\t\t<set name="lHand" val="0"/>\n'
        '\t\t<set name="walkSpd" val="50"/>\n'
        '\t\t<set name="runSpd" val="120"/>\n'
        '\t\t<set name="targetable" val="true"/>\n'
        '\t\t<set name="undying" val="true"/>\n'
        '\t</npc>\n'
        '</list>\n'
    ) % {"tag": tag, "nome": nome or ("NPC " + str(tag)),
         "titulo": titulo, "usa_titulo": "true" if titulo else "false",
         "base": base_tag,
         # Zero significa "sorteia como sempre", que e o que o servidor faz
         # com qualquer NPC que nao declare o campo.
         "social": ('\t\t<set name="socialAction" val="%d"/>\n' % int(social))
                   if int(social) > 0 else ""}


# ---------------------------------------------------------------------------
# A operacao inteira
# ---------------------------------------------------------------------------
def criar_npc(T, system, trabalho, saida, base_tag, novo_tag, efeitos,
              modo="script", pacote=None, classe=None, nome="", titulo="",
              escala_rapida=1.0, substituir=False, social=1, aolog=None,
              servidor_pronto=None, tamanho=1.0):
    """
    Gera tudo o que um NPC com efeito precisa, sem tocar no cliente.

    Devolve um dicionario com os arquivos produzidos. Nada e instalado aqui --
    `instalar()` e um passo separado, de proposito: o usuario ve o que saiu,
    confere, e so entao autoriza a copia sobre o cliente que ele usa para
    jogar.
    """
    system = Path(system)
    trabalho = Path(trabalho)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    registro = []

    def anotar(texto):
        registro.append(texto)
        if aolog:
            aolog(texto)

    if not efeitos:
        raise ErroDat("escolha pelo menos um efeito.")

    anotar("lendo npcgrp.dat...")
    grp = Npcgrp(system, T, trabalho)
    anotar("    %d NPCs no arquivo." % len(grp.linhas))

    ok, motivo = grp.conferir_ciclo()
    anotar("conferencia do ciclo de leitura e escrita: %s" % motivo)
    if not ok:
        raise ErroDat("o npcgrp.dat deste cliente nao volta identico pela "
                      "definicao embutida. Gravar seria arriscado, entao parei.")

    linha = grp.clonar(base_tag, novo_tag, substituir=substituir)
    anotar("NPC %s clonado de %s (malha %s)."
           % (novo_tag, base_tag, grp.campo(linha, "mesh")))

    relatorio = {"registro": registro, "modo": modo, "tag": str(novo_tag),
                 "base": str(base_tag), "arquivos": {}}

    if modo == "rapido":
        grp.aplicar_efeito_rapido(linha, efeitos[0]["caminho"], escala_rapida)
        anotar("coluna rb_effect preenchida com %s (escala %.2f)."
               % (efeitos[0]["caminho"], float(escala_rapida)))
        if len(efeitos) > 1:
            anotar("    aviso: o modo rapido so tem uma coluna de efeito; "
                   "os outros %d foram ignorados." % (len(efeitos) - 1))
    else:
        # O sufixo _FX nao e enfeite: o UCC avisa "Class names shouldn't end
        # in a digit", e todo id de NPC termina em digito.
        pacote = nome_de_classe(pacote or ("FX_%s" % novo_tag))
        classe = nome_de_classe(classe or ("Npc_%s_FX" % novo_tag))
        # A classe do NPC copiado, que a gerada vai estender. E o que preserva
        # o comportamento dele: animacao, conversa, o que aquele tipo de NPC
        # fizer. Herdar de LineagePawn direto jogaria tudo isso fora.
        mae = grp.campo(linha, "class")
        classe_mae = nome_de_classe(mae.split(".")[-1]) if mae else "LineagePawn"
        anotar("classe do NPC base: %s" % (mae or "(nenhuma)"))

        # O esqueleto da malha e o que permite converter a altura pedida para
        # o sistema de coordenadas do osso. Sem ele o efeito sai no lugar
        # errado -- e nao ter a malha nao pode impedir a geracao.
        esqueleto = []
        try:
            malha = grp.campo(linha, "mesh")
            informacao = dados_da_malha(T, system, malha, trabalho) or {}
            esqueleto = informacao.get("esqueleto") or []
            if esqueleto:
                anotar("esqueleto lido: %d ossos, chao em %.2f."
                       % (len(esqueleto), informacao.get("chao") or 0.0))
        except Exception as e:
            anotar("aviso: nao consegui ler o esqueleto da malha (%s); a "
                   "altura vai no eixo Z, como se o osso fosse a raiz." % e)

        texto = fonte_uc(classe, classe_mae,
                         "%s (%s)" % (base_tag, grp.campo(linha, "mesh")),
                         efeitos, esqueleto, tamanho=tamanho)

        arquivo_uc = saida / (classe + ".uc")
        arquivo_uc.write_text(texto, encoding="latin-1", newline="")
        relatorio["arquivos"]["uc"] = arquivo_uc
        anotar("fonte gerado: %s" % arquivo_uc.name)

        compilado, log = compilar(T, pacote, {classe: texto}, mae=mae,
                                  aolog=anotar)
        destino_u = saida / (pacote + ".u")
        shutil.copy2(compilado, destino_u)
        compilado.unlink(missing_ok=True)
        relatorio["arquivos"]["u"] = destino_u
        relatorio["pacote"] = pacote
        relatorio["classe"] = classe
        anotar("pacote compilado: %s (%d bytes)" % (destino_u.name, destino_u.stat().st_size))

        grp.definir(linha, "class", "%s.%s" % (pacote, classe))
        grp.limpar_efeito_rapido(linha)
        anotar("coluna class do NPC %s apontada para %s.%s" % (novo_tag, pacote, classe))

    destino_grp = saida / "npcgrp.dat"
    grp.gravar(destino_grp)
    relatorio["arquivos"]["npcgrp"] = destino_grp
    anotar("npcgrp.dat gerado (%d NPCs)." % len(grp.linhas))

    # O nome nunca fica vazio: sem ele, o cliente desenha "NoNameNPC" sobre a
    # cabeca do monstro enquanto o servidor chama o mesmo id de "NPC 90006".
    # Um id, um nome -- e o mesmo dos dois lados.
    nome = (nome or "").strip()
    if not nome:
        try:
            nome = (Npcname(system, T, trabalho).nomes().get(str(base_tag), "")
                    or "").strip()
        except ErroDat:
            nome = ""
        nome = nome or ("NPC %s" % novo_tag)
        anotar("nome em branco; usando \"%s\" nos dois lados." % nome)

    if nome:
        try:
            nomes = Npcname(system, T, trabalho)
            criou = nomes.definir_nome(novo_tag, nome, titulo)
            destino_nome = saida / "npcname-e.dat"
            nomes.gravar(destino_nome)
            relatorio["arquivos"]["npcname"] = destino_nome
            anotar("npcname-e.dat: nome \"%s\" %s." % (nome, "criado" if criou else "atualizado"))
        except ErroDat as e:
            # Nome e enfeite: o servidor pode manda-lo com usingServerSideName.
            # Perder o npcname nao pode derrubar a geracao inteira.
            anotar("aviso: nao consegui escrever o npcname-e.dat (%s). "
                   "O servidor ainda pode enviar o nome." % e)

    # O lado do servidor vem pronto de quem chamou quando a tela preencheu os
    # atributos, o drop e a loja. So na falta disso vale o molde fixo daqui --
    # que e uma casca com valores de exemplo, e nao o NPC que o usuario montou.
    #
    # Dois arquivos para o mesmo id seria pior do que um errado: quem
    # instalasse os dois ficaria com o servidor lendo o que viesse por ultimo.
    if servidor_pronto:
        texto, extensao = servidor_pronto
    else:
        texto = xml_servidor(novo_tag, nome, titulo, base_tag, social)
        extensao = ".xml"
    arquivo_xml = saida / ("npc_%s%s" % (novo_tag, extensao))
    arquivo_xml.write_text(texto, encoding="utf-8", newline="")
    relatorio["arquivos"]["xml"] = arquivo_xml
    anotar("Lado do servidor gerado: %s" % arquivo_xml.name)

    return relatorio



def _garantir_chave_do_cliente(system, aolog=None):
    """Converte o cliente para a chave em que gravamos, se precisar."""
    try:
        import l2chaves
        T = motor.carregar_config()
        l2chaves.garantir_para_gravar(
            T, system, Path(motor.BASE) / "trabalho" / "chaves", aolog=aolog)
    except Exception as erro:                       # noqa: BLE001
        if aolog:
            aolog("  nao deu para conferir a chave do cliente: %s" % erro)


def instalar(relatorio, system, aolog=None):
    """
    Copia o que foi gerado para o cliente, guardando antes o que estava la.

    As copias de seguranca levam a data no nome e nunca sao sobrescritas: e o
    que permite voltar atras depois da terceira ou quarta tentativa, quando
    ninguem lembra mais qual era o arquivo bom.
    """
    system = Path(system)
    feitos = []

    # Cliente oficial vira cliente convertido antes de receber qualquer
    # tabela: as duas chaves no mesmo cliente nao convivem.
    _garantir_chave_do_cliente(system, aolog)

    # Os do servidor e o fonte nao vao para o cliente.
    alvos = [(c, Path(o)) for c, o in relatorio["arquivos"].items()
             if c not in ("xml", "uc")]

    guardar(system, [o.name for _c, o in alvos], aolog)

    for _chave, origem in alvos:
        destino = system / origem.name
        shutil.copy2(origem, destino)
        feitos.append(destino.name)
        if aolog:
            aolog("instalado: %s" % destino.name)

    return feitos
