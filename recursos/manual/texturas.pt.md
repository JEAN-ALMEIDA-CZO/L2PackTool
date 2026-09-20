# Texture Upscaler: ampliar a textura de um pacote

Esta aba pega um pacote de textura do cliente, amplia cada imagem com uma rede
neural e remonta o pacote. O caminho completo é este:

```
.utx criptografado
  -> descriptografa
  -> extrai as texturas
  -> converte para PNG
  -> amplia (upscayl)
  -> comprime em DXT5 com mipmaps
  -> remonta o pacote
  -> criptografa de volta
```

Cada passo é uma ferramenta separada, e todas ficam em `ferramentas/`. Faltando
uma delas, a aba diz qual é na hora de processar.


## Abrindo um pacote

**Abrir um .utx…** escolhe um arquivo. **Lote: escolher pasta…** processa
todos os `.utx` de uma pasta de uma vez.

Aberto o pacote, a lista mostra cada textura com o tamanho dela. Clicando numa,
a prévia aparece à direita, com os botões de trocar a imagem, melhorar só
aquela ou exportar.


## A escala é a decisão que importa

> **O cliente do Lineage 2 é de 32 bits.** Escala 2x **quadruplica** a memória
> de textura; 4x multiplica por dezesseis.
>
> Não é uma questão de disco: é a memória que o processo do jogo consegue
> endereçar. Passando disso, o cliente fecha sozinho — e fecha ao entrar numa
> área específica, não ao carregar o pacote, o que torna a causa difícil de
> ligar ao efeito.

Na prática: marque **o que o jogador vê de perto** — arma, armadura, rosto — e
deixe cenário e coisa distante como está. Um pacote inteiro em 4x é a receita
mais comum de cliente que fecha.


## O modelo

`upscayl-standard-4x` é o padrão e o melhor ponto de partida. Os outros servem
a materiais diferentes: uns preservam superfície lisa, outros amaciam pedra e
tecido. A descrição de cada um aparece ao escolher.

A escala do modelo e a escala pedida são coisas distintas — um modelo `4x`
usado em escala `2x` amplia e reduz de volta, o que costuma dar resultado
melhor do que ampliar direto em 2x.


## Processar

**Marcar todas** / **Desmarcar todas** e depois **Processar**. O andamento
mostra em que textura está e quanto falta.

Só as texturas marcadas são ampliadas. As outras entram no pacote remontado
como estavam — nada se perde por não ter sido marcado.

O resultado sai numa pasta de trabalho. O pacote do cliente não é tocado até
você instalar.


## O que sai diferente do que entrou

O pacote remontado não é byte a byte igual ao original, mesmo nas texturas que
você não marcou: ele é reconstruído do zero pelo `ucc`. Isso é normal, e é o
motivo de o original ficar guardado.

Textura com transparência mantém o canal alfa. Textura já em DXT é
descomprimida, ampliada e comprimida de novo — e recompressão sempre custa um
pouco de qualidade, o que é mais um argumento para marcar só o que importa.
