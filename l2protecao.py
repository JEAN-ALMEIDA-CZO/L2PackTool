#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fechar o cliente com a chave de quem é dono dele.

## O que este módulo faz, em uma frase

Troca a chave dos arquivos escolhidos do `system` pela chave derivada de uma
frase que só o dono sabe, e escreve essa chave dentro do executável do cliente
-- para que o jogo continue abrindo os arquivos e mais ninguém consiga
produzir arquivos que ele aceite.

## A ordem importa, e é esta

    1. copiar o original para `backup_protecao` (uma vez por arquivo);
    2. abrir com a chave atual -- a do cliente, ou a do l2encdec;
    3. fechar com a chave nova;
    4. ABRIR DE NOVO e comparar byte a byte com o passo 2;
    5. só então trocar o arquivo, e por último a chave do executável.

O passo 4 é o que separa esta função de uma que estraga cliente. Arquivo que
não volta igual não é instalado, e o `system` fica como estava.

O executável é o ÚLTIMO a mudar: enquanto ele tem a chave velha, um arquivo
novo já gravado só deixaria o jogo sem abrir aquele arquivo. Na ordem
contrária -- exe primeiro --, um erro no meio deixaria o cliente inteiro sem
abrir nada.

## Onde funciona, e onde não

Do C3 ao Interlude o módulo RSA mora como texto hexa dentro do `l2.exe` e do
`engine.dll`, e é trocável. Do Kamael em diante o executável vem empacotado: a
chave só existe em memória, entregue pelo loader, e trocá-la exigiria um
loader próprio -- que este programa não escreve. Nesses clientes a página
oferece o que dá: fechar com a chave do l2encdec, que já tira o cliente da
lista dos que se abrem com as chaves originais.

## O que isso protege

A ESCRITA. Sem a frase, ninguém gera um `itemname-e.dat` que o seu cliente
aceite.

A LEITURA não, e nenhum esquema do lado do cliente protege: para jogar, o
cliente precisa abrir, e por isso carrega a chave de leitura dentro de si.
Quem tem o seu cliente pode achá-la -- este mesmo programa acha em
milissegundos. O que a chave própria faz é tirar o seu servidor do "qualquer
um abre com um clique" e pôr no "quem souber procurar".
"""

import shutil
import time
from pathlib import Path

import l2cripto
import motor

PASTA_GUARDA = "backup_protecao"

# O formato em que tudo sai. E o unico que tem chave -- os outros usam senha
# fixa ou derivada do nome, e ali nao ha o que trocar.
METODO_DE_CHAVE = "413"

# O que o WINDOWS carrega, e nao o cliente. Cifrado, nao carrega -- e o jogo
# nem abre. Nao entra na protecao por cifra de jeito nenhum; para esses ha a
# lista de impressoes digitais, em `assinar` e `conferir_assinaturas`.
DO_WINDOWS = (".dll", ".exe", ".sys", ".vxd", ".ocx", ".drv", ".des")

NOME_DAS_IMPRESSOES = "impressoes-do-cliente.txt"

# As pastas do cliente que guardam conteudo carregado pelo jogo. Sao estas que
# o botao "todos os pacotes" varre -- o resto do cliente e executavel,
# configuracao solta e som.
PASTAS_DE_CONTEUDO = ("system", "SysTextures", "systextures", "Animations",
                      "animations", "MAPS", "maps", "StaticMeshes",
                      "staticmeshes", "Textures", "textures")

# O que esses pacotes sao, por extensao.
PACOTES = (".utx", ".u", ".ukx", ".usx", ".unr", ".int", ".usk")

# Configuracao lida como TEXTO pelo motor, antes de qualquer decifragem.
# Cifrar um desses nao da erro: o jogo ignora a configuracao em silencio, que
# e pior. Medido: L2.ini e User.ini JA vem cifrados de fabrica e nao entram
# nesta regra -- a regra vale para o que vem cru.
CONFIGURACAO = (".ini", ".int_", ".cfg")

# Os grupos que a tela oferece. Nome do arquivo em minusculas, porque o disco
# do Windows nao liga e o do usuario pode ter qualquer caixa.
GRUPOS = (
    ("itens", "Itens e armas",
     ("weapongrp.dat", "armorgrp.dat", "etcitemgrp.dat", "itemname-e.dat")),
    ("skills", "Habilidades",
     ("skillgrp.dat", "skillname-e.dat", "skillsoundgrp.dat")),
    ("npcs", "NPCs e monstros",
     ("npcgrp.dat", "npcname-e.dat", "mobskillanimgrp.dat")),
    ("mundo", "Mundo e textos",
     ("zonename-e.dat", "questname-e.dat", "systemmsg-e.dat",
      "sysstring-e.dat", "huntingzone-e.dat")),
)


class ErroDeProtecao(Exception):
    pass


def arquivos_do_grupo(system, chaves):
    """Os arquivos que existem, para os grupos escolhidos."""
    system = Path(system)
    quero = set()
    for chave, _rotulo, nomes in GRUPOS:
        if chave in chaves:
            quero.update(n.lower() for n in nomes)
    achados = []
    for arquivo in sorted(system.iterdir()):
        if arquivo.is_file() and arquivo.name.lower() in quero:
            achados.append(arquivo)
    return achados



def _relativo(caminho, system):
    """
    O caminho do arquivo dentro do cliente, para a copia de seguranca.

    Guardar so o nome bastava enquanto tudo vinha da `system`. Alcancando o
    cliente inteiro, dois arquivos de mesmo nome em pastas diferentes --
    e isso existe -- se sobrescreveriam na volta.
    """
    caminho, raiz = Path(caminho), Path(system).parent
    try:
        return Path(caminho).resolve().relative_to(raiz.resolve())
    except (ValueError, OSError):
        return Path(caminho.name)


def pacotes_do_cliente(system):
    """Todo pacote das pastas de conteudo do cliente, sem repetir."""
    raiz = Path(system).parent
    vistos, saida = set(), []
    for nome in PASTAS_DE_CONTEUDO:
        pasta = raiz / nome
        if not pasta.is_dir():
            continue
        for arquivo in sorted(pasta.iterdir()):
            chave = str(arquivo).lower()
            if (arquivo.is_file() and arquivo.suffix.lower() in PACOTES
                    and chave not in vistos):
                vistos.add(chave)
                saida.append(arquivo)
    return saida

def estado_do_cliente(system):
    """
    O que dá para fazer neste cliente. Devolve um dicionário para a tela.

    `trocavel` é o que decide tudo: sem ele, chave própria não é possível, e
    a tela precisa dizer isso antes de a pessoa escolher arquivos.
    """
    system = Path(system)
    onde = l2cripto.onde_trocar_a_chave(system) if system.is_dir() else []
    return {
        "system": system,
        "existe": system.is_dir(),
        "trocavel": bool(onde),
        "executaveis": [p for p, _o, _m in onde],
        "modulo_atual": onde[0][2] if onde else None,
    }


def marca_da_chave(modulo):
    """Oito dígitos do começo e do fim -- para conferir sem mostrar a chave."""
    texto = "%064x" % modulo if modulo else ""
    return "%s…%s" % (texto[:8], texto[-8:]) if texto else "—"


def _abrir_como_der(T, caminho, modulo=None):
    """
    O conteúdo aberto, tentando a chave do cliente e depois o l2encdec.

    Devolve (conteúdo, método, rabo, de_onde). A ordem não é gosto: a chave do
    cliente é a que vale para os arquivos dele, e o l2encdec entra quando o
    arquivo veio de outro lugar -- ou quando o método não é dos que este
    programa faz sozinho.
    """
    dados = Path(caminho).read_bytes()
    met = l2cripto.metodo(dados)
    if met is None:
        return dados, None, b"", "não estava cifrado"

    if met in l2cripto.SO_XOR:
        conteudo, rabo = l2cripto.abrir_xor(dados, met, Path(caminho).name)
        return conteudo, met, rabo, "chave do formato"

    if modulo is not None:
        expoente = l2cripto.expoente_que_abre(dados, modulo)
        if expoente is not None:
            conteudo, rabo = l2cripto.abrir_41x(dados, modulo, expoente)
            return conteudo, met, rabo, "chave do cliente"

    # Sobrou o l2encdec, que tem as chaves originais e a dele.
    #
    # Aqui vai `l2item._decifrar`, e nao `motor.descriptografar`: o segundo foi
    # escrito para PACOTE e confirma o resultado procurando a assinatura
    # Unreal. Tabela e configuracao nao tem assinatura nenhuma, e por isso ele
    # recusava arquivo que tinha sido aberto certo -- inclusive o
    # itemname-e.dat, que e o principal.
    import l2item

    trabalho = Path(motor.BASE) / "trabalho" / "protecao"
    trabalho.mkdir(parents=True, exist_ok=True)
    try:
        aberto = l2item._decifrar(T, Path(caminho), trabalho)
    except Exception as erro:                       # noqa: BLE001
        raise ErroDeProtecao(
            "não consegui abrir %s: nem a chave do cliente nem o l2encdec "
            "serviram (%s)." % (Path(caminho).name, str(erro)[:70]))
    if aberto is None or not Path(aberto).is_file():
        raise ErroDeProtecao(
            "não consegui abrir %s: nem a chave do cliente nem o l2encdec "
            "serviram." % Path(caminho).name)
    return Path(aberto).read_bytes(), met, dados[-l2cripto.RABO:], "l2encdec"


def proteger(T, system, escolhidos, frase, aolog=None, trocar_exe=True,
             converter=False):
    """
    Fecha os arquivos escolhidos com a chave da frase. Devolve o relatório.

    Nada é instalado sem passar pela conferência: cada arquivo é reaberto com
    a chave nova e comparado com o que saiu da leitura. O executável só muda
    depois de todos os arquivos, e só se todos passarem.

    `converter` estende a proteção aos arquivos que não usam formato de chave
    -- os pacotes e os que vêm sem cifra nenhuma. Eles são fechados no formato
    de chave, que o cliente escolhe pelo cabeçalho. Vem desligado porque essa
    conversão não tem amostra em cliente original: ver o cabeçalho deste
    módulo.
    """
    def diga(texto):
        if aolog:
            aolog(texto)

    estado = estado_do_cliente(system)
    if not estado["existe"]:
        raise ErroDeProtecao("não achei a pasta system em %s" % system)
    if not estado["trocavel"] and trocar_exe:
        raise ErroDeProtecao(
            "este cliente guarda a chave empacotada (Kamael em diante): não dá "
            "para escrever a sua nela. Use a opção sem troca de chave.")

    alvos = [Path(p) for p in escolhidos]
    if not alvos:
        raise ErroDeProtecao("nenhum arquivo escolhido.")

    modulo_atual = estado["modulo_atual"]
    expoente = l2cripto.EXPOENTE_413
    for alvo in alvos:
        if l2cripto.metodo(alvo.read_bytes()[:28]) in ("411", "412", "413",
                                                       "414"):
            achado = (l2cripto.expoente_que_abre(alvo.read_bytes(),
                                                 modulo_atual)
                      if modulo_atual else None)
            if achado:
                expoente = achado
                break

    par = l2cripto.par_da_frase(frase, expoente=expoente)
    diga("chave da frase: %d bits, expoente 0x%x, marca %s"
         % (par["bits"], par["publico"], marca_da_chave(par["modulo"])))

    guarda = Path(system) / PASTA_GUARDA
    guarda.mkdir(parents=True, exist_ok=True)
    prontos, recusados = [], []

    for alvo in alvos:
        try:
            conteudo, met, rabo, de_onde = _abrir_como_der(T, alvo,
                                                           modulo_atual)
            if met is None and alvo.suffix.lower() in CONFIGURACAO:
                # Config que vem crua o motor le como texto, antes de
                # decifrar. Cifrada, ela nao da erro: passa a ser ignorada em
                # silencio -- e ninguem liga o problema a isto.
                recusados.append((alvo.name, "configuração lida como texto"))
                diga("  %-22s RECUSADO: é configuração que o jogo lê como "
                     "texto; cifrada, ela passaria a ser ignorada em silêncio."
                     % alvo.name)
                continue

            if alvo.suffix.lower() in DO_WINDOWS:
                # Recusado, e nao avisado: quem carrega isto e o Windows, e
                # cifrado ele nao carrega. Seria entregar um cliente que nao
                # abre.
                recusados.append((alvo.name, "o Windows é quem carrega"))
                diga("  %-22s RECUSADO: quem carrega este arquivo é o "
                     "Windows, não o cliente -- cifrado, ele não carrega e o "
                     "jogo não abre. Use «impressões digitais» para ele."
                     % alvo.name)
                continue

            precisa_converter = met is None or met in l2cripto.SO_XOR
            if precisa_converter and not converter:
                porque = ("não está cifrado" if met is None
                          else "formato %s não usa chave" % met)
                recusados.append((alvo.name, porque))
                diga("  %-22s pulado: %s -- marque «converter» para fechá-lo "
                     "com a sua chave" % (alvo.name, porque))
                continue

            # Convertido ou não, o que sai é sempre formato de chave: é o
            # único em que a chave do dono existe. O cliente escolhe o
            # decifrador pelo cabeçalho, e é o cabeçalho que muda aqui.
            met_saida = METODO_DE_CHAVE if precisa_converter else met
            novo = l2cripto.fechar_41x(conteudo, par["modulo"],
                                       par["privado"], met_saida,
                                       rabo_modelo=rabo or None)
            # A conferencia: reabrir com a chave nova e comparar com o que
            # saiu da leitura. Sem isto, um erro so apareceria no jogo.
            volta, _rabo = l2cripto.abrir_41x(novo, par["modulo"],
                                              par["publico"])
            if volta != conteudo:
                recusados.append((alvo.name, "a ida e volta não bateu"))
                diga("  %-22s RECUSADO: a ida e volta não bateu" % alvo.name)
                continue

            copia = guarda / _relativo(alvo, system)
            copia.parent.mkdir(parents=True, exist_ok=True)
            if not copia.exists():
                shutil.copy2(alvo, copia)
            alvo.write_bytes(novo)
            prontos.append(alvo.name)
            diga("  %-22s %s%s, lido pela %s, %d bytes -> %d"
                 % (alvo.name, met or "sem cifra",
                    (" -> %s" % met_saida) if precisa_converter else "",
                    de_onde, copia.stat().st_size, len(novo)))
        except Exception as erro:                   # noqa: BLE001
            recusados.append((alvo.name, str(erro)[:80]))
            diga("  %-22s RECUSADO: %s" % (alvo.name, str(erro)[:60]))

    trocados = []
    if trocar_exe and prontos:
        for caminho in estado["executaveis"]:
            copia = guarda / (caminho.name + ".antes-da-chave")
            if not copia.exists():
                shutil.copy2(caminho, copia)
            antigo, _novo = l2cripto.trocar_chave_do_cliente(caminho,
                                                             par["modulo"])
            conferido, _pos = l2cripto.chave_do_cliente(caminho)
            if conferido != par["modulo"]:
                shutil.copy2(copia, caminho)
                raise ErroDeProtecao(
                    "a chave não ficou gravada em %s; o arquivo foi "
                    "restaurado." % caminho.name)
            trocados.append(caminho.name)
            diga("  %-22s chave %s -> %s"
                 % (caminho.name, marca_da_chave(antigo),
                    marca_da_chave(par["modulo"])))

    return {"prontos": prontos, "recusados": recusados,
            "executaveis": trocados, "marca": marca_da_chave(par["modulo"]),
            "guarda": guarda}


def desfazer(system, aolog=None):
    """Põe de volta tudo o que está em `backup_protecao`."""
    def diga(texto):
        if aolog:
            aolog(texto)

    system = Path(system)
    guarda = system / PASTA_GUARDA
    if not guarda.is_dir():
        raise ErroDeProtecao("não há %s neste cliente: nada foi protegido por "
                             "aqui." % PASTA_GUARDA)
    raiz = system.parent
    voltaram = []
    for copia in sorted(guarda.rglob("*")):
        if not copia.is_file():
            continue
        dentro = copia.relative_to(guarda)
        nome = dentro.name
        if nome.endswith(".antes-da-chave"):
            dentro = dentro.with_name(nome[:-len(".antes-da-chave")])
        # Copia com caminho relativo volta para o lugar de onde veio; copia
        # antiga, que so tinha o nome, volta para a `system` -- que era o
        # unico lugar de onde ela podia ter saido.
        destino = (raiz / dentro) if len(dentro.parts) > 1 else (system / dentro)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(copia, destino)
        voltaram.append(str(dentro))
        diga("  %s voltou" % dentro)
    return voltaram


def relatorio(system):
    """O que a tela mostra ao abrir: o que já está protegido, e por qual chave."""
    estado = estado_do_cliente(system)
    guarda = Path(system) / PASTA_GUARDA
    estado["protegidos"] = sorted(str(p.relative_to(guarda))
                                  for p in guarda.rglob("*")
                                  if p.is_file()) if guarda.is_dir() else []
    estado["marca"] = marca_da_chave(estado["modulo_atual"])
    estado["quando"] = (time.strftime("%d/%m/%Y %H:%M",
                                      time.localtime(guarda.stat().st_mtime))
                        if guarda.is_dir() else "")
    return estado


# ---------------------------------------------------------------------------
# A frase
# ---------------------------------------------------------------------------
# Sem hifen nem caractere que se confunda ao ler: nada de O e 0, I e l, 1.
# Quem for ditar a frase por telefone -- e alguem vai -- agradece.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
GRUPOS_DA_FRASE = 6
LETRAS_POR_GRUPO = 5


def frase_nova(grupos=GRUPOS_DA_FRASE):
    """
    Uma frase sorteada, em grupos de cinco. Trinta caracteres, 150 bits.

    O sorteio e do `secrets`, que existe para isto -- `random` serve para
    embaralhar carta, nao para escolher chave. Frase inventada na hora costuma
    ser o nome do servidor mais o ano, e essa qualquer um adivinha.
    """
    import secrets

    partes = []
    for _ in range(grupos):
        partes.append("".join(secrets.choice(ALFABETO)
                              for _ in range(LETRAS_POR_GRUPO)))
    return "-".join(partes)


def dentro_do_cliente(caminho, system):
    """
    O arquivo cairia dentro da pasta do cliente?

    Importa porque o arquivo da frase E a chave: guardado ali, ele vai junto
    com o cliente quando o cliente for distribuido -- e a protecao inteira vai
    junto com ele.
    """
    try:
        raiz = Path(system).resolve().parent
        Path(caminho).resolve().relative_to(raiz)
        return True
    except (ValueError, OSError):
        return False


def guardar_frase(caminho, frase, marca, cliente=""):
    """
    Escreve a frase num arquivo de texto, com o aviso do que ele é.

    Devolve o caminho. Não sobrescreve em silêncio: arquivo que já existe é
    renomeado com a data antes, porque duas chaves diferentes com o mesmo nome
    é o tipo de coisa que só se descobre quando já não dá para voltar.
    """
    import time

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        velho = caminho.with_name("%s_%s%s"
                                  % (caminho.stem,
                                     time.strftime("%Y%m%d_%H%M%S"),
                                     caminho.suffix))
        caminho.replace(velho)

    caminho.write_text(
        "L2PackTool -- a chave do seu cliente\n"
        "=====================================\n\n"
        "ESTE ARQUIVO E A CHAVE. Quem o tiver pode gerar arquivos que o seu\n"
        "cliente aceita. Guarde fora da pasta do cliente e fora do que voce\n"
        "distribui.\n\n"
        "frase:  %s\n"
        "marca:  %s\n"
        "cliente: %s\n"
        "quando: %s\n\n"
        "A frase e o que importa: com ela, o programa refaz a mesma chave em\n"
        "qualquer maquina. A marca serve so para conferir que e a chave certa,\n"
        "sem precisar mostrar a frase.\n"
        % (frase, marca, cliente or "-",
           time.strftime("%d/%m/%Y %H:%M")),
        encoding="utf-8")
    return caminho


# ---------------------------------------------------------------------------
# Impressoes digitais: o que dá para fazer por quem não se cifra
# ---------------------------------------------------------------------------
def impressao(caminho, pedaco=1 << 20):
    """O SHA-256 do arquivo, lido aos pedaços para caber em memória."""
    import hashlib

    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        while True:
            dados = arquivo.read(pedaco)
            if not dados:
                break
            resumo.update(dados)
    return resumo.hexdigest()


def arquivos_do_windows(system):
    """Os arquivos que o Windows carrega -- os que não se cifram."""
    system = Path(system)
    if not system.is_dir():
        return []
    return sorted(p for p in system.iterdir()
                  if p.is_file() and p.suffix.lower() in DO_WINDOWS)


def assinar(system, destino, aolog=None):
    """
    Guarda a impressão digital de cada arquivo que o Windows carrega.

    O arquivo de impressões vai para FORA do cliente, e isso não é detalhe:
    guardado dentro, ele seria distribuído junto, e quem trocasse um `.dll`
    trocaria a lista no mesmo movimento.
    """
    import time

    system = Path(system)
    destino = Path(destino)
    alvos = arquivos_do_windows(system)
    if not alvos:
        raise ErroDeProtecao("não achei arquivo do Windows em %s." % system)
    if dentro_do_cliente(destino, system):
        raise ErroDeProtecao(
            "guardar a lista dentro do cliente não serve: ela iria junto com "
            "o cliente, e quem trocasse um arquivo trocaria a lista também.")

    linhas = ["# L2PackTool -- impressões digitais do cliente",
              "# %s" % system,
              "# %s" % time.strftime("%d/%m/%Y %H:%M"), ""]
    for alvo in alvos:
        digital = impressao(alvo)
        linhas.append("%s  %d  %s" % (digital, alvo.stat().st_size, alvo.name))
        if aolog:
            aolog("  %-24s %s…" % (alvo.name, digital[:16]))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino, len(alvos)


def conferir_assinaturas(system, lista, aolog=None):
    """
    Compara o cliente de hoje com a lista guardada.

    Devolve {"iguais", "mudaram", "sumiram", "novos"}. Nomes, e não caminhos:
    é o que se lê de relance quando a pergunta é "trocaram alguma coisa?".
    """
    system = Path(system)
    guardadas = {}
    for linha in Path(lista).read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        partes = linha.split(None, 2)
        if len(partes) == 3:
            guardadas[partes[2]] = (partes[0], int(partes[1]))

    iguais, mudaram, sumiram = [], [], []
    for nome, (digital, tamanho) in sorted(guardadas.items()):
        alvo = system / nome
        if not alvo.is_file():
            sumiram.append(nome)
            continue
        agora = impressao(alvo)
        if agora == digital:
            iguais.append(nome)
        else:
            mudaram.append(nome)
            if aolog:
                aolog("  %-24s MUDOU (%d -> %d bytes)"
                      % (nome, tamanho, alvo.stat().st_size))
    novos = [p.name for p in arquivos_do_windows(system)
             if p.name not in guardadas]
    return {"iguais": iguais, "mudaram": mudaram, "sumiram": sumiram,
            "novos": novos}
