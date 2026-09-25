# Os textos do cliente: mensagem, interface e fala de NPC

Tudo o que o jogo escreve na tela e não é nome de item nem de habilidade mora em
três tabelas do `system`:

| Arquivo | O que guarda | Exemplo |
| --- | --- | --- |
| `systemmsg-e.dat` | mensagem do sistema | `You have been disconnected from the server.` |
| `sysstring-e.dat` | texto da interface | `Equipment`, `Quest Item` |
| `npcstring-e.dat` | fala de NPC com variável dentro | `Hello! I am $s1.` |

São **11.499 textos** num cliente do High Five, **3.764** num do C5. O
`npcstring-e` só existe da Freya em diante; onde ele não existe, a tela diz isso
e trabalha com os outros dois.

Quem monta servidor mexe nisso por dois motivos: **traduzir** e **trocar o que o
jogo diz pelo que o servidor dele diz** — o nome do servidor na mensagem de
entrada, a explicação de um sistema próprio, o aviso de um evento.


## A busca é o centro da tela

Onze mil linhas não se percorrem rolando. Escreva na busca o texto **como ele
aparece no jogo** — "disconnected", "Equipment", "Welcome" — e a lista se fecha
em torno dele. O campo também aceita o id, quando você já o conhece.

Duas ajudas ao lado:

- **tabela** — limita a uma das três;
- **só as que têm $s1** — mostra apenas as frases com marca, que são as que o
  servidor preenche.


## A marca vale mais que o texto

`$s1`, `$s2`, `$c1` são os **buracos onde o servidor encaixa** número, nome de
jogador ou item:

```
The server will be coming down in $s1 second(s).
```

O servidor manda o `60`; o cliente escreve `60` no lugar do `$s1`. São 1.135
frases com marca no High Five.

Reescrever a frase **sem a marca** não dá erro em lugar nenhum: ela continua
aparecendo, só chega sem o dado que anunciava — "O servidor vai cair em
segundo(s)". Por isso a tela conta as marcas antes e depois, e pergunta quando
alguma se perde. Se for de propósito, confirme; se não, o texto volta como
estava.

Quando você marca uma frase, o rótulo em cima do campo diz quantas marcas ela
tem e quais são.


## A segunda linha

Só a **mensagem de sistema** tem uma segunda linha (`sub_msg`) — o que o jogo
escreve embaixo da principal. Nas outras duas o campo fica apagado, em vez de
aceitar um texto que não iria para lugar nenhum.

O resto de cada linha — cor, som, grupo — **não é mexido**. Uma mensagem com a
cor trocada continua funcionando; uma mensagem sem a marca, não. A tela cuida do
que importa e deixa o resto exatamente como estava.


## O caminho: aplicar, gerar, instalar

Três passos, e eles são separados de propósito:

1. **Aplicar** guarda o texto novo na memória. Nada foi escrito ainda.
2. **Gerar as tabelas** escreve os `.dat` numa pasta à parte (`textos_gerados`).
   Dá para abrir o resultado e olhar antes de o cliente depender dele.
3. **Instalar no cliente** copia para o `system`. Na primeira vez os originais
   são guardados em `system/backup_textos`, e **Restaurar originais** os traz de
   volta de lá.

Feche o cliente antes de instalar — o Windows não deixa escrever num arquivo que
o jogo está lendo.


## A prova, antes de gravar

Ao carregar, cada tabela é aberta, **remontada** e comparada byte a byte com o
binário original. Se a volta não reproduz a ida, a definição não descreve este
cliente: a tabela pode ser lida, e gravar nela fica bloqueado.

As três tabelas voltam idênticas em onze clientes, de C3 a High Five. O Interlude
entrou sem essa prova — não há cliente dele aqui para medir — e o programa não
diz o contrário.


## O que isto não faz

- **Não traduz nada sozinho.** O texto novo é o que você escrever.
- **Não mexe em nome de item nem de habilidade.** Esses estão no `itemname-e` e
  no `skillname-e`, nas abas de Itens e Habilidades.
- **Não cria texto novo.** Os ids são os que o cliente conhece; um id inventado
  seria um texto que o servidor nunca pede.
