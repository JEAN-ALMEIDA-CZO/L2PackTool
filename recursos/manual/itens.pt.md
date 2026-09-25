# Criar um item: o que preencher

Um item do Lineage 2 existe em dois lugares ao mesmo tempo, e os dois têm de
concordar:

- o **cliente** sabe desenhar o item — malha, textura, ícone, som;
- o **servidor** sabe o que ele faz — dano, defesa, peso, preço.

O que amarra os dois é o **id**. Se só um lado tiver o item, não aparece erro
nenhum: aparece confusão. Item sem nome, ícone em branco, ou um item que o
servidor entrega e o cliente não desenha.

Esta aba cuida dos dois lados. As tabelas do cliente saem prontas para instalar;
o XML do servidor sai junto, e você copia para a pasta de itens do seu servidor.


## Editar ou criar

A tela tem um **modo**, escrito em letras grandes no alto do painel da direita:

```
Editando o item 1 — Short Sword
Item novo 30000, copiado do 1
```

**Clicar num item da lista edita aquele item.** Os campos se enchem com os dados
dele, o id fica travado no dele, e o botão vira **Regravar o item**. O id trava
de propósito: mudar o número ali seria, na verdade, criar outro.

**Criar passa pela janela Novo item…** Ela pergunta o id (com Sugerir), nome,
descrição e ícone; recusa um id que já exista sem a marca de substituir; avisa se
o id cair na faixa do jogo. O que sai dela preenche o painel, e os campos
continuam editáveis.

Depois de gerar, a tela passa a **editar o que acabou de sair**.


## 1. Escolha o item base

Todo item novo nasce como cópia de um que já funciona. Não é preguiça: uma
linha do `armorgrp.dat` tem **332 colunas**, e a maioria não tem nada a ver com
aparência — é peso, som ao equipar, tipo de cristal, e a malha e a textura de
cada uma das doze combinações de raça e sexo. Inventar esses valores dá um item
que existe e está errado.

Procure na lista pelo nome, pelo id ou pelo nome do ícone. Clique na linha: o
ícone aparece no canto, e os campos do XML já se preenchem com o que dá para
ler da tabela do cliente.

**Escolha um base parecido com o que você quer.** Uma espada nova copiada de
uma espada herda o jeito de segurar, o som do golpe e a animação. Copiada de um
chapéu, não.


## 2. Identificação

### id

O número que o cliente e o servidor usam para falar do mesmo item.

**Sugerir** procura o primeiro id livre a partir de **30000**, longe da faixa
do jogo original. Use isso. Um id na faixa do jogo sobrescreve um item de
verdade — e aí a espada que você criou vira a Adena de alguém.

O programa avisa quando o id escolhido cai abaixo de 30000.

### nome

O que o jogador lê. Vem preenchido com o nome do item base; troque.

### descrição

O texto que aparece ao parar o mouse sobre o item, no inventário. Pode ficar
vazio.

### ícone

A referência tem a forma `pacote.objeto` — por exemplo
`icon.weapon_long_sword_i00`. É o desenho de 32×32 que aparece no inventário.

Na janela **Novo item…** o ícone se escolhe **vendo**: há uma grade de
miniaturas à direita, com a arte no tamanho em que o jogo a desenha. Clique
numa para escolher.

A grade abre nos ícones **parecidos com o do item base** — copiando uma espada,
começa nas armas — e mostra 240 por vez; o rótulo diz quantos ficaram de fora e
a busca reduz. Nada fica escondido: o campo de busca alcança os 13.690.

O ícone não precisa ser o do item base. Trocar só o ícone é a forma mais barata
de dar cara nova a um item copiado, sem mexer em modelo nenhum.

Logo abaixo da grade, **Usar uma imagem minha** aceita um desenho seu — veja a
última seção.

### substituir se o id já existir

Deixe **desmarcado**. Marcado, ele apaga o item que estiver naquele id em vez de
recusar — o que só serve quando você está refazendo um item que criou antes.


## 3. XML do servidor

O que estiver em branco **não é escrito**. O servidor tem um valor padrão para
todo campo, e um campo ausente vale esse padrão. Preencher só o que importa
deixa o arquivo legível.

### tipo no servidor

`Weapon`, `Armor` ou `EtcItem`. Vem preenchido.

Um caso que confunde: **escudo fica no `weapongrp` do cliente, mas para o
servidor é `Armor`**. O programa detecta pelo item base e já marca o tipo certo.
Se marcar `Weapon`, o personagem empunha o escudo como arma.

### ação ao clicar

O que acontece no clique duplo do inventário. `equip` para arma e armadura;
`skill_reduce` para poção; `none` para material e item de missão.

### parte do corpo

Onde o item é vestido:

| valor | onde |
| --- | --- |
| `rhand` | mão direita — arma de uma mão |
| `lrhand` | as duas mãos — espadão, arco, lança |
| `lhand` | mão esquerda — escudo |
| `chest`, `legs`, `feet`, `gloves`, `head` | as peças da armadura |
| `fullarmor` | peito e pernas na mesma peça |
| `neck` | colar |
| `rfinger;lfinger` | anel |
| `rear;lear` | brinco |
| `none` | não é vestido |

### material

De que o item é feito. Não é decoração: o material decide o som ao ser
atingido, e conta para algumas resistências. Vem preenchido do cliente e acerta
em 100% dos itens conferidos.

### grau

`D`, `C`, `B`, `A`, `S`, ou vazio para item sem grau. É o que controla quais
cristais o item devolve e a partir de que nível ele pode ser usado.

### peso

Em unidades do jogo — a Short Sword pesa `1600`. Vem preenchido.

### preço

Quanto o NPC cobra. **Não sai do cliente**, então vem vazio: preencha ou deixe
em zero.

### cristais

Quantos cristais o item devolve ao ser quebrado.

### tipo de arma

`SWORD`, `BLUNT`, `DAGGER`, `BOW`, `POLE`, `DUAL`, `DUALFIST`, `FIST`,
`BIGSWORD`, `BIGBLUNT`, `ETC`, `FISHINGROD`.

Decide qual habilidade o personagem pode usar com o item na mão e qual animação
de ataque ele toca. Vem preenchido, e o programa já separa espada de espadão
pelo número de mãos.

### tipo de armadura

`LIGHT`, `HEAVY`, `MAGIC` — leve, pesada, de tecido. Decide as penalidades de
classe: mago de armadura pesada perde regeneração de mana.

### dano aleatório, soulshots, spiritshots

Saem do cliente. `soulshots` e `spiritshots` são quantos tiros o item consome
por golpe.

### negociável, largável, vendável, destruível, guardável

Deixe em branco para o padrão (tudo permitido). Marque `false` no que quiser
travar — um item de evento costuma ser `is_tradable false` e `is_dropable
false`.


## Ler do servidor

O cliente guarda aparência, peso e material. **Dano, defesa e preço não existem
nele.** O botão **Ler do servidor**, na aba XML, procura o item na pasta de
dados do servidor e traz os campos e os status.

Lê o item **marcado na lista** — e não o do campo **id novo**. O campo diz
para onde o item vai; a lista diz de onde ele vem. Para reler um item que
você criou, marque-o na lista: ele está lá depois de gerar.

Não achando, avisa que o item ainda não existe do lado do servidor. Não é
erro: é o caso de preencher e gerar.

Funciona nos dois formatos. Nos cores de banco, as colunas de combate (`p_dam`,
`p_def`, `critical`) voltam para o bloco de status, que é onde o XML as põe.

**O que a tela não mostra volta como estava.** Um item do servidor costuma ter
mais do que campos: condição de uso (`<cond>`), bônus de encantamento
(`<enchant>`), o que o core daquele pack inventou — 41% dos itens do datapack do
High Five têm algo assim. Isso é lido e devolvido igual na regravação, junto com
os `<set>` que esta tela não oferece (`icon`, `attack_range`). A linha de
situação diz quantos blocos ficaram guardados.

Antes disso, regravar um item trazido do servidor **apagava** essas partes: o
arquivo saía com os campos certos e sem o que fazia o item ser daquela classe.


## Conjunto de armadura

O botão **Conjunto…**, no rodapé, abre as duas metades do conjunto — porque
mexer numa só é o erro clássico: o texto aparece no inventário e o bônus não vem,
ou o bônus vem e nada explica por quê.

| Lado | O que guarda | Onde |
| --- | --- | --- |
| cliente | a lista de peças e o **texto** do bônus | `itemname-e.dat` |
| servidor | a **habilidade** que o conjunto concede | `armorsets/` ou `armorSets.xml` |

A lista fica **numa peça só**, que costuma ser o peitoral — é assim que o jogo
escreve, e foi contado antes de escrever igual: das 207 linhas com conjunto do
High Five, 195 têm o próprio id como primeiro da lista, e só 8 das 691 peças
apontadas por alguma lista levam lista própria.

Marque a peça principal na lista de itens, abra a janela e acrescente as outras
por id (**Usar a peça da lista** pega a que está marcada atrás). A parte do corpo
de cada uma aparece ao lado, lida do cliente; peça que o cliente não tem é aceita
depois de um aviso, porque um conjunto com peça inexistente nunca se completa.

O texto do bônus é o que o jogador lê: escreva como o jogo escreve — `P. Def. +2%
e Max HP +41.`

Do lado do servidor, informe a **skill do conjunto** (crie-a na aba
Habilidades) e, se houver, a do escudo e a do +6. A forma do XML não se escolhe
em menu: o programa lê a pasta do servidor do projeto e vê qual está lá — o
`<set id=…>` do L2J ou a linha `<armorset …/>` do aCis.

**Gravar no cliente** escreve o `itemname-e` na pasta de saída; o cliente só
muda em **Instalar no cliente**, na tela de itens, como sempre.

Nas crônicas C3 e C4 o botão avisa que não há o que gravar: a coluna `set_ids`
não existe no `itemname` delas. O conjunto do servidor continua funcionando; só
não há texto no cliente.

## 4. Status que o item dá ao jogador

É esta parte que faz o item **valer alguma coisa**. Sem ela, a espada nova tem
a aparência certa e dano nenhum.

Cada linha tem três partes: **operação**, **status** e **valor**.

### A operação

Diz como o valor entra na conta:

| operação | o que faz |
| --- | --- |
| `add` | soma ao total já calculado |
| `baseadd` | soma à base, antes dos multiplicadores |
| `sub` | subtrai |
| `mul` | multiplica (`1.1` = mais 10%) |
| `basemul` | multiplica a base |
| `div` | divide |
| `set` | fixa o valor, ignorando o que havia |
| `enchant` | a parcela que cresce a cada encantamento |

**Na prática**, seguindo o que o próprio jogo faz:

- arma: `set` para `pAtk`, `mAtk`, `rCrit` e `pAtkSpd`;
- armadura: `baseadd` para `pDef` ou `mDef`, e `enchant` para a parte que sobe
  com o encantamento;
- escudo: `set` para `sDef` e `rShld`, `sub` para `rEvas`;
- acessório: `baseadd` para `mDef`, `add` para bônus como `maxMp`.

### A ordem

Ao lado da operação há a **ordem**: em que momento da conta aquele valor entra.
Ela é preenchida sozinha, com o que o jogo usa para cada operação:

| operação | ordem | o que significa |
| --- | --- | --- |
| `set` | `0x08` | fixa a base |
| `enchant` | `0x0C` | o que cresce a cada +1, logo depois da base |
| `add` / `sub` | `0x10` | soma antes dos multiplicadores |
| `mul` / `basemul` | `0x30` | multiplica |
| — | `0x40` | soma **depois** dos multiplicadores |

Os números não são escolha de estilo: saem da contagem do datapack, onde `set`
aparece com `0x08` nos 4.736 status, sem uma exceção.

**Ela é obrigatória.** O servidor lê o atributo sem verificar se ele existe:

```java
String order = n.getAttributes().getNamedItem("order").getNodeValue();
```

Faltando, a leitura estoura e a **tabela de itens inteira** deixa de carregar.
Quem tiver um item gerado por uma versão anterior deste programa, com status e
sem ordem, precisa regravá-lo.

Mexa nela só se souber por quê. `0x40` serve para um bônus que deve entrar
depois das contas de classe — é o que o jogo faz com `maxMp` de acessório.

### O status

Escolha na lista. Ela está agrupada por assunto — vida e mana, ataque e defesa,
taxas e esquiva, atributos, PvP, resistências, vulnerabilidades, reflexo,
contra tipo de criatura, limites.

Os mais usados:

| status | o que é |
| --- | --- |
| `pAtk` / `mAtk` | ataque físico / mágico |
| `pDef` / `mDef` | defesa física / mágica |
| `pAtkSpd` / `mAtkSpd` | velocidade de ataque / de magia |
| `rCrit` | taxa de crítico (10 = 1%) |
| `cAtk` | dano crítico |
| `accCombat` / `rEvas` | precisão / esquiva |
| `maxHp` / `maxMp` / `maxCp` | vida, mana e CP máximos |
| `regHp` / `regMp` | regeneração |
| `runSpd` | velocidade de corrida |
| `sDef` / `rShld` | defesa e taxa de bloqueio do escudo |
| `STR`, `CON`, `DEX`, `INT`, `WIT`, `MEN` | atributos |

**Por que isso importa**: um nome de status que o servidor não conhece não é
ignorado. Ele derruba o carregamento da **tabela de itens inteira** — todos os
itens do servidor, não só o novo.

A lista é do programa, e nem todo core tem todos os nomes dela. O botão
**Conferir com o servidor** lê a pasta que você apontou e marca com ⚠ os que o
seu não tem. Quando o código-fonte está junto da pasta de dados, a resposta sai
do `Stats.java` dele e é completa; quando só há os `.jar`, sai dos `stat="..."`
que o datapack usa — menor, mas todo nome ali é prova de que sobe.

### O valor

Um número. Pode ter vírgula decimal escrita com ponto (`1.15`) e pode ser
negativo para penalidade.

Cuidado com a escala: `rCrit` conta em décimos de por cento (`80` é 8%), e
`pAtkSpd` é um número absoluto (uma arma comum fica perto de `379`). Quando
tiver dúvida, olhe um item parecido no seu servidor.

### Ver o XML

Mostra o arquivo pronto antes de gerar. Vale sempre o olho antes de instalar.


## 5. Skills que o item carrega

Uma arma pode dar uma habilidade a quem a equipa, ou disparar uma no golpe.
Neste servidor isso **não** é um `<skill>` dentro do item: são campos `<set>`,
com o id e o nível escritos juntos.

| campo | quando vale | quantas |
| --- | --- | --- |
| `item_skill` | enquanto o item estiver equipado | várias, separadas por `;` |
| `enchant4_skill` | a partir do +4 | uma |
| `oncrit_skill` | ao dar um crítico | uma |
| `oncast_skill` | ao castar | uma |

O valor é `id-nível`: `3599-1`. Para várias, `3599-1;3600-2`.

### A chance, que engole em silêncio

`oncrit_skill` e `oncast_skill` **exigem** a chance junto — `oncrit_chance`,
`oncast_chance`, em por cento. O servidor faz:

```java
if (id > 0 && level > 0 && chance > 0)
```

Sem a chance, ou com ela em zero, a skill é **descartada sem uma linha de log**.
Não dá erro, o servidor sobe normalmente, e a arma simplesmente não faz nada.
Quem for testar vai culpar a habilidade, e não o campo que faltou. Por isso o
botão **Conferir** existe, e a janela pergunta antes de deixar passar.


## 6. Os números do cliente (arma)

Na janela **Novo item**, quando a base é uma arma, aparece a página **Números**.
São as colunas do `weapongrp.dat` — **o que a tooltip do inventário mostra**.

Isso é diferente dos Status. Os Status são do servidor: o que o golpe faz de
verdade. Os Números são do cliente: o que o jogador lê. **Os dois podem
discordar sem que nenhum reclame.** A Draconic Bow deste cliente mostra 581 de
P.Atk na tooltip; o servidor usa 561.

Ao lado de cada caixa há o nome cinza do status correspondente:

| cliente | servidor |
| --- | --- |
| `patt` / `matt` | `pAtk` / `mAtk` |
| `critical` | `rCrit` |
| `speed` | `pAtkSpd` |
| `hit_mod` | `accCombat` |
| `avoid_mod` | `rEvas` |
| `shield_pdef` / `shield_rate` | `sDef` / `rShld` |

`hit_mod` e `avoid_mod` são os únicos com sinal no cliente. Do lado do servidor
o sinal vira a **operação**: `-3` no cliente é `<sub stat="accCombat" val="3">`.

O botão **Copiar para os Status** faz essa tradução e escreve tudo na página
Status, já com a operação e a ordem certas. É o caminho curto para os dois lados
contarem a mesma história.


## 7. Gerar, instalar, e o próximo item

**Gerar** escreve as tabelas alteradas e o `<id>-item.xml` numa pasta à parte.
**Nada no cliente muda ainda.**

**Instalar no cliente** põe as tabelas no lugar. Na primeira vez, as originais
vão para `system/backup_itens`; **Restaurar originais** as traz de volta e
desfaz tudo de uma vez.

O XML você copia à mão para a pasta de itens do servidor — em geral
`data/xml/items/` — e reinicia o gameserver.

Depois de gerar, a tela já se prepara para o próximo: sugere o id livre
seguinte, limpa nome, descrição e status, e mantém o item base marcado. Dez
itens criados em sequência saem num `weapongrp.dat` só, instalado de uma vez.

**Feche o cliente antes de instalar.** O jogo aberto mantém as tabelas em
memória e grava por cima ao sair.



## 8. Ícone próprio

Na janela de escolher ícone, a aba **Imagem própria** aceita um desenho seu —
PNG, JPG, BMP, TGA, DDS.

O que acontece: a imagem é ajustada para 32×32 (sem esticar: se não for
quadrada, entra centralizada num quadrado transparente), comprimida em DXT,
montada num pacote `.utx`. O campo do ícone já recebe a referência pronta.

O pacote fica **preparado, e não instalado**: ele sai na pasta de saída junto
com as tabelas e entra em `systextures` no mesmo **Instalar no cliente**. Uma
ação, um lugar — instalar na hora deixaria um ícone dentro do cliente enquanto o
resto ainda não existe em lugar nenhum.

**O pacote é seu.** O programa nunca grava dentro do `Icon.utx` ou do `Icon.u`
do jogo, e recusa se você tentar: um erro no pacote próprio custa um ícone; no
do jogo custaria os catorze mil. Não há perda — o cliente carrega quantos
pacotes de ícone houver, e o seu já tem vários.

Acrescentar um segundo ícone ao mesmo pacote **remonta o pacote inteiro**, com
os que já estavam dentro. É mais lento e é o único jeito honesto: meia
remontagem perderia os antigos.

O nome do pacote e o do ícone aceitam letras, números e sublinhado. O nome do
arquivo importa de verdade — a chave de criptografia do `.utx` deriva dele —
então renomear o pacote depois de criado o corrompe. Se precisar de outro nome,
crie de novo.

## Se alguma coisa der errado

**"A volta não reproduz o original"** — a definição das tabelas não descreve
este cliente, e gravar fica bloqueado de propósito. Em geral o cliente é de
outra crônica. Nada foi escrito.

**Item sem nome no jogo** — as tabelas foram instaladas pela metade. Elas se
casam pelo id e precisam ir juntas. Use **Restaurar originais** e gere de novo.

**O servidor não sobe depois do XML** — quase sempre é um nome de status ou de
material escrito à mão fora da lista. Olhe o log do gameserver: ele diz o nome
que não reconheceu.

**O item aparece sem ícone** — a referência do ícone aponta para um objeto que
não existe. Use **Escolher…** em vez de digitar, ou rode a aba **Conferir
Cliente**, que lista tudo que as tabelas pedem e não está instalado.

**O ícone não aparece na tela, mas aparece em jogo** — há pack cujo pacote de
ícone vem protegido: cabeçalho fora do padrão, que nenhum leitor de fora abre.
O jogo abre porque tem a chave; o programa não.

Nesse caso o ícone fica **vazio**, e o registro diz qual pacote não abriu:

```
o pacote PacoteCustom nao abriu; os icones dele nao vao aparecer
```

O programa não pega o desenho de outro pacote para preencher o buraco. O objeto
costuma existir no `Icon.u` com o mesmo nome, mas nada garante ser a mesma arte
— e um desenho errado com cara de certo apagaria o único sinal de que há um
pacote para resolver. Decifre o pacote e recrie-o em `.utx`, e o ícone aparece.
