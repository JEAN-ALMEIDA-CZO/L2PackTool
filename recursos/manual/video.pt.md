# Lobby Vídeo: a tela de entrada do cliente

Aqui você troca a tela que aparece antes de escolher o personagem. Dá para
usar um dos lobbys prontos ou pôr um vídeo seu.


## Dois caminhos

**Instalar lobby** põe no cliente o lobby escolhido, do jeito que ele é —
mapa, cenário, texturas e a música dele. Os de C1 a C6 são os originais de
cada crônica.

**Gerar vídeo e instalar** monta o seu filme no lobby do L2PackTool. Esse é o
único que tem tela de vídeo; escolhendo outro na lista e clicando aqui, o
programa usa o do L2PackTool e avisa no registro.

Os lobbys viajam compactados dentro do programa. Só o escolhido é aberto, e
só na hora de instalar.


## O vídeo

Formatos: MP4, AVI, MKV, MOV, WEBM, GIF e WEBP animado. O vídeo entra inteiro
e centralizado.

O tamanho da tela é calculado para preencher a janela do jogo, de uma 4:3 a
uma ultralarga. Preencher custa as beiradas do filme: numa tela de notebook
você vê cerca de 70% da altura. Atrás fica um painel preto, para não aparecer
cenário no que sobrar.


## O trecho

As duas réguas marcam começo e fim; **Vídeo inteiro** devolve os dois aos
extremos.

O número de quadros sai da cadência do vídeo, e é o que mantém a velocidade
original. Cada quadro ocupa uns 2 MB no pacote; passando do limite, a cadência
cai sozinha — o filme fica mais picotado, mas o pacote carrega.

A prévia amostra o vídeo inteiro e a régua escolhe a fatia, então o ritmo que
você vê é o que vai ao jogo.

**Repetir sem parar** faz o filme voltar ao começo. Sem isso ele toca uma vez
e congela no último quadro.


## A logo

Uma imagem sua por cima do vídeo. Arraste com o mouse na prévia; onde ficar é
onde vai.


## Instalar

O cliente precisa estar fechado — o jogo segura os arquivos do lobby enquanto
roda. O que for sobrescrito vai antes para `backup_lobby`.

Gerar o vídeo demora: cada quadro é convertido e comprimido, e o pacote passa
de cem megabytes. A janela pode parecer parada; acompanhe pela barra.

Depois de instalar, o programa confere se o cliente tem tudo o que o mapa do
lobby procura, e diz o que faltar.


## Por que não é uma textura animada

A primeira versão desta aba animava uma textura com a corrente `AnimNext`, que
é como o cliente anima fogo e água. Passava em tudo o que dá para conferir de
fora, e na tela não acontecia nada.

O filme é um `MaterialSequence`: o material feito para tocar uma lista no
tempo, numa malha plana na frente da câmera. É o que esta aba gera.
