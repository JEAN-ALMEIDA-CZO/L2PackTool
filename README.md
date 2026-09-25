<div align="center">

<img src="recursos/logo.png" alt="L2PackTool" width="200">

# L2PackTool

**Ferramentas de cliente e servidor para Lineage II — de C1 a Gracia Final.**

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
| **Proteção** | fecha as tabelas do cliente com uma chave sua, para ninguém gerar arquivo que ele aceite |
| **Arquivos** | abre e fecha `.dat`, `.utx`, `.u`, `.unr`, `.ini`, e trata o cliente oficial: chave, loader e patcher |
| **Conferir Cliente** | varre o cliente e diz o que falta |

Há também uma **linha de comando** (`L2PackTool-cli`) para o que se repete:
ampliar uma pasta inteira, abrir cem arquivos, conferir um cliente dentro de
um script, montar a tela de vídeo num lobby, animar textura em lote
(`animar --listar` mostra o que o pacote tem).

## As crônicas

O programa abre onze, e cada uma é um **núcleo**: uma pasta com a definição de
cada tabela e um manifesto dizendo o que foi provado nela — e provado quer
dizer medido, num cliente de verdade, pela ida e volta byte a byte. A lista
sai em ordem de lançamento, e não de alfabeto: a posição vem do manifesto, e
crônica nova entra no lugar certo só por existir.

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
| CT2.1 — Gracia Part 1 | 9 de 9 | binário |
| CT2.2 — Gracia Part 2 | 9 de 9 | binário |
| CT2.3 — Gracia Final | 9 de 9 | binário |

Até o C2 as tabelas do cliente são **texto** (`weapongrp.txt`, com os campos
escritos por nome); de C3 em diante são binário descrito por `.ddf`. O
programa lê e grava os dois, e as abas não precisam saber qual é.

Acrescentar uma crônica é largar uma pasta em `recursos/definicoes/` — nem o
nome na tela exige mexer em código. O que ela não conseguir provar fica
escrito como não provado, e a tabela correspondente é recusada em vez de ler
campo deslocado.

**O projeto manda, inclusive quando não tem.** As pastas de cliente e de
servidor das abas vêm do projeto e são somente-leitura. Projeto sem servidor
agora significa *sem servidor*: o campo é limpo ao trocar de projeto, em vez de
guardar o caminho do anterior — antes o cabeçalho dizia `servidor: —` e a aba
lia o XML do outro projeto assim mesmo. Sem projeto nenhum nada muda: vale o
que estiver no `config.ini`, como antes de os projetos existirem.

**Ele descobre a crônica sozinho.** Ao apontar a pasta do cliente, o programa
mede quatro tabelas contra cada definição instalada e escolhe a que reproduz o
arquivo. Uma tabela só não bastaria: várias atravessam crônicas sem mudar. Se
a crônica do projeto estiver errada, o erro diz qual é a certa, em vez de
falar em `field 13 / 57`. Tabela que o cliente não tem não conta contra
ninguém — por isso um cliente de C3 continua saindo com confiança "certa"
medindo três.

A quarta é o `transformdata`, e ela entrou por necessidade: **Gracia Part 1 e
Part 2 têm definição idêntica** em weapongrp, itemname-e e npcgrp, e sem ela um
cliente de Part 2 sairia como Part 1, com confiança "certa" — o pior tipo de
erro. O Part 2 acrescenta um campo nessa tabela, e a separação foi medida nas
duas direções: a definição de uma não descreve o cliente da outra.

**O tipo da habilidade tem duas escalas.** A coluna `oper_type` do `skillgrp`
não quer dizer o mesmo em todas as crônicas, e isso foi medido por habilidade
conhecida nos cinco clientes:

| | Power Strike | Divine Heal | Weapon Mastery | Critical Chance | Relax |
| --- | --- | --- | --- | --- | --- |
| C3 a Kamael | 0 | 0 | 2 | 2 | 3 |
| Hellbound em diante | 0 | 1 | 11 | 12 | 6 |

Na escala antiga, 0 e 1 são ativa, 2 é passiva e 3 é alternável. Na nova, 0 a 5
e 7 são ativa (física, mágica, aura, especial, pesca, transformação), 6 é
alternável e 11 a 16 são passiva. Qual escala vale se decide **olhando a
tabela** — valor de 10 para cima só existe na nova —, e não pelo nome da
crônica, que obrigaria a lembrar do código a cada núcleo novo.

## Proteção

A aba **Proteção** fecha as tabelas escolhidas do cliente com uma chave gerada
a partir de uma frase sua. Sem essa frase ninguém produz arquivo que o seu
cliente aceite — e a frase não é guardada em lugar nenhum: nem no programa,
nem no arquivo de configuração, nem no cliente.

Dá para marcar grupos (itens, habilidades, NPCs, mundo) ou escolher arquivo a
arquivo — inclusive tabelas que não estão em grupo nenhum.

O botão *Gerar chave* sorteia uma frase forte, e *Salvar…* a guarda num
arquivo — fora da pasta do cliente, que o programa recusa por ser o que você
distribui.

Cada arquivo é copiado antes, refeito e **conferido** — só entra no cliente se
voltar idêntico. A chave do executável é trocada por último, e só se todos
passarem. *Voltar ao original* desfaz tudo.

Duas coisas ditas na própria tela, porque prometer mais seria desonesto:

- isto tranca a **escrita**, não a leitura. Para jogar, o cliente precisa abrir
  os arquivos, então ele carrega o que precisa para abri-los; quem tiver o seu
  cliente pode chegar lá. O que muda é sair do "qualquer um abre com um clique"
  para o "quem souber procurar";
- funciona nos clientes que guardam a chave no executável. Nos mais novos ela
  chega por loader, e aí a chave própria não se aplica.

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
ícone de Lineage II moderno — fundo transparente, leitura em tamanho pequeno,
silhueta antes do detalhe —, ao qual se somam as suas observações e o tamanho
que a arte vai ter no jogo. O botão *Ver o pedido* mostra exatamente o que sai.

**Imagem de referência muda o pedido.** Sem imagem anexada o modelo desenha a
partir da descrição. Com imagem, ela deixa de ser inspiração e passa a ser o
ponto de partida: o pedido manda o modelo ler a imagem primeiro, preservar o
objeto, a silhueta, a paleta e o ângulo, e aplicar **somente** as mudanças
pedidas.

**Tamanho.** A IA devolve 1024x1024; o ícone do cliente tem 32 ou 64. A caixa
*no cliente* diz qual é o seu, entra no pedido e manda na prévia — ao lado da
prévia grande aparece a arte no tamanho real, ampliada sem suavizar, que é o
que o jogador vai ver. O pacote de ícone é montado nesse tamanho, e a frase
sob a prévia acompanha a caixa.

**Fundo.** Transparente é o padrão, porque ícone entra sobre a moldura do
inventário — mas botão e moldura às vezes querem cor. A caixa *fundo* compõe
sobre preto, branco, cinza escuro ou uma cor sua, sem gastar outra geração: a
arte original fica guardada, então voltar para transparente devolve a
transparência. Vale também para os quadros da animação.

**Os botões dizem a verdade.** Um botão habilitado é uma promessa, então o
estado dos cinco sai de um lugar só: sem chave o *Gerar* fica desligado (e o
recado lembra que *Abrir imagem…* não depende de chave); enquanto trabalha,
ele vira *Gerando…* e o resto desliga; depois de gerar vira *Gerar de novo*, e
só aí *Usar esta* e *Animar no cliente…* acendem. Na aba de itens, *Preparar o
ícone* segue o conteúdo dos campos em vez da ordem dos cliques, e o rodapé diz
o que falta — nome inválido não se adivinha olhando um botão cinza.

**Erro de API vira frase.** Modelo que só devolve texto, chave inválida,
modelo aposentado, cota estourada: cada um tem o seu recado com o que fazer, e
o texto original da API vai no fim, para quem for procurar na internet.

**Animação.** Doze movimentos (pulso, giro, varredura, contorno, cintilar,
onda, matiz e outros), todos em ciclo fechado: o quadro depois do último é o
primeiro, porque num ícone que roda o tempo todo o pulo da volta é a única
coisa que se enxerga. A arte pode vir da IA ou do disco — animar um PNG seu
não pede chave de API nenhuma.

**GIF.** Modelo de imagem devolve um quadro, nunca um GIF — não há resposta
animada nessas APIs. O contrário funciona: *Abrir imagem…* aceita GIF, WEBP
animado e APNG, e aí os quadros do arquivo **são** a animação, reamostrados ao
longo do tempo para a contagem que o destino pede. Quadro desenhado ganha de
movimento sintético, então o modo de movimento sai de cena nesse caso.

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

Baixe o instalador da [**versão mais nova**](../../releases/latest) — hoje a
**1.5.2**. Ele instala em `%LocalAppData%\Programs\L2PackTool`, sem pedir
administrador, e já traz as ferramentas de terceiros dentro. Instalar por cima
atualiza no lugar; o que mudou em cada versão está no
[CHANGELOG](CHANGELOG.md).

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
