<div align="center">

<img src="recursos/logo.png" alt="L2PackTool" width="120">

# L2PackTool

**Ferramentas de cliente e servidor para Lineage II — de C1 a Hellbound.**

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
| **Lobby Vídeo** | a tela de entrada: catorze lobbys prontos (C1 a High Five), ou o seu vídeo |
| **Texture Upscaler** | amplia as texturas de um `.utx` por IA e remonta o pacote *(em testes)* |
| **Arquivos** | abre e fecha `.dat`, `.utx`, `.u`, `.unr`, `.ini`, e trata o cliente oficial: chave, loader e patcher |
| **Conferir Cliente** | varre o cliente e diz o que falta |

Há também uma **linha de comando** (`L2PackTool-cli`) para o que se repete:
ampliar uma pasta inteira, abrir cem arquivos, conferir um cliente dentro de
um script, montar a tela de vídeo num lobby, animar textura em lote
(`animar --listar` mostra o que o pacote tem).

## As crônicas

O programa abre oito, e cada uma é um **núcleo**: uma pasta com a definição de
cada tabela e um manifesto dizendo o que foi provado nela — e provado quer
dizer medido, num cliente de verdade, pela ida e volta byte a byte.

| Crônica | Tabelas | Formato |
| --- | --- | --- |
| C1 — Harbingers of War | 8 de 8 | texto |
| C2 — Age of Splendor | 8 de 8 | texto |
| C3 — Rise of Darkness | 8 de 8 | binário |
| C4 — Scions of Destiny | 8 de 8 | binário |
| C5 — Oath of Blood | 8 de 8 | binário |
| C6 — Interlude | 8 de 8 | binário |
| CT1 — The Kamael | 8 de 8 | binário |
| CT1.5 — Hellbound | 8 de 8 | binário |

Até o C2 as tabelas do cliente são **texto** (`weapongrp.txt`, com os campos
escritos por nome); de C3 em diante são binário descrito por `.ddf`. O
programa lê e grava os dois, e as abas não precisam saber qual é.

Acrescentar uma crônica é largar uma pasta em `recursos/definicoes/` — nem o
nome na tela exige mexer em código. O que ela não conseguir provar fica
escrito como não provado, e a tabela correspondente é recusada em vez de ler
campo deslocado.

**Ele descobre a crônica sozinho.** Ao apontar a pasta do cliente, o programa
mede três tabelas contra cada definição instalada e escolhe a que reproduz o
arquivo. Uma tabela só não bastaria: várias atravessam crônicas sem mudar. Se
a crônica do projeto estiver errada, o erro diz qual é a certa, em vez de
falar em `field 13 / 57`.

## Cliente oficial

Cliente recém-baixado vem fechado com as chaves da NCSoft. O programa lê essas
chaves, mas só sabe gravar com as do l2encdec — a chave privada da NCSoft
nunca foi publicada.

Antes de instalar qualquer tabela, ele confere em que chave o cliente está e,
se for a original, **converte a pasta `system` inteira primeiro**: cada arquivo
é aberto, fechado com a outra chave, aberto de novo e comparado byte a byte, e
o original só é trocado se bater — com cópia em `backup_chaves`.

Falta o jogo conhecer a chave nova, e isso o programa também faz. Na primeira
instalação num cliente oficial ele põe o `loader` da crônica ao lado do
executável e, se o `l2.exe` ainda não foi tratado, oferece rodar o `patcher`
uma vez — que exige administrador, e por isso é pedido com o aviso do Windows,
não escondido. A resposta fica guardada: quem recusou não é perguntado de novo,
e quem aceitou não repete. O `l2.exe` original vai para
`l2.exe.antes-do-patcher` antes de qualquer coisa, e a mudança é conferida
depois — se o arquivo não mudou, o programa diz isso em vez de garantir que
deu certo.

## Arte por IA

Onde o programa aceita uma imagem sua — ícone de item, de habilidade, textura
de botão — ele aceita também **gerar** uma. Em *Configurações* você escolhe o
provedor (Gemini ou Claude), cola a sua chave e escreve o **modelo à mão**: os
nomes de modelo mudam e são aposentados, então nenhum fica preso no código, e
há um link para a lista de cada fabricante ao lado do campo.

O pedido enviado não é o seu texto solto: há um prompt fixo, escrito para
ícone de Lineage II moderno — fundo transparente, leitura em 32x32, silhueta
antes do detalhe —, ao qual se somam as suas observações e as imagens de
referência que você anexar. O botão *Ver o pedido* mostra exatamente o que sai.

**Animação.** Doze movimentos (pulso, giro, varredura, contorno, cintilar,
onda, matiz e outros), todos em ciclo fechado: o quadro depois do último é o
primeiro, porque num ícone que roda o tempo todo o pulo da volta é a única
coisa que se enxerga. A arte pode vir da IA ou do disco — animar um PNG seu
não pede chave de API nenhuma.

E os quadros vão para dentro do jogo por um dos dois caminhos que o Lineage II
tem. O programa pergunta qual, porque não são a mesma coisa:

**A corrente do motor.** Uma textura aponta para a seguinte pela propriedade
`AnimNext`, e o Unreal percorre sozinho — ninguém programa nada. É assim que
funciona o `anim70.u` que circula nos clientes: `anim_over` com
`TotalFrameNum = 21` e `MaxFrameRate = 50`, seguido de `02 → 03 → … → 21`.
Escolha o pacote e a textura, e ela passa a andar. Ela **não muda de conteúdo
nem de endereço**: ganha uma propriedade, e quem a usa hoje continua achando o
mesmo nome. Os quadros vão num `.utx` novo, ao lado. Medido num `Icon.utx`
oficial de Hellbound: 4.662 texturas, nenhuma com o desenho alterado, duas
importações a mais, e o umodel lendo a corrente antes de qualquer instalação.

**A família numerada.** O outro caminho não é do motor, é do código da
interface: `cooltime000..359`, `ToggleEffect001..013`. Quem escolhe o quadro a
cada instante é o cliente, que conhece esses nomes — então aqui não dá para
inventar animação, dá para trocar o **desenho** da que existe, mantendo nome,
contagem, tamanho e formato.

Em resumo: para animar o que hoje está parado, a corrente; para mudar a cara
do que já anda, a família. Os dois guardam o original antes de gravar.


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
recursos/definicoes/  um núcleo por crônica: definições e o que foi provado
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

A licença cobre **o código deste projeto**. As ferramentas de terceiros
(UModel, texconv, Upscayl, ffmpeg, l2encdec, UCC) pertencem a seus autores e
não são redistribuídas aqui. Lineage II é marca registrada da NCSoft; este
projeto não tem vínculo com a NCSoft e não redistribui conteúdo do jogo.

## Créditos

Feito por **Jean Almeida — ÐarkÐomi**.
