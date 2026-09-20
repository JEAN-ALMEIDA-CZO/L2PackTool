# NPC e loja: o lado do servidor

O cliente sabe **desenhar** o NPC — malha, textura, som. Isso é trabalho da aba
de NPC Effects. O que ele não sabe é **o que o NPC é**: quanto de vida tem, o
que larga ao morrer, onde nasce, o que vende. Nada disso existe no cliente.

Esta aba gera essa metade.


## Escolha o servidor primeiro

O cliente do Lineage 2 é um só; o emulador não.

| Formato | Quem usa | Onde guarda |
| --- | --- | --- |
| **XML** | aCis, L2jServer, Mobius, Lisvus | `data/xml/npcs`, `data/xml/multisell` |
| **Banco** | L2jFrozen e os cores de datapack antigo | tabelas `npc`, `droplist`, `spawnlist` |

Não é só o formato: os nomes mudam. Onde o aCis escreve
`<set name="pAtk" val="700"/>`, o banco tem uma coluna `patk`. Onde o aCis diz
`type="Monster"`, o banco diz `L2Monster`.

A caixa **Servidor** no alto escolhe, e o mesmo formulário sai no formato certo.

A primeira opção dela não é um core: **Detectar pelo servidor** lê a pasta que
você apontou e monta o perfil a partir dela — em que pastas as coisas moram, se
o alvo da habilidade leva prefixo, como a gaveta de drop é escrita, em que
unidade vai a chance. Leva cerca de dois segundos, e **o que foi visto aparece
ao lado da caixa**.

É a opção de partida porque "qual é o meu core?" costuma não ter resposta
simples: quem monta um servidor pega um core, troca o nome e mexe no que quer.
Um servidor com nome próprio pode ser aCis por baixo, com quatro diferenças —
e essas diferenças estão escritas nos arquivos dele.

Os cores prontos continuam na lista, e escolher um manda. Detectar é o padrão,
não uma imposição.

**Um core que não está na lista** também se acrescenta largando um `.json` em
`recursos/servidores/`. O arquivo diz o formato, as pastas ou tabelas, e o
de-para dos campos. Não há código a mexer.

Uma coisa que vale saber: o `INSERT` sai com **os nomes das colunas**, e não por
posição. Schema de emulador não é fixo, e uma coluna a mais no meio faria um
insert posicional pôr preço no lugar de peso — sem erro e sem aviso.


## Ler do servidor

O botão **Ler do servidor**, no topo do passo 2, procura este NPC na pasta de
dados do servidor e traz o que ele tem: atributos, drop, spawn e loja.

Ele lê o NPC **marcado na lista** — e não o do campo **id novo**. O campo diz
para onde o NPC vai; a lista diz de onde ele vem. É assim que se copia os
atributos de um monstro que já funciona: o cliente nunca guardou vida nem
ataque, e assim não é preciso digitá-los.

Não achando, o programa avisa que o NPC ainda não existe do lado do servidor.
Não é erro: é o caso de preencher e gerar.

Funciona nos dois formatos. Num `INSERT` que não nomeia as colunas — e quase
todo `.sql` que circula é assim — o programa usa a ordem das colunas declarada
no perfil. Se o perfil não tiver essa ordem, ele diz que não soube ler, em vez
de adivinhar por posição.

O nome e o título voltam para o passo 1. O que **você digitou** nunca é
apagado; o que veio de uma leitura anterior é substituído.

## Atributos

Escolha o NPC base na lista — ele serve de referência de aparência e de id. Os
campos vêm com valores de partida plausíveis para um NPC de nível 70; ajuste.

O **id** deve bater com o do cliente. Se você criou o NPC na aba de NPC Effects,
use o mesmo id aqui: é ele que amarra os dois lados.

**tipo** decide o comportamento: `Monster` ataca, `Folk` fica parado e conversa,
`Merchant` abre loja, `Teleporter` teleporta, `RaidBoss` é chefe. No servidor de
banco o nome sai com o prefixo `L2` automaticamente.

**vida, mana, ataque, defesa** são os números de combate. Para um NPC que só
conversa, eles não importam; para um monstro, são tudo.

**raio e altura de colisão** vêm do tamanho do boneco. Errados, o personagem
atravessa o NPC ou fica preso longe dele.

**experiência e SP** é o que o jogador ganha ao matar. Zero num NPC de cidade.

**raio de agressão** em zero faz o NPC não atacar sozinho.


## Drop

O que o NPC larga ao morrer.

A **chance é percentual**: `2.5` é 2,5%. Para o servidor de banco o número é
convertido para a escala dele (onde 1.000.000 é 100%) — você digita em por cento
nos dois casos.

A **gaveta** separa:

| gaveta | o que é |
| --- | --- |
| `DROP` | o item cai no chão ao morrer |
| `CURRENCY` | adena — o item 57 |
| `SPOIL` | só sai no roubo, com a habilidade de spoil |

Adena é o item **57**. Um monstro comum tem uma linha `CURRENCY` com adena e
algumas linhas `DROP`.


## Spawn

Onde o NPC nasce. As coordenadas se pegam em jogo, no comando que mostra a
posição do personagem.

**direção** é para onde ele olha, de 0 a 65535. **renasce em** é em segundos.

Marque **gerar o spawn junto** para o arquivo sair. Sem marcar, só o NPC é
gerado — o que serve quando você vai colocá-lo em jogo pelo comando de spawn.


## Loja

O multisell: o que o jogador paga e o que recebe.

É XML nos dois formatos de servidor — até os cores de banco guardam a loja em
arquivo.

**Adena é o item 57.** Uma venda comum é pagar adena e receber o item. Uma troca
é pagar um item e receber outro. Dá para pôr várias linhas; cada uma é uma opção
na janela da loja.

O **id da loja** é o nome do arquivo. Para o NPC abrir a loja, o servidor precisa
saber disso — em geral por um script ou pelo tipo `Merchant` com a loja ligada ao
id. Isso varia de core para core e fica fora do que esta tela gera.


## Gerar

**Ver o que sai** mostra tudo antes. **Gerar** grava na pasta escolhida.

O que sai:

- `<id>-npc.xml` ou `<id>-npc.sql` — o NPC, com o drop dentro no caso do XML
- `<id>-spawn.xml` ou `.sql` — se você marcou
- `<id da loja>.xml` — o multisell

Copie para as pastas do servidor; se for banco, rode o `.sql` nele. O gameserver
precisa reiniciar.

**Nada é gravado no cliente por esta aba.** Ela só escreve o lado do servidor.
