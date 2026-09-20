<div align="center">

<img src="recursos/logo.png" alt="L2PackTool" width="120">

# L2PackTool

**Ferramentas de cliente e servidor para Lineage II — Interlude.**

Criar NPC com efeito, item, arma, habilidade e loja; trocar a tela de entrada
por um vídeo seu; ampliar textura por IA; abrir e fechar os arquivos do
cliente. Tudo numa janela só, em português, inglês e espanhol.

</div>

---

## O que ele faz

| Aba | Para quê |
| --- | --- |
| **NPC com efeito** | põe um efeito visual num NPC, ajusta altura e osso, e escreve a XML do servidor |
| **Itens** | cria arma, armadura ou consumível copiando um do cliente — nome, destaque, ícone, status e skills |
| **Habilidades** | o mesmo do lado das skills, com a tabela do cliente e a XML do servidor |
| **Glow** | o brilho das armas, e cópia de arma com o glow escolhido |
| **Multisell** | as lojas, lendo os itens do cliente |
| **Mob** | os monstros: status, drop e spawn |
| **Lobby Vídeo** | a tela de entrada: sete lobbys prontos (C1 a C6), ou o seu vídeo |
| **Texture Upscaler** | amplia as texturas de um `.utx` por IA e remonta o pacote *(em testes)* |
| **Arquivos** | abre e fecha `.dat`, `.utx`, `.u`, `.unr`, `.ini` |
| **Conferir Cliente** | varre o cliente e diz o que falta |

## Instalar

Baixe o instalador na página de [**Releases**](../../releases). Ele instala em
`%LocalAppData%\Programs\L2PackTool`, sem pedir administrador, e já traz as
ferramentas de terceiros dentro.

Para rodar do código:

```bat
pip install pillow
python gui.py
```

Nesse caso as ferramentas de terceiros ficam por sua conta — o programa as
procura sozinho numa pasta `ferramentas/` ao lado dele, e o que não achar pode
ser apontado no `config.ini`:

| Ferramenta | Para quê | Onde obter |
| --- | --- | --- |
| **UModel** | extrai as texturas do `.utx` | <https://www.gildor.org/en/projects/umodel> |
| **texconv** | comprime em DXT com mipmaps | <https://github.com/microsoft/DirectXTex/releases> |
| **Upscayl** | o upscale por IA | <https://upscayl.org> |
| **ffmpeg** | lê o vídeo do lobby | <https://ffmpeg.org> |
| **l2encdec** | descriptografa e criptografa | acompanha o L2FileEdit |
| **UCC** | remonta o pacote | acompanha o L2Editor |

L2FileEdit e L2Editor circulam nas comunidades de servidor privado. Não são
redistribuídos aqui: o UCC contém código da Epic Games e da NCSoft, e crédito
não substitui permissão.

## Compilar

```bat
python compilar.py --tudo          :: o L2PackTool, em dist/
python compilar.py --instalador    :: o instalador, em release/
```

Precisa de [PyInstaller](https://pyinstaller.org) e, para o instalador, do
[Inno Setup](https://jrsoftware.org/isinfo.php).

## O repositório

```
gui*.py            as abas da interface
l2*.py             o motor: pacotes Unreal, tabelas .dat, mapas, XML do servidor
recursos/manual/   o manual que abre dentro do programa, em três idiomas
recursos/definicoes/  o formato de cada tabela .dat
idiomas/           as traduções da interface
instalador.iss     o script do instalador
LEIA-ME.md         a documentação longa, com o porquê de cada decisão
```

Não estão aqui, e por bons motivos: as **ferramentas de terceiros** (o UCC não
pode ser redistribuído) e os **lobbys** (mapa, malha e música são da NCSoft).
A pasta `recursos/lobbies/` explica o formato para você pôr os seus.

## Documentação

O **[LEIA-ME.md](LEIA-ME.md)** é a documentação longa: o que cada aba faz, o
que deu errado no caminho e por que cada decisão ficou como está. O programa
também traz o manual embutido, no botão de ajuda.

## Licença

[MIT](LICENSE) — use, modifique e redistribua à vontade, inclusive em
servidor comercial. A única condição é manter o aviso de copyright.

A licença cobre o código deste projeto. As ferramentas de terceiros são de
seus autores, e conteúdo do jogo não é redistribuído aqui.

## Créditos

Feito por **Jean Almeida — ÐarkÐomi**.
As ferramentas de terceiros são de seus respectivos autores.

Lineage II é marca registrada da NCSoft. Este projeto não tem vínculo com a
NCSoft e não redistribui conteúdo do jogo.
