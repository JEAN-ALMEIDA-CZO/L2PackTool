# Mob: o status, as skills e a lista de drop

Um mob do servidor mora num `<npc>` dentro de `data/xml/npcs`, e cada arquivo
carrega até mil deles. As três coisas que você mexe — o status, os golpes e o
que ele dropa — ficam a centenas de linhas uma da outra.

Esta aba abre esse bloco, edita as três, e **reescreve só ele**. Os outros mil
NPCs do arquivo não são tocados em byte nenhum.


## Abrindo

**Servidor** é a pasta do servidor, ou direto a pasta `npcs` dele — a tela acha
o caminho a partir de qualquer um dos dois. **Abrir os mobs** lê tudo:

```
4000 mobs em ...\data\xml\npcs.
```

O core lê `npcs` e depois `raidboss`, `grandboss`, `farmzone`, `custom` e
`events`, nessa ordem. **Id repetido faz valer o último a carregar** — a
definição anterior é descartada em silêncio. A tela avisa quando encontra
repetidos, porque é o tipo de coisa que faz alguém editar um mob a tarde
inteira sem entender por que o jogo não muda.

**Cliente** não é obrigatório, mas vale: é dele que saem o nome e o desenho de
cada item da lista de drop, e é o que permite a conferência avisar quando um
drop aponta para um item que não existe.


## Achando o mob

A lista tem filtro por texto (nome ou id), por **tipo** e por **faixa de
nível**. Os três se somam. A caixa de tipo se enche com os tipos que o seu pack
realmente usa — 79 deles, neste caso, e não uma lista fixa.


## Status

O primeiro quadro é a identidade; o segundo, os `<set>`; o terceiro, o `<ai>`.

Os status aparecem na ordem em que se pensa neles — nível, tipo, exp, HP, os
atributos — e o que o seu mob tiver além disso entra no fim, em vez de sumir.

> **O `<ai>` é a armadilha silenciosa.** O core lê `type`, `ssCount`, `ssRate`,
> `spsCount`, `spsRate`, `aggro`, `canMove` e `seedable` **sem verificar se
> existem**:
>
> ```java
> set.set("canMove", Boolean.parseBoolean(attrs.getNamedItem("canMove").getNodeValue()));
> ```
>
> Faltando um, aquilo é um `NullPointerException` no carregamento. A
> conferência cobra os oito. Tendo `clan`, o `clanRange` passa a ser
> obrigatório pelo mesmo motivo.


## Skills

A raça fica num campo próprio, e não na lista de golpes. O motivo:

```java
if (skillId == L2Skill.SKILL_NPC_RACE)   // 4416
{
    set.set("raceId", level);
    continue;                            // não registra skill nenhuma
}
```

**A linha `<skill id="4416" level="9"/>` não é uma skill.** O core lê o `level`
dela como a raça do mob — 9 é Demon — e sai fora. Ela no meio da lista de
golpes seria um convite a apagar a raça achando que estava tirando um ataque.

Os golpes de verdade ficam na lista de baixo. Skill que não existe na tabela do
servidor é ignorada com um aviso no log — vale conferir o log depois de
recarregar.


## Drop

Cada categoria é uma gaveta; dentro dela, os itens com o ícone ao lado do nome.

> **A chance é por milhão.** `DropData.MAX_CHANCE` é `1000000`, então:
>
> | no arquivo | na prática |
> | --- | --- |
> | `1000000` | 100% |
> | `79637` | 7,9637% |
> | `5` | 0,0005% |
>
> É o erro mais comum de lista de drop: escrever `5` querendo 5% faz o item
> não cair nunca. Na janela do drop os dois campos aparecem juntos, e mexer
> num acerta o outro.

**A categoria `-1` é spoil** (sweep), e o core sempre a visita. De `0` para
cima são grupos de drop comum, e o core sorteia **um item por grupo** — pôr
dez itens numa categoria só faz eles disputarem entre si, e não caírem juntos.

Drop de item que o cliente não conhece é descartado pelo core:

```java
if (ItemTable.getInstance().getTemplate(data.getItemId()) == null)
{
    _log.warning(" Droplist data for undefined itemId: " + data.getItemId());
    continue;
}
```

Em jogo, o mob simplesmente não dropa aquilo, e sem ler o log ninguém descobre
por quê. Abra as tabelas do cliente e a conferência pega isso antes.


## Minions

Os mobs que nascem junto. O `id` é de outro NPC; `min` e `max` são quantos vêm.


## O que a tela não edita

`<petdata>` — a tabela de níveis do pet, que tem cem linhas — e `<teachTo>`
não são editados aqui. **Eles voltam byte a byte.** Quando existem, a tela diz
no canto:

```
preservado sem tocar: petdata
```

É uma promessa que vale a pena conferir: `Ver a XML` mostra o bloco inteiro do
jeito que vai ser gravado.


## Gravar

**Conferir** cruza o mob com o cliente e com o que o core exige. **Ver a XML**
mostra o bloco pronto. **Gravar no servidor** troca só aquele `<npc>` dentro do
arquivo e deixa uma cópia datada ao lado:

```
20000-20999.xml.20260917-174900.bak
```

Depois, no jogo:

```
//reload npc
```
