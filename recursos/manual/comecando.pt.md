# Começando

Este programa mexe em duas coisas separadas, e quase todo problema de quem
começa vem de confundir as duas.

**O cliente** é o que o jogador tem na máquina dele. Ele sabe **desenhar**:
malha, textura, ícone, som, nome que aparece na tela. São arquivos `.dat`,
`.u`, `.utx`, `.ukx` dentro da pasta do jogo.

**O servidor** é o emulador. Ele sabe **o que a coisa é**: quanta vida um mob
tem, o que ele larga ao morrer, quanto um item custa, o que uma habilidade
faz. São XML e tabelas de banco, e nada disso existe no cliente.

Um item que só existe no servidor aparece em jogo sem nome e sem desenho. Um
item que só existe no cliente nunca chega à mão de ninguém. As duas metades
precisam bater, e é isso que as abas deste programa fazem.


## O primeiro passo é o projeto

Antes de qualquer coisa, abra **Projetos…** no cabeçalho e crie um: um nome,
a pasta do cliente e a pasta do servidor.

Escolher o projeto aponta as duas pastas em **todas as abas de uma vez**.
Quem mexe em mais de um servidor troca de projeto no cabeçalho em vez de
acertar dezoito campos.

Sem projeto, o botão `Carregar` de cada aba diz o que falta e onde resolver —
ele não fica cinza sem explicar.


## O segundo passo é carregar

Cada aba tem **um** botão `Carregar`. Ele traz tudo o que aquela aba usa: as
tabelas do cliente, os dados do servidor, ou os dois.

A primeira leitura das tabelas do cliente demora — são quase dez mil itens e
três mil habilidades. Depois disso fica guardada, e as abas dividem o mesmo
catálogo entre si: o que a aba de Itens leu serve ao drop do mob e à lista da
multisell.


## O mapa das abas

| aba | mexe em | lado |
| --- | --- | --- |
| Texture Upscaler | textura de pacote `.utx` | cliente |
| NPC | criar NPC: malha, nome, efeito | cliente |
| NPC — lado do servidor | status, drop, spawn, loja daquele NPC | servidor |
| Lobby Vídeo | o vídeo da tela de login | cliente |
| Itens | criar e editar item | os dois |
| Habilidades | criar e editar habilidade | os dois |
| Glow | o brilho da arma e o encantamento | cliente |
| Multisell | a lista de trocas de um NPC | servidor |
| Mob | status, skills e drop de mob que já existe | servidor |
| Conferir Cliente | o que as tabelas pedem e não está instalado | cliente |
| L2Crypt | abrir e fechar arquivo do cliente | cliente |


## O que nunca acontece sozinho

- **Nada é instalado sem você mandar.** Gerar e instalar são dois botões
  diferentes, em toda aba. O que é gerado fica numa pasta de saída até você
  decidir.
- **O que é sobrescrito vira cópia antes.** Arquivo do cliente vai para
  `system/backup_*`; XML do servidor ganha uma cópia datada ao lado.
- **O que o programa não entende, ele não toca.** Editar o HP de um mob não
  reescreve o resto do arquivo, e blocos que este programa não conhece voltam
  byte a byte.


## Depois de instalar

Coisa de cliente pede o cliente fechado na hora de instalar, e aberto de novo
depois. Coisa de servidor pede um comando em jogo:

```
//reload npc          depois de mexer em mob ou NPC
//reload multisell    depois de mexer em multisell
```

O manual de cada aba diz qual é o comando dela.
