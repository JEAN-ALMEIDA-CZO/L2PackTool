# Conferir Cliente: o que as tabelas pedem e não está lá

O cliente não avisa quando falta alguma coisa. Falta a textura, ele desenha o
boneco branco e segue. Falta o pacote inteiro, ele mostra o item sem modelo e
não escreve nada em lugar nenhum.

Esta tela responde três perguntas, nesta ordem — que é a ordem em que elas
aparecem para quem monta um cliente:

1. **o que falta?** — a conferência, que só lê
2. **onde eu acho isso?** — a procura numa pasta com outros clientes
3. **instala pra mim** — a cópia para dentro do cliente


## A conferência

`Carregar` lê as tabelas do cliente, junta toda referência a pacote que elas
fazem — malha, textura, ícone, som — e confere uma por uma contra o que está
nas pastas.

O resumo sai em cartões, para ser lido de longe antes de qualquer lista. Só
depois vem o relatório, separado por situação:

| situação | o que significa |
| --- | --- |
| **pacotes que faltam** | o cliente pede o arquivo e ele não está em pasta nenhuma |
| **objetos que faltam** | o arquivo está lá, mas não tem dentro o que a tabela pede |
| **presentes, conteúdo não aberto** | pacote `Lineage2Ver111`, que só abre por inteiro — a conferência confirma que o arquivo existe e para por aí |

O relatório sai **completo**, sem abreviar. Se um pacote é pedido por 86
referências, as 86 aparecem — ele existe para ser conferido, e meia lista não
confere nada.


## Ler o relatório

Cada bloco de pacote ausente traz o nome, quantas referências o pedem, e de
qual tabela vem o pedido:

```
ArmorSet_Custom                   86 referencias   (armorgrp.dat)
    ArmorSet_Custom.Drop_Custom_CAP_b_m00
    ArmorSet_Custom.FD_Custom_CAP_b_m00
    ...
```

A tabela entre parênteses diz onde procurar a origem. `armorgrp.dat` é
armadura; `weapongrp.dat`, arma; `npcgrp.dat`, NPC.

**Um pacote ausente com muitas referências** costuma ser um pack que foi
instalado pela metade — as tabelas vieram, os arquivos não.

**Um objeto ausente dentro de pacote presente** é mais estreito: alguém trocou
o pacote por uma versão que não tem aquele objeto, ou a tabela aponta para um
nome escrito errado.


## Procurar e instalar

Apontando uma pasta com outros clientes, a tela procura nela os arquivos que
faltam e mostra o que achou. Daí dá para copiar para dentro do cliente.

A cópia é sempre **para dentro**: o cliente de origem não é tocado.


## O que a conferência não faz

Ela não abre pacote `Ver111` para olhar o conteúdo. Aqueles só abrem por
inteiro, e fazê-lo para cada referência custaria minutos por arquivo. Por isso
existe a categoria "presentes, conteúdo não aberto": ali a conferência
confirma que o arquivo existe e para.

Ela também não confere o servidor. Para cruzar cliente e servidor — item que
existe de um lado e não do outro — o caminho é o `Carregar` desta aba com o
projeto apontando os dois.
