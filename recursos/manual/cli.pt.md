# Linha de comando: fazer em lote o que a tela faz um a um

O `L2PackTool-cli.exe` é o mesmo motor do programa, sem a interface. Ele existe
para o que se repete: abrir cem arquivos do cliente, ampliar a textura de uma
pasta inteira, conferir um cliente dentro de um script.

Sem argumento nenhum, ele lista o que sabe fazer:

```
L2PackTool-cli
```


## Os comandos

| comando | o que faz |
| --- | --- |
| `upscale` | amplia as texturas de um `.utx` e remonta o pacote |
| `abrir` | descriptografa arquivo do cliente — `.dat`, `.utx`, `.u`, `.unr`, `.ini` |
| `fechar` | criptografa de volta, com o nome que o jogo espera |
| `extrair` | tira as texturas de um pacote, como imagens |
| `listar` | mostra a versão e os objetos de um pacote |
| `conferir` | confere o cliente e diz que arquivo falta |
| `lobby` | põe o vídeo na tela de login de um lobby, com câmera fixa |
| `ferramentas` | diz quais ferramentas foram encontradas, e onde |
| `ajuda` | a lista; `ajuda <comando>` detalha um deles |

`<comando> -h` mostra as opções daquele comando. Todo comando aceita **um
arquivo ou uma pasta**: apontando a pasta, ele trabalha em tudo que houver
dentro, em ordem de nome.


## Abrir e fechar

```
L2PackTool-cli abrir "C:\Lineage II\system\itemname-e.dat" -o .\aberto
L2PackTool-cli fechar .\aberto\itemname-e.dat -o .\fechado
```

O original **nunca é tocado**: o que sai é cópia nova, na pasta de `-o`.

Ao abrir, o método vem do cabeçalho do próprio arquivo. Ao fechar, ele vem da
**extensão** — um arquivo aberto não guarda em lugar nenhum o que era. `--versao`
força outro método, quando você sabe mais que a extensão.

> **O nome do arquivo de saída importa.** Na versão 121 a chave deriva dele: o
> mesmo conteúdo salvo com dois nomes gera dois arquivos diferentes. Para
> devolver ao cliente, mantenha o nome que tinha.

Todo arquivo fechado é conferido pela ida e volta: ele é aberto de novo e
comparado com o que entrou. Não batendo, sai `[a ida e volta não confere]` ao
lado do nome.


## Upscale

```
L2PackTool-cli upscale Fantasy.utx -s 2
L2PackTool-cli upscale C:\texturas -s 2 -o C:\saida
```

| opção | o que é |
| --- | --- |
| `-s` | a escala: 2, 3 ou 4 |
| `-n` | o modelo do upscayl |
| `-o` | onde gravar os `.utx` finais |
| `-t` | a pasta de trabalho |
| `--parar-em` | interrompe após `descriptografar`, `extrair` ou `comprimir` |

> **Escala 2x quadruplica a memória de textura; 4x multiplica por dezesseis.**
> O cliente é de 32 bits, e passando disso ele fecha sozinho — ao entrar numa
> área, não ao carregar o pacote. A página do Texture Upscaler explica o que
> vale marcar.

Quem já chamava pelo caminho direto continua chamando:

```
L2PackTool-cli C:\texturas -s 2
```

Sem um comando conhecido na frente, o pedido é de upscale, como sempre foi.


## Listar e extrair

```
L2PackTool-cli listar Fantasy.utx
L2PackTool-cli extrair Fantasy.utx -o .\texturas
```

`listar` lê o pacote **mesmo fechado**: a versão 121 é decifrada na memória. A
111 só abre por inteiro, e essa pede `abrir` antes.

`extrair` grava as imagens numa subpasta com o nome do pacote.


## Conferir

```
L2PackTool-cli conferir "C:\Lineage II" -o relatorio.txt
```

O mesmo relatório da aba Conferir Cliente, completo. Sem `-o`, ele sai na tela.

**O código de saída serve a script:** `0` quando não há problema, `1` quando
falta alguma coisa. Dá para encadear:

```
L2PackTool-cli conferir "C:\Lineage II" -o faltando.txt || notepad faltando.txt
```


## Quando falta ferramenta

```
L2PackTool-cli ferramentas
```

Lista cada ferramenta e o caminho em que ela foi achada, ou `NÃO ENCONTRADA`. A
busca é por nome dentro de `ferramentas/`, ao lado do programa — por isso a
pasta funciona ao ser copiada para qualquer lugar.

Cada comando cobra só o que usa: `abrir` e `fechar` precisam do `l2encdec`,
`extrair` do `umodel`, e `upscale` precisa de todas.


## O que a linha de comando não faz

Editar mob, multisell, item e skill, e criar NPC. São trabalhos de escolher na
tela e ver o efeito antes de gravar — em parâmetro de comando virariam uma
lista longa sem conferência possível.


## O lobby

```
L2PackTool-cli lobby "C:\Lineage II" -p L2PackTool
```

Monta a tela de login no mapa do lobby: câmera fixa no ponto, tela do tamanho
certo e painel preto atrás. O original do mapa é guardado na primeira vez e
serve de ponto de partida nas seguintes — instalar duas vezes não deixa duas
telas.

| opção | o que faz |
| --- | --- |
| `-p` | nome do pacote de vídeo instalado, sem `.usx` |
| `--formato` | a janela mais alta a cobrir, largura ÷ altura (padrão 1,25) |
| `--escala` | a escala da tela à mão, em vez da calculada |
| `--camera` | `x,y,z` ou `x,y,z,giro` — muda o ponto da câmera |

A saída diz o que cobre, tela por tela.
