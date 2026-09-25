; ---------------------------------------------------------------------------
;  O instalador do L2PackTool
; ---------------------------------------------------------------------------
;  Instala POR USUARIO, em %LocalAppData%\Programs\L2PackTool, e nao pede
;  administrador. Nao e preguica: o programa grava config.ini, projetos.ini,
;  trabalho\ e saida\ ao lado do proprio executavel, e Program Files e
;  somente leitura para quem nao e administrador -- instalado la, ele abriria
;  e perderia tudo o que o usuario configurasse, em silencio. Enquanto os
;  caminhos gravaveis nao mudarem para %APPDATA%, este e o destino correto.
;
;  O executavel instalado e o `-Completo`, que ja traz as ferramentas de
;  terceiros dentro. O nome do arquivo nao muda no caminho: o recurso de
;  versao dentro dele declara `OriginalFilename`, e arquivo que se chama
;  diferente do que declara e mais um sinal a favor do antivirus. Quem ganha
;  o nome curto e o atalho.
;
;  Compilar:  python compilar.py --instalador
;             (ou: ISCC.exe instalador.iss)

#define Nome        "L2PackTool"
#define Versao      "1.7.0"
#define Autor       "Jean Almeida - " + "ÐarkÐomi"
#define Endereco    "https://github.com/JEAN-ALMEIDA-CZO"
#define Executavel  "L2PackTool-Completo.exe"

[Setup]
; O AppId identifica o programa para atualizacoes e desinstalacao. Nao muda
; nunca -- trocar aqui faz a proxima versao instalar ao lado da atual em vez
; de por cima dela.
AppId={{8B2F5E14-4C7A-4E0B-9A3D-5D2F1C7E9A40}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher={#Autor}
AppPublisherURL={#Endereco}
AppSupportURL={#Endereco}
AppUpdatesURL={#Endereco}
VersionInfoVersion={#Versao}.0
VersionInfoCompany={#Autor}
VersionInfoDescription={#Nome} - ferramentas de cliente Lineage II
VersionInfoProductName={#Nome}

; Por usuario: sem UAC, sem elevacao, sem prompt.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes

; So x64: o executavel e de 64 bits.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; O programa segura os proprios arquivos enquanto roda.
CloseApplications=yes
RestartApplications=no

SetupIconFile=recursos\icone.ico
; As imagens do assistente, desenhadas por `arte_do_instalador.py` a partir
; da marca e da paleta do programa. Uma medida por escala de tela: o Inno
; escolhe a mais proxima, e assim nada fica borrado num monitor de 200%.
WizardImageFile=recursos\instalador\painel-100.bmp,recursos\instalador\painel-125.bmp,recursos\instalador\painel-150.bmp,recursos\instalador\painel-175.bmp,recursos\instalador\painel-200.bmp
WizardSmallImageFile=recursos\instalador\selo-100.bmp,recursos\instalador\selo-125.bmp,recursos\instalador\selo-150.bmp,recursos\instalador\selo-175.bmp,recursos\instalador\selo-200.bmp
WizardImageStretch=no
UninstallDisplayIcon={app}\{#Executavel}
UninstallDisplayName={#Nome} {#Versao}
; O que aparece na entrada de Programas e Recursos (appwiz.cpl), que em
; instalacao por usuario mora em HKCU e e lida tanto por ele quanto por
; Configuracoes > Aplicativos.
AppComments=Ferramentas de cliente e servidor para Lineage II Interlude
AppReadmeFile={app}\LEIA-ME.html
AppContact={#Endereco}
WizardStyle=modern
WizardSizePercent=110
Compression=lzma2/max
SolidCompression=yes
; O conteudo ja vem comprimido de dentro do executavel; avisar o Inno disso
; evita gastar minutos tentando comprimir o que nao comprime mais.
LZMANumBlockThreads=4
OutputDir=dist
OutputBaseFilename={#Nome}-Setup-{#Versao}
; Espaco necessario, para o instalador poder avisar antes de comecar.
ExtraDiskSpaceRequired=10485760

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
pt.AtalhoArea=Criar um atalho na área de trabalho
pt.AbrirLeiaMe=Ler o LEIA-ME
pt.Rodando=O L2PackTool está aberto. Feche-o e tente de novo.
pt.ApagarDados=Apagar também as configurações, os projetos e os arquivos gerados?%n%nIsso inclui config.ini, projetos.ini e as pastas trabalho e saída.%n%nRespondendo Não, eles ficam onde estão e uma instalação futura os reaproveita.
en.AtalhoArea=Create a desktop shortcut
en.AbrirLeiaMe=Read the README
en.Rodando=L2PackTool is running. Close it and try again.
en.ApagarDados=Also delete settings, projects and generated files?%n%nThat includes config.ini, projetos.ini and the trabalho and saida folders.%n%nAnswering No leaves them in place for a future install to reuse.
es.AtalhoArea=Crear un acceso directo en el escritorio
es.AbrirLeiaMe=Leer el LÉAME
es.Rodando=L2PackTool está abierto. Ciérralo e inténtalo de nuevo.
es.ApagarDados=¿Borrar también la configuración, los proyectos y los archivos generados?%n%nIncluye config.ini, projetos.ini y las carpetas trabalho y saida.%n%nSi respondes No, se quedan donde están y una instalación futura los reaprovecha.

[Tasks]
Name: "atalho"; Description: "{cm:AtalhoArea}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#Executavel}"; DestDir: "{app}"; Flags: ignoreversion
Source: "recursos\LEIA-ME.html"; DestDir: "{app}"; Flags: ignoreversion isreadme
; Os lobbys das cronicas do Chaotic Throne ficam ao lado do programa, e nao
; dentro dele: sao 62 MB que quem usa um lobby so nao precisa carregar no exe.
Source: "lobbies\*.zip"; DestDir: "{app}\lobbies"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Executavel}"
Name: "{group}\{cm:AbrirLeiaMe}"; Filename: "{app}\LEIA-ME.html"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; Tasks: atalho

[Run]
Filename: "{app}\{#Executavel}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; O que o programa escreve sozinho e nao consta da lista de arquivos: sem
; isto, a pasta fica para tras com restos dentro.
Type: filesandordirs; Name: "{app}\abertos"
Type: files; Name: "{app}\erros.log"
Type: files; Name: "{app}\notify.log"

[Code]
{ Desinstalar nao apaga o que o usuario produziu sem perguntar: projeto,
  configuracao e as pastas de trabalho e saida podem ter horas de serviço
  dentro. A pergunta e uma so, e o padrao e nao apagar. }
procedure CurUninstallStepChanged(CurStep: TUninstallStep);
var
  Pasta: string;
begin
  if CurStep = usPostUninstall then
  begin
    if MsgBox(ExpandConstant('{cm:ApagarDados}'), mbConfirmation,
              MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      Pasta := ExpandConstant('{app}');
      DeleteFile(Pasta + '\config.ini');
      DeleteFile(Pasta + '\projetos.ini');
      DeleteFile(Pasta + '\efeitos.json');
      DeleteFile(Pasta + '\malhas.json');
      DelTree(Pasta + '\trabalho', True, True, True);
      DelTree(Pasta + '\saida', True, True, True);
      DelTree(Pasta + '\cena_lobby', True, True, True);
      DelTree(Pasta, True, True, True);
    end;
  end;
end;
