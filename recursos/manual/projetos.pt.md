# Projetos: as duas pastas num lugar só

Um projeto guarda três coisas: um nome, a **pasta do cliente** e a **pasta do
servidor**. Escolher o projeto no cabeçalho aponta as duas em todas as abas.


## Por que isto existe

Cada aba pedia as duas pastas de novo. Eram dezoito campos para o mesmo
caminho, e bastava um ficar para trás — depois de mexer numa cópia do cliente,
por exemplo — para uma tela gravar no lugar errado sem avisar.

Quem mexe em dois servidores ao mesmo tempo trocava dezoito campos a cada
troca. Agora troca um.


## Criando

**Projetos…**, no cabeçalho, abre a janela. À esquerda os projetos que
existem; à direita o nome e as duas pastas.

- **pasta do cliente** — a raiz do jogo, aquela que tem `system` dentro. Pode
  apontar a `system` direto: o programa acha a raiz a partir dela.
- **pasta do servidor** — a pasta de dados do emulador, aquela com `xml` ou
  `data/xml` dentro.

**Guardar** grava e já escolhe o projeto. **Novo** limpa os campos para criar
outro. **Apagar** tira o projeto da lista — as pastas não são tocadas, só o
atalho para elas.

O nome aceita letras, números e espaço. `[` e `]` não servem, porque o arquivo
de projetos é um `.ini` e eles quebrariam a seção.


## Trocando

O seletor aparece em dois lugares: no cabeçalho e no alto de cada aba. São o
mesmo controle — mexer num muda o outro na hora, e as abas recebem os
caminhos novos sem precisar recarregar nada.

Ao lado dele ficam as duas pastas escritas por extenso. É a resposta para "em
que servidor eu estou mexendo", e ela precisa estar à vista de quem vai gravar
alguma coisa.


## Quando falta pasta

O `Carregar` de cada aba confere antes de trabalhar, e diz o que falta:

```
Nenhum projeto escolhido. Crie um em Projetos… com a pasta do
cliente e a do servidor.

A pasta do cliente do projeto Interlude não existe mais: D:\cliente-antigo
```

A pasta é conferida **no disco**, e não só no arquivo de projetos. O caso
comum é o cliente ter sido movido ou renomeado: sem essa conferência o erro
apareceria lá dentro, falando de outra coisa.


## Onde isto fica guardado

Num `projetos.ini` ao lado do programa. Ele é texto, e dá para copiar entre
máquinas.

Quem já usava o programa antes dos projetos não perde nada: na primeira
execução, as pastas que estavam na configuração antiga viram um projeto
chamado `Padrão`.


## O que o projeto não faz

Ele aponta pastas. Não copia, não move e não instala nada. Trocar de projeto
não mexe em arquivo nenhum — só muda para onde as abas estão olhando.
