# L2PackTool

Upscale automatizado de texturas `.utx` do Lineage 2, por linha de comando.
Escrito e validado contra um cliente **Interlude** real.

```
.utx criptografado
  → umodel -dump       lê o formato original de cada textura
  → l2encdec -l        descriptografa
  → umodel -export     extrai as texturas
  → Pillow             TGA → PNG
  → upscayl-bin        amplia (IA), preservando o canal alfa
  → texconv            comprime NO FORMATO DE CADA UMA, com mipmaps
  → ucc make           remonta o pacote
  → l2encdec -e 121    criptografa de volta
```

O programa tem duas abas: **Texturas**, que é o acima, e **NPC com efeito**,
que monta NPCs com partículas a partir do que o cliente já tem instalado.

---

> **A ampliação de texturas está em testes.** Ela depende de um programa de
> fora — o upscayl — e de modelos que mudam de versão para versão, então o
> resultado varia com a máquina e com o modelo escolhido. Comece por um pacote
> só e entre no jogo antes de ampliar o acervo inteiro. A aba avisa isso na
> própria página.

## Leia isto antes de rodar no acervo inteiro

**O cliente do Lineage 2 é de 32 bits.** Ele endereça pouco menos de 2 GB, e
textura ocupa memória proporcional à área. Upscale 2× multiplica por **4**;
4× multiplica por **16**.

No teste deste repositório, um pacote de 8 KB virou 57 KB com 2× — **sete
vezes maior**. Aplicado aos ~380 pacotes de um cliente Interlude, o acervo sai
de alguns GB para muito além do que o processo consegue mapear. O sintoma é o
cliente fechar sozinho ao entrar em certas áreas, e é difícil de diagnosticar
porque não acontece sempre.

**Recomendação:** rode só no que o jogador vê de perto — armaduras, armas,
rostos, interface. Terreno e cenário distante rendem pouco visualmente e são
justamente os pacotes maiores.

Outras ressalvas, todas verificadas na prática:

- **Faça backup do `system/` e do `Textures/` antes.** Nenhuma etapa aqui é
  reversível sem os originais.
- **Nunca renomeie um `.utx` durante o processo.** Na criptografia
  `Lineage2Ver121` a chave XOR deriva do *nome do arquivo*. Renomear não dá
  erro: produz um arquivo corrompido em silêncio. O script preserva o nome em
  todas as etapas justamente por isso.
- **Dimensões precisam continuar potência de dois.** Por isso só 2×, 3× e 4×
  são aceitos.
- **Teste um pacote pequeno primeiro** e entre no jogo antes de processar
  centenas. `--parar-em` existe para inspecionar cada etapa.

---

## Instalação

Há duas formas.

**Pelo instalador** (`L2PackTool-Setup-<versão>.exe`): instala em
`%LocalAppData%\Programs\L2PackTool`, sem pedir administrador, cria os atalhos
e aparece em Aplicativos Instalados para desinstalar. Essa versão já traz as
ferramentas de terceiros dentro dela — nada a baixar.

**Pelo executável solto**: a versão enxuta traz apenas o código deste projeto e
o Pillow. As demais ferramentas são de terceiros e **você precisa baixá-las** —
os links são oficiais e todas são gratuitas.

| Ferramenta | Para que serve | Onde obter |
|---|---|---|
| **UModel (UE Viewer)** | extrai as texturas do `.utx` | <https://www.gildor.org/en/projects/umodel> |
| **texconv** (DirectXTex) | comprime em DXT5 com mipmaps | <https://github.com/microsoft/DirectXTex/releases> |
| **Upscayl** | o upscale por IA | <https://upscayl.org> |
| **l2encdec** | descriptografa e criptografa | acompanha o **L2FileEdit** |
| **UCC** (L2Editor) | remonta o pacote | acompanha o **L2Editor** |

L2FileEdit e L2Editor circulam nas comunidades de servidor privado — RaGEZONE,
MaxCheaters, EmuDevs. Não são redistribuídos aqui: o UCC contém código da Epic
Games e da NCSoft, e o crédito não substitui a permissão de redistribuir.

### As ferramentas sao encontradas sozinhas

Basta colocar tudo dentro da pasta **`ferramentas/`**, ao lado do executavel.
O programa varre essa pasta recursivamente e reconhece cada ferramenta **pelo
nome do arquivo** — nao importa como voce nomeou as subpastas nem quantos
niveis elas tem. Atualizar uma ferramenta e so trocar a pasta dela.

```
L2PackTool/
├─ L2PackTool.exe
├─ ferramentas/
│  ├─ umodel/          umodel.exe
│  ├─ texconv/         texconv.exe
│  ├─ upscayl/         upscayl-bin.exe
│  ├─ upscayl-models/  *.param + *.bin
│  ├─ l2encdec/        l2encdec_old.exe
│  ├─ l2asm/           l2asm.exe + l2disasm.exe   (só a aba de NPC usa)
│  └─ L2Editor/        …/UCC.exe
└─ LEIA-ME.md
```

Repare no **`l2encdec_old.exe`**: circulam dois binários com esse nome, e o
menor dos dois falha em boa parte dos `.u` deste cliente — imprime
`L2FileEditFix mode [2]` e não grava nada. O programa procura o `_old`
primeiro justamente por isso. Se você apontar o outro no `config.ini`, a aba
de NPC não vai achar efeito nenhum.

A pasta inteira pode ser movida ou copiada para outra maquina sem
reconfigurar nada.

### Sobreposicao manual (opcional)

Se preferir apontar para instalacoes que voce ja tem, crie um `config.ini` ao
lado do executavel. Ele tem prioridade sobre a busca automatica:

```ini
[ferramentas]
l2encdec = C:\...\L2FileEdit\data\l2encdec\l2encdec_old.exe
umodel   = C:\...\umodel\umodel.exe
upscayl  = C:\Program Files\Upscayl\resources\bin\upscayl-bin.exe
modelos  = C:\Program Files\Upscayl\resources\models
texconv  = C:\...\texconv\texconv.exe
ucc      = C:\...\L2Editor-Compiled\L2Editor\UCC.exe
l2asm    = C:\...\L2FileEdit\data\l2asm-disasm\l2asm.exe
l2disasm = C:\...\L2FileEdit\data\l2asm-disasm\l2disasm.exe
```

A pasta do cliente fica guardada à parte, na seção `[cliente]`, e a aba de NPC
a preenche sozinha na primeira vez que você aponta a pasta `system`.

---

## Idioma

O programa fala **português do Brasil**, **inglês** e **espanhol**. Clique em
**⚙ Configurações**, no alto da janela, escolha e confirme: as abas se refazem
na hora, e a escolha fica gravada no `config.ini` para a próxima abertura.

    [interface]
    idioma = pt        ; pt, en ou es

Se houver trabalho em andamento — uma textura sendo processada, um NPC sendo
gerado, o jogo aberto em DevMode — a janela não é refeita no meio do caminho: a
escolha vale a partir da próxima abertura, e o programa avisa isso.

### As traduções são arquivos, não código

Ficam em `idiomas/`, ao lado do executável, um `.ini` por língua:

    idiomas/
      en.ini
      es.ini

Cada frase é uma seção numerada, com o original em português e a tradução:

    [0138]
    pt = Marcar todas
    t = Select all

Para corrigir uma frase mal traduzida, edite o `t =` e reabra o programa — não
é preciso recompilar nada. Três detalhes de quem edita:

- **não mexa na linha `pt`**: é ela que casa a tradução com a frase do
  programa;
- `\n` é quebra de linha e `\s` é um espaço no começo ou no fim da linha
  (o formato `.ini` descarta espaço solto nas pontas);
- `%s`, `%d` e afins são preenchidos pelo programa e **precisam aparecer na
  mesma ordem** da frase original. Trocar a ordem é a única alteração capaz de
  derrubar a janela; o resto, no pior caso, fica feio.

Frase sem tradução sai em português, nunca em branco. O programa procura
`idiomas/` primeiro ao lado do executável e depois dentro dele, então apagar a
pasta por engano não deixa a janela sem texto.

### Acrescentar um idioma

Quem mexe no código: `IDIOMAS`, no alto do `idioma.py`, lista os idiomas
oferecidos. Acrescente o par `("it", "Italiano")`, rode

    python atualizar_idiomas.py

e um `idiomas/it.ini` nasce com todas as frases e o `t =` vazio, pronto para
preencher. O mesmo comando serve depois de mexer em qualquer texto da
interface: ele põe os arquivos em dia sem perder o que já estava traduzido, e
avisa se alguma tradução perdeu um `%s` pelo caminho.

---

## Uso

### Interface grafica

Clique duas vezes em **`L2PackTool.exe`**.

1. **Abrir um .utx…** — mostra as miniaturas de todas as texturas do pacote,
   com caixa de selecao; marque so as que quiser ampliar. Ou
   **Lote: escolher pasta…**, que processa varios pacotes sem previa.
2. Ajuste a escala (2x recomendado) e o modelo
3. **Processar** — a barra mostra a textura atual, o percentual dela, o tempo
   decorrido e a previsao de termino
4. Ao terminar, ele **pergunta onde salvar** os pacotes prontos

O processamento roda numa thread separada, entao a janela continua respondendo
durante as horas que o Upscayl pode levar. Se voce cancelar a pergunta do
destino, os arquivos ficam em `_saida_provisoria/` e nao se perdem.

### O formato de cada textura é preservado

Uma textura volta para o pacote **no formato em que estava**. O programa lê
isso do próprio `.utx`, antes de mexer em qualquer coisa, e a linha de
andamento mostra o que encontrou:

```
  inventario: 277 texturas com formato conhecido
  formatos: DXT1 x145, DXT3 x23, DXT5 x90, RGBA8 x19
```

Versões anteriores comprimiam tudo em DXT5, o que errava de duas formas ao
mesmo tempo: uma textura opaca que era DXT1 **dobrava de tamanho** sem ganhar
nada — e num cliente de 32 bits esse é exatamente o custo que derruba o jogo —
e o pacote saía com um formato que não era o do original.

O canal alfa atravessa a ampliação intacto: o Upscayl processa os quatro
canais e devolve o alfa também ampliado, e o formato de destino continua sendo
um que o suporta.

Quatro formatos têm equivalente exato em DDS: DXT1, DXT3, DXT5 e RGBA8. Os
legados — P8, L8, G16 — não têm: não há como voltar a uma paleta depois de
ampliar. Nesses o programa escolhe DXT1 ou DXT5 conforme a textura use alfa, e
**escreve no andamento qual escolheu**:

```
    fundo_menu: TEXF_P8 nao tem equivalente em DDS; escolhi BC1_UNORM
```

### Exportar texturas no formato original

Duas portas, conforme quantas você quer:

- **Exportar marcadas…**, na barra das miniaturas — marque quantas quiser e
  escolha a pasta de destino;
- **Exportar esta…**, no painel de propriedades — só a textura selecionada, com
  o nome de arquivo que você escolher.

A marca é a mesma da ampliação. Marque, exporte, e desmarque depois se não for
ampliar nada.

**O que sai é o que está lá dentro.** Nada é recomprimido nem convertido:

| A textura no pacote | O arquivo que sai |
|---|---|
| DXT1, DXT3, DXT5 | `.dds` com o mesmo DXT |
| RGBA8 e os sem compressão | `.tga` |

No caso do DDS, os bytes de pixel do arquivo exportado são **os mesmos bytes**
que estão dentro do `.utx` — o umodel copia os blocos DXT para dentro de um
recipiente DDS sem tocar neles. Dá para conferir: descriptografe o pacote e
procure o conteúdo do `.dds` lá dentro; ele está inteiro, na mesma ordem.

Serve para guardar o original antes de mexer, abrir no Photoshop com o plugin de
DDS, ou levar uma textura para outro pacote.

O caminho é rápido porque não há conversão nenhuma: três texturas saem em menos
de um segundo. Acima de doze texturas o programa exporta o pacote inteiro de uma
vez e separa o que você pediu — abrir o pacote custa mais do que copiar os bytes.

### Trocar uma textura por outra imagem

Cada miniatura tem um botão **trocar…**, e o painel de propriedades tem
**Trocar esta imagem…** para a textura selecionada. Serve **PNG, JPG, BMP, TGA,
WebP e DDS** — inclusive DDS em um formato que o pacote não usa.

Você não precisa preparar a imagem. O programa a encaixa sozinho, e mostra no
painel o que vai fazer com ela antes de processar:

    trocar por      minha_pedra.dds
                    1024x1024 -> 256x256
                    cortada no centro
                    DDS -> DXT1 (BC1_UNORM)

O que é ajustado:

- **o tamanho**, porque o cliente usa potências de dois e grava os bits de
  dimensão no pacote;
- **a proporção**: se a sua imagem tem outra, ela é *cortada no centro* até a
  proporção certa antes de ser reduzida. Cortar tira as bordas; esticar
  estragaria o desenho inteiro;
- **o alfa**, se o original tinha e a imagem nova não tem. Uma placa recortada
  não vira um retângulo opaco só porque o arquivo novo veio sem canal de
  transparência;
- **o formato**, que é o ponto mais fácil de errar a mão.

Sobre o formato, a regra é uma só: **vale o que o pacote exige para AQUELA
textura**, nunca o formato do arquivo que você escolheu. Se ela era DXT1, sua
imagem sai DXT1 — mesmo que você tenha entregue um DDS em BC7. Se era DXT5, sai
DXT5. Se era RGBA8, sai RGBA8. Um PNG comum também serve de entrada: o formato
de saída não muda por causa disso.

Formatos legados do Unreal (P8, L8, G16, RGBA7) não têm equivalente em DDS.
Nesses, o programa escolhe DXT5 ou DXT1 conforme o alfa e **escreve a troca no
andamento** — substituição silenciosa é a que ninguém descobre.

DDS que o Pillow não sabe ler (BC6H, meio-float, cabeçalho DX10 incomum) entra
pelo texconv, que já está na pasta de ferramentas. Você não precisa fazer nada:
se o Pillow recusar, o desvio acontece sozinho.

Trocar **desmarca** a textura: ela não é ampliada, porque já está no tamanho que
você quer.

### Melhorar uma textura só

Clique numa miniatura e use **Melhorar só esta**, no painel de propriedades.
Ele desmarca o resto, marca aquela e processa.

O pacote sai **completo**: as outras texturas entram na remontagem do jeito que
estavam, no tamanho e no formato originais. É o caminho para corrigir uma
textura sem esperar o pacote inteiro — e sem o custo de memória de ampliar tudo.

### Os `?` ao lado dos campos

Os círculos azuis espalhados pela janela abrem uma explicação ao parar o mouse
sobre eles: o que aquele campo faz, o que o valor significa e o que costuma dar
errado. Estão nos dois lados do programa, e acompanham o idioma escolhido.

### Quanto tempo isso leva

Muito mais do que parece. Numa Intel HD 620 (grafica integrada), uma textura
**512x512 em 2x leva cerca de 80 segundos**, e o custo cresce com a area: uma
1024x1024 passa de quatro minutos. Um pacote com 44 texturas de 1024 e uma
tarde inteira.

A barra nao esta travada — ela anda **dentro** de cada textura, conforme o
Upscayl reporta os proprios blocos, e a linha abaixo dela mostra o tempo
decorrido e a previsao. Se ainda assim estiver lento demais, `upscayl-lite-4x`
e sensivelmente mais rapido, e marcar menos texturas resolve de vez: quase
sempre so um punhado delas aparece perto do jogador.

### Linha de comando

O `L2PackTool-cli.exe` e o mesmo motor sem a interface, para o que se repete.
Sem argumento nenhum ele lista o que sabe fazer:

```bat
L2PackTool-cli.exe
```

| comando | o que faz |
| --- | --- |
| `upscale` | amplia as texturas de um `.utx` e remonta o pacote |
| `abrir` | descriptografa arquivo do cliente (`.dat` `.utx` `.u` `.unr` `.ini`) |
| `fechar` | criptografa de volta, com o nome que o jogo espera |
| `extrair` | tira as texturas de um pacote, como imagens |
| `listar` | mostra a versao e os objetos de um pacote |
| `conferir` | confere o cliente e diz que arquivo falta |
| `lobby` | põe o vídeo na tela de login de um lobby, com câmera fixa |
| `ferramentas` | diz quais ferramentas foram encontradas, e onde |
| `ajuda` | a lista; `ajuda <comando>` detalha um deles |

```bat
L2PackTool-cli.exe upscale MinhaTextura.utx              :: um pacote, 2x
L2PackTool-cli.exe upscale "C:\L2\Textures" -s 2         :: pasta inteira
L2PackTool-cli.exe upscale pacote.utx -n remacri-4x      :: outro modelo
L2PackTool-cli.exe upscale pacote.utx --parar-em extrair :: inspecionar antes

L2PackTool-cli.exe abrir "C:\L2\system\itemname-e.dat" -o .\aberto
L2PackTool-cli.exe fechar .\aberto\itemname-e.dat -o .\fechado
L2PackTool-cli.exe listar pacote.utx
L2PackTool-cli.exe conferir "C:\L2" -o relatorio.txt
```

Todo comando aceita um arquivo **ou uma pasta**, e `<comando> -h` mostra as
opcoes daquele comando. Os `.utx` prontos saem em `saida/`; copie para o
`Textures/` do cliente, mantendo o nome.

Quem ja chamava pelo caminho direto continua chamando: sem um comando conhecido
na frente, o pedido e de upscale, como sempre foi.

**O codigo de saida serve a script:** `0` deu certo, `1` faltou alguma coisa --
o que permite encadear o `conferir` com o que vier depois.

O que fica so na interface: editar mob, multisell, item e skill, e criar NPC.
Sao trabalhos de escolher na tela e ver o efeito antes de gravar.

### A janela rola

O programa nasceu em tela grande, e numa de 1366x768 — a mais comum em notebook
— quase toda aba pede mais altura do que cabe. O Tk simplesmente corta o que
sobra: o botão fica fora da janela, sem aviso e sem jeito de alcançá-lo.

Cada aba está dentro de uma área rolável. A barra só aparece quando o conteúdo
passa da altura disponível, então em tela grande nada muda. A roda do mouse tem
um tratador único, que a partir do widget sob o ponteiro sobe até achar o
primeiro que rola — assim a roda mexe na lista quando o ponteiro está sobre a
lista, e na aba quando está fora dela.

| aba | altura que pede |
| --- | --- |
| Lobby Vídeo | 1063 px |
| Itens | 1072 px |
| Conferir Cliente | 938 px |
| NPC com efeito | 858 px |
| Texture Upscaler | 752 px |
| L2Crypt | 675 px — a única que cabe inteira |

---

### A pasta `trabalho/`

E onde ficam os arquivos intermediarios, e ela **se apaga sozinha** quando o
pacote termina bem. Um `.utx` de 8 KB gera dezenas de MB ali no meio do
caminho, e um lote grande passa facil de 1 GB — por isso nao se acumula.

Se o programa for fechado no meio, ou se voce cancelar a pergunta do destino,
o que sobrou e removido na abertura seguinte. `_saida_provisoria/` e a unica
excecao: e ali que ficam os pacotes ja prontos de um salvamento cancelado, e
esses ninguem apaga por voce.

Com `--parar-em`, nada e apagado — a pasta existe justamente para ser
inspecionada.

---

## A aba "NPC com efeito"

Faz NPCs com partículas — aura, fogo, gelo, o que o cliente tiver — sem abrir
o L2Editor e sem escrever UnrealScript.

### Uma aba, dois passos

O NPC é um assunto só — aparência, efeito e atributos do servidor são partes do
mesmo bicho — mas cabem mal na mesma tela. A aba tem dois passos, na ordem em
que se preenche:

| passo | o que tem |
| --- | --- |
| **1 · Cliente e efeitos** | o NPC base, o id novo, nome e título, os efeitos |
| **2 · Servidor** | atributos, drop, spawn, loja, e a prévia do que vai sair |

Até a versão anterior isso eram **duas abas**, e havia um defeito real: a aba de
efeitos escrevia um XML de servidor com valores de exemplo, e a de atributos
escrevia outro com os valores de verdade. **Dois arquivos para o mesmo id** — e
quem instalasse os dois ficaria com o servidor lendo o que viesse por último.

Agora é um só. O passo 2 não tem id nem nome próprios: ele pergunta ao passo 1.

### Um cliente, vários servidores

O cliente do Lineage 2 é um só; o emulador não.

| Formato | Quem usa | Onde guarda |
| --- | --- | --- |
| **XML** | aCis, L2jServer, Mobius, Lisvus | `data/xml/npcs`, `data/xml/multisell` |
| **Banco** | L2jFrozen e os cores de datapack antigo | tabelas `npc`, `droplist`, `spawnlist` |

Não é só o formato. Onde o aCis escreve `<set name="pAtk" val="700"/>`, o banco
tem uma coluna `patk`; onde o aCis diz `type="Monster"`, o banco diz
`L2Monster`; e a chance de drop é percentual num e em milionésimos no outro.

Por isso o programa trabalha com um conjunto de campos **próprio, neutro**, e
cada perfil diz como traduzi-lo. A caixa **Servidor** escolhe, e a **prévia**
mostra o arquivo pronto — XML ou `INSERT` — atualizando sozinha enquanto você
preenche.

**Um core novo é um arquivo.** `recursos/servidores/<nome>.json` declara o
formato, as pastas ou tabelas, o de-para dos campos e as conversões de valor.
Não há código a mexer.

#### Detectar pelo servidor

Houve uma versão com um perfil por servidor, e ela não se sustentou. O caso que
a derrubou: um servidor de teste tinha nome próprio, e eu escrevi um perfil
com esse nome. Só que aquele era o nome **do servidor dele**, não de um core
— por baixo era aCis, com quatro diferenças. Quem monta um servidor pega
um core, troca o nome e mexe no que quer; um arquivo por pessoa seria pedir que
cada uma descrevesse à mão o que os próprios arquivos já dizem.

Então a primeira opção da caixa **Servidor** deixou de ser um perfil:
**Detectar pelo servidor** lê a pasta apontada e monta o perfil a partir dela.
Leva cerca de dois segundos numa pasta de dados inteira.

O que a leitura decide, e com que prova:

| O quê | Como decide |
| --- | --- |
| formato | conta elementos XML contra `INSERT INTO` |
| onde ficam item, habilidade e NPC | a pasta com **mais definições** de cada tipo |
| prefixo do alvo e do modo | a maioria dos valores começar com `TARGET_` / `OP_` |
| gaveta de drop | `<category type=>` contra `<category id=>` |
| unidade da chance | a maior chance vista passar de 100 |

Nada disso é palpite: cada resposta sai de contagem, e **o que foi visto
aparece na tela**, ao lado da caixa. Detectar em silêncio trocaria o palpite do
usuário pelo meu.

No servidor que motivou tudo isto, a leitura diz:

```
XML: itens em xml/items (9201), skills em xml/skills (2702),
     npcs em xml/npcs (6373); target das habilidades com TARGET_;
     operateType das habilidades com OP_; gaveta de drop numerada (id=);
     chance de drop em milionesimos (a maior vista foi 1e+06)
```

As quatro diferenças dele em relação ao aCis — e todas davam erro **silencioso**,
que é o pior tipo:

| Onde | aCis | esse servidor | o que acontecia |
| --- | --- | --- | --- |
| alvo | `ONE` | `TARGET_ONE` | o nome do core aparecia como se fosse o neutro |
| modo | `ACTIVE` | `OP_ACTIVE` | idem |
| gaveta de drop | `type="SPOIL"` | `id="-1"` | **todo monstro voltava sem drop** |
| chance | por cento | milionésimos | `700000` numa coluna chamada "chance %" |

Uma quinta diferença não precisa de detecção, porque o programa passou a aceitar
as duas escritas: o bloco `<for>` dele põe `order` antes de `stat`
(`<set order="0x08" stat="pAtk" val="24"/>`), e o leitor exigia `stat` logo
depois do nome da operação — a tela mostrava *0 status* num item que tem quatro.

**Prefixo em vez de lista.** O de-para de valor aceita `prefixos`, e não só
`valores`: basta saber que há um `TARGET_` para cobrir os 28 alvos. Escrever as
28 linhas à mão envelheceria pior — um alvo fora da lista sairia sem prefixo, e
sem erro nenhum.

**Uma definição não é uma referência.** O mesmo nome de elemento serve para os
dois: o NPC escreve `<skill id="4416" level="6"/>` para dizer que sabe aquela
habilidade, e a receita escreve `<item id="57" count="10"/>` para dizer do que é
feita. Somados, davam 27 mil "habilidades" dentro da pasta de NPCs e itens de
receita contados como itens do jogo. A definição se reconhece pelo que só ela
tem — um nome, um tipo, a contagem de níveis.

**A escrita também segue o que foi detectado.** Na gaveta numerada, cada item
ganha **a sua própria gaveta**: uma gaveta sorteia UM item entre os seus, então
juntar tudo numa só transformaria cinco drops independentes num drop único —
com a chance de cada um intacta na tela e o resultado errado no jogo. O espólio
é a exceção: é sempre a gaveta `-1`, e vai inteiro nela.

Os perfis prontos continuam na lista, e escolher um manda: detectar é o padrão,
não uma imposição. Um core com arrumação estranha o bastante para enganar a
leitura ainda pode ser dito na mão.

O `INSERT` sai com **os nomes das colunas**, e não por posição: schema de
emulador não é fixo, e uma coluna a mais no meio faria um insert posicional pôr
preço no lugar de peso, sem erro e sem aviso.

A leitura também usa o perfil para saber **onde olhar primeiro**. A varredura
para no primeiro arquivo que casa, então a ordem decide o resultado: num
servidor de verdade, o item 1 vinha de `xml/recipes.xml`, onde `<item id="1">`
é ingrediente de receita e não item do jogo — voltavam zero campos e zero
status, e nada na tela dizia que o arquivo lido era o errado. Agora a pasta
declarada no perfil vai na frente, e o resto da árvore fica atrás, como rede
para os cores que guardam as coisas noutro lugar.

O caminho do perfil (`data/xml/items`) é cortado pela cauda antes de comparar,
porque quem aponta a pasta é o usuário e ele costuma apontar já de dentro do
`data`.

### Ler do servidor

O caminho de ida — formulário para arquivo — existia desde o começo. Este é o
de volta: **Ler do servidor** procura o NPC na pasta de dados e traz o que ele
tem para o formulário — atributos, drop, spawn e loja.

Ele lê o NPC **marcado na lista** — e não o do campo **id novo**. É assim que
se copia os atributos de um monstro que já funciona: o cliente nunca guardou
vida nem ataque, e agora não é preciso digitá-los.

Não achando, o programa diz isso com todas as letras: o NPC ainda não existe do
lado do servidor, e é o caso de preencher e gerar.

A primeira versão tentava o id novo antes, para que quem tivesse acabado de
gerar pudesse reler. Parecia esperto e era confuso: o campo do id novo vem
preenchido com um id livre sugerido, e num servidor que já tenha alguma coisa
naquele id a tela trazia outro NPC sem explicar por quê. Hoje a regra é uma
só, e o botão diz o id: **Ler o 20003 do servidor**. Para reler o que você
criou, marque-o na lista — ele está lá depois de gerar.

A volta custa uma tradução a mais. No XML do aCis o nome do campo no arquivo é
o mesmo que o programa usa, então não há o que inverter; no banco, `patk` tem
de virar `pAtk` outra vez, `L2Monster` tem de virar `Monster` e a chance de
drop precisa sair de 1.000.000 e voltar a 100%.

Há um caso que o de-para sozinho não resolve: o `INSERT` **sem nomes de
coluna**. Os `.sql` que circulam são quase todos assim, e aí a única saída é
saber a ordem das colunas daquela tabela. Ela está no perfil, em `colunas`, e
só é usada na leitura — ao escrever, o programa sempre nomeia. Sem essa ordem,
o programa diz que não soube ler, em vez de adivinhar campo por posição e pôr
vida no lugar de mana.

Testado nos dois: o Gremlin do aCis volta com 43 campos e 15 drops, e um
`custom_npc.sql` posicional volta com 37 campos, o tipo desconvertido de
`L2Teleporter` para `Teleporter` e o drop de 1.000.000 para 100%.

O nome e o título vão para o passo 1, com uma regra: o que **você digitou**
nunca é apagado, mas o que veio de uma leitura anterior é substituído — senão,
ler um NPC depois do outro deixava o nome do primeiro grudado no segundo.

### O que o passo 2 gera

- **atributos** — vida, ataque, defesa, velocidade, tipo, colisão;
- **drop** — em três gavetas: `DROP`, `CURRENCY` (adena, o item 57) e `SPOIL`.
  A chance é percentual nos dois formatos;
- **spawn** — onde nasce, com coordenadas, direção e tempo de renascimento;
- **loja** — o multisell, que é XML nos dois mundos.

Tudo sai na mesma pasta que o resto da geração, para ninguém instalar só metade
do conjunto.

O botão **Manual** ali abre o texto que acompanha o preenchimento campo a campo.

### O id vem do cliente

O campo do id novo é preenchido com o **primeiro id livre** encontrado no
`npcgrp.dat`, a partir de 90000 — e não com o maior mais um. Num cliente com um
id solto lá em cima, e quase todo cliente modificado tem, o maior mais um
jogaria o NPC novo para uma faixa que o próprio cliente trata mal.

Clicar no NPC base preenche nome e título a partir do que o cliente sabe dele.

### Como funciona

Um NPC, para o cliente, é uma linha do `npcgrp.dat`: qual malha usar, quais
texturas, e **qual classe UnrealScript governa aquele boneco**. Um NPC com
efeito aponta para uma classe própria, que ao nascer cria um emissor de
partículas e o gruda no esqueleto.

O programa faz isso em quatro passos:

1. lê o `npcgrp.dat` e lista os NPCs que o cliente tem
2. varre os `.u` da pasta `system` e cataloga **todos os efeitos instalados** —
   num cliente Interlude típico são mais de 850 só no `LineageEffect.u`
3. você escolhe um NPC para copiar a aparência e um efeito para acender
4. ele gera a classe, compila com o UCC, reescreve o `npcgrp.dat` e ainda
   escreve o XML do lado do servidor

A primeira leitura demora alguns segundos; depois fica em cache.

### O NPC continua sendo o que era

A classe gerada **estende a classe do NPC copiado**, não uma classe genérica.
Isso é o que preserva o comportamento dele: animação de espera, caminhada,
sombra, e o que aquele tipo de NPC souber fazer. O efeito é acrescentado por
cima, sem substituir nada.

Duas decisões concretas sustentam isso:

- o gancho é **`PostSetPawnResource`**, e **não se chama `Super` nela**;
- o efeito é preso ao esqueleto depois disso, quando ele já existe.

**O gancho já foi `PostBeginPlay`, e isso era um erro meu.** Este cliente tem 19
NPCs com classe própria que funcionam, e o pacote deles está aqui dentro —
`SGERfjsEffects.u`. Decifrado e lido, ele acende assim:

```unrealscript
class SGERfjs_Effect_Ice extends LineagePawn
  Config(User);

simulated function PostSetPawnResource ()
{
  Effect0 = Spawn(Class'SGERfjs_Effect',self,'None',Location,Rotation);
  ...
}
```

`PostSetPawnResource` é chamada pela engine **depois** de pôr os recursos do
boneco no lugar; `PostBeginPlay` roda antes disso. Quem a chama é a engine, por
nome — nenhum pai precisa declará-la, e é por isso que a classe de referência
pode tê-la mesmo estendendo `LineagePawn`, que não tem (conferido no
`LineageWarrior.u`, onde `class LineagePawn extends Pawn` mora).

**E não se chama `Super` nela — isso custou um cliente fechado.** Eu tentei:
como as classes do `LineageMonster.u` têm a sua `PostSetPawnResource`, parecia
errado descartar o que o NPC base faz ali. Para o `Super` compilar, declarei a
função no **talo** da classe-mãe — a classe de mentira que o programa cria,
porque a de verdade mora no cliente. O compilador aceitou. O jogo não:

```
General protection fault!
History: UObject::ProcessEvent <- (Npc_60000_FX ...,
  Function FX_60000.Npc_60000_FX.PostSetPawnResource)
  <- APawn::PostLoadProcess <- TickAllActors <- ...
```

O talo fez o `Super.` compilar contra uma função **que eu mesmo tinha
inventado**. Em jogo o pacote é ligado à classe de verdade, e a chamada apontou
para o nada. A classe de referência deste cliente nunca chamou `Super` ali — só
declara a função e deixa a engine chamá-la.

A lição vale para todo o arranjo do talo: ele serve para o compilador aceitar a
herança, e **declarar nele uma função que a classe real talvez não tenha é
trocar um erro de compilação por um crash**. O `PostBeginPlay` continua lá
porque o `LineagePawn` de verdade tem o dele — isso está conferido no fonte que
o próprio `LineageWarrior.u` do cliente guarda.

### Onde o efeito vai ficar: a régua

O campo **Altura (Z)** é dado nas unidades da malha, e sem uma referência
escolher esse número é tentativa e erro — com uma recompilação e um reinício do
cliente a cada tentativa.

Ao lado dos campos há uma régua que mostra a altura **real** da malha do NPC
base, com uma marca no Z escolhido e a leitura em palavras: *nos pés, na altura
das pernas, da cintura, do peito, da cabeça, acima da cabeça*. Ela redesenha a
cada tecla.

Ao lado da barra ficam as referências do corpo — **pés, cintura, cabeça e acima
da cabeça** — na altura que *aquela* malha tem de fato. Num orc de 38 unidades a
cintura fica em 20 e a cabeça em 33; num de 45,5, em 24 e 40.

A medida sai dos vértices: o programa exporta o `.psk` da malha com o umodel e
mede o alcance em Z da nuvem de pontos — que é exatamente a unidade que o
`SetRelativeLocation` usa. Nem o `npcgrp.dat` guarda tamanho, nem serve a altura
do XML do servidor, que é a caixa de colisão e é outra coisa.

Para calibrar: um orc mede **38** unidades; um humanoide, **46**. O
`SGERfjs_Effect_Ice`, que já roda neste cliente, usa Z=60 — flutuando acima da
cabeça.

Medir leva cerca de um décimo de segundo e fica em `alturas.json`.

### Ver o NPC com o efeito: DevMode

O botão **Abrir o jogo em DevMode** sobe o próprio cliente sem servidor, num
mapa local, com o console de desenvolvimento ligado. É o **único** jeito de ver
o efeito: partícula do Unreal Engine 2 só o motor do jogo desenha.

O `Engine.dll` do cliente traz uma família inteira de comandos para isso — os
nomes foram lidos do binário, onde ficam juntos como o Unreal guarda os
literais comparados pelo `ParseCommand`:

No binário eles ficam em **pares** — nome por extenso seguido do atalho curto —,
que é como o `ParseCommand` os compara:

| comando | para quê |
|---|---|
| **`nv`** | *NpcViewer* — o visualizador de NPC |
| `pv` | *PawnViewer* — o visualizador de personagem |
| `sv` | *SkillViewer* — o visualizador de skill |
| `SPAWNACTOR Class=FX_<id>.Npc_<id>_FX` | faz nascer a classe gerada aqui |
| `SPAWNNPCS` | faz nascer NPCs do npcgrp |
| `MESHCHANGE MESHNAME=<Pacote.malha>` | troca a malha |
| `CHANGEANIM ANIM=WAIT\|WALK\|RUN` | troca a animação |
| `DEFAULTCAMERA DISTANCE=200 PITCH=0 YAW=0` | posiciona a câmera |
| `AddEffect` / `DeleteEffect` | põe e tira efeito no alvo |
| `BONESCALE` / `BS` | escala de osso |
| `DeleteSelectedActor` | apaga o selecionado |
| `CheckGrp` | confere os `.dat` e aponta os erros deles |

Os **nomes** são certos, lidos do binário. Os argumentos marcados com `=` são o
que os literais vizinhos indicam, não documentação.

O console abre com **Tab** (`ConsoleKey=9`, que no Unreal é `IK_Tab`).

Na lista de NPCs criados há o botão **Ver no jogo**: ele abre o DevMode e deixa
o comando daquele NPC na área de transferência. No jogo é Tab, Ctrl+V, Enter. O
console do cliente não recebe nada de fora — é uma janela do próprio jogo, sem
porta de entrada —, então colar é o mais perto de automático que dá para chegar.

Dois tropeços conhecidos:

- **Aviso de AGP.** Aparece *"The game may not be consistant because AGP is
  deactivated"* e o jogo **fica parado nele** até alguém clicar OK — sem janela
  de mundo, só o processo consumindo CPU. Não há configuração que desligue: a
  mensagem está fixa no `D3DDrv.dll`, dentro do `UD3DRenderDevice::SetRes`,
  como resultado de uma checagem de hardware que nenhuma máquina moderna passa.
- **Elevação.** O `L2.exe` tem manifesto de administrador, então o programa o
  abre pelo shell (que sabe pedir a elevação) e depois não consegue mais
  gerenciá-lo — nem encerrá-lo.

### Os .ini do cliente são protegidos sozinhos

O `l2.ini` e o `user.ini` do cliente são **criptografados** — começam com o
cabeçalho `Lineage2Ver`, como os `.dat`. O jogo em DevMode grava por cima deles
em **texto puro** ao sair, e a partir daí o jogo normal não consegue mais
lê-los: abre com erro.

Por isso o programa copia os dois antes de abrir o DevMode e os devolve
**depois que o jogo fecha** — depois, e não antes, porque é ao sair que o Unreal
grava a configuração. A espera é por nome de processo, já que o `L2.exe` sobe
elevado e um programa comum não consegue nem segurar um descritor dele.

As cópias ficam em `systemackup_devmode\`. Se o programa for fechado com o
jogo ainda aberto, elas ficam lá e são devolvidas na abertura seguinte.

### O osso vem da malha

O efeito é preso a um osso do esqueleto, e a lista de ossos é lida da própria
malha do NPC base — do bloco `REFSKELT` do `.psk`. O padrão é o **primeiro**
osso, que é a raiz do esqueleto: `Bip01` em toda malha humanoide deste cliente.
Prender na raiz faz o efeito acompanhar o boneco inteiro.

Isso corrigiu um erro que vinha desde o começo: o padrão era `Dummy`, e **esse
osso não existe em malha nenhuma**. O orc tem `Dummy01`; o `a_casino_FDarkElf`
tem `Shoulder L Bone Dummy`. Com um nome que não existe, o `AttachToBone` não
acha onde prender e o efeito fica solto na posição do ator em vez de acompanhar
o boneco.

Um orc tem 44 ossos; um humanoide com capa e saia, 85. Vale olhar a lista: além
da raiz há `Bip01 head`, `Bip01 L Hand`, `Sword Bone`, `Cape Bone` e outros,
que servem para prender o efeito numa parte específica.

### A altura, e por que ela não funcionava

O efeito ficava colado no osso por mais alto que se pedisse. Foram três
tentativas, e as duas primeiras foram erro meu — ficam aqui porque a terceira
só faz sentido depois delas.

**Primeira: `SetRelativeLocation`.** Os números que saem do gerador estavam
certos, então o problema não era a conta: era deslocar um ator **já preso a um
osso**. O motor recalcula a posição dele a partir do osso a cada quadro.

**Segunda: mover o ator por `Tick`.** Passei a escrever a posição todo quadro,
com `GetBoneCoords` + `SetLocation`, como o próprio `Engine.u` faz com a sombra.
O usuário descreveu o resultado numa frase que vale mais que qualquer teoria:

> aparece na altura certa em milissegundos e desce no corpo

A posição valia um quadro e alguém a desfazia. Brigar quadro a quadro com o
motor é uma briga que não se ganha.

**Terceira, e a certa: o deslocamento é da PARTÍCULA.** Um `Emitter` não guarda
partícula — guarda uma lista de `ParticleEmitter`, e cada uma decide sozinha em
que sistema de coordenadas vive. Está no `Engine.u` deste cliente:

```unrealscript
class Emitter extends Actor
var() export editinline array<ParticleEmitter> Emitters;

class ParticleEmitter extends Object
var (General) EParticleCoordinateSystem CoordinateSystem;
var (Location) vector StartLocationOffset;

enum EParticleCoordinateSystem {
    PTCS_Independent, PTCS_Relative, PTCS_Absolute,
    PTCS_RelativeRotation, PTCS_Spray };
```

| valor | o que faz |
| --- | --- |
| `PTCS_Absolute` | coordenadas do mundo — **ignora o ator**, mover o emissor não muda nada |
| `PTCS_Independent` | a partícula nasce no ator e depois vive solta no mundo |
| `PTCS_Relative` | tudo relativo ao ator — a partícula acompanha |

E o `StartLocationOffset` desloca **onde a partícula nasce**, dentro desse
sistema. Um marcador de quest já vem feito para pairar sobre a cabeça: ele
carrega esse deslocamento dentro de si, e nenhuma altura nossa o move.

Então o script gerado passa a escrever nos emissores do efeito:

```unrealscript
for ( i = 0; i < Alvo.Emitters.Length; i++ )
{
	Alvo.Emitters[i].CoordinateSystem = PTCS_Relative;
	Alvo.Emitters[i].StartLocationOffset = Desloca;
}
```

O emissor volta a ser **preso ao osso** (acompanha o boneco) e o deslocamento é
o mesmo vetor que já se calculava, girado para o sistema daquele osso. Nada a
sobrescrever, nada a refazer por quadro: **o `Tick` e o `Seguir` saíram
inteiros**.

Na tela há uma caixa **"obedecer à altura"**, marcada por padrão e gravada por
efeito. Desmarcada, o efeito sai exatamente como o autor dele fez — que é o
certo quando se quer justamente aquele comportamento.

**A escala tem a mesma história.** Pedir escala 2,00 não engordava nada, porque
`SetDrawScale` é do **ator** e a partícula tem o tamanho dela, em
`StartSizeRange`. Exatamente o mesmo erro da posição, um andar acima:

```unrealscript
if ( Escala != 1.0 )
{
	Alvo.Emitters[i].StartSizeRange.X.Min *= Escala;
	...
	Alvo.Emitters[i].StartLocationRange.Z.Max *= Escala;
}
```

O `StartLocationRange` — a faixa onde as partículas nascem — escala junto: só
aumentar o tamanho de cada uma, sem abrir a faixa, daria um efeito **gordo e
apertado** em vez de um efeito maior. O deslocamento **não** entra na escala: ele
é a altura pedida, em unidades do mundo, e dobrar o efeito não muda onde ele
deve ficar.

Os campos de `rangevector` são nativos e não estão declarados em UnrealScript
neste `Engine.u` — procurei. Escrevi `X.Min`/`X.Max`, que é a forma conhecida, e
deixei o UCC responder: **Success - 0 error(s)**. Quando a fonte não dá para ler,
o compilador é a segunda melhor testemunha — e está aqui, e não na máquina de
quem usa.

### O NPC assentado no chão

O cilindro de colisão é o que põe o boneco no chão, e o `height` é a **metade**
da altura dele — o próprio `Engine.u` anota `// Half-height cyllinder`.
Pequeno demais, o NPC nasce enterrado; grande demais, flutua.

Os valores de partida da tela eram fixos: `radius 8`, `height 24`, herdados de
um monstro qualquer. Num esqueleto de 53,9 unidades a meia altura é 27 — ele
nascia enterrado até a cintura.

O botão **Medir a colisão pela malha** tira os dois da malha do NPC base. A
altura já saía da nuvem de vértices do `.psk`; o raio passou a sair da mesma
nuvem, pelo maior alcance horizontal. Medir os dois no mesmo lugar é de graça,
porque o `.psk` já está aberto:

| malha | medido | o cliente mostra |
| --- | --- | --- |
| `skeleton_archer_m00` | altura 53,9 → `height 27`, `radius 12` | ColliH 27, ColliR 11 |
| `gremlin_m00` | altura 31,5 → `height 16`, `radius 11` | ColliH 15, ColliR 10 |

São valores **medidos**, e não os oficiais — os do jogo foram ajustados à mão.
Servem de ponto de partida honesto, que é mais do que um número fixo fazia.

### O tamanho do NPC

**No servidor não há campo de escala.** Procurei nos 6.373 NPCs do servidor do
usuário: os 30 campos que aparecem não incluem `scale` nem nada parecido.

Mas tamanho é **desenho**, e desenho é do cliente. `var(Display) float
DrawScale;` está no `Engine.u` dele, e é o mesmo "Scale" que o NpcViewer aplica.
A classe gerada é um Actor como outro qualquer, então ela mesma se
redimensiona, no `PostSetPawnResource` — o mesmo gancho do efeito, pelo mesmo
motivo:

```unrealscript
simulated function PostSetPawnResource()
{
	SetDrawScale(2.00);
	...
```

A linha só aparece quando há o que mudar: uma linha à toa num arquivo gerado é
uma linha que alguém vai ler e se perguntar por quê.

**A colisão não acompanha sozinha.** Ela vem do servidor, e um NPC dobrado com
colisão simples fica com meio corpo enterrado e uma caixa de acerto que não bate
com o que se vê. Por isso **Medir a colisão pela malha** multiplica pelo tamanho
— as duas pontas do mesmo número:

```
silver_cat_m00, altura 30,8    tamanho 1,00  ->  height 15, radius 7
                               tamanho 2,00  ->  height 31, radius 15
```

O cliente mostra `ColliH 15,000000` e `ColliR 7,000000` para esse NPC. A medida
bate.

**E ela não é opção: é o que assenta o boneco no chão.** O NPC dobrado nasceu
enterrado até o peito, e a medida das três malhas explica por quê:

| malha | altura | origem da malha | `ColliH` do cliente |
| --- | --- | --- | --- |
| `silver_cat_m00` | 30,8 | nos pés (chão −0,1) | 15 |
| `gremlin_m00` | 31,5 | 6 acima dos pés | 15 |
| `skeleton_archer_m00` | 53,9 | nos pés (chão −0,0) | 27 |

Nas três, `ColliH` é a **metade da altura** — o que só fecha se o motor desenhar
a malha **centrada no ponto do NPC** e puser esse ponto em `chão + ColliH`. Com o
boneco dobrado e o cilindro no tamanho antigo, os pés descem meia altura extra:
30,8 de malha com `ColliH 15` afunda 15,8. Foi exatamente o que apareceu na tela.

Por isso **mudar o tamanho refaz raio e altura na hora**, e não só quando alguém
lembra de apertar o botão:

```
tamanho 1,00  ->  height 15, radius 7
tamanho 1,50  ->  height 23, radius 11
tamanho 2,00  ->  height 31, radius 15
tamanho 0,50  ->  height  8, radius 4
```

Quem quiser outro número continua digitando por cima: o campo e o botão seguem
sendo do usuário.

**No DevMode a colisão não vem do XML.** O NpcViewer usa o campo `ColliH` da
própria janela dele, que começa com o valor de fábrica — então um NPC dobrado
aparece enterrado ali mesmo com o XML certo. Para ver o tamanho novo no
visualizador, digite a altura de colisão e clique em **Apply**. Em jogo, quem
manda é o `height` que o servidor lê.

### A arma na mão

`rHand` e `lHand` levam um **id de item**, e digitar id de cabeça tem o mesmo
problema do ícone: `1472` não diz nada. No servidor do usuário, 2.113 NPCs
carregam arma assim.

**Escolher a arma…** abre a lista de armas do cliente — 1.346 neste — com o
desenho ao lado, filtro por nome ou id, e a que já está no campo vem marcada.
Há também **Mão vazia**, que é o `0` que o servidor entende por "nada".

A lista sai do `weapongrp.dat` e do `itemname-e.dat` pelo mesmo `l2item` da aba
de Itens — não há catálogo à parte para envelhecer. Ler custa alguns segundos, e
por isso acontece na primeira vez que a janela abre e fica guardado na aba.

### O recado do fim parou de mandar copiar o que já foi copiado

A mensagem depois de instalar dizia "copie este arquivo para
data/xml/npcs/custom/" **mesmo quando o programa acabara de gravá-lo ali**.
Mandar alguém fazer o que já está feito é pior do que não dizer nada: quem
obedece copia por cima do próprio arquivo, e quem desconfia perde tempo
conferindo.

Agora são dois recados, e o título já diz qual é o caso:

```
Pronto -- falta recarregar        Falta o servidor
A XML já está no servidor:        1. copie este arquivo para ...
  <caminho>                       2. //reload npc
1. //reload npc                   3. //spawn 90002
2. //spawn 90002
```

Ele saiu de dentro do `instalar` para um método próprio, `recado_do_fim`. No
meio da instalação, a única forma de ver o texto era instalar de verdade no
cliente do usuário — que é exatamente o que não se faz para conferir uma frase.

### A XML vai direto para o servidor

O cliente e o servidor são dois lados do mesmo NPC, e até agora só um deles era
entregue no lugar certo: a XML ficava na pasta de trabalho esperando ser
copiada à mão. A pasta do servidor já está apontada na tela ao lado, e o perfil
detectado já sabe onde os NPCs moram — faltava ligar as duas pontas.

Com **"gravar a XML na pasta do servidor"** marcado, ela vai para
`<pasta>/<pasta de NPCs do perfil>/custom/`. Num servidor real isso resolve
para algo como:

```
D:/servidor/build/dist/game/data/xml/npcs/custom
```

A subpasta `custom` é a convenção dos datapacks L2J: misturar com os arquivos
de fábrica torna impossível saber depois o que foi acrescentado. O caminho do
perfil é cortado pela cauda antes de comparar, como na leitura, porque quem
aponta a pasta costuma apontar já de dentro do `data`.

Falhar ali não derruba a geração: o NPC foi gerado, o que não deu foi a
entrega, e o registro diz qual foi o erro. E o caminho exato vai para o
registro sempre — isto escreve na pasta do **servidor**, e não numa pasta de
trabalho.

### O nome vai para os dois lados

O campo do nome vazio era tratado de um jeito por cada lado — o XML do servidor
caía no padrão `NPC 90006`, e o `npcname-e.dat` simplesmente não era escrito.

Dois tratamentos para a mesma falta dão dois resultados diferentes. Agora o
nome se resolve **uma vez**, e nunca fica vazio: o que foi digitado; não
havendo, o nome do NPC base — que é o que o jogador já via ali —; e em último
caso `NPC <id>`.

**O "NoNameNPC" do NpcViewer não vem daí.** Ele parecia prova de que o
`npcname-e.dat` não tinha sido escrito, e não era: a linha gravada é
estruturalmente idêntica à de um NPC que o cliente mostra normalmente —

```
20001 -> ['20001', 'a,Gremlin\0',       'a,',        '0', 'FF', '0', '-1']
60000 -> ['60000', 'a,Gremlin Quest\0', 'a,Teste\0', '0', 'FF', '0', '-1']
```

— e a string **`NoNameNPC` está dentro de `system/engine.dll`**, em UTF-16.
É rótulo do executável, e não daquela tabela: o visualizador simplesmente não
mostra o nome do `npcname-e.dat` ali. Vale conferir buscando um NPC de fábrica
no mesmo visualizador — se o 20001 também aparecer como NoNameNPC, está
respondido.

### Vários efeitos no mesmo NPC

A lista de efeitos aceita seleção múltipla — Ctrl ou Shift marcam vários, e
*Adicionar* manda todos de uma vez com a altura e a escala do momento.

Cada efeito guarda **a sua própria** altura, escala e osso. Para mudar um que
já está na lista, marque-o na caixa de baixo, ajuste os campos e clique em
*Aplicar ao marcado* — sem precisar tirar e pôr de novo.

### Ver a malha em 3D

O botão **Ver a malha em 3D** abre o visualizador do umodel no NPC base: malha
com textura, ossos e as animações, para girar e inspecionar.

A janela abre sem console: o `CREATE_NO_WINDOW` suprime o terminal cheio de
avisos de som que o umodel imprime, sem impedir que ele abra a janela própria.

Ele **não mostra o efeito**, e nenhum programa fora do jogo mostra. As classes
que o umodel abre são `SkeletalMesh, MeshAnimation, VertMesh, StaticMesh,
Texture, Sounds` — emissor de partícula não está na lista. Um sistema de
partículas do Unreal Engine 2 tem dezenas de parâmetros por emissor (taxa,
velocidade, cor ao longo da vida, sub-UV, colisão); desenhar aquilo é trabalho
do motor do jogo.

Pelo mesmo motivo não existe ajuste ao vivo: Z e escala ficam compilados dentro
do `.u`, que o cliente lê no arranque.

### Os dois modos

**Script** *(recomendado)* — gera e compila uma classe própria. É o único com
controle fino: osso de encaixe, altura, escala e mais de um emissor no mesmo
NPC.

**Rápido** — preenche as três colunas de efeito que o `npcgrp.dat` já tem
(`rb_effect_on`, `rb_effect`, `rb_effect_fl`). Não compila nada, mas aceita um
efeito só e apenas a escala.

Uma ressalva honesta sobre o modo rápido: essas colunas existem e o cliente as
lê — são o que faz a aura girar em volta dos 25 raid bosses do jogo. Que elas
aceitem **qualquer** emissor, e não só a aura de boss, é dedução a partir do
formato, não observação. O modo script não tem essa dúvida: este cliente já
tem 25 NPCs feitos exatamente assim, e o modelo de código usado aqui foi lido
de dentro de um deles.

### O NPC reage ao clique

O campo **Social ao clicar** define a animação que o NPC toca quando o jogador
clica nele — o que faz o jogador perceber que foi notado.

O servidor já mandava uma animação social ao clicar, mas sorteada entre oito
ids (`Rnd.get(8)`). O problema é que uma malha tem no máximo **três** slots
sociais (`SpWait01`, `spwait02`, `spwait03`), e várias têm só um: o orc, por
exemplo, tem oito sequências no total e apenas `SpWait01`. A maioria dos
cliques pedia uma animação inexistente e o cliente não mostrava nada.

O padrão é **1**, que é o slot que praticamente toda malha do jogo possui. Com
**0**, o NPC volta ao sorteio padrão do servidor.

Isso exige o lado do servidor atualizado: `NpcTemplate` passou a ler
`socialAction` do XML (padrão 0, então nenhum NPC existente muda), e o
`Npc.onAction` usa esse id quando houver. A resposta ao clique tem trava
própria de 3 segundos, separada da trava de 12 segundos da animação ociosa —
senão um clique logo depois de uma animação automática não mostraria nada.

### Acrescentar efeito a um NPC que já existe

Nem sempre se quer um NPC novo. Para pôr efeito num NPC que o cliente já tem —
ou para mexer num que você mesmo fez — marque ele na lista da esquerda e clique
em **Editar este NPC…** (duplo clique na linha faz o mesmo).

O formulário se preenche com o id, o nome e o título dele. Daí é só escolher o
efeito, ajustar altura e escala e clicar em **Gerar**: o programa pergunta se
pode substituir, a linha antiga sai e a nova entra no lugar, **com o mesmo id**.

Os três casos se comportam de formas diferentes, e é proposital:

| O NPC | O que acontece |
|---|---|
| Do próprio cliente | Ele vira a base de si mesmo: aparência e comportamento continuam os dele, e o efeito é acrescentado por cima |
| Criado por este programa | Os efeitos que ele já tem voltam para a lista, e você **acrescenta** aos que estão lá em vez de trocá-los |
| Criado por este programa, mas sem o `.u` | O programa avisa e para. Sem o fonte não dá para saber de quem ele copiou a aparência, e gerar por cima estenderia uma classe que não existe mais |

A classe gerada estende a classe original do NPC — um gremlin continua se
comportando como gremlin. Dá para conferir no `.uc` que sai na pasta de saída:
`class Npc_20001_FX extends gremlin`.

### A coluna "efeito" da lista

Ela mostra o efeito que o NPC acende, venha de onde vier:

- **modo rápido**: a coluna `rb_effect` do `npcgrp.dat`. Neste cliente, 25 NPCs
  a usam — são os chefes, com a auréola;
- **modo script**: o efeito está dentro do pacote `.u` do NPC, e não no `.dat`.
  O programa abre o pacote e lê o fonte guardado nele.

A coluna `effect` do `npcgrp.dat` **não** é mostrada de propósito: ela vale
`LineageEffect.p_u002_a` em todos os 6541 NPCs do cliente — é o efeito genérico
de nascimento e morte, e não diz nada sobre o NPC.

### Remover um NPC criado

O botão **NPCs criados…** lista o que este programa criou *neste* cliente, lido
do próprio `npcgrp.dat` — não de um registro à parte, que ficaria desatualizado
na primeira troca de cliente ou restauração de backup.

Remover é cirúrgico: tira a linha daquele id do `npcgrp.dat`, o nome dele do
`npcname-e.dat`, e apaga o `FX_<id>.u`. Não restaura backup — restaurar traria
o arquivo inteiro como estava antes e levaria junto todos os outros NPCs
criados depois.

Verificado na prática: depois de criar, instalar e remover, os dois `.dat`
voltam **byte a byte** ao que eram antes.

Do lado do servidor ainda é preciso apagar `data/xml/npcs/custom/npc_<id>.xml`
e dar `//reload npc` — o programa avisa, mas não mexe na pasta do servidor.

### Editar um NPC já criado

**Duplo clique** nele na lista de NPCs criados (ou o botão *Editar*): o
formulário volta a ficar como estava quando ele foi feito — NPC base
selecionado, efeitos na lista, osso, altura, escala, id e nome. Mude o que
quiser e clique em *Gerar*; o programa oferece substituir, e a linha antiga sai
para a nova entrar no lugar.

Nada disso vem de um registro paralelo. O UCC guarda o `.uc` dentro do próprio
pacote compilado, e o programa escreve ali tudo o que usou: o NPC base no
cabeçalho e uma linha `Acender(...)` por emissor, com caminho, osso, altura e
escala. Ler de volta do pacote instalado é mais confiável do que manter um
arquivo à parte — se o pacote está no cliente, foi ele que gerou o que se vê em
jogo.

### Antes de gravar, ele confere

Toda gravação do `npcgrp.dat` passa por um teste: o arquivo é lido, remontado
sem nenhuma alteração e comparado byte a byte com o original. Se a volta não
reproduzir a ida, **nada é gravado**. O motivo é que um erro aqui não dá
mensagem de erro — dá um cliente carregando NPCs com os campos deslocados.

### Gerar e instalar são separados

**Gerar** escreve tudo em `saida/npc/` e não toca no cliente. Você confere o
que saiu e só então clica em **Instalar no cliente**, que copia por cima
guardando antes o que estava lá em `system/backup_npc/`, com data no nome.

---

### O lado do servidor

O cliente sozinho não faz NPC nenhum aparecer — ele só desenha o que o
servidor mandar nascer. Por isso é gerado também um `npc_<id>.xml` no formato
do L2J/aCis: copie para `data/xml/npcs/custom/`, reinicie o gameserver e use
`//spawn <id>`.

### Se alguma coisa der errado

O programa deixa dois arquivos ao lado do executável:

| arquivo | o que tem dentro |
|---|---|
| `npc.log` | tudo o que a aba mostrou no andamento, com hora, recomeçado a cada abertura |
| `erros.log` | qualquer falha, com o rastro completo |

Eles existem porque uma janela que fecha leva o andamento junto, e sem rastro
em disco não sobra nada para investigar. Se o programa fechar sozinho, a última
linha do `npc.log` diz em que etapa ele estava.

Há também um modo que faz tudo sozinho, para conferir se a máquina está em
ordem sem depender de você clicar em nada:

```bat
L2PackTool.exe --autoteste
```

Ele lista as ferramentas encontradas, lê o cliente, cria um NPC de teste (id
`59999`) e escreve o resultado no `erros.log`. **Não instala nada no cliente.**

### O que ele não consegue ler

Alguns pacotes usam proteção própria e não abrem. Eles aparecem no andamento,
com nome e motivo, em vez de sumirem em silêncio — um catálogo incompleto que
não avisa é pior do que um que admite o que faltou.

---

## A aba "Lobby Vídeo"

Põe o seu vídeo na tela de login. Escolher o vídeo, cortar o trecho na régua,
olhar a prévia, aplicar.

**Os lobbys vêm dentro do programa**, sete deles, compactados. Não há pasta
para apontar, nada é procurado no cliente, e não é preciso que ele já tenha um
lobby de vídeo: funciona em cliente que nunca teve um.

| lobby | o que é |
| --- | --- |
| **L2PackTool** | o que recebe vídeo. Cenário próprio, câmera fixa, tela montada na instalação |
| **C1 a C6** | os lobbys originais de cada crônica, de Harbingers of War a Interlude |

São 48 MB somados — crus seriam 90. O programa lê de cada zip só o cartão de
visita para montar a lista; o escolhido é aberto numa pasta temporária na hora
de instalar e some depois. Acrescentar outro lobby é largar outro `.zip` em
`recursos/lobbies`, com as pastas do cliente dentro (`maps`, `staticmeshes`,
`textures`, `music`, `system`) — não há nada a recompilar.

### Dois caminhos

**Instalar lobby** põe no cliente o que estiver escolhido, do jeito que é:
mapa, cenário, texturas, a música daquela crônica e o `logongrp.dat` dela.
Serve a quem só quer trocar a tela de entrada.

**Gerar vídeo e instalar** monta o filme no lobby do L2PackTool. Ele é o único
com tela de vídeo; escolhendo outro na lista e clicando aqui, o programa usa o
do L2PackTool e diz isso no registro.

Os pacotes entram no cliente com o nome do sistema — `L2PackTool.usx` para o
vídeo, `L2PackTool_lobby.usx` para o cenário. Renomear o arquivo não bastaria:
o mapa procura o pacote pelo nome, e esse nome é trocado dentro dele também.

### A câmera fica parada, e a tela cobre a janela

Um lobby tem três cenas — login, seleção e criação de personagem — e cada uma é
uma lista de ações de câmera. Para vídeo só serve a ação que **põe** a câmera no
ponto; a que a **leva** por um percurso recomeça toda vez que a tela é montada,
e a de login é montada mais de uma vez: ao abrir o jogo, ao voltar da seleção,
ao cair a conexão. Com percurso, cada volta pega a câmera num lugar diferente e
o filme aparece cortado ou torto. Na instalação, a cena de login passa a ter uma
ação só, e ela é um salto. As outras duas telas não são tocadas.

O tamanho da tela sai de conta. A malha mede 2048 por 1152,7 unidades e a
câmera abre 50 graus, o que dá, para cada distância, quanto da janela o filme
cobre. O programa calcula a escala que cobre a tela mais exigente de uso comum
— a de 5 por 4 — e com isso cobre todas: 4:3, 16:10, 16:9 e ultralarga. Cobrir
custa as beiradas do filme: num notebook vê-se cerca de 70% da altura. Atrás da
tela fica um painel preto, colado nela, para não aparecer cenário no que sobrar.

Depois de copiar, o programa **confere**: abre cada pacote que o mapa usa e vê
se o que ele procura está lá dentro. Pacote existir não garante nada — o que
deixa o cenário sem textura é faltar um objeto dentro dele. Pacote que não se
consegue abrir não vira falta; falta é o que se prova ausente.

### Como um lobby de vídeo é feito

Vale contar, porque a resposta óbvia está errada e custou caro descobrir.

A hipótese razoável era animar uma textura do lobby com a corrente `AnimNext` —
que é como o próprio cliente anima fogo e água, e o `FX_E_T.utx` de fábrica traz
81 correntes dessas. Isso funciona em tudo o que dá para conferir de fora: a
propriedade é escrita, o umodel lê a corrente inteira, o cliente carrega o
pacote sem reclamar. E na tela não acontece nada.

Um lobby de vídeo pronto mostrou o motivo. Por dentro, ele é assim:

```
demev  (MaterialSequence)  um item por quadro {Material, Time, Action}
Shg1   (Shader)            Diffuse = demev, SelfIllumination = demev
seq    (StaticMesh)        Materials[0] = Shg1   ← a tela: 4 vértices, 2 faces
blk    (Texture)           preta, que o mapa importa pelo nome
```

`MaterialSequence` é o material feito para tocar uma **lista de materiais no
tempo**; `AnimNext` anima textura de partícula. Era a ferramenta errada para o
serviço. A malha `seq` é um plano na frente da câmera, e é ele que você vê.

O quadro é 2048×2048 com o vídeo em 16:9 (2048×1152) centralizado e faixa preta
em cima e embaixo. A faixa existe porque o Unreal 2 quer textura em potência de
dois, e 2048×1152 não é; a malha amostra só a faixa do meio, então no jogo a
borda preta não aparece. O programa mede isso no modelo em vez de supor.

### O que é gerado e o que vem do modelo

**Escrito byte a byte pelo programa**: os quadros, o `MaterialSequence`, o
`Shader` e o `ConstantColor`. Nada disso passa pelo `ucc` — o pacote sai no
mesmo licenciado do modelo, e o formato de cada objeto foi lido de um lobby que
funciona.

**Copiado do lobby**: o `Lobby.unr` da cena; o `logongrp.dat`, que diz onde
cada personagem fica parado dentro dela; e os **543 bytes nativos da malha
`seq`** — geometria, caixa envolvente e árvore de colisão. Escrever isso à mão seria chute caro. É por isso que o
modelo existe, e é por isso que **tudo isso tem de ser do mesmo modelo**: cada
lobby põe a tela no seu próprio tamanho e lugar, e as posições dos personagens
são coordenadas daquela cena. Vêm embutidos e casados, então não há como errar
o par.

O `logongrp.dat` é o que mais passa despercebido. Instalar o lobby sem ele não
dá erro nenhum: o vídeo toca, e os personagens aparecem nas posições do lobby
anterior — dentro de uma parede, de costas, ou fora do quadro. Ele vai para
`system/`, e o que estava lá é guardado em `system/backup_lobby/` com a data no
nome, mesmo quando as cópias de segurança estão desligadas: são 304 bytes, e
não se refazem.

Três detalhes que só aparecem quando se tenta:

- Os INT dentro da malha que apontam para ela mesma são `TLazyArray`: guardam
  **posição absoluta**. Copiando a malha para outro arquivo, cada um é
  recalculado — o que se mantém é a distância até o fim do objeto.
- Todo material do pacote carrega um rabo de 4 bytes que muda de pacote para
  pacote (`00 d9 b4 00` num, `c0 be ab 0f` noutro). Vem do modelo, não é
  suposto.
- Booleano se grava com **código de tamanho 5 e tamanho zero** (`53 00`), e não
  com código 0. Com código 0, quem lê entende que há um byte de valor e come o
  `None` que fecha a lista. Quem tirou a dúvida foi o `lineagemonsterstex.utx`
  do próprio jogo.

### A régua de corte

Ela escolhe que trecho do vídeo vira o lobby, e o resto sai sozinho: o número de
quadros é **cadência do vídeo × duração do trecho**, o que faz o filme rodar na
velocidade do arquivo original. O `-ss` do ffmpeg vem antes do `-i`, para ele
saltar direto ao ponto em vez de decodificar o vídeo inteiro até lá.

Cada quadro custa dois megabytes no pacote, então trecho curto é pacote pequeno.
Um vídeo de 20 s a 60 quadros por segundo pediria 1201 quadros e 2,4 GB; o
programa reduz a cadência até caber no orçamento e diz na tela que reduziu.

**Repetir sem parar no jogo** grava a propriedade `Loop` na sequência. Sem ela o
filme toca uma vez, congela no último quadro e só recomeça quando o próprio
lobby reinicia.

### A logo

Uma imagem por cima do vídeo, aplicada aos quadros gerados. Escolha a imagem,
o tamanho e a posição; a prévia mostra o resultado com o vídeo rodando por
baixo.

Tamanho e posição são guardados em **porcentagem da área visível**, e não em
pixels. É o que faz a prévia (640 de largura) e o quadro final (2048) caírem no
mesmo lugar — em pixels, a logo sairia três vezes maior num do que no outro. O
letterbox também é levado em conta: a posição vertical é medida dentro da faixa
útil, senão a logo subiria 448 pixels ao ir para o jogo.

Transparência de PNG é preservada.

**Só num trecho** faz a logo aparecer entre dois tempos, contados a partir do
início do trecho escolhido na régua. Desmarcado, ela fica o vídeo inteiro.

A logo entra no mesmo filtro que gera os quadros, então a prévia e o resultado
final são a mesma conta rodando em tamanhos diferentes:

```
[0:v] fps,scale,pad [base] ; [1:v] scale=L:-1 [marca] ;
[base][marca] overlay=X:Y:enable='between(t,A,B)'
```

### A prévia responde na hora

O vídeo é amostrado **uma vez, inteiro**, quando você o escolhe. Daí em diante
a régua de corte só escolhe quais desses quadros entram — sem chamar o ffmpeg
de novo, sem espera.

A razão está na medição, num MP4 de 3840×2160 a 60 quadros por segundo:

```
150 quadros de  5 s → 18,6 s        40 quadros de  5 s → 13,8 s
150 quadros de 20 s → 48,2 s        40 quadros de 20 s → 45,4 s
```

O custo acompanha a **duração decodificada**, não a quantidade de quadros
pedida. Extrair a cada movimento da régua seria pagar dezenas de segundos por
movimento.

A logo segue o mesmo princípio: ela é desenhada sobre a prévia, não embutida
nos quadros dela. Arrastar move um item na tela e o tamanho reescala uma imagem
pequena — as duas coisas são instantâneas, e o vídeo continua rodando por
baixo. No pacote final a logo entra pelo ffmpeg, com a mesma fração de posição
e tamanho.

### A prévia, e o que ela garante

**Do vídeo escolhido**: sai do mesmo ffmpeg que vai gerar os quadros de verdade,
com o mesmo enquadramento e na mesma velocidade. A faixa preta não entra, porque
a tela do lobby também não a mostra. Duas diferenças, ditas na cara: é menor, e
passa menos quadros no mesmo tempo. E a cor ainda não passou pela compressão
DXT1.

**Do pacote**: os bytes saem do arquivo instalado, ganham um cabeçalho DDS e
viram imagem — o Pillow decodifica DXT1 sozinho. A ordem das operações importa
mais do que parece: cortar e encolher **antes** de converter para RGB deixa o
trabalho cinco vezes mais rápido, porque `convert()` obriga o Pillow a
decodificar o quadro inteiro de uma vez — trinta quadros de 2048×2048 caem de
8,5 s para 1,7 s. Aqui não sobra ressalva: é o que o cliente vai desenhar.

A prévia anda pelo **relógio**, e não contando `after()`: contar acumula atraso,
e em duzentos quadros o filme ficaria visivelmente mais lento do que o do jogo.
Se a máquina engasgar, ela pula quadro em vez de atrasar o filme.

### Feche o cliente antes

Pacote aberto pelo jogo não pode ser gravado, e o Windows recusa com "o arquivo
já está sendo usado por outro processo".

---

## A aba "Itens"

Cria um item novo — arma, armadura ou consumível — copiando um que já existe
no cliente.

Um item mora em dois lugares ao mesmo tempo, e os dois têm de concordar:

| Arquivo | O que guarda |
| --- | --- |
| `weapongrp.dat` | armas: malha, textura, ícone, som, tipo de cristal |
| `armorgrp.dat` | armaduras: o mesmo, para cada combinação de raça e sexo |
| `etcitemgrp.dat` | o resto: poções, materiais, flechas |
| `itemname-e.dat` | o nome, o destaque e a descrição |

O cliente casa as duas metades pelo **id**. Escrever só numa delas produz item
sem nome, ou nome sem item — e nenhum dos dois casos dá erro. Dá confusão.

### Editar e criar são dois assuntos

O mesmo da aba de Habilidades, pelo mesmo motivo. O modo fica escrito em letras
grandes no alto do painel:

```
Editando o item 1 — Short Sword
Item novo 30000, copiado do 1
```

**Clicar na lista edita**: o id passa a ser o do item marcado, o campo trava, e
o botão vira `Regravar o item`. **`Novo item…`** abre a janela que pergunta id,
nome, destaque, descrição e ícone, recusa um id que já exista sem a marca de
substituir, e avisa quando o id cai na faixa do jogo.

O **destaque** é a palavra que o jogo desenha em dourado ao lado do nome, na
dica do item: `Legendary`, `Light`, o grau do conjunto. Sai da coluna
`add_name` do `itemname-e`. Numa cópia ele vem preenchido com o do item base —
apagar o campo tira a palavra da cópia, sem tocar no original. Depois de gerar, a tela passa a editar o
que acabou de sair.

**Duplo clique numa linha da tabela de status** devolve operação, status e valor
para os campos de cima, e o botão vira `Guardar`.

### Por que copiar em vez de criar do zero

Uma linha do `armorgrp` tem **332 colunas**. As que têm a ver com aparência são
umas poucas; o resto é peso, som ao equipar, tipo de cristal, e a malha e a
textura de cada uma das doze combinações de raça e sexo. Inventar esses valores
dá um item que existe e está errado. Herdá-los de um item que o cliente já
desenha é a diferença entre "funciona" e "quase".

Por isso o fluxo é: escolha o item base na lista, mude o id, o nome e o ícone,
e o resto vem junto.

### A definição da tabela, e a prova antes de gravar

Um `.dat` é um binário sem cabeçalho de formato. Quem diz onde cada campo
começa é uma definição `.ddf` — e uma definição errada não dá erro: ela lê
campos deslocados e grava lixo por cima da tabela. O sintoma aparece no jogo,
depois.

Duas defesas:

1. **A definição é medida neste cliente.** As definições base ficam junto do
   programa, mas elas descrevem os campos, não quantas colunas cada tabela
   dinâmica tem — e isso muda de cliente para cliente. O programa mede no
   arquivo do usuário antes de ler qualquer coisa.

2. **A ida e volta.** Ao abrir, cada uma das quatro tabelas é remontada sem
   nenhuma alteração e comparada com o binário original. Se a volta não
   reproduz a ida byte a byte, a definição não descreve este cliente, e gravar
   fica bloqueado. O resultado de cada tabela aparece no andamento.

### Ler do servidor

O cliente guarda aparência, peso e material. **Dano, defesa e preço não existem
nele** — são só do servidor. Até aqui, criar um item a partir de outro obrigava
a digitar tudo isso de novo.

**Ler do servidor** procura o item na pasta de dados e traz o que ele tem: os
campos e o bloco de status. Lê o item **marcado na lista** — e não o do campo
**id novo**, pela mesma razão que na aba de NPC. Não achando, o programa avisa,
e é o caso de preencher e gerar.

Na Long Sword do aCis, volta com `price 136000`, `material FINE_STEEL` e os
quatro status (`pAtk 24`, `mAtk 17`, `rCrit 8`, `pAtkSpd 379`). Nos cores de
banco, volta da tabela `weapon`/`armor`/`etcitem`, com as colunas de combate
(`p_dam`, `p_def`, `critical`) convertidas de volta para o bloco de status — que
é onde o XML as põe.

### O ícone na tela

Procurar "Long Sword" numa lista de 9.534 linhas é uma coisa; ver a espada é
outra. O ícone do item selecionado é lido direto do pacote do cliente e
mostrado ao lado do formulário, **no tamanho em que o jogo o desenha**: 32×32.
Ampliar não acrescenta informação nenhuma — só borra o desenho.

O botão **Escolher…** abre a lista completa de ícones instalados, com filtro e
prévia. Neste cliente são 13.690, somados de `system/Icon.u`,
`systextures/Icon.utx` e dos pacotes de ícone avulsos que foram instalados por
cima. Digitar no filtro reduz a lista; clicar mostra o desenho.

A lista de itens também não tem corte: as 9.534 linhas entram em 0,16 s, e
limitar a lista escondia justamente o item que se estava procurando.

### Vários itens seguidos

Depois de gerar, a tela já se prepara para o próximo: sugere o id livre
seguinte, limpa nome, descrição e status, e mantém o item base selecionado. O
botão **Limpar para outro** faz o mesmo a qualquer momento.

Cada geração acumula nas mesmas tabelas — dez itens criados em sequência saem
num `weapongrp.dat` só, instalado de uma vez.

### O XML do servidor

Sai da mesma tela, na aba **XML do servidor**, no formato do aCis.

**O que já vem preenchido** é o que existe na tabela do cliente: peso,
material, grau de cristal, parte do corpo, tipo de arma, soulshots. O cliente
guarda isso como número e o servidor escreve por nome, e a correspondência
entre os dois não está documentada em lugar nenhum — foi deduzida cruzando os
9.208 itens que existem nos dois lados. Cada número caiu sempre no mesmo nome:

| campo | acerto |
| --- | --- |
| grau de cristal | 100% |
| material | 100% |
| peso | 100% |
| parte do corpo | 98% |
| tipo de arma | 96% |
| tipo de armadura | 95% |

Um caso que só aparece assim: **escudo mora no `weapongrp` do cliente, mas para
o servidor é `Armor`**. São 95 escudos, todos com `body_part` 8, e todos
`type="Armor"` no datapack — sem uma exceção. Gerado como `Weapon`, o
personagem empunharia o escudo como arma. O programa detecta e já marca o tipo
certo.

**O que não vem preenchido** é o que não existe no cliente: dano, defesa,
preço. Inventá-los produziria um item que existe e está errado, que é pior do
que um item que precisa ser completado.

### Os status

O bloco `<for>` do XML é montado na tela: escolha a operação, o status e o
valor, e acrescente. Saem assim:

```xml
<for>
    <set stat="pAtk" val="120" />
    <add stat="maxHp" val="500" />
    <enchant stat="pDef" val="3" />
</for>
```

A **operação** diz como o valor entra na conta:

| | |
| --- | --- |
| `add` | soma ao total já calculado |
| `baseadd` | soma à base, antes dos multiplicadores |
| `sub` | subtrai |
| `mul` / `basemul` / `div` | multiplica ou divide |
| `set` | fixa o valor |
| `enchant` | a parcela que cresce a cada encantamento |
| `addMul` / `subDiv` | as duas combinações restantes |

Os **122 status** oferecidos estão agrupados — vida e mana, ataque e defesa,
taxas e esquiva, atributos, PvP, resistência a elementos, vulnerabilidades,
reflexo, contra tipo de criatura, limites. São os nomes lidos do `Stats.java`
do próprio servidor, e não de uma lista de internet.

Isso importa mais do que parece: um nome de status que o servidor não conhece
**não é ignorado**. Ele lança `NoSuchElementException` e derruba o carregamento
da tabela de itens inteira — todos os itens do servidor, não só o novo. É por
isso que a tela oferece escolha em lista e não campo de texto livre.

O mesmo vale para material, grau, parte do corpo e tipo: todos vêm de listas
tiradas dos enums do servidor.

**Ver o XML** mostra o resultado antes de gerar. Ao gerar, o arquivo sai junto
das tabelas, com o nome `<id>-item.xml`.

### O manual

O botão **Manual**, no rodapé da aba, abre um texto que acompanha o preenchimento
de ponta a ponta: o que é cada campo, que valor se costuma pôr, qual operação
usar em arma, em armadura, em escudo e em acessório, e o que fazer quando alguma
coisa dá errado.

Ele existe porque a dica de canto de tela responde "o que é este campo" e não
"o que eu faço agora" — e vinte balõezinhos soltos não somam um fio de
raciocínio. O texto tem busca, e vem em português, inglês e espanhol; faltando o
idioma escolhido, vale o português.

### Escolher o ícone vendo

`icon.skill1345` não diz nada, e são **13.690** deles. Escolher ícone por nome
não é escolher — por isso a janela de criar (item ou habilidade) traz uma
**grade de miniaturas** no lado direito, com a arte no tamanho em que o jogo a
desenha.

A grade mostra 240 por vez. Montar catorze mil miniaturas congelaria a janela
por minutos, e ninguém olha catorze mil ícones — quem procura, filtra; o rótulo
diz quantos ficaram de fora. As miniaturas chegam por uma thread, uma a uma,
então a janela responde desde o primeiro instante.

**A ordem não é alfabética: é por parecença com o ícone da base.** Copiando a
habilidade 1, a grade abre em `icon.skill0000`, `icon.skill0001`, `icon.skill0002`;
copiando uma Short Sword, abre em `icon.weapon_*`. Duas voltas decidem: o nome
sem os dígitos (`skill0001` → `skill`) e, mais larga, a família antes do
primeiro sublinhado (`weapon_small_sword_i00` → `weapon`).

Um **filtro fixo** faria o mesmo trabalho e seria pior: esconderia os pacotes
próprios de quem usa o programa. Uma ordem só muda por onde se começa a olhar.

### Ícone próprio

A mesma janela aceita um desenho seu — PNG, JPG, BMP, TGA, DDS — e faz o
caminho inteiro:

```
imagem  →  32×32 RGBA  →  DDS comprimido  →  ucc make  →  .utx Ver121  →  systextures/
```

Leva cerca de 2,5 segundos. O campo do ícone já recebe a referência pronta.

**Preparado, e não instalado.** O pacote fica na pasta de saída junto com as
tabelas e entra no cliente no mesmo **Instalar no cliente** — uma ação, um
lugar. A versão anterior instalava na hora, e isso põe um ícone dentro do
cliente enquanto a habilidade dele ainda não existe em lugar nenhum: um
meio-termo que ninguém pediu e que só aparece quando alguém estranha um ícone
solto.

Imagem que não é quadrada entra **centralizada** num quadrado transparente, e
não esticada: esticar um retângulo para 32×32 deforma o desenho.

**O pacote é seu.** O programa nunca grava dentro do `Icon.utx` ou do `Icon.u`
do jogo, e recusa se você tentar. A razão é de risco: um erro no pacote próprio
custa um ícone, e no do jogo custaria os catorze mil que já estão lá. Não há
perda — o cliente resolve `Pacote.Objeto` procurando `Pacote.utx` nas pastas de
textura, e este cliente já carrega vários pacotes de ícone avulsos
(`IconsByAllInOne`, `MAYKE_MENDES_ICON`, `cartola_by_SHEV`).

Acrescentar um segundo ícone ao mesmo pacote **remonta o pacote inteiro**: os
que já estavam são extraídos de volta e entram junto. É mais lento, e é o único
jeito honesto — meia remontagem perderia os antigos.

O nome do arquivo importa de verdade: a chave do Ver121 deriva dele, então
renomear o pacote depois de criado o corrompe. O que já estava lá vai para
`systextures/backup_icones/` com a data no nome.

O ícone criado fica disponível para item e para habilidade — é o mesmo campo de
texto nos dois lados.

---

### O id

O id é o que amarra o cliente ao servidor. **Sugerir** procura o primeiro id
livre a partir de 30000, longe da faixa do jogo original — escrever por cima de
um item que existe é o erro mais caro aqui. Um id abaixo disso pede
confirmação.

### Trocar a aparência de um item que já existe

O botão **Trocar aparência…** muda para onde um item aponta, **sem criar item
novo**: o id e o nome ficam.

Não há lista fixa de campos, porque ela muda com a tabela: uma arma aponta para
23 objetos, uma armadura para 38 — cada combinação de raça e sexo tem o seu par
de malha e textura. A janela mostra toda coluna cujo valor tem a forma
`pacote.objeto`, que é o formato de referência, e deixa trocar qualquer uma.

**Trocar o pacote em bloco** existe porque é assim que um pack de retextura
chega: os mesmos nomes de objeto, noutro pacote. Trocar 38 referências à mão
seria o caminho para errar uma.

A troca fica na memória; **Gerar** escreve as tabelas e **Instalar no cliente**
as põe no lugar, como em qualquer outra alteração da aba.

### Gerar, instalar, restaurar

**Gerar** escreve as tabelas alteradas numa pasta à parte, sem tocar no
cliente. **Instalar no cliente** as põe no lugar — e, na primeira vez, guarda
as originais em `system/backup_itens`. **Restaurar originais** traz aquelas
cópias de volta, desfazendo tudo de uma vez.

Feche o cliente antes de instalar: o jogo aberto mantém as tabelas em memória e
grava por cima ao sair.

### A janela "Novo item", e o caso da arma

A janela é um caderno de quatro páginas. Quando a base é uma arma, todas as
quatro aparecem:

| página | o que é |
| --- | --- |
| Identificação | id, nome, descrição, ícone |
| Números | as colunas do `weapongrp.dat` — a tooltip do inventário |
| Status | o bloco `<for>` do servidor — o que o golpe faz |
| Skills | `item_skill` e as três irmãs |

**Números e Status são lados diferentes da mesma arma, e podem discordar sem
que nenhum reclame.** A Draconic Bow deste cliente mostra 581 de P.Atk na
tooltip e o servidor usa 561: os dois arquivos estão certos, cada um no seu
papel, e o jogador lê um número e bate com outro.

A correspondência entre os dois lados foi conferida item a item contra o
datapack:

| cliente | servidor |
| --- | --- |
| `patt` / `matt` | `pAtk` / `mAtk` |
| `critical` | `rCrit` |
| `speed` | `pAtkSpd` |
| `hit_mod` | `accCombat` |
| `avoid_mod` | `rEvas` |
| `shield_pdef` / `shield_rate` | `sDef` / `rShld` |

`hit_mod` e `avoid_mod` são os únicos com sinal no cliente; do lado do servidor
o sinal vira a operação — `-3` no cliente é `<sub stat="accCombat" val="3">`. O
botão **Copiar para os Status** faz a tradução inteira, com a operação e a ordem
certas.

### O `a,` no nome do item, que era um defeito

O programa escrevia `a,Draconic Bow` na coluna `name` do `itemname-e.dat`, e o
cliente mostrava exatamente isso -- com o `a,` a vista, no inventario.

O defeito se escondeu porque a leitura tirava o proprio prefixo: `_limpar` corta
`a,` do comeco, entao a ida e a volta pelo programa pareciam certas. Foi
contando as 9.432 linhas do arquivo que ele apareceu:

| coluna | com prefixo | sem |
| --- | --- | --- |
| `name` | **1** (a que este programa criou) | 9.431 |
| `description` | 9.432 | 0 |

E nenhuma das 9.432 descricoes termina em `\0`, que o programa tambem
acrescentava. Os dois vieram de suposicao, e nao do arquivo.

Corrigido: nome cru, descricao com `a,` e sem `\0`. **Item ja criado com o
prefixo se conserta regravando** -- `definir_nome` reescreve a linha que ja
existe.

### Skill em item

Neste core não existe `<skill>` dentro de `<item>` — em nenhum dos 9.201 do
datapack. São campos `<set>`, com o id e o nível escritos juntos:

| campo | quando vale | quantas |
| --- | --- | --- |
| `item_skill` | enquanto equipado | várias, separadas por `;` |
| `enchant4_skill` | a partir do +4 | uma |
| `oncrit_skill` + `oncrit_chance` | ao dar crítico | uma |
| `oncast_skill` + `oncast_chance` | ao castar | uma |

Cuidado com a chance. O core faz `if (id > 0 && level > 0 && chance > 0)`:
faltando a chance, ou com ela em zero, a skill é **descartada sem uma linha de
log**. O servidor sobe, a arma não faz nada, e quem testar vai culpar a
habilidade. A janela confere antes de deixar passar.

### O `order`, que era um defeito

Até esta versão o programa escrevia `<add stat="pAtk" val="150" />`, sem
`order`. O core lê o atributo sem verificar se ele existe:

```java
String order = n.getAttributes().getNamedItem("order").getNodeValue();
```

Sem ele, a leitura estoura e a **tabela de itens inteira** deixa de carregar —
os 9.201, não só o novo. Nos 4.736 status do datapack, zero estão sem `order`.

Agora ele é sempre escrito, com o que o jogo usa para cada operação: `set` em
`0x08`, `enchant` em `0x0C`, `add` e `sub` em `0x10`, `mul` em `0x30`. A caixa
fica à vista e pode ser trocada; `0x40` é a soma que entra depois dos
multiplicadores.

**Quem já gerou item com status por uma versão anterior precisa regravá-lo.**

### Os status que o seu servidor conhece

A lista de status é do programa, e nem todo core tem todos os nomes dela. No
aCis deste servidor, sete dos 122 não existem — e um nome desconhecido não é
ignorado: `Stats.valueOfXml` lança `NoSuchElementException` e a carga para.

**Conferir com o servidor** lê a pasta apontada e marca com ⚠ os que faltam.
Quando o código-fonte está junto da pasta de dados, a resposta sai do
`Stats.java` dele e é completa — foi assim que os 121 deste servidor foram
lidos. Quando só há os `.jar`, sai dos `stat="..."` que o datapack usa: menor,
mas todo nome ali é prova de que sobe.

---

## A aba "Habilidades"

Cria uma habilidade nova copiando uma que já existe. Mesmo desenho da aba de
Itens, com uma diferença que muda tudo: **habilidade tem nível**.

Ela não é uma linha, é um bloco de linhas — uma por nível — em cada tabela:

| Arquivo | O que guarda |
| --- | --- |
| `skillgrp.dat` | ícone, mana, alcance, tempo de uso — por nível |
| `skillname-e.dat` | nome e descrição — por nível |

Neste cliente são **3.067 habilidades em 42.019 linhas**. A lista mostra uma
linha por habilidade, e não por nível: a lista por nível teria 42 mil entradas
com a mesma habilidade repetida quarenta vezes.

Copiar leva todos os níveis, nas duas tabelas, de uma vez. Meia cópia produz a
habilidade que existe até o nível 12 e some no 13.

### Editar e criar são dois assuntos

A tela começou como um formulário só, chamado "Habilidade nova", que também
servia para olhar uma que já existe. Dava para marcar a 12610 na lista, ver os
dados dela no formulário, e o campo do id mostrar **90000** — dois assuntos no
mesmo lugar, sem nada dizendo qual valia. Foi assim que a tela trouxe a 90000
quando se pediu a 1.

Agora há um **modo**, escrito em letras grandes no alto do painel:

```
Editando a habilidade 1086 — Might
Nova habilidade 90000, copiada da 1086
```

**Clicar na lista edita.** O id passa a ser o da habilidade marcada e o campo
fica travado: mudar o número ali era, na verdade, criar outra. O botão muda de
`Gerar` para `Regravar a habilidade`, e pergunta antes.

**Criar passa por uma janela própria.** `Nova habilidade…` abre um diálogo que
pergunta o id (com Sugerir), nome, descrição, ícone e o corte de nível, recusa
um id que já exista sem a marca de substituir, e avisa se o id cair na faixa do
jogo. O que sai dali preenche o painel, que passa ao modo "nova" — e os campos
continuam editáveis: é um começo guiado, não uma cerca.

Depois de gerar, a tela passa a **editar o que acabou de sair**. Antes ela se
limpava e sugeria o próximo id, o que empurrava para criar outra e deixava a
recém-criada sem jeito óbvio de reabrir.

### Ajustar um status sem refazê-lo

Duplo clique numa linha da tabela de status devolve **operação, status e
valor** para os campos de cima, e o botão vira `Guardar`. Antes, trocar `1.30`
por `1.25` exigia tirar a linha e escrever os três campos de novo — com chance
de errar o que estava certo.

### Copiar até o nível

Existe por causa das **rotas de encantamento**. A habilidade 50002 tem 6.410
níveis; clonar isso por engano dobra a tabela sem servir para nada. Em branco a
cópia leva tudo, e acima de 100 níveis o programa pergunta antes.

### O que vem do cliente

Modo (ativa, passiva, alternável), mana por uso, alcance e tempo de uso são
lidos do `skillgrp`. O `hit_time` do cliente é em segundos e o servidor conta em
milissegundos — a conversão é feita.

O resto é escolhido em lista: 96 tipos de efeito, 28 alvos, 3 modos, 8
elementos, mais os 122 status do bloco `<for>`, os mesmos dos itens. Todos
lidos do código do seu servidor, pelo mesmo motivo de sempre: um nome que ele
não conhece derruba o carregamento da tabela de habilidades inteira.

### Ler do servidor

O mesmo da aba de Itens, pelo mesmo motivo: **poder, recarga e tipo de efeito
não existem no cliente**. O `skillgrp` guarda ícone, mana, alcance e tempo de
uso, e mais nada.

Na Power Strike do aCis, volta com `skillType PDAM`, `reuseDelay 13000`,
`weaponsAllowed SWORD,BLUNT,BIGBLUNT,BIGSWORD` e `overHit true`.

A leitura **abre as tabelas**: `#power` volta como os 37 números dele, que é
exatamente o que o campo aceita de volta. Dá para ler uma habilidade pronta,
mexer no nível 5 e regravar.

A versão anterior mostrava o apelido `#power` e avisava que havia uma tabela.
Era honesto e inútil: não dava para editar, e regravar escreveria
`val="#power"` apontando para uma tabela que o XML novo não teria — uma
habilidade quebrada, sem nada avisando.

Habilidade é XML **até nos cores de banco**: o L2jFrozen guarda item e NPC em
tabelas, mas as habilidades ficam em arquivo. Por isso aqui só há o caminho do
XML, e isso não é um buraco.

### Valor por nível

O "Power 25" que vira "Power 27" não é um número: é uma lista com um valor por
nível, e o jogo a escreve com `<table>`.

**Basta escrever os valores separados por espaço**, em qualquer campo do XML ou
na coluna `valor` de um status. O programa monta a tabela e aponta o `<set>`
para ela:

```
power:  431 458 486 516 547
```
```xml
<table name="#power"> 431 458 486 516 547 </table>
<set name="power" val="#power" />
```

Vírgula e ponto-e-vírgula valem como espaço. Um campo com texto —
`SWORD,BLUNT` — continua sendo um valor só: aquilo é uma lista de armas, não
uma progressão.

O formato foi lido do datapack do L2J e conferido no servidor do próprio
usuário, que tem **5.020 tabelas** dentro. Três coisas saíram dessa leitura: as
tabelas vêm antes dos `<set>`; os valores são separados por espaço; e a
referência `#nome` vale também **dentro do `<for>`** — lá há 608 blocos assim,
incluindo `<add order="0x40" stat="runSpd" val="#spd"/>`.

E uma regra que não está escrita em lugar nenhum: **a tabela precisa ter
exatamente `levels` números**. Uma a menos não dá erro ao gravar — o servidor é
que derruba a habilidade, ou entrega o nível errado, muito depois. O programa
confere e avisa antes de gerar.

### O que a tela não faz

Fica de fora o `<effect>` dentro do `<for>` — veneno por segundo,
transformação, invocação — e o `<cond>` que exige arma ou classe. O XML gerado é
a base correta; isso se acrescenta por cima.

O botão **Manual** abre o texto que acompanha o preenchimento campo a campo,
com a tabela dos tipos de efeito e o que cada um significa.

---

## A aba "Glow"

Poe o efeito de particula que acompanha a arma -- o risco de luz da lamina, o
halo do arco, a aura das armas de boss.

O glow e do **cliente**. Ele mora no `weapongrp.dat`, e nao no servidor: quem
equipa a arma ve o brilho porque o cliente **dele** tem a tabela alterada. Isso
significa que o glow tem de ir no patch, junto com as texturas e as malhas.

### Onde os numeros ficam

Cada arma tem espaco para dois efeitos, cada um com cinco ajustes. A definicao
embutida do `weapongrp.dat` chama cinco dessas colunas de `junk`, porque quem a
escreveu nao sabia o que eram. Os dados deste cliente dizem o que sao:

| coluna | o que e |
| --- | --- |
| `effA` | o efeito -- `LineageEffect.c_u006` |
| `junk1A[0]` | ao longo da lamina, do cabo a ponta |
| `junk1A[1]` | altura |
| `junk1A[2]` | lado |
| `junk1A[3]` | tamanho |
| `junk1A[4]` | intensidade |

**282 das 1.346 armas** deste cliente ja tem glow, em **48 combinacoes
distintas** desses cinco numeros. Se fossem colunas sem uso, ou seriam iguais
em todas, ou seriam ruido; quarenta e oito combinacoes ajustadas e o que prova
que sao ajuste de verdade.

A faixa que o jogo usa: **-20 a 4** no comprimento, **0,80 a 1,55** no tamanho,
**0,20 a 1,00** na intensidade. Nao e limite -- e referencia, para quem digita
saber se esta perto ou longe do que o jogo faz.

### A regua

A direita fica a lamina deitada, com o cabo de um lado e a ponta do outro, e o
circulo laranja onde o glow cai. Os dois numeros das pontas saem da **malha
desta arma**: o `.psk` e exportado do pacote do cliente e medido vertice a
vertice.

Uma arma deita no eixo de maior alcance. A Dragon Slayer vai de **-17,83 a
40,76** no X, e menos de 8 no Y e no Z -- o cabo atras do zero, a lamina toda a
frente. E nesse eixo que o ajuste longitudinal anda.

**A regua nao desenha o glow.** Particula do Unreal Engine 2 so o motor do jogo
desenha -- nem o umodel abre. Ela diz **onde** o efeito vai ficar; como ele
parece, so em jogo. O botao **Ver a arma em 3D** abre a malha no visualizador
do umodel, pelo mesmo motivo: da para ver o formato da arma, nao o brilho.

### Escolher o efeito, e a lista de sugestao

A lista e a mesma da aba de NPC -- todo efeito de particula instalado neste
cliente, e o mesmo cache em disco, para nao varrer 787 MB de pacotes duas
vezes. Sao **1.812**.

A esmagadora maioria nao foi feita para arma: sao auras de NPC, efeitos de
chao, magias. Postos numa espada, ficam do tamanho errado, no lugar errado, ou
simplesmente nao aparecem. Varios sao de cronicas mais novas e nao funcionam em
Interlude -- e o aviso que o tutorial da comunidade da, e ele esta certo.

Por isso a lista abre com **so os que o jogo usa em arma** marcada, e com o
aviso escrito na tela.

**A sugestao nao e uma lista copiada de forum.** Ela e contada no cliente do
usuario: qual efeito o jogo usa em cada tipo de arma. Se o cliente pos `c_u002`
em nove adagas e em mais nada, aquele e o efeito da adaga -- e ele funciona,
porque o jogo o desenha todo dia. Uma lista escrita a mao envelheceria, e o
cliente de quem usa o programa nao e o de quem escreveu o tutorial.

Neste cliente a contagem da 29 efeitos:

| efeito | onde o jogo usa |
| --- | --- |
| `c_u001` | punho (22) |
| `c_u002` | adaga (9) |
| `c_u003` / `c_u008` | arco (9 e 20) |
| `c_u004` | espada, adaga, espadao, dupla (54) |
| `c_u005` / `c_u007` | maca, marreta, lanca |
| `c_u006` | espada (18) |
| `c_u000` | espadao (5) |
| `e_u092_a`..`e_u092_k` | hero glow, um por tipo de arma |
| `SHEV_weapon_shadow_*` | as shadow weapons deste servidor |

A correspondencia do hero glow bate com a que o tutorial publica -- a = espada,
b = espadao, g = adaga, h = punho, i = arco, j = espada dupla --, o que
confirma as duas pontas. A diferenca e que aqui ela foi medida, e o cliente
ainda acrescenta o `k` para lanca, que a lista do forum nao tem.

Escolhida a arma, os efeitos daquele tipo sobem para o topo, e a coluna **usado
em** diz em quantas armas iguais o jogo usa cada um.

**Os cinco numeros vem junto.** Pondo um efeito sugerido, os ajustes sao
preenchidos com os que o jogo usa naquele efeito -- e nao com 0 e 1. O glow
nasce enquadrado na lamina em vez de encolhido no cabo.

Desmarcando a caixa, voltam os 1.812.

### A pagina "Armas criadas"

As armas do cliente com id acima de 30000 -- a faixa que o jogo nao usa.

A lista sai do proprio `weapongrp.dat`, e nao de um registro a parte. Mesmo
motivo da aba de NPC: registro envelhece quando o usuario troca de cliente,
restaura um backup ou copia a pasta para outra maquina, e a tela passaria a
mostrar armas que nao existem e a esconder as que existem.

Isso tambem mostra arma custom feita por outro programa, e esta certo -- quem
abre a pagina quer ver as armas custom do cliente dele.

- **Editar o glow desta** leva a arma para a outra pagina, ja escolhida.
- **Ver a XML** monta a XML na hora, a partir da linha do cliente, e mostra.
- **Gravar a XML no servidor** escreve na pasta de itens dele. Onde e essa
  pasta sai do proprio servidor, pelo farejador. Nao conseguindo descobrir, ele
  avisa e nao grava.
- **A subpasta nao e sempre `custom`.** Aquela e a convencao dos datapacks L2J,
  mas ha pack que reparte a pasta de itens por tipo -- `weapons`, `armors`,
  `accessories`, `etcitems` -- e que NAO le arma de `custom`. Gravar ali entrega
  o arquivo onde o servidor ignora, e o sintoma e "criei a arma e ela nao
  existe". A caixa ao lado do campo Servidor lista as subpastas que existem e ja
  marca a que casa com o tipo do item.
- **Copiar de outra arma...** traz o efeito e os cinco ajustes de uma arma que
  ja tem o glow no lugar. Os cinco numeros nao se acertam no palpite: o efeito
  sai do lugar e nao ha como saber qual deles esta errado. O registro avisa
  quando a arma de origem e de outro tipo -- os numeros valem, mas a malha de um
  espadao nao tem o tamanho da de uma adaga.
- **Excluir** tira a arma das tabelas na memoria e apaga a XML do servidor
  junto. O cliente so muda em Instalar no cliente.

O campo **Servidor** no alto da tela, com a caixa marcada, entrega a XML da
arma nova direto na criacao. O farejo roda numa thread: ele le a pasta de dados
inteira -- 4,6 s neste servidor -- e fazer isso na thread da tela congelaria a
janela a cada atualizacao da lista.

### Criar arma nova, em vez de mexer numa que existe

Por um glow numa arma do jogo muda **aquela arma para todo mundo** -- qualquer
Dragon Slayer do servidor passa a brilhar. As vezes e o que se quer; na maioria
das vezes, nao.

**Criar arma nova...** copia a arma escolhida para um id proprio, ja com o glow
que esta na tela, e a original nao e tocada. A janela pergunta id, nome,
descricao e icone; a copia leva a linha inteira do `weapongrp.dat` -- malha,
textura, som, tipo, peso e os numeros do cliente vem da base.

A copia e a mesma de `Itens`: `Itens.clonar`, o nome no `itemname-e`, o XML por
`l2item.xml_servidor`. Nao ha um segundo caminho de criacao para envelhecer em
paralelo.

O XML que sai tem **so o que da para ler do cliente**: tipo, parte do corpo,
peso, material, grau, tiro. Dano, defesa e preco nao existem no `weapongrp.dat`.
Para completar, a aba **Itens** tem a janela de quatro paginas -- e a mensagem
do fim diz isso.

### Gerar e instalar

Como nas outras abas: **Gerar** escreve o `weapongrp.dat` alterado numa pasta a
parte, **Instalar no cliente** copia, e o original vai para `backup_itens/` na
primeira vez.

Antes de gravar, a tabela e remontada a partir da definicao e comparada com o
binario original byte a byte. Se a volta nao reproduz a ida, nada e escrito.

O cliente le o `weapongrp.dat` **so no arranque**.

### A pagina "Encantamento"

**Vale para TODAS as armas do servidor.** Nao e ajuste de item.

O glow das outras paginas e da arma: uma Dragon Slayer com `c_u000` brilha
sempre, ja em +0. O brilho de encantamento e o halo que qualquer arma ganha ao
ser refinada, e ele mora no `env.int` -- um arquivo so para o cliente inteiro.

| campo | o que faz | no jogo original |
| --- | --- | --- |
| `EnchantMeshShow` | do +N em diante a malha muda | 4 |
| `EnchantEffectShow` | do +N em diante o brilho aparece | 7 |

Baixando o segundo para 4, toda arma +4 passa a brilhar.

#### O defeito que fazia a cor nao mudar

O `aplicar` descarregava os niveis novos ao encontrar QUALQUER cabecalho de
secao. O primeiro cabecalho do arquivo e o `[EnvSetup]`, na linha 1 -- entao o
bloco inteiro `Enchant0..N` era escrito no topo, **fora de toda secao**, e o
`[EnchantEffect]` continuava com o que sempre teve.

O sintoma era exatamente "mudei a cor e nao mudou nada": os niveis novos so
existiam naquele bloco fantasma, e a arma caia de volta no `Enchant=`.

Nao apareceu antes porque so acontece quando ha nivel NOVO. Trocar a cor de um
nivel que ja existe e substituicao no lugar, e aquilo funcionava -- foi o que os
testes cobriram. E a leitura tinha o mesmo furo: lendo solto, ela dava por bom o
bloco fantasma e a tela mostrava como certo um arquivo que o jogo ignorava.

Corrigido nos dois lados: escrever so dentro do `[EnchantEffect]`, com o gatilho
sendo SAIR da secao; e ler so de dentro dela. Mais `linhas_fora_da_secao`, que
acha o lixo, e `limpar_fora_da_secao`, que o tira -- o `Gerar` limpa sozinho, e
a leitura avisa.

Uma cautela que quase virou outro defeito: o detetor marcava tambem as 22 linhas
`Enchant*` do `[Variation]`, porque olhava se A LINHA era o cabecalho do
Variation em vez de se estavamos DENTRO dele. A limpeza teria apagado a secao de
augmentation inteira. Pegou porque o teste rodou o detetor contra o arquivo
original, que e limpo por definicao, e ele acusou 22.

#### As duas cores: o que da e o que nao da para afirmar

Duas respostas opostas foram dadas aqui antes -- "misturam num gradiente" e
"alternam" --, e as duas eram deducao. Vale registrar o que sustenta cada peca:

- Nos 21 niveis de fabrica a cor 2 e **sempre a mesma cor da 1, um pouco mais
  escura**, sem excecao. Isso e medido.
- O `env.int` aponta para um material cuja cadeia passa por um `FadeColor` -- a
  classe do Unreal que vai e volta entre duas cores. **Mas as cores gravadas
  nele sao outras**: (7,20,69)/(5,15,48), (24,41,46)/(34,45,47),
  (90,122,128)/(80,109,115). Nenhuma e a cor de nivel nenhum, entao o material
  tem a pulsacao dele, com cores proprias, e as do arquivo entram por outro
  caminho.
- `EnchantMeshShow`, `EnchantEffectShow` e as linhas `Enchant*` **nao estao na
  tabela de nomes de nenhum `.u`**: quem as le e o codigo nativo do executavel.
  Nao ha o que ler.

Entao a tela nao afirma mais o que as duas cores fazem. Ela diz o que e medido e
manda testar em jogo.

#### O editor de cor

Sao 21 niveis, duas cores cada, mais opacidade e intensidade -- oito numeros por
nivel. A primeira versao da tela era uma fila de oito caixinhas chamadas `R1
G1 B1 R2 G2 B2 Opacity Num`. Funcionava e nao dizia nada: ninguem escolhe cor
digitando 87 num campo chamado G1.

O desenho atual vem do que a comunidade ja usa -- o L2EE do tutorial: duas
cores, tres barras cada, uma amostra e a linha pronta -- com tres diferencas:

1. **A linha se gera sozinha**, a cada movimento da barra. Nao ha botao "Gerar
   Codigo": o codigo esta sempre a vista, e ja e o que vai ser gravado.
2. **Grava direto no arquivo.** No L2EE a linha e copiada a mao para um editor
   de `.int`; aqui ela entra no `env.int` pelo caminho conferido.
3. **A faixa dos 21 niveis fica desenhada**, e da para clicar. A progressao
   deste cliente -- cinza ate o +3, azul do +4 ao +15, vermelho dali em
   diante -- se le de uma vez, o que a tabela de numeros nao deixa ver.

Mais **Copiar para os de cima**, que repete o nivel atual em todos os acima
dele: o caminho curto para "do +7 em diante tudo vermelho" sem mexer em catorze
niveis a mao. E **Voltar ao original**, que desfaz um nivel so.

O numero sai como o arquivo o escreve: `0.4` e `1`, e nao `0.40` e `1.00`. Duas
casas deixariam as linhas mexidas visivelmente diferentes das outras dezoito.

#### Acima do +20

Logo abaixo da serie ha uma linha **`Enchant=`**, sem numero. E o que o cliente
usa para qualquer encantamento acima do ultimo nivel escrito. Neste cliente ela
e identica ao `Enchant20` -- e por isso um +40 hoje tem a mesma cor do +20.

Servidor que encanta mais alto tem dois caminhos, e a tela oferece os dois:

1. **Mexer so no `Enchant=`**, pela caixa `este e o Enchant=`. Uma linha
   resolve tudo acima do +20.
2. **Dar cor propria a cada nivel, ate o +60.** Essas linhas nao existem no
   arquivo, entao `aplicar` passou a saber INSERIR: as novas entram em ordem,
   logo antes do `Enchant=`, e so na secao `[EnchantEffect]` -- o `[Variation]`
   repete os mesmos nomes de chave e nao e assunto desta tela.

Na faixa, o nivel sem linha propria sai **tracejado**, e a cor que aparece nele
e emprestada do `Enchant=`. Entrando num deles, os campos ja vem com essa cor:
e o que aquele nivel tem hoje, e um branco diria que a cor e nenhuma.

**Uma ressalva honesta**: que o cliente LEIA `Enchant21` em diante nao da para
provar fora do jogo. O que da para afirmar e que escrever nao quebra nada --
chave desconhecida num `.int` do Unreal e ignorada, e se for ignorada continua
valendo o `Enchant=`, como hoje. O manual diz isso ao usuario.

Um defeito apareceu no caminho e vale registrar: a primeira versao decidia o
que inserir comparando `cores` com `env["cores"]` -- e os dois sao o MESMO
dicionario, porque a tela mexe nele direto. O nivel recem-acrescentado ja estava
la na hora da comparacao, a lista de pendentes saia vazia, e o arquivo voltava
com os 21 de sempre **sem nada dizer que faltou**. Agora quem responde "o que o
arquivo ja tem" e o proprio texto, anotado enquanto ele e percorrido.

#### Sobre os valores altos

Ha tutorial sugerindo opacidade e intensidade bem acima de 1, com o aviso de que
"pode lagar o servidor". A parte do valor alto esta certa; a do servidor, nao.

Neste cliente o jogo nunca passa de 1 nos dois -- `0.1` ate o +6, `0.4` no +7,
`1` do +13 em diante. Particula e desenhada pelo **cliente**, todo quadro, em
toda arma encantada que estiver na tela: quem sente e a maquina de quem joga,
ainda mais numa cidade cheia. A tela diz isso ao lado dos dois campos.

O `[Variation]` -- as cores de augmentation -- e **lido e nao tocado**: ele
repete os mesmos nomes de chave, e mexer nele achando que se mexe no
encantamento seria mudar o que nao se ve.

O modulo troca **linha por linha**, e nao reescreve o arquivo: o `env.int` tem
cerca de duzentas chaves -- neblina, sombra, agua, shaders -- e o programa
entende duas dezenas. Remontar o arquivo a partir do que ele entende apagaria o
resto.

Duas armadilhas resolvidas na leitura:

- **A codificacao.** O arquivo decifrado deste cliente e texto simples -- 5.906
  bytes para 5.906 caracteres. Uma primeira versao gravava UTF-16 sempre, e o
  arquivo saia com o dobro do tamanho. A leitura passou a devolver a
  codificacao junto, e a gravacao usa aquela.
- **A volta.** Antes de o arquivo ser dado como pronto, ele e cifrado e
  decifrado de volta, e o resultado comparado com o que se queria gravar. Nao
  batendo, nada e instalado -- um `env.int` quebrado deixa o cliente **sem
  iluminacao nenhuma**, e o sintoma nao parece com a causa.

O original vai para `backup_env/` na primeira instalacao. Sem mudanca nenhuma,
o arquivo gerado decifra para um texto **identico** ao original.

### O que fica de fora

Criar efeito de particula novo. A lista mostra o que o cliente ja tem; um
efeito inedito e um pacote novo, feito fora daqui.

---

## A aba "Multisell"

A lista de trocas que um NPC oferece: de um lado o que o jogador paga, do outro
o que ele recebe. Montada como um **checkout** -- os itens com icone, nome e
descricao dos dois lados, a quantidade a vista, e a conta escrita por extenso.

Do lado do cliente **nao ha arquivo**. Multisell e inteiramente do servidor; o
cliente so desenha o que o pacote manda. O que o cliente precisa e conhecer os
ITENS usados, e e para isso que serve a conferencia.

### O nome do arquivo e a chave

Do core deste servidor, e nao e obvio:

    final int id = file.getName().replaceAll(".xml", "").hashCode();

**Nao existe campo de id dentro da XML.** O identificador e o nome do arquivo, e
e por ele que o NPC abre a lista:

    multisell <nome>          no bypass do HTML
    exc_multisell <nome>      so o que o jogador ja tem no inventario

Disso saem tres coisas que a tela avisa: renomear troca a lista de identidade;
duas listas com o mesmo nome sao a MESMA lista, mesmo em pastas diferentes -- a
segunda a carregar apaga a primeira --; e o nome nao aceita espaco, porque o
bypass quebraria.

### Os NPCs

    public boolean isNpcAllowed(int npcId) {
        return _npcsAllowed == null || _npcsAllowed.contains(npcId);
    }

Sem nenhum `<npc>`, **qualquer** NPC abre. Com pelo menos um, so aqueles -- e
`isNpcOnly()` passa a ser verdadeiro, o que impede abrir a lista sem NPC, de um
painel da comunidade por exemplo. O campo em branco na tela quer dizer isso, e a
dica explica.

### O que a conferencia pega

Ela cruza a lista com as tabelas do cliente:

- item que **nao existe no cliente** -- em jogo a linha sairia sem nome e sem
  desenho, e ninguem saberia por que;
- quantidade zero ou negativa;
- troca com um lado so;
- nome de arquivo invalido, ou ja usado por outra lista.

### A prova de leitura

O modulo foi conferido contra as 177 multisells deste servidor: todas abriram,
10.028 trocas no total, e cada uma regravada e relida deu o mesmo resultado. A
unica diferenca na ida e volta e o `enchant="0"`, que deixa de ser escrito --
zero e o padrao do core, e escreve-lo e ruido.

---

## A aba "Conferir Cliente"

O cliente nunca avisa que faltou arquivo. Ele desenha o boneco branco, a mão
sem arma, o quadrado vazio no lugar do ícone, e segue jogando. Quem montou o
cliente só descobre quando alguém reclama.

Esta aba faz a pergunta que o cliente não faz: **do que as tabelas pedem, o
que não está instalado?**

O resultado da conferiência contra o servidor sai em **quadro**, e não numa
linha corrida. A linha era esta:

```
647 diferenças. cliente: 9534 itens, 3067 habilidades, 6541 NPCs |
servidor: 9430, 2703, 6519 (xml)
```

Três números sem rótulo depois do "servidor:", que só se entendiam contando a
ordem da metade anterior da frase; e "647 diferenças" sem dizer diferenças de
quê. Agora:

```
                 itens   habilidades    NPCs
no cliente       9.534         3.067   6.541
no servidor      9.430         2.702   6.519
só no cliente      104           389      62
só no servidor       0            24      40
```

E, embaixo, o que o número quer dizer para quem vai jogar: *"O cliente mostra
555 coisas que o servidor não conhece: quem as vir no jogo não consegue
usá-las."*

A conferiência também **fareja o servidor antes de ler**, e mostra no rodapé o
que viu. Sem isso, o `<item id="1">` de `recipes.xml` — que ali é ingrediente
de receita — entrava na conta como item do jogo.

Ela só lê. Nada no cliente muda até você marcar pacotes e apertar
**Instalar no cliente**.

### Como a conferência funciona

Duas metades.

**As referências.** As tabelas `.dat` guardam os caminhos de modelo, textura,
ícone e som no formato `Pacote.Objeto` — `LineageWeapons.small_sword_m00_wp`,
`icon.weapon_small_sword_i00`. São lidas `npcgrp`, `weapongrp`, `armorgrp`,
`etcitemgrp`, `skillgrp`, `itemgrp`, `pledgegrp` e `doorgrp`, as que existirem.

Os caminhos saem por varredura de texto, e não por definição `.ddf`. A razão é
prática: aqui interessa *achar* as referências, não interpretar as colunas. Uma
varredura não depende de a definição descrever aquele cliente — e cliente
modificado sempre tem coluna a mais ou a menos — e não corre o risco de ler
campo deslocado, porque nada é gravado de volta.

**O que existe.** Cada pacote instalado é aberto só nas tabelas de nome e de
exportação, que dizem quais objetos moram ali dentro.

### Por que isso termina em segundos e não em horas

A pasta de um cliente tem algo como 1.500 pacotes e 12 GB. Descriptografar
tudo para consultar duas tabelas de alguns kilobytes seria absurdo.

Não é preciso. O `Lineage2Ver121` dos `.utx` é um XOR de **um byte só**,
derivado do nome do arquivo: dá para decifrar qualquer pedaço do arquivo sem
tocar no resto. O programa lê o cabeçalho, salta para a tabela de nomes e para
a de exportação, e pronto — alguns kilobytes por pacote.

Os `.usx`, `.ukx` e `.u` usam Blowfish, que não permite esse acesso por pedaço.
Desses o programa confirma que o arquivo existe e **diz no relatório que o
conteúdo não foi aberto**, em vez de dar por bom o que não conferiu.

### O que o relatório separa

| Situação | O que significa | O que fazer |
| --- | --- | --- |
| **falta o pacote** | O arquivo não está em pasta nenhuma do cliente. | Instalar o pacote. É o que a procura resolve. |
| **falta dentro do pacote** | O arquivo está lá, mas não tem dentro o objeto que a tabela pede. | Ou a tabela cita um nome errado, ou o pacote é de outra versão. |
| **não conferido** | Pacote com Blowfish: existe, o conteúdo não foi aberto. | Nada. É um limite declarado, não um problema. |

Os cinco números no alto da tela resumem tudo, e a lista de baixo mostra, por
pacote, quantas referências dependem dele e de quais tabelas elas vieram.
Clicando numa linha aparecem exemplos das referências — é por eles que se
reconhece o que quebrou em jogo.

**Salvar relatório…** grava tudo em texto, com as referências listadas pacote
por pacote.

### Procurar em outros clientes

Quase todo pacote que falta num cliente existe noutro. Aponte em **Pasta** o
lugar onde os seus clientes ficam — a pasta que contém todos eles serve — e o
programa desce por todas as subpastas procurando, pelo nome, os pacotes que
faltam. Ele não assume que os arquivos estão arrumados: o mesmo pacote muda de
lugar de um cliente para o outro.

O que for achado entra na lista com o tamanho, de qual cliente veio e para qual
pasta vai. Quando o mesmo pacote aparece em mais de um cliente, todos aparecem,
do maior para o menor — e aí a escolha é sua. Marcar dois com o mesmo nome é
recusado: seria instalar um por cima do outro sem você escolher qual.

### Instalar

A cópia vai para a pasta de onde o arquivo veio: um `.utx` que estava em
`systextures` volta para `systextures`, e não para `textures`. A diferença
importa para o cliente. Sem essa pista, vale a extensão.

Três cuidados embutidos:

- **nada é sobrescrito.** Se já existe arquivo com aquele nome, ele não era o
  que faltava, e a cópia é recusada;
- a cópia vai primeiro para um nome provisório na pasta de destino e só depois
  é renomeada — um cliente com metade de um `.utx` não abre;
- o que acabou de ser copiado é aberto de volta. Num `.utx` isso é prova de
  verdade: a chave do Ver121 deriva do nome do arquivo, então um pacote que
  chegou com outro nome não decifra, e a assinatura não bate. O erro aparece
  ali, e não na tela de carregamento.

Depois de instalar, confira de novo: os números mostram o que aquilo resolveu.

### Conferir contra o servidor

A conferência de cima olha o cliente contra ele mesmo — textura que falta. Esta
olha o cliente contra o **servidor**, e pega o erro mais silencioso de servidor
privado: o que existe num lado e não no outro.

| situação | o que acontece em jogo |
| --- | --- |
| item só no cliente | o jogador nunca recebe |
| item só no servidor | cai no chão como cubo branco, sem nome |
| habilidade só no cliente | aparece na lista e não existe |
| habilidade só no servidor | o cliente não sabe desenhar |
| NPC só no servidor | nasce e não aparece |
| nível a mais no servidor | do nível N em diante a habilidade não desenha |

Nenhum desses casos dá erro em lugar nenhum.

Aponte a pasta de dados do servidor. O programa lê os **dois formatos** — os
cores em XML e os de banco, que guardam a mesma coisa em tabelas — e a leitura é
por varredura, então um core que escreva o XML de outro jeito continua sendo
lido.

No par deste computador a conferência achou 326 itens e 431 habilidades que o
cliente desenha e o servidor não entrega, 9 NPCs que o servidor faz nascer e o
cliente não desenha, e 29 habilidades em que o servidor entrega mais níveis do
que o cliente tem.

Só lê. Nada é alterado dos dois lados.

---

### Quando o pacote não está em cliente nenhum

Marcando uma linha de **falta o pacote**, o botão **Procurar na internet** abre
o navegador com o nome do arquivo já pesquisado. É o que sobra quando a procura
nas suas pastas não achou nada: quase todo pack de armadura ou de arma que
circula traz o nome do arquivo no anúncio.

O botão fica desligado nas linhas de "falta dentro do pacote" — ali o arquivo
existe, e baixar outra cópia não resolve.

Baixe só de onde você confia. O programa abre a busca; o que vem depois é sua
decisão.

### O que ela não faz

Não conserta tabela. Quando a referência está errada — um nome de objeto que
nunca existiu, lixo que sobrou de uma edição anterior — ela mostra o problema e
para aí. Corrigir a tabela é decisão de quem a editou.

---

## A aba "L2Crypt"

Abrir e fechar os arquivos do cliente. É a aba mais simples do programa e a
mais usada quando se quer só *olhar* alguma coisa.

Quase tudo no cliente é criptografado, e não é sempre do mesmo jeito:

| Método | Onde aparece | Como é |
| --- | --- | --- |
| `Lineage2Ver111` | `.u`, `.unr`, `.usx`, `.uax` | Blowfish |
| `Lineage2Ver121` | `.utx` | XOR com chave tirada do nome do arquivo |
| `Lineage2Ver413` | `.dat`, `.ini` | RSA |

A aba lê o cabeçalho de cada arquivo e responde na lista, ao lado do nome, se
ele está criptografado e por qual método — inclusive "não", para os que já estão
abertos.

Escolha arquivos avulsos ou uma pasta inteira, aponte onde salvar, e use
**Descriptografar** ou **Criptografar**. A pasta de destino não pode ser a
mesma dos originais, nos dois sentidos: gravar por cima do original quebra o
cliente.

Ao criptografar, o método vem da **extensão**, e não do arquivo — um arquivo
aberto não guarda de onde veio. Arquivo que já está criptografado é copiado
como está: fechar duas vezes produz algo que o cliente não lê.

A conferência é feita abrindo de volta o que acabou de sair e comparando com o
que entrou. É a mesma para todos os métodos, e por isso não engana: a
verificação que vinha embutida no compressor usa um caminho que serve para
pacote Unreal e dá falso negativo num `.dat` Ver413.

---

## Qual modelo usar

Os sete modelos foram rodados na **mesma** textura de pedra do cliente. A
nitidez foi medida por energia de borda e o ruido pelo desvio do detalhe fino,
depois conferidos a olho — os numeros abaixo sao relativos entre si, nao
absolutos.

| Modelo | Nitidez | Ruido | Para que serve |
|---|---:|---:|---|
| **upscayl-standard-4x** | 24,8 | 4,98 | **Padrao.** Equilibrado, melhor ponto de partida |
| high-fidelity-4x | 21,3 | 4,17 | O mais conservador. Pele, rosto, superficies lisas |
| remacri-4x | 29,8 | 5,97 | O mais nitido. Pedra, metal, tecido |
| ultramix-balanced-4x | 28,8 | 5,59 | Entre os dois, contraste mais alto |
| ultrasharp-4x | 26,8 | 5,05 | Interface e icones. Em terreno marca a costura |
| digital-art-4x | 25,3 | 4,98 | Arte desenhada, cores chapadas |
| upscayl-lite-4x | 23,3 | 4,53 | O mais rapido, menos detalhe. Lotes grandes |

**Na duvida, use o padrao.** Ele foi desenhado para ser razoavel em tudo, e a
diferenca entre modelos e muito menor do que a diferenca entre 1x e 2x.

**Nitidez alta nao e sempre melhor.** O que esses modelos fazem e *inventar*
detalhe plausivel. Em pedra e tecido isso ajuda; em pele, metal polido e
superficie lisa, aparece como grao que nao existia. Por isso o `remacri` e
otimo em armadura de placa e ruim em rosto.

**Evite o `ultrasharp` em terreno.** Ele endurece as bordas, e a emenda entre
os tiles do chao vira uma linha visivel — justamente onde o jogador mais olha.

O teste acima foi feito em **uma** textura pequena. Se voce vai processar
centenas, vale rodar dois ou tres modelos num pacote representativo e comparar
dentro do jogo antes de decidir.

---

## Problemas conhecidos e o que significam

**`Error spawning xDxTex.exe`** — o compressor DXT que o editor chamaria não
acompanha os builds de L2Editor que circulam. Este script contorna comprimindo
antes com o texconv e importando DDS pronto, então a mensagem não deve
aparecer. Se aparecer, as texturas entraram cruas e o pacote ficará ~4× maior.

**`ucc make` para num pacote de terceiros** — o `UT2003.ini` do L2Editor lista
pacotes cujo código-fonte não vem no build. O script gera um `Build.ini`
isolado com apenas o necessário, sem alterar o original.

**`Couldn't read the image`** — o Upscayl só lê jpg/png/webp. Alimentado com
TGA ele falha *retornando código zero*, ou seja, em silêncio. O script converte
antes para PNG por causa disso.

**Texturas saindo escuras** — o Upscayl grava no PNG os campos `sRGB` e
`gAMA=0,45455`. O texconv respeita esses campos: lê a imagem como sRGB e, ao
gravar em `BC3_UNORM` (que é linear), converte — a textura sai com **menos da
metade do brilho**, e o pacote inteiro fica escurecido no jogo. O script apaga
esses campos antes de comprimir. Se você montar o ciclo à mão, ou passe
`--ignore-srgb` ao texconv, ou converta para TGA no meio (o TGA não tem onde
guardar gama, que é por que ciclos mais antigos escapavam disso sem saber).

**`Critical Error: Serial size mismatch: Got X, Expected Y`** — o cliente
abriu, leu um objeto e ele acabou antes (ou depois) do que a tabela prometia.
Quase sempre a textura citada no erro **não é a culpada**: ela só teve o azar
de vir depois da que mudou.

A causa está nos mipmaps. Cada um é gravado numa `TLazyArray`, e uma
`TLazyArray` começa com um inteiro que é a **posição no arquivo** logo depois
dos dados — o motor pula para lá quando não quer carregar o bloco. É posição
absoluta, não relativa ao objeto. Então mover um objeto de lugar sem corrigir
esse número deixa o arquivo com tabelas impecáveis e conteúdo mentiroso.

Pior: o umodel não repara, porque ele lê tudo em vez de pular. Quem confere de
verdade é o cliente.

Por isso o programa **não move nada**: o que muda é recopiado para o fim do
arquivo, com os saltos recalculados, e todo objeto que não foi pedido continua
no endereço que o próprio conteúdo dele diz que está. A cópia velha fica no
meio como peso morto — é o que faz o pacote de quadros sair com o dobro do
tamanho em disco. Não custa memória no jogo: o que não é apontado nunca é
lido.

Se a mensagem aparecer mesmo assim, restaure o original de `backup_lobby` e
reporte — é sinal de que algum objeto tem deslocamento absoluto num lugar que
o programa ainda não conhece.

**"A volta não reproduz o original"** — a prova de ida e volta da aba de
Itens. A definição `.ddf` usada não descreve as tabelas deste cliente: ela
acerta o suficiente para ler, mas a remontagem não devolve os mesmos bytes. Em
geral o cliente é de outra crônica, ou foi editado por uma ferramenta que
acrescentou coluna. Gravar fica bloqueado de propósito — campo deslocado não dá
erro, dá item errado.

**Item novo sem nome, ou nome sem item** — as quatro tabelas de item foram
instaladas pela metade. Elas se casam pelo id e precisam ir juntas. Use
Restaurar originais e gere de novo.

**"nao conferido (Blowfish)" no relatório de conferência** — não é defeito. Os
`.usx`, `.ukx` e `.u` usam Lineage2Ver111, que só abre o arquivo inteiro; a
conferência confirma que o pacote existe e não abre o conteúdo. Os `.utx`, que
é onde moram as texturas, são conferidos por dentro.

**Cliente recusa o pacote** — pacotes Unreal são retrocompatíveis: versão
*menor ou igual* carrega, maior não. Clientes Interlude são versão 123, e o
L2Editor grava 123, então funciona. Um UCC de UnrealEngine2Runtime grava 126 e
**não** serve.

---

## Compilar e assinar

```
python compilar.py                 os dois normais
python compilar.py --completo      os dois com as ferramentas juntas
python compilar.py --tudo          os quatro
python compilar.py --so-assinar    assina o que ja esta em dist/
```

### Sobre o aviso de vírus

Vale ser exato, porque a diferença custa dinheiro.

**Assinatura não é um selo de "não é vírus".** Ela diz duas coisas: quem
publicou o arquivo, e que ele não foi alterado desde então. O Windows só
acredita nisso se o certificado subir até uma Autoridade Certificadora que ele
já traz de fábrica.

| situação | o que o usuário vê |
| --- | --- |
| sem assinatura | "O Windows protegeu o seu PC", editor desconhecido |
| certificado feito em casa | **o mesmo aviso** — some só na máquina de quem gerou |
| certificado de uma CA | o aviso some (o tipo OV ainda junta reputação com o tempo) |

O certificado feito em casa (`New-SelfSignedCertificate`) engana quem o gera: na
máquina dele o certificado está na loja de confiança, o aviso some, e parece
resolvido. Em qualquer outra máquina o aviso continua igual. Serve para testar o
processo, não para resolver o problema.

Um certificado de CA de verdade (DigiCert, Sectigo, SSL.com e afins) custa por
ano, exige comprovar identidade — de pessoa física também serve, com documento —
e hoje a chave vem obrigatoriamente em token físico ou HSM na nuvem.

Por isso `compilar.py` **não inventa certificado**. Sem um configurado, ele
compila, avisa que saiu sem assinatura e para por aí.

### O que já está feito, e não custa nada

Assinatura é uma parte. Estas outras pesam no heurístico de antivírus:

- **Sem UPX.** Executável empacotado é o que empacotador de malware produz, e o
  heurístico sabe disso. Os `.spec` estão com `upx=False`. Custa alguns
  megabytes a mais; evita um sinal forte contra.
- **Com dados de versão.** Nome do produto, descrição, versão e nome original do
  arquivo, escritos por `versao.py` — um arquivo por executável, porque o
  `OriginalFilename` tem de bater com o nome real. Binário anônimo é suspeito
  por si.
- **Ícone e nome próprios**, que já havia.

Os quatro executáveis desta versão passam limpos no Windows Defender.

### Configurar o certificado

Duas maneiras, nenhuma com senha escrita em arquivo:

```
rem a recomendada -- o certificado já instalado na loja do Windows
set L2PACKTOOL_CERT_SHA1=a1b2c3...

rem ou um .pfx em disco
set L2PACKTOOL_CERT_PFX=C:\caminho\cert.pfx
set L2PACKTOOL_CERT_SENHA=...
```

O carimbo de tempo é sempre posto, e o script tenta três servidores em ordem.
Sem carimbo a assinatura morre junto com o certificado, e os executáveis já
distribuídos passam a acusar erro.

Depois de assinar, o script pergunta ao próprio Windows se ele aceita a cadeia
(`signtool verify /pa`). É a única resposta que vale: ter assinado não quer
dizer que alguém confia.

---

## Créditos

Este script apenas orquestra o trabalho de outras pessoas. O mérito técnico é
delas:

- **UModel / UE Viewer** — Konstantin Nosov (Gildor)
- **DirectXTex / texconv** — Microsoft Corporation (licença MIT)
- **Upscayl** — equipe do Upscayl, sobre Real-ESRGAN (Xintao Wang et al.)
- **Pillow** — Jeffrey A. Clark e contribuidores
- **l2encdec, l2asm e l2disasm** — M. Soltys (DStuff) e o autor do
  L2FileEdit
- **Definições .ddf das tabelas** — da biblioteca do l2asm/l2disasm,
  conferidas neste programa pela ida e volta byte a byte
- **L2Editor / UCC** — Epic Games (Unreal Engine 2) e NCSoft (Lineage 2),
  com as modificações da comunidade
- **Lineage 2** é marca registrada da NCSoft

Use por sua conta e risco, no seu próprio cliente. Nada aqui contorna proteção
de cópia nem se destina a redistribuir conteúdo da NCSoft.

## Licença

O código deste projeto é de domínio público — use, altere e redistribua à
vontade. As ferramentas de terceiros mantêm cada uma a sua licença.
