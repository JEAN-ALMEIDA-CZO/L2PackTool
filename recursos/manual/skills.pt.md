# Criar uma habilidade: o que preencher

Uma habilidade existe nos mesmos dois lugares que um item — o **cliente** sabe
desenhar, o **servidor** sabe o que ela faz — e o **id** amarra os dois.

A diferença que muda tudo: habilidade tem **nível**. Ela não é uma linha, é um
bloco de linhas, uma por nível, em cada tabela:

| Arquivo | O que guarda |
| --- | --- |
| `skillgrp.dat` | ícone, mana, alcance, tempo de uso — por nível |
| `skillname-e.dat` | nome e descrição — por nível |

Neste cliente são 3.067 habilidades em 42.019 linhas. Copiar uma habilidade
copia todos os níveis dela, nas duas tabelas, de uma vez. Meia cópia produz a
habilidade que existe até o nível 12 e some no 13.


## Editar ou criar

A tela tem um **modo**, escrito em letras grandes no alto do painel da direita:

```
Editando a habilidade 1086 — Might
Nova habilidade 90000, copiada da 1086
```

**Clicar numa habilidade da lista edita aquela habilidade.** Os campos se enchem
com os dados dela, o id fica travado no dela, e o botão vira **Regravar a
habilidade**. O id trava de propósito: mudar o número ali seria, na verdade,
criar outra.

**Criar passa pela janela Nova habilidade…** Ela pergunta o id (com Sugerir),
nome, descrição, ícone e o corte de nível; recusa um id que já exista sem a marca
de substituir; avisa se o id cair na faixa do jogo. O que sai dela preenche o
painel, e os campos continuam editáveis — é um começo guiado, não uma cerca.

Depois de gerar, a tela passa a **editar o que acabou de sair**: é o que se faz
em seguida, ver como ficou e ajustar.


## 1. Escolha a habilidade base

A lista mostra **uma linha por habilidade**, não por nível — seriam 42 mil
linhas com a mesma habilidade repetida quarenta vezes. A coluna "níveis" diz
quantos a cópia vai levar.

Procure pelo nome, pelo id ou pelo nome do ícone. Escolha uma base parecida com
o que você quer: o modo (ativa, passiva, alternável), o tempo de uso e a
animação vêm dela.


## 2. Identificação

### id

**Sugerir** procura o primeiro livre a partir de **90000**. Essa faixa fica
longe de duas coisas: dos ids do jogo e das **rotas de encantamento**, que
ocupam os 50000 e diante.

### nome e descrição

O nome vai igual em todos os níveis, que é como o jogo faz.

A descrição do jogo muda de nível para nível — é o "Power 25" que vira "Power
27". Deixando a descrição em branco, cada nível herda a descrição do mesmo
nível da habilidade base, o que costuma ser o mais próximo do certo. Escrevendo
uma, ela vai igual em todos.

### ícone

`pacote.objeto`, como no item — os ícones de habilidade costumam ser
`icon.skill0003`.

Na janela **Nova habilidade…** o ícone se escolhe **vendo**: há uma grade de
miniaturas à direita, que abre nos `icon.skill*` porque parte do ícone da
habilidade base. Mostra 240 por vez; o rótulo diz quantos ficaram de fora e a
busca reduz — nada fica escondido.

Logo abaixo, **Usar uma imagem minha** aceita um desenho seu; veja a última
seção.

### copiar até o nível

Em branco, a cópia leva todos os níveis de verdade.

Preencha quando a base tiver muitos níveis e você só quiser os primeiros.


### as rotas de encantamento

A rota de encantamento **não é outra habilidade**: são níveis altos da mesma —
101, 102, 103 para a primeira rota; 201 para a segunda; e assim por diante. No
High Five há oito rotas, até a casa dos 800.

Duas coisas seguem disso.

**A contagem de níveis é só dos níveis de verdade.** A habilidade 1 tem 37
níveis e 247 linhas no cliente: as outras 210 são rotas. Somar tudo escrevia
`levels="247"` no XML — servidor prometendo nível que o cliente não desenha.
Conferido contra o datapack: 7.576 habilidades certas antes, **8.102 de 8.136**
agora. O rótulo da habilidade marcada diz as duas contas, quando há rotas.

**A cópia não leva as rotas, a menos que você marque.** Elas apontam, no
`ench_skill_id`, para a habilidade parceira do **original** — copiadas, o cliente
passa a oferecer um encantamento que o servidor novo não tem, apontando para
outra habilidade. Sem elas, a marca `is_ench` também é zerada: deixá-la sem as
rotas abriria a janela de encantamento vazia.

A caixa fica apagada quando a habilidade marcada não tem rota nenhuma.


## 3. XML do servidor

**Já vem preenchido** o que está no `skillgrp`: modo, mana por uso, alcance e
tempo de uso. O `hit_time` do cliente é em segundos e o servidor conta em
milissegundos; a conversão é feita.

O resto é escolha sua, sempre em lista.

### tipo de efeito

O que a habilidade faz. É o campo mais importante — ele decide qual código do
servidor roda.

| tipo | o que é |
| --- | --- |
| `PDAM` | dano físico |
| `MDAM` | dano mágico |
| `BLOW` | golpe furtivo (pelas costas) |
| `DRAIN` | dano que devolve vida |
| `HEAL` / `HOT` | cura, na hora ou ao longo do tempo |
| `MANAHEAL` / `MANARECHARGE` | recupera mana |
| `BUFF` | melhora um status por um tempo |
| `DEBUFF` | piora um status do alvo |
| `PASSIVE` | vale sempre, sem ser usada |
| `CONT` | efeito contínuo enquanto ativa |
| `STUN`, `ROOT`, `SLEEP`, `FEAR`, `PARALYZE` | controle |
| `POISON`, `BLEED` | dano ao longo do tempo |
| `RESURRECT` | ressuscita |
| `AGGDAMAGE` / `AGGDEBUFF` | provocação |

### modo

`ACTIVE` usa-se apertando; `PASSIVE` vale sempre; `TOGGLE` liga e desliga e
consome mana enquanto ligada. Vem do cliente.

### alvo

`SELF` em si mesmo, `ONE` num alvo, `PARTY` no grupo, `CLAN` no clã, `AURA` em
tudo à volta, `AREA` numa área a partir do alvo. Há 28 opções na lista.

### poder

Para dano é o dano base; para cura é o quanto cura; para efeito de controle é
a chance. O que significa depende do tipo de efeito.

### nível mágico

O nível do personagem a partir do qual a habilidade tem eficiência cheia. Usar
uma habilidade de nível mágico muito acima do seu reduz o efeito.

### mana por uso, mana ao começar, vida por uso

Custo. `mana ao começar` é o que sai ao iniciar o gesto — o resto sai quando
completa.

### alcance, alcance do efeito, raio

`alcance` é de onde dá para usar. `alcance do efeito` é até onde o efeito
alcança. `raio` é o tamanho da área nas habilidades de área.

### tempo de uso, tempo final, recarga

Em milissegundos. `tempo de uso` é a animação; `tempo final` é a trava logo
depois; `recarga` é quanto tempo até poder usar de novo.

### elemento

`FIRE`, `WATER`, `WIND`, `EARTH`, `HOLY`, `DARK`. Faz o dano contar contra a
resistência correspondente do alvo.

### armas permitidas

Restringe a habilidade a um tipo de arma na mão — `SWORD`, `BOW`, `DUAL`. Em
branco, qualquer arma serve.

### é magia

`true` faz a habilidade contar como magia: é interrompida ao levar dano e usa
spiritshot em vez de soulshot.

### provocação

Quanto ódio a habilidade gera nos monstros.


## Ler do servidor

**Poder, recarga e tipo de efeito não existem no cliente.** O `skillgrp` guarda
ícone, mana, alcance e tempo de uso, e mais nada.

O botão **Ler do servidor**, na aba XML, traz o resto. Ele lê a habilidade
**marcada na lista** — e não a do campo **id novo**. O campo diz para onde a
habilidade vai; a lista diz de onde ela vem. Para reler uma que você criou,
marque-a na lista: ela está lá depois de gerar.

Não achando, avisa que a habilidade ainda não existe do lado do servidor.

Um aviso aparece quando a habilidade usa valor por nível: o `<set>` traz o
apelido (`#power`) e a tabela fica fora da tela. O apelido é mostrado como está.

## 4. Status que a habilidade dá

O bloco `<for>`, igual ao dos itens: **operação**, **status**, **valor**.

É isso que faz um `BUFF` valer alguma coisa. Um sopro que aumenta ataque é
`skillType BUFF` mais `mul` em `pAtk` com valor `1.15` — 15% a mais.

Para `PASSIVE` costuma ser `add` ou `mul` direto no status.

**Duplo clique numa linha da tabela** devolve operação, status e valor para os
campos de cima, e o botão vira **Guardar**. Trocar `1.30` por `1.25` não exige
mais tirar a linha e escrever os três campos de novo.

**Cuidado com a escala**: `mul` multiplica (`1.15` = mais 15%), `add` soma o
número cru. Um `add` de `1.15` em `pAtk` soma um ponto de ataque, não 15%.

A lista de status é a mesma dos itens, e pelo mesmo motivo é fechada: um nome
que o servidor não conhece derruba o carregamento da tabela de habilidades
inteira.


## Valor por nível

O jogo escreve progressão com `<table>`: o "Power 25" que vira "Power 27" não é
um número, é uma lista com um valor por nível.

**Basta escrever os valores separados por espaço**, em qualquer campo do XML ou
na coluna `valor` de um status:

```
431 458 486 516 547
```

O programa monta a tabela e faz o `<set>` apontar para ela:

```xml
<table name="#power"> 431 458 486 516 547 </table>
<set name="power" val="#power"/>
```

Vírgula e ponto-e-vírgula valem como espaço. Um campo com texto, como
`SWORD,BLUNT`, continua sendo um valor só — aquilo é uma lista de armas, não uma
progressão.

**A conta tem de bater com o número de níveis.** Uma tabela com menos valores do
que a habilidade tem níveis não dá erro ao gravar: o servidor é que derruba a
habilidade, ou entrega o nível errado, muito depois. O programa confere e avisa
antes de gerar.

**Ler do servidor abre as tabelas.** O `#power` volta como os números dele, que
é o que o campo aceita de volta — dá para ler uma habilidade pronta, mexer no
nível 5 e regravar.


## 5. O que esta tela não faz

**Efeitos.** Um `<effect>` dentro do `<for>` — veneno que tira vida a cada
segundo, transformação, invocação — também fica de fora. O XML gerado é a base
correta; o efeito se acrescenta por cima.

**Condições.** O `<cond>` que exige arma, classe ou estado não é gerado.


## 6. Gerar, instalar, e a próxima

**Gerar** escreve as tabelas e o `<id>-skill.xml` numa pasta à parte. Nada no
cliente muda ainda.

**Instalar no cliente** põe as tabelas no lugar, guardando as originais em
`system/backup_skills` na primeira vez. **Restaurar originais** desfaz.

O XML vai à mão para a pasta de habilidades do servidor — em geral
`data/xml/skills/` — e o gameserver reinicia.

Depois de gerar, a tela se prepara para a próxima: sugere o id seguinte, limpa
nome, descrição, corte de nível e status.

**Feche o cliente antes de instalar.**


## 7. Ícone próprio

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
