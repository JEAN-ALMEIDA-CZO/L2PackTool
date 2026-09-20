# NPC: criar um NPC no cliente

Esta aba cria um NPC novo no **cliente** — a aparência dele: qual malha usa,
que nome mostra, e que efeito brilha em volta. O que o NPC **é** — vida, drop,
spawn, loja — fica na aba de baixo, `2 - Servidor`.

A tela tem três partes, na ordem em que se usa:

1. os NPCs que o cliente já tem, para escolher de quem copiar a aparência
2. os efeitos que o cliente já tem, para escolher o que vai brilhar
3. o formulário do NPC novo, com os dois botões


## Escolher de quem copiar

`Carregar` lê o `npcgrp.dat` e lista os NPCs do cliente com a malha de cada um.
A coluna da direita diz o que aquele NPC tem: `Mesh x2, Sprite x1` quer dizer
duas malhas e um efeito.

Copiar de um NPC que já funciona é o caminho curto: a malha, a textura e as
animações vêm prontas, e o que você muda é o id, o nome e o efeito.


## O efeito

A lista de efeitos sai dos pacotes do próprio cliente. `Adicionar o efeito
selecionado` prende um efeito ao NPC novo; `Aplicar ao marcado` põe num que já
existe.

A **altura (Z)** move o efeito para cima ou para baixo em relação ao osso
escolhido. O desenho ao lado mostra onde ele fica na malha — um efeito no `Z`
errado sai dos pés ou flutua acima da cabeça.

**Obedecer à altura** faz o efeito escalar junto com a malha. Sem isso, um
efeito desenhado para um boneco de tamanho normal fica minúsculo num gigante.


## Script ou rápido

| modo | o que faz |
| --- | --- |
| **Script (compila)** | gera uma classe própria e compila um pacote `FX_<id>.u` |
| **Rápido (só o .dat)** | escreve só a linha no `npcgrp.dat` |

O modo rápido é mais simples e não cria arquivo novo, mas não dá para prender
efeito nele. O modo script é o que permite efeito, e por isso é o padrão
quando há efeito escolhido.

> Um NPC com classe própria costuma aparecer como `NoNameNPC` no visualizador,
> mesmo com o nome gravado no `npcname-e.dat`. Não é defeito: o visualizador
> resolve o nome de outro jeito que o jogo. A saída é marcar **o servidor manda
> o nome e o título** na aba do servidor.


## Ver no jogo

O visualizador abre a malha com textura e roda as animações. Ele **não mostra
o efeito**: emissor de partícula não está entre os recursos que ele abre, e
nenhum visualizador de Lineage 2 desenha partícula do Unreal Engine 2 — isso só
o motor do jogo faz.

Para ver o efeito de verdade, o caminho é o modo de desenvolvimento do próprio
cliente. Os comandos que ele reconhece estão listados na aba.


## Gerar e instalar

São passos separados de propósito.

**Gerar** escreve tudo numa pasta de saída e não toca no cliente. Você vê o que
saiu — as tabelas, o pacote, o nome — e só então autoriza.

**Instalar no cliente** copia para dentro. O que for sobrescrito vai antes para
`system/backup_npc`.

Quem instala por engano num cliente que usa para jogar descobre o problema na
hora de entrar no jogo, que é tarde.


## NPCs criados neste cliente

O botão abre a lista do que este programa já pôs neste cliente, com a opção de
remover. Remover tira a linha do `npcgrp.dat`, o nome do `npcname-e.dat` e o
pacote `FX_<id>.u` — tudo com cópia antes.

Do lado do servidor ainda fica o XML daquele NPC, que precisa ser apagado à mão
e seguido de `//reload npc`. A janela diz isso na hora.
