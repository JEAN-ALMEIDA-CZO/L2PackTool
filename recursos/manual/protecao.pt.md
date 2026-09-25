# Proteção: fechar o cliente com a sua chave

Todo cliente de Lineage II guarda as suas tabelas fechadas, e a "senha" que
abre é a mesma em todos eles — está nas ferramentas públicas há vinte anos.
Por isso qualquer pessoa abre o `itemname` de qualquer servidor com dois
cliques.

Esta tela troca essa senha pela **sua**: uma chave gerada a partir de uma
frase que só você sabe, escrita dentro do seu cliente. Depois disso, ninguém
produz um arquivo que o seu cliente aceite sem ter a frase.


## O que ela protege, e o que não protege

**Protege a escrita.** Sem a sua frase, ninguém gera um `itemname-e.dat` que o
seu cliente vá carregar. Quem tentar trocar uma tabela do seu servidor precisa
da frase — ou de refazer o cliente inteiro.

**Não protege a leitura**, e nenhum programa protegeria. Para jogar, o cliente
precisa abrir os arquivos: ele carrega dentro de si o que é preciso para
abri-los. Quem tem o seu cliente pode chegar lá — este mesmo programa chega em
milissegundos.

O que muda é o custo. O seu servidor sai do *"qualquer um abre com um clique
em ferramenta pública"* e passa para o *"quem souber procurar"*. É um degrau
real, e é o único degrau que existe deste lado.


## A frase

O botão **Gerar chave** sorteia uma frase forte — trinta caracteres em grupos
de cinco, sem os que se confundem ao ler (nada de `O` e `0`, `I` e `l`). Frase
inventada na hora costuma ser o nome do servidor mais o ano, e essa qualquer
um adivinha.

A mesma frase dá sempre a mesma chave, em qualquer máquina. **Ela não é
guardada em lugar nenhum**: nem no programa, nem na configuração, nem no
cliente. Perdeu a frase, perdeu a capacidade de gerar arquivos novos para
aquele cliente — o que já está instalado continua funcionando, e o backup
também.

**Salvar…** guarda a frase num arquivo de texto, com a marca da chave e a
data. Guardar **dentro da pasta do cliente é recusado**: dali o arquivo iria
junto com o cliente para os jogadores.

A *marca* são oito dígitos do começo e do fim da chave. Serve para conferir
que você está usando a chave certa sem precisar mostrar a frase.


## O que dá para proteger

| jeito | o que pega |
| --- | --- |
| **grupos** | itens e armas, habilidades, NPCs, mundo e textos |
| **Escolher…** | arquivo a arquivo, inclusive tabela que não está em grupo nenhum |
| **Todos os .dat** | todas as tabelas de uma vez |

O que o botão protege é a **união** dos grupos com a lista. Arquivo de fora da
pasta do cliente é deixado de fora: a chave gravada no executável é a daquele
cliente, e um arquivo de fora fechado com ela não seria lido por cliente
nenhum.


## Converter os pacotes

As tabelas (`.dat`) já vêm num formato que aceita chave. Os pacotes — `.utx`,
`.u`, `.int` — usam um formato **sem chave**: a senha deles é fixa, ou sai do
próprio nome do arquivo. Neles não há chave a trocar.

Marcando **converter**, eles são convertidos para o formato que aceita chave.
O cliente escolhe o decifrador pelo cabeçalho do arquivo, e não pela extensão
— no seu próprio cliente o mesmo `.ini` aparece em dois formatos lado a lado.

Essa opção vem **desligada**, e o motivo é honesto: nenhum cliente original
traz `.utx` nesse formato, então essa parte não tem como ser provada aqui.
**Converta um arquivo, abra o jogo, confira, e só então converta o resto.**


## `.dll` e `.exe` não entram

Quem carrega um `.dll` é o Windows, e não o cliente. O cadeado deste programa
é lido pelo cliente, que decifra antes de usar; o Windows não sabe nada disso.
`Engine.dll` cifrado não carrega, e o jogo nem abre. Por isso esses arquivos
são **recusados**, com o motivo — não aceitos com um aviso.

Para eles há a **impressão digital**: o programa anota o resumo de cada
`.dll` e `.exe` do cliente num arquivo, fora do cliente, e depois compara.
Não impede a troca, mas responde em segundos à pergunta que importa quando
algo estranho acontece no servidor: *trocaram alguma coisa?* A conferência diz
o que mudou, o que sumiu e o que apareceu.


## A ordem do trabalho, e por que ela é essa

1. o original é copiado para `backup_protecao`;
2. o arquivo é aberto com a chave atual;
3. é fechado com a chave nova;
4. é **aberto de novo e comparado** com o passo 2;
5. só então substitui o original.

A chave do executável é trocada **por último**, e só se todos os arquivos
passarem. Na ordem contrária, um erro no meio deixaria o cliente inteiro sem
abrir nada; nesta, o pior caso é um arquivo não trocado.

Arquivo que não volta idêntico não é instalado, e o motivo aparece no
andamento.

**Voltar ao original** desfaz tudo, inclusive a chave do executável.


## Onde funciona

Parte dos clientes guarda a chave dentro do executável, e ali ela é trocável.
Nos mais novos ela chega por *loader*, em memória, e trocá-la exigiria um
loader próprio — que este programa não escreve. A tela diz em qual caso o seu
cliente está **antes** de você escolher arquivos.


## Antes de mexer no que está no ar

Faça numa cópia do cliente primeiro. Proteja um arquivo, abra o jogo, confira,
e só então trate o cliente que os jogadores usam. `Voltar ao original` existe
justamente porque a primeira tentativa costuma ensinar alguma coisa.
