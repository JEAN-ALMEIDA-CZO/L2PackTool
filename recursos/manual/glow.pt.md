# Glow: o brilho da arma

O **glow** é o efeito de partícula preso a uma arma — o risco de luz que
acompanha a lâmina, o halo do arco, a aura das armas de boss. Ele é do
**cliente**: mora no `weapongrp.dat`, não no servidor. Quem equipa a arma vê o
brilho porque o cliente dele tem a tabela alterada; um jogador com o cliente
original não vê nada.

Isso tem uma consequência prática: **o glow tem de ir no patch do cliente**,
junto com as texturas e as malhas. Não adianta mexer só no servidor.


## Onde os números ficam

Cada arma tem espaço para **dois** efeitos, cada um com cinco ajustes:

```
efeito         LineageEffect.c_u006    qual partícula
ao longo da lâmina                     do cabo para a ponta
altura                                 sobe e desce
lado                                   para os lados
tamanho                                o quanto o efeito cresce
intensidade                            o quanto ele brilha
```

Neste cliente, **282 das 1.346 armas** já têm glow, em 48 combinações
diferentes desses cinco números — ou seja, eles são mesmo ajustados arma a
arma, e não copiados de um padrão.

A faixa que o jogo usa nas armas dele:

| ajuste             | do jogo        |
|--------------------|----------------|
| ao longo da lâmina | -20 a 4        |
| tamanho            | 0,80 a 1,55    |
| intensidade        | 0,20 a 1,00    |

**Não são limites.** São referência: se você digitar 40 no comprimento, o
programa aceita, e o efeito vai parar fora da arma. A régua avisa quando isso
acontece.


## A régua

À direita fica a **lâmina deitada**, com o cabo de um lado e a ponta do outro.
Os dois números nas pontas não são chute: saem da **malha desta arma**,
exportada do pacote do cliente e medida vértice a vértice.

Uma arma deita no eixo de maior alcance. A Dragon Slayer, por exemplo, vai de
**-17,8 a 40,8** no eixo X: o cabo fica atrás do zero, a lâmina toda à frente.
É nesse eixo que o ajuste *ao longo da lâmina* anda — por isso o círculo
laranja se move quando você digita.

O tamanho do círculo acompanha o campo **tamanho**.

**A régua não desenha o efeito.** Partícula do Unreal Engine 2 só o motor do
jogo desenha — nem o umodel abre. A régua diz **onde** o brilho vai ficar; como
ele *parece*, só em jogo.


## Ver a arma em 3D

O botão **Ver a arma em 3D** abre a malha no visualizador do umodel: dá para
girar, ver o formato e entender onde é a ponta. Serve para escolher o valor de
*ao longo da lâmina* com alguma noção, principalmente em armas compridas.

O glow **não** aparece ali, pelo motivo acima.


## Escolher o efeito

A lista da direita começa com a caixa **só os que o jogo usa em arma**
marcada — e é assim que ela deve ficar na maioria das vezes.

O cliente tem **1.812 efeitos instalados**, e a esmagadora maioria não foi
feita para arma: são auras de NPC, efeitos de chão, magias. Postos numa espada,
ficam do tamanho errado, no lugar errado, ou simplesmente não aparecem. Vários
são de crônicas mais novas e não funcionam em Interlude — é o aviso que o
tutorial da comunidade dá, e ele está certo.

> **Nem todo efeito da lista completa é compatível.** A lista marcada mostra os
> que **este cliente já desenha em armas** — não é opinião, é contagem do
> `weapongrp.dat` dele.

### Como a sugestão é montada

O programa conta, no seu cliente, qual efeito o jogo usa em cada tipo de arma.
Se o cliente pôs `c_u002` em nove adagas e em mais nada, aquele é o efeito da
adaga — e ele funciona, porque o jogo o desenha todo dia.

Neste cliente a contagem dá:

| efeito | onde o jogo usa |
| --- | --- |
| `c_u001` | punho (22) |
| `c_u002` | adaga (9) |
| `c_u003` / `c_u008` | arco (9 e 20) |
| `c_u004` | espada, adaga, espadão, dupla (54 no total) |
| `c_u005` / `c_u007` | maça, marreta, lança |
| `c_u006` | espada (18) |
| `c_u000` | espadão (5) |
| `e_u092_a` … `e_u092_k` | o **hero glow**, um por tipo de arma |
| `SHEV_weapon_shadow_*` | shadow weapons de um pack custom |

A correspondência do hero glow bate com a que o tutorial publica — a = espada,
b = espadão, g = adaga, h = punho, i = arco, j = espada dupla. A diferença é
que aqui ela foi **medida no seu cliente**, e não copiada.

Escolhendo uma arma, os efeitos daquele tipo sobem para o topo, com a coluna
**usado em** dizendo em quantas armas iguais o jogo o usa.

### Copiar de uma arma que já funciona

Os cinco números não se acertam no palpite. O efeito sai do lugar — fica no
meio do corpo, atrás da arma, grande demais — e não há como saber qual dos cinco
está errado.

Se alguma arma do jogo já tem o glow no lugar certo, **os números dela são a
resposta**. `Copiar de outra arma…` abre a lista de armas do cliente, com ícone
e filtro, e traz o efeito e os cinco ajustes daquela para os campos.

É o caminho mais curto quando o que você quer é "igual àquela, com outra cor".

O registro avisa quando a arma de origem é de **outro tipo** — copiar de um
espadão para uma dupla, por exemplo. Os números continuam válidos, mas a malha
de uma não tem o tamanho da da outra, e o enquadramento pode não valer.

### Os cinco números vêm junto

Pondo um efeito sugerido, os cinco ajustes são preenchidos com **os que o jogo
usa naquele efeito** — não com 0 e 1. O glow nasce enquadrado na lâmina em vez
de encolhido no cabo.

Desmarcando a caixa, a lista volta a mostrar os 1.812. Vale para quem sabe o
que está procurando.


## Criar uma arma nova, em vez de mexer numa que existe

Pôr um glow numa arma do jogo muda **aquela arma para todo mundo**. Quem
equipar uma Dragon Slayer, qualquer uma, vai ver o brilho novo. Às vezes é o
que se quer; na maioria das vezes, não.

**Criar arma nova…** copia a arma escolhida para um id próprio, já com o glow
que está na tela. A original não é tocada.

A janela pergunta o id, o nome, a descrição e o ícone. A cópia leva a linha
inteira do `weapongrp.dat`: malha, textura, som, tipo, peso e os números do
cliente vêm da base.

Use um id **acima de 30000**, longe da faixa do jogo. Escrever por cima de um
item que existe é o erro mais caro aqui.

Sai junto o `<id>-item.xml` do servidor — mas **só com o que dá para ler do
cliente**: tipo, parte do corpo, peso, material, grau, tiro. Dano, defesa e
preço não existem no `weapongrp.dat`; eles são do servidor.

Para completar, vá à aba **Itens**, marque a arma nova na lista e use a janela
**Novo item**, que tem as páginas de Números, Status e Skills. Lá é o lugar
disso, e ter dois lugares que fazem a mesma coisa daria duas coisas para
consertar quando ela mudar.

## A página "Armas criadas"

Lista as armas do cliente com id **acima de 30000** — a faixa que o jogo não
usa. Ela sai do próprio `weapongrp.dat`, e não de um registro guardado à parte:
um registro envelheceria quando você trocasse de cliente, restaurasse um backup
ou copiasse a pasta para outra máquina, e a tela passaria a mostrar armas que
não existem e a esconder as que existem.

Isso também mostra armas custom feitas por outros programas — e está certo:
quem abre essa página quer ver as armas custom do cliente, não só as que
passaram por aqui.

| coluna | o que diz |
| --- | --- |
| tipo | espada, arco, adaga… lido do cliente |
| glow | o efeito que ela tem hoje |
| XML | se já existe uma, na pasta de saída ou na do servidor |

**Editar o glow desta** leva a arma para a outra página, já escolhida e com o
glow que ela tem.

**Ver a XML** monta a XML na hora, a partir da linha do cliente, e mostra. Ela
tem só o que dá para ler de lá — dano, defesa e preço são do servidor.

**Gravar a XML no servidor** escreve na pasta de itens dele. Onde é essa pasta
sai do próprio servidor: o programa lê os arquivos dele para descobrir. Não
conseguindo, ele avisa e não grava — melhor não gravar do que gravar no lugar
errado. Depois, no jogo: `//reload item`.

**A subpasta importa.** `custom` é a convenção dos datapacks L2J, mas não é a de
todos: há pack que reparte a pasta de itens por tipo — `weapons`, `armors`,
`accessories`, `etcitems` — e que **não lê arma de `custom`**. Gravar ali
entrega o arquivo num lugar que o servidor ignora, e o sintoma é "criei a arma e
ela não existe".

A caixa ao lado do campo Servidor lista as subpastas que **existem** no seu
servidor e já marca a que casa com o tipo do item — `weapons` para arma, quando
ela está lá. A escolha fica guardada.

**Excluir** tira a arma das tabelas na memória, e apaga a XML do servidor
junto. O cliente só muda em **Instalar no cliente**, então até lá dá para
desfazer fechando o programa sem gerar.

Marcando **gravar a XML no servidor** no alto da tela, a XML da arma nova é
entregue direto na criação.

## Gerar e instalar

Como nas outras abas, são dois passos de propósito:

1. **Gerar** escreve o `weapongrp.dat` alterado numa pasta à parte. Nada é
   copiado para o cliente.
2. **Instalar no cliente** copia. Na primeira vez, o arquivo original vai para
   `backup_itens/`, e **Restaurar originais** desfaz tudo.

Antes de gravar qualquer coisa, a tabela é remontada a partir da definição e
comparada com o binário original **byte a byte**. Se a volta não reproduz a
ida, a definição não descreve este cliente e nada é escrito — é o que impede um
`weapongrp.dat` quebrado de chegar ao cliente.

O cliente lê o `weapongrp.dat` **só no arranque**. Depois de instalar, feche e
abra o jogo.


## A página "Encantamento"

> **Isto vale para TODAS as armas do servidor.** Não é ajuste de item.

O glow das outras páginas é **da arma**: uma Dragon Slayer com `c_u000` brilha
sempre, já em +0. O brilho de **encantamento** é outro — é o halo que qualquer
arma ganha ao ser refinada, o azul do +4, o dourado do +7 — e ele mora no
`env.int`, que é um arquivo só para o cliente inteiro.

### Os dois números

| campo | o que faz | no jogo original |
| --- | --- | --- |
| `EnchantMeshShow` | do +N em diante a arma ganha cor | 4 |
| `EnchantEffectShow` | do +N em diante aparece a chama | 7 |

São independentes: dá para a arma ganhar cor sem chama, e o contrário. **Abaixo
do primeiro número, mexer na cor daquele nível não muda nada na tela** — é o
motivo mais comum de "editei e não aconteceu nada".

Baixando o segundo para 4, toda arma +4 passa a brilhar. Os dois são
independentes: dá para a malha mudar sem brilho, e o contrário.

### A cor de cada nível

O cliente de fábrica traz **21 níveis**, `Enchant0` a `Enchant20`, com duas
cores cada — o jogo faz o brilho variar entre elas — mais opacidade e
intensidade.

**A faixa no alto** mostra todos de uma vez, cada um partido nas suas duas
cores. Neste cliente dá para ver a progressão inteira num relance: cinza até o
+3, azul do +4 ao +15, vermelho do +16 ao +20. Clique numa coluna para editar
aquele nível.

### Acima do +20

Logo abaixo da série há uma linha **`Enchant=`**, sem número. Ela é o que o
cliente usa para **qualquer encantamento acima do último nível escrito**. Neste
cliente ela é igual ao +20 — e é por isso que um +40 hoje tem a mesma cor do
+20.

Servidor que encanta mais alto tem dois caminhos:

1. **Mexer só no `Enchant=`.** Marque a caixa `este é o Enchant=`, escolha a
   cor e guarde. Uma linha resolve tudo acima do +20.
2. **Dar cor própria a cada nível**, até o **+60**. Escolha o nível no campo e
   edite normalmente. O programa escreve `Enchant21` em diante no arquivo, na
   ordem, logo antes do `Enchant=`.

Na faixa, os níveis **tracejados** ainda não têm linha própria: a cor que
aparece neles é emprestada do `Enchant=`. Entrando num deles, os campos já vêm
com essa cor — é o que aquele nível tem hoje, e não um branco.

> **Uma ressalva.** Que o cliente *leia* `Enchant21` em diante não dá para
> provar fora do jogo — só testando. O que dá para afirmar é que escrever não
> quebra nada: chave desconhecida num `.int` do Unreal é ignorada, e se for
> ignorada continua valendo o `Enchant=`, exatamente como hoje.

**Copiar para os de cima** repete o nível atual em todos acima dele **e na
linha `Enchant=`** — é o caminho curto para "do +20 em diante tudo dourado".

### Escolher a cor

> **O que o jogo faz com as duas cores, este manual não afirma** — não dá para
> provar fora do jogo, e afirmar sem provar já custou caro aqui.
>
> O que se sabe, e como:
>
> - Nos 21 níveis de fábrica a cor 2 é **sempre a mesma cor da 1, um pouco mais
>   escura** — `(40,87,126)` e `(30,70,110)` no +7, `(220,0,0)` e `(195,0,0)`
>   no +20. Vale para os 21, sem exceção.
> - O `env.int` aponta para o material
>   `LineageEffectsTextures.Etc.Enchant_Aura001_Shader01`, cuja cadeia passa
>   por um `FadeColor` — a classe do Unreal que vai e volta entre duas cores.
>   **Mas as cores gravadas nesse FadeColor são outras**: `(7,20,69)`/`(5,15,48)`,
>   `(24,41,46)`/`(34,45,47)`, `(90,122,128)`/`(80,109,115)`. Nenhuma é a cor de
>   nível nenhum. O material tem a pulsação dele, com cores próprias.
> - `EnchantMeshShow`, `EnchantEffectShow` e as linhas `Enchant*` **não estão
>   na tabela de nomes de nenhum `.u`**: quem as lê é o código nativo do
>   executável, não UnrealScript. Não há o que ler.
>
> Para descobrir: ponha duas cores bem diferentes num nível que o cliente
> certamente lê e olhe em jogo. É a única resposta que vale.

**Se você mudou a cor e nada aconteceu**, o motivo mais provável não é a cor —
é o arquivo. Veja a seção seguinte.

### Linhas no lugar errado

Uma versão anterior deste programa escrevia os níveis novos **antes do primeiro
cabeçalho do arquivo**, fora de toda seção, onde o jogo nunca os lê. O sintoma
era exatamente "editei e não mudou nada".

Ao ler um `env.int` assim, a tela avisa e diz quantas linhas estão fora do
lugar. **Gerar e instalar de novo limpa o arquivo** e põe tudo dentro de
`[EnchantEffect]`. Quem preferir começar do zero: **Restaurar original** e
refazer.

Cada cor tem uma amostra e três barras — vermelho, verde e azul. A barra
escreve o número e o número move a barra: são o mesmo valor, e não duas cópias
dele.

Embaixo, **a linha do arquivo se escreve sozinha**, a cada movimento:

```
Enchant7=(R1=40,G1=87,B1=126,R2=30,G2=70,B2=110,Opacity=0.4,Num=0.3)
```

É exatamente o que vai ser gravado. **Copiar** a põe na área de transferência,
para quem quiser levá-la para outro lugar.

Nada disso mexe no arquivo ainda: **Guardar o nível** guarda na memória,
**Voltar ao original** desfaz só aquele nível com o que o arquivo tinha quando
foi lido, e **Copiar para os de cima** repete o nível atual em todos os acima
dele — o caminho curto para "do +7 em diante tudo vermelho" sem mexer em
catorze níveis a mão.

### Opacidade e intensidade

Vão de 0,1 a 1 — e **o jogo nunca passa de 1** nos dois. Neste cliente:

| nível | opacidade | intensidade |
| --- | --- | --- |
| +0 a +6 | 0,1 | 0,1 |
| +7 | 0,4 | 0,3 |
| +10 | 0,7 | 0,8 |
| +13 em diante | 1 | 1 |

Há tutorial por aí sugerindo valores bem acima disso, com o aviso de que "pode
lagar o servidor". A parte do valor alto está certa; a do servidor, não.
Partícula é desenhada pelo **cliente**, todo quadro, em toda arma encantada que
estiver na tela — quem sente é a máquina de quem joga, ainda mais numa cidade
cheia.

### Gerar, instalar, restaurar

Os mesmos três passos das outras páginas, com uma conferência a mais: antes de
o arquivo ser dado como pronto, ele é **cifrado e decifrado de volta**, e o
resultado comparado com o que se queria gravar. Não batendo, nada é instalado.

Isso importa aqui mais do que nas tabelas: um `env.int` quebrado deixa o
cliente **sem iluminação nenhuma**, e o sintoma não parece com a causa.

O original vai para `backup_env/` na primeira instalação, e **Restaurar
original** o traz de volta byte a byte.

O cliente lê o `env.int` **só no arranque**.

## O que esta tela não faz

**Não cria efeito novo.** A lista mostra o que o cliente já tem. Um efeito
inédito é um pacote de partícula novo, feito fora daqui.


## Custo

Partícula é desenhada **todo quadro**, em **toda arma igual a esta** que
estiver na tela. *Tamanho* e *intensidade* altos numa arma comum de servidor
cheio pesam mais do que numa arma de boss que uma pessoa só carrega. Vale
testar com gente reunida antes de soltar.
