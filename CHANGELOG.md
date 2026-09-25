# Mudanças

O que cada versão trouxe, e por quê. As datas são de lançamento.

O programa segue [versionamento semântico](https://semver.org/lang/pt-BR/):
número do meio sobe quando entra funcionalidade, último quando é só conserto.
Nenhuma versão até aqui quebrou compatibilidade — projeto gravado na 1.0
continua abrindo.

---

## 1.5.1 — 24/09/2026

**Gerar a chave pelo programa.** Botão *Gerar chave* na aba Proteção: sorteia
uma frase forte em grupos de cinco, sem caracteres que se confundam ao ler, e
deixa-a à vista. Frase inventada na hora costuma ser o nome do servidor mais o
ano — e essa qualquer um adivinha.

**Guardar a chave.** *Salvar…* escreve a frase num arquivo de texto com a
marca da chave e a data. Salvar **dentro da pasta do cliente é recusado**: dali
o arquivo iria junto com o cliente para os jogadores, e a proteção junto com
ele.

---

## 1.5.0 — 24/09/2026

**Proteção (anticheat).** Aba nova: fecha as tabelas escolhidas do cliente com
uma chave gerada a partir de uma frase sua. Sem a frase, ninguém gera arquivo
que o seu cliente aceite. A frase não é guardada em lugar nenhum.

Cada arquivo é copiado antes, refeito e conferido — só entra no cliente se
voltar idêntico —, e a chave do executável é trocada por último. *Voltar ao
original* desfaz tudo. A tela diz o que a proteção faz e o que não faz, e
avisa quando o cliente não aceita chave própria.

**Abrir sem depender de ferramenta de fora.** Quando o l2encdec não está
instalado, é barrado pelo antivírus ou não dá conta, o programa passa a abrir
sozinho os formatos que sabe — antes o arquivo simplesmente não abria.

---

## 1.4.0 — 24/09/2026

**Gracia.** Três crônicas novas, e cada uma provada contra um cliente de
verdade pela ida e volta byte a byte:

| núcleo | armas | itens | habilidades | NPCs |
| --- | ---: | ---: | ---: | ---: |
| CT2.1 — Gracia Part 1 | 2.837 | 13.007 | 48.778 | 8.437 |
| CT2.2 — Gracia Part 2 | 2.938 | 13.494 | 49.270 | 8.625 |
| CT2.3 — Gracia Final | 3.371 | 15.643 | 58.602 | 9.355 |

**O `transformdata` entrou na detecção.** Part 1 e Part 2 têm definição
*idêntica* nas três tabelas que a detecção media — um cliente de Part 2 sairia
como Part 1, com confiança "certa", que é o pior tipo de erro. Só o
`transformdata` separa os dois, e a separação foi medida nas duas direções. De
quebra, tabela que o cliente não tem deixou de contar contra a crônica.

**O tipo da habilidade estava errado em todas as crônicas.** A coluna
`oper_type` tem duas escalas, e o programa usava uma terceira:

- C3 a Kamael — Dash, Majesty e Shield Stun apareciam como *passiva*, e as
  masteries como *alternável*. No C3: 439/407/422 antes, **846 ativas, 422
  passivas, 14 alternáveis** agora.
- Hellbound em diante — mais da metade não aparecia com tipo nenhum. No
  Gracia: 2.778 em branco antes, **zero** agora.

Qual escala vale se decide olhando a tabela, e não pelo nome da crônica.

**Projeto sem servidor lia o servidor do vizinho.** Ao trocar de projeto, o
campo da pasta só era reescrito quando o projeto novo tinha uma: sem ela,
ficava o caminho do anterior, e a aba lia o XML de outro projeto com o
cabeçalho dizendo `servidor: —`. Agora o projeto manda inclusive quando diz
"não tenho".

Menores: lista de crônicas em ordem de lançamento; lobby podendo declarar mais
de uma crônica (a tela do Gracia serve Part 1 e Part 2); cartão de lobby
ilegível deixando de fazer o lobby sumir da lista.

---

## 1.3.0 — 24/09/2026

**Arte por IA.** Onde o programa aceita uma imagem sua, aceita também gerar
uma. Provedor (Gemini ou Claude), chave e **modelo escrito à mão** ficam em
*Configurações* — nome de modelo é aposentado, e o que está preso no código
morre com ele.

- o pedido tem prompt fixo de ícone de Lineage II moderno, mais as suas
  observações e o tamanho que a arte vai ter no jogo;
- **imagem de referência** deixa de ser inspiração: o pedido manda o modelo
  ler a imagem, preservar objeto, silhueta, paleta e ângulo, e aplicar só o
  que foi pedido;
- **fundo** à escolha: transparente, preto, branco ou uma cor sua, sem gastar
  outra geração;
- prévia no tamanho real do cliente (32 ou 64), ampliada sem suavizar;
- erro da API vira frase com o que fazer — modelo que só devolve texto, chave
  inválida, modelo aposentado, cota estourada.

**Animação que o jogo toca.** Doze movimentos em ciclo fechado, e duas formas
de pôr no cliente, porque são camadas diferentes do jogo:

- **a corrente do motor** (`AnimNext`): a textura escolhida passa a percorrer
  quadros novos e o Unreal toca sozinho. Medido num `Icon.utx` oficial: 4.662
  texturas, nenhuma com o desenho alterado;
- **a família numerada** (`ToggleEffect001..013`): troca o desenho de uma
  animação que o cliente já toca.

GIF seu também serve: os quadros do arquivo *são* a animação, reamostrados
para a contagem que o destino pede. (A IA não gera GIF — essas APIs devolvem
um quadro.)

**Correções que vieram junto:** pacote Ver111 sem *tail* que o l2encdec
cortava (20 bytes a menos, e o arquivo não abria); mipmaps não reconhecidos em
pacote oficial; nome de arquivo que faz parte da chave; o botão *IA…* da aba
de itens, que nunca tinha funcionado.

---

## 1.2.0 — 23/09/2026

**Oito crônicas.** C1, C2, C3, C4, C5, Interlude, Kamael e Hellbound. Cada uma
é um núcleo: as definições das tabelas e um manifesto dizendo o que foi
provado. Até o C2 as tabelas do cliente são texto, e de C3 em diante binário —
o programa lê e grava os dois, e as abas não precisam saber qual é.

**Ele descobre a crônica sozinho.** Ao apontar a pasta do cliente, mede
tabelas contra cada definição instalada e escolhe a que reproduz o arquivo. Se
a crônica do projeto estiver errada, o erro diz qual é a certa, em vez de
falar em `field 13 / 57`.

**Gravar em cliente oficial.** Cliente recém-baixado vem fechado com as chaves
da NCSoft, que o programa lê mas não sabe gravar. Antes de instalar, ele
converte a `system` inteira — cada arquivo é reaberto e comparado byte a byte,
e o original só é trocado se bater. Põe o `loader` da crônica ao lado do
executável e oferece o `patcher` uma vez, com cópia do `l2.exe` antes.

**Ícones do C3.** O ícone mora em `icon[4]` nessa crônica: olhando só a
primeira coluna, 6.218 dos 6.391 itens pareciam não ter ícone.

---

## 1.1.0 — 22/09/2026

A interface encontra o seu lugar: um botão dourado por página, a barra de
projeto no cabeçalho em vez de repetida em cada aba, o painel do servidor
seguindo o projeto, a descrição do item vinda do arquivo do cliente e
aparecendo nas listas das outras páginas, a arte do instalador saindo da marca
e da paleta do programa. Excluir a arma passou a tirá-la do cliente, e não só
da memória.

---

## 1.0.0

Primeira versão pública: NPC com efeito, itens, habilidades, glow, multisell,
mob, lobby com vídeo, ampliação de textura por IA, abrir e fechar arquivos do
cliente e conferir o cliente. Interlude.
