#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Projetos: a pasta do cliente e a do servidor, num lugar só.

Cada aba pedia as duas pastas de novo. Eram nove campos para o mesmo caminho, e
bastava um ficar para trás -- depois de mexer numa cópia do cliente, por
exemplo -- para uma tela gravar no lugar errado sem avisar. Quem mexe em dois
servidores ao mesmo tempo trocava dezoito campos a cada troca.

Aqui existe um **projeto**: um nome, uma pasta de cliente e uma de servidor.
Escolher o projeto muda as duas em todas as abas de uma vez.

## Como as abas ficam sabendo

Elas se inscrevem com `ao_trocar`. Trocar de projeto chama cada inscrito, que
atualiza os próprios campos. Não há laço de verificação nem releitura: quem
precisa saber pediu para ser avisado.

Um inscrito que estoura não pode derrubar a troca -- se a aba de vídeo tem um
defeito, a de itens ainda assim precisa receber o caminho novo. Por isso cada
chamada vai dentro do seu próprio `try`.

## A migração

Quem já usava o programa tem as pastas no `config.ini`, em `cliente/system` e
`servidor/pasta`. Na primeira execução sem projeto nenhum, isso vira um projeto
chamado `Padrão` -- ninguém perde o que já tinha configurado, e ninguém precisa
saber que a estrutura mudou.
"""

import configparser
from pathlib import Path

import motor

ARQUIVO = Path(motor.BASE) / "projetos.ini"

# A secao que guarda qual projeto esta escolhido. Nome com espaco nao colide
# com nome de projeto porque projeto nao pode se chamar assim -- ver
# `nome_valido`.
_ESCOLHA = " escolha "

# Quem quer ser avisado quando o projeto muda.
_inscritos = []


# =========================================================================
# o arquivo
# =========================================================================
def _ler():
    cfg = configparser.ConfigParser()
    cfg.optionxform = str           # preserva maiuscula na chave
    if ARQUIVO.is_file():
        try:
            cfg.read(ARQUIVO, encoding="utf-8")
        except configparser.Error:
            pass                    # arquivo corrompido nao pode travar o
                                    # programa; ele volta a ser um vazio
    return cfg


def _gravar(cfg):
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            cfg.write(f)
    except OSError:
        pass


# =========================================================================
# ler
# =========================================================================
def nome_valido(nome):
    """
    O nome serve? Devolve o motivo, ou "" quando está bom.

    Vira nome de seção num `.ini`, então `[` e `]` quebram o arquivo, e o nome
    reservado da escolha não pode ser usado.
    """
    nome = (nome or "").strip()
    if not nome:
        return "o projeto precisa de um nome"
    if nome == _ESCOLHA.strip():
        return "esse nome é reservado"
    for proibido in "[]":
        if proibido in nome:
            return "o nome não pode ter `%s`" % proibido
    if "\n" in nome or "\r" in nome:
        return "o nome não pode ter quebra de linha"
    return ""


def listar():
    """Os projetos, em ordem alfabética."""
    return sorted(s for s in _ler().sections() if s != _ESCOLHA)


def dados(nome):
    """{"cliente": ..., "servidor": ...} daquele projeto, ou vazio."""
    cfg = _ler()
    if not nome or not cfg.has_section(nome):
        return {"cliente": "", "servidor": ""}
    return {"cliente": cfg.get(nome, "cliente", fallback=""),
            "servidor": cfg.get(nome, "servidor", fallback="")}


def atual():
    """O nome do projeto escolhido, ou "" se não há nenhum."""
    cfg = _ler()
    escolhido = cfg.get(_ESCOLHA, "projeto", fallback="")
    if escolhido and cfg.has_section(escolhido):
        return escolhido
    # Escolha apagada ou apontando para projeto que sumiu: cai no primeiro.
    restantes = [s for s in cfg.sections() if s != _ESCOLHA]
    return sorted(restantes)[0] if restantes else ""


def cliente():
    """A pasta do cliente do projeto escolhido."""
    return dados(atual())["cliente"]


def servidor():
    """A pasta do servidor do projeto escolhido."""
    return dados(atual())["servidor"]


def ha_projeto():
    return bool(atual())


# =========================================================================
# escrever
# =========================================================================
def guardar(nome, pasta_cliente, pasta_servidor, antigo=None):
    """
    Cria ou muda um projeto. Renomeia quando `antigo` vem preenchido.

    Devolve o motivo da recusa, ou "" quando deu certo.
    """
    problema = nome_valido(nome)
    if problema:
        return problema
    nome = nome.strip()
    cfg = _ler()
    if antigo and antigo != nome and cfg.has_section(antigo):
        cfg.remove_section(antigo)
    if nome in [s for s in cfg.sections() if s != _ESCOLHA] and not antigo:
        return "já existe um projeto com esse nome"
    if not cfg.has_section(nome):
        cfg.add_section(nome)
    cfg.set(nome, "cliente", str(pasta_cliente or ""))
    cfg.set(nome, "servidor", str(pasta_servidor or ""))
    _gravar(cfg)
    if atual() in ("", antigo or ""):
        escolher(nome)
    return ""


def apagar(nome):
    cfg = _ler()
    if cfg.has_section(nome):
        cfg.remove_section(nome)
        _gravar(cfg)
    if cfg.get(_ESCOLHA, "projeto", fallback="") == nome:
        escolher(atual())       # cai no primeiro que sobrou, ou em nada


def escolher(nome):
    """Troca o projeto em uso e avisa todo mundo que pediu para saber."""
    cfg = _ler()
    if not cfg.has_section(_ESCOLHA):
        cfg.add_section(_ESCOLHA)
    cfg.set(_ESCOLHA, "projeto", str(nome or ""))
    _gravar(cfg)
    avisar()


# =========================================================================
# quem quer saber
# =========================================================================
def ao_trocar(funcao):
    """
    Registra alguém para ser avisado quando o projeto mudar.

    Devolve a própria função, para quem quiser cancelar depois com
    `nao_avisar`.
    """
    if funcao not in _inscritos:
        _inscritos.append(funcao)
    return funcao


def nao_avisar(funcao):
    if funcao in _inscritos:
        _inscritos.remove(funcao)


def limpar_inscritos():
    """
    Esquece todo mundo. Chamar antes de remontar as abas.

    Trocar o idioma destrói as abas e monta outras. Sem isto os inscritos
    antigos continuariam na lista, apontando para widgets que já não existem:
    a cada troca de projeto o Tk estouraria uma vez por aba morta.
    """
    del _inscritos[:]


def avisar():
    """
    Chama os inscritos, um a um, sem deixar um derrubar os outros.

    Uma aba com defeito não pode impedir as outras de receber o caminho novo:
    o estrago seria justamente o que este módulo existe para evitar -- telas
    apontando para pastas diferentes.
    """
    nome = atual()
    d = dados(nome)
    for funcao in list(_inscritos):
        try:
            funcao(nome, d["cliente"], d["servidor"])
        except Exception:                           # noqa: BLE001
            pass


# =========================================================================
# a migração
# =========================================================================
def migrar():
    """
    Sem projeto nenhum, monta um a partir do `config.ini` antigo.

    Devolve o nome criado, ou "" se não havia o que migrar. Roda uma vez, no
    arranque: quem já usava o programa não perde as pastas que configurou, e
    não precisa saber que a estrutura mudou.
    """
    if listar():
        return ""
    antigo_cliente = motor.ler_opcao("cliente", "system", "") or ""
    antigo_servidor = motor.ler_opcao("servidor", "pasta", "") or ""
    if not antigo_cliente and not antigo_servidor:
        return ""
    nome = "Padrão"
    guardar(nome, antigo_cliente, antigo_servidor)
    escolher(nome)
    return nome
