# L2Crypt: abrir e fechar arquivo do cliente

Quase tudo no cliente do Lineage 2 é criptografado: `.dat`, `.utx`, `.u`,
`.unr`, `.ini`. Nenhum editor comum abre isso. O programa já precisava
decifrar para fazer o resto do trabalho — esta aba põe essa capacidade na sua
mão, nos dois sentidos.


## O original nunca é tocado

O que entra é **lido**. O que sai é **cópia nova, em outra pasta**. Não há
caminho em que esta aba escreva por cima do arquivo que você escolheu.


## Descriptografar

Escolha o arquivo e a pasta de saída. O método é reconhecido pelo cabeçalho do
próprio arquivo, que diz a versão:

| cabeçalho | como abre |
| --- | --- |
| `Lineage2Ver111` | Blowfish |
| `Lineage2Ver120` | XOR pela posição do byte |
| `Lineage2Ver121` | XOR por chave tirada do nome do arquivo |
| `Lineage2Ver411` a `414` | RSA, em blocos, com o conteúdo comprimido |

Arquivo já aberto — sem esse cabeçalho — é copiado como está.


## Criptografar

Aqui há duas coisas que surpreendem, e as duas têm o mesmo motivo: **um
arquivo aberto não guarda em lugar nenhum como ele era**.

> **O método sai da extensão**, e não do que estava no arquivo. Um `.utx`
> aberto à mão não registra em parte alguma que era `Ver121`; quem decide é a
> extensão do nome que você deu.
>
> **O nome do arquivo de saída importa.** A chave do `Ver121` deriva dele. O
> mesmo conteúdo salvo com dois nomes diferentes gera dois arquivos
> diferentes, e o jogo só lê o que tiver o nome que ele espera.

Na prática: para devolver um arquivo ao cliente, salve com **o mesmo nome** que
ele tinha.


## O que fazer com o arquivo aberto

Um `.dat` aberto continua sendo binário — ele não vira texto legível. Para
editar tabela do cliente existem as abas de Itens, Habilidades e NPC, que
entendem o formato de cada uma.

Esta aba serve para o que aquelas não cobrem: olhar um arquivo, comparar duas
versões, levar um `.ini` para outro editor, ou devolver ao cliente um arquivo
que você mexeu por fora.


## Quando dá errado

**"não é um pacote do cliente"** — o cabeçalho não bate com nenhuma versão
conhecida. Costuma ser pack com proteção própria: o arquivo é cifrado, mas com
um cabeçalho fora do padrão que nenhum leitor de fora reconhece.

**Abriu, mas o conteúdo veio embaralhado** — a decifragem rodou com a chave
errada. No `Ver121` isso acontece quando o arquivo foi renomeado em algum
momento, porque a chave vem do nome.
