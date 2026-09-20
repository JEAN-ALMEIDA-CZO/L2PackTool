# Multisell: a lista de trocas de um NPC

Uma **multisell** é a lista que abre quando você fala com um NPC de troca: de um
lado o que o jogador **paga**, do outro o que ele **recebe**. Adena por uma
arma, materiais por uma armadura, um item +0 por outro +8.

Ela é um arquivo XML no servidor, e só. **Do lado do cliente não há arquivo** —
o cliente apenas desenha o que o pacote manda.


## O nome do arquivo é a chave

Isto sai do código do seu servidor, e não é óbvio:

```java
final int id = file.getName().replaceAll(".xml", "").hashCode();
```

**Não existe campo de id dentro da XML.** O identificador da lista é o nome do
arquivo. É por ele que o NPC a abre:

```
multisell 1000          no bypass do HTML do NPC
exc_multisell 1000      só mostra o que o jogador já tem no inventário
```

Três consequências práticas:

- **Renomear troca a lista de identidade.** O bypass antigo para de achar.
- **Duas listas com o mesmo nome são a MESMA lista**, mesmo em pastas
  diferentes: a segunda a carregar apaga a primeira.
- O nome não precisa ser número. Use letras, números, `-` e `_` — espaço não
  serve, porque o bypass quebraria.

A tela mostra o bypass pronto ao lado do campo do nome, para copiar.


## Montando uma troca

O quadro **A troca** tem os dois lados. Em cada um:

- **+ item** abre a lista de itens do cliente, com ícone, nome e filtro
- **Quantidade…** muda o número e o encantamento do item marcado
- **Tirar** remove

A quantidade é **por troca**: `1000` de Adena quer dizer que cada clique do
jogador custa mil.

O **encantamento** em zero não é escrito no arquivo — é o padrão do servidor.
Num item que o jogador *recebe*, ele sai já refinado; num item que ele *paga*,
só serve o item naquele +N exato.

Um lado pode ter vários itens: `500.000 Adena + 5 Blessed SoE → 1 Dragon
Slayer` é uma troca só.

**Pôr na lista** manda a troca para o checkout embaixo. Duplo clique numa troca
do checkout traz ela de volta para edição; **Subir** e **Descer** mudam a ordem
em que o jogador as vê.

Cada linha do checkout mostra os dois lados, com o ícone ao lado do nome de
cada item:

```
3 ▸  [] Gold Bar x 30  +  [] Dark Ticket x 30.000   →   [] Saint Spear x 1 +5
```

Troca com muitos itens não cabe numa linha, e o último nome sairia cortado. O
**triângulo** na frente do número abre a lista:

```
1 ▾  5 itens                                        →   1 item
        [] Titanium Breastplate x 1                        [] Dark Coin x 1
        [] Event Coin Lv.1 x 50
        [] Golden Enchant: Armor x 500
        [] Tournament Point's Lv.1 x 1.000
        [] Dark Ticket x 50.000
```

O triângulo só aparece onde há o que abrir: troca de um item por um item já diz
tudo na própria linha. Clicar no triângulo abre e fecha; clicar no resto da
linha apenas marca a troca, e duplo clique manda ela de volta para edição.


## Os NPCs

O campo **NPCs** leva os ids que podem abrir esta lista, separados por espaço ou
vírgula.

> **Em branco, QUALQUER NPC abre.** É assim no core:
>
> ```java
> public boolean isNpcAllowed(int npcId) {
>     return _npcsAllowed == null || _npcsAllowed.contains(npcId);
> }
> ```
>
> A lista só fica restrita quando tem pelo menos um NPC. E, estando restrita,
> ela deixa de poder ser aberta **sem** NPC — de um painel da comunidade, por
> exemplo.


## As duas opções

| opção | o que faz |
| --- | --- |
| `cobrar a taxa do castelo` | desconta a taxa da região na troca |
| `manter o encantamento` | o item recebido sai com o mesmo +N do item dado |

`manter o encantamento` serve para troca de arma por arma: quem entrega uma +8
recebe a nova +8. Sem ela, o item sai no +N que a troca disser.


## A conferência, e o que ela pega

**Conferir** cruza a lista com as tabelas do cliente e avisa:

- item que **não existe no cliente** — em jogo aquela linha sairia sem nome e
  sem desenho, e ninguém saberia por quê
- quantidade zero ou negativa
- troca com um lado só
- nome de arquivo inválido, ou **já usado por outra lista**

É a razão de valer a pena abrir as tabelas do cliente antes: sem elas a tela
funciona só com os ids, e você perde essa checagem.


## Gerar e instalar

**Ver a XML** mostra o arquivo pronto, com um comentário legível em cada troca:

```xml
<!-- 500000 Adena + 5 Blessed Scroll of Escape -> 1 Dragon Slayer -->
<item>
    <ingredient id="57" count="500000"/>
    <ingredient id="1538" count="5"/>
    <production id="81" count="1" enchant="8"/>
</item>
```

**Instalar no servidor** grava na pasta de multisell dele — onde ela fica sai do
próprio servidor, lido dos arquivos. Uma cópia fica sempre em
`multisell_gerada/`, para recuperar se alguém mexer no do servidor à mão.

Depois, no jogo:

```
//reload multisell
```

E o bypass no HTML do NPC, que a tela mostra pronto.


## Onde o cliente entra

Não há arquivo de multisell no cliente. O que o cliente precisa é **conhecer os
itens** usados: id, nome e ícone. Item criado na aba de Itens já entra aqui pelo
nome, com o desenho, assim que as tabelas são abertas.

Se você montar uma troca com um item que só existe no servidor, a conferência
avisa — e em jogo aquela linha apareceria vazia.
