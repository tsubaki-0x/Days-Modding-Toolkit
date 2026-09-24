# Summer Days — engenharia reversa e integração no Days ModToolkit

## Objetivo desta página

Esta é a documentação consolidada do trabalho de **Summer Days japonês / rUGP 5.7** que levou ao suporte CRio atual do **Days ModToolkit**.

Ela registra não apenas o uso final da GUI, mas o caminho de engenharia reversa que tornou o backend possível: separação entre script e assets, 'SEL', primeiras reconstruções quebradas, fórmulas de offset/tamanho, alpha1, alpha2, round-trip integral, testes em jogo, arquitetura do backend e integração visual.

> **Importante:** o Summer Days possui dois fluxos técnicos diferentes:
>
> - 'EXE\rUGP.rio' → script, VM, string pool e Stage 8C;
> - 'EXE\rUGP.rio.Op\...' → assets em CRio, backend integrado ao Days ModToolkit.
>
> O repacker CRio genérico **não substitui** a Stage 8C para edição do script.

## 1. Estado canônico

Base confirmada:

~~~text
Summer Days japonês
rUGP 5.7
~~~

Estado do script pesquisado durante o projeto:

~~~text
rUGP.rio original:
20.050.818 bytes
SHA-256:
91c001143e37ff7659f286d97c33c02a8e65d075a3a68c4ca6573d3ec4426d51

main.rsx:
string pool CP932
87.688 entradas
2.611.414 bytes
17.420 entradas com japonês

Stage 8:
1.095 cenas
21.614 ocorrências
16.078 unidades únicas
1.546 compartilhadas

Voz:
23.969 eventos
20.474 links com texto
0 ambiguidades
~~~

Estado canônico do backend CRio que motivou a integração:

~~~text
73 contêineres CRio
137.741 objetos
27 arquivos externos não-CRio
0 erros de scan
0 contêineres sem suporte de repack
73/73 round-trips aprovados
0 falhas
0 hashes ausentes
~~~

Além do round-trip estrutural, houve:

- repack integral de 'EXE\rUGP.rio.Op' aceito pelo jogo;
- repack de contêiner individual;
- repack com payload realmente modificado;
- 'TITLE' modificado funcionando no jogo.

## 2. Como o problema foi separado

A investigação começou procurando texto em 'DATA.Op' e em objetos que pareciam scripts. Alguns desses arquivos eram apenas logs/listas auxiliares.

A divisão correta foi:

~~~text
EXE\rUGP.rio
└─ lógica/script compilado
   └─ main.rsx / CrUAVMScript
      └─ bytecode + string pool

EXE\rUGP.rio.Op\
└─ CRio de assets
   ├─ PNG
   ├─ OGG
   ├─ WMV/ASF
   ├─ WAV
   ├─ UI
   ├─ escolhas
   └─ demais recursos
~~~

Essa separação orienta a arquitetura atual do toolkit:

~~~text
School Days HQ / Shiny Days → GPK/STACK
Summer Days assets          → CRio
Summer Days script          → Stage 8C especializada
~~~

## 3. Pesquisa do script: por que ela importa para o toolkit

Embora o backend Stage 8C ainda seja separado do CRio integrado, a pesquisa do script foi essencial para descobrir onde **não** estavam as escolhas visíveis e para entender a divisão entre dados e assets.

Dentro de 'rUGP.rio', o alvo real foi:

~~~text
main.rsx / CrUAVMScript
~~~

O string pool confirmado usa CP932, termina strings em NUL e é referenciado por opcode compacto '0x14'.

Regra de largura:

~~~text
offset < 0x8000  → operando de 2 bytes
offset >= 0x8000 → operando de 4 bytes
~~~

A Stage 8C reconstrói o pool, realoca referências, preserva largura dos operandos, trata a fronteira '0x8000', atualiza o tamanho serializado de 'main.rsx' e reconstrói a região duplicada do fim do arquivo.

Essa parte permanece uma tecnologia própria e não foi misturada ao writer CRio.

## 4. Descoberta das escolhas visíveis

A análise de imports reconstruiu dois grupos:

~~~text
AddSelecter        → rótulos internos de rota
AddSelecterPicture → escolhas/UI visíveis por imagem
~~~

Contagens finais:

~~~text
AddSelecter:
1.532 calls
60 grupos

AddSelecterPicture:
166 calls
25 grupos
~~~

Conclusão: **as escolhas que o jogador enxerga são PNGs**.

Isso levou ao alvo:

~~~text
EXE\rUGP.rio.Op\DATA.Op\SEL
~~~

Estrutura:

~~~text
2.801 objetos
35 objetos-pasta
2.766 PNGs
~~~

Hash original:

~~~text
8ecbcb009b9a9ed8420d1acba83fcd7e2844d3586fc2d2cee8bbf57ca2bb0643
~~~

Hash do 'SEL' PT-BR funcional:

~~~text
eca072c1e9273dfa112892ad53f8deba976ee47679a9de7ac3914ae85b396b7e
~~~

## 5. 'SEL': as reconstruções que quebraram

O 'SEL' foi o laboratório que mostrou o que um repacker CRio precisava preservar.

### 5.1 Primeira iteração — offsets antigos

Quando os PNGs traduzidos mudaram de tamanho, todos os payloads seguintes mudaram de posição. Uma primeira reconstrução preservou ponteiros antigos e quebrou em jogo.

A correção seguinte passou a recalcular os offsets dos **2.801 objetos**.

### 5.2 Segunda iteração — tamanhos ainda antigos

Mesmo com ponteiros corrigidos, as escolhas ficaram invisíveis.

A análise mostrou que os metadados de tamanho dos PNGs modificados continuavam inconsistentes. O contêiner tinha offsets em grande parte atualizados, mas **2.766 tamanhos PNG** ainda estavam stale/incompatíveis.

### 5.3 Solução

A reconstrução correta passou a recalcular:

~~~text
offset real de cada payload
tamanho real de cada payload
campo encoded offset
campo encoded size
~~~

Depois disso, as escolhas voltaram a aparecer.

Essa sequência foi o ponto de partida prático para transformar um reparo específico de 'SEL' em um **repacker CRio universal**.

## 6. Prefixo e árvore CRio

Prefixo confirmado:

~~~text
CD 32 6E 59 14 00 00 00 FF FF 01 00 04 00 43 52 69 6F
~~~

Layout:

~~~text
0x12 → root count (uint16 LE)
0x14 → início da tabela recursiva de objetos
~~~

Cada objeto preserva:

- nome;
- nome raw;
- classe ou referência de classe;
- pai;
- filhos;
- flags;
- campo encoded offset;
- campo encoded size;
- child count;
- payload offset;
- payload size.

Os nomes são principalmente CP932/Shift-JIS.

Os payloads são armazenados de forma contígua em **preorder** da árvore.

## 7. Fórmula de offset

A fórmula foi confirmada:

~~~text
encoded_offset = real_offset + 0xA2FB6AD1 mod 2^32
~~~

Inversa:

~~~text
real_offset = encoded_offset - 0xA2FB6AD1 mod 2^32
~~~

## 8. Fórmula de tamanho

A primeira versão da pesquisa ainda não entendia corretamente todos os payloads grandes. A fórmula final foi obtida e validada:

~~~text
encoded_size =
    0xE7B5D9F8
    + ROL32(size, 13)
    + (size & 0xFFF)
    mod 2^32
~~~

Validação:

~~~text
11.762 objetos
87 payloads >= 0x80000
maior payload testado ≈ 110,64 MiB
~~~

Essa descoberta eliminou a principal limitação da alpha1.

A mesma fórmula também apareceu de forma independente no tamanho serializado de 'main.rsx', reforçando a relação entre as famílias de formato da engine.

## 9. Flags de nó

Flags observadas e suportadas:

~~~text
08 C0 00
18 C0 00
~~~

No 'COMMON':

~~~text
8.820 objetos → 08 C0 00
3 objetos     → 18 C0 00
~~~

Os três objetos com '18 C0 00' eram dois cursores e um ícone.

O layout restante continuou compatível com a mesma lógica de árvore/repack.

## 10. 'CAutoFolder'

Pastas possuem payload próprio.

Payload confirmado:

~~~text
A4 CB F6 29 14 00 00 00 FF FF 01 00 0B 00
43 41 75 74 6F 46 6F 6C 64 65 72
~~~

Classe:

~~~text
CAutoFolder
~~~

O backend preserva o payload e valida que a estrutura não seja alterada de modo incompatível.

## 11. Tipos reconhecidos

A alpha2 reconhece:

~~~text
PNG
OGG
RIFF/WAV
WMV/ASF
BMP
DDS
JPEG
ZIP
CRIO aninhado
FOLDER / CAutoFolder
classes declaradas
UNKNOWN
~~~

Arquivos externos que não são CRio são classificados como:

~~~text
LOOSE
~~~

e preservados pelo caminho.

## 12. Segurança específica de PNG

PNG recebe validação reforçada:

- assinatura;
- chunks;
- CRC de cada chunk;
- IHDR;
- largura;
- altura;
- IEND;
- ausência de bytes extras depois de IEND.

Por padrão:

~~~text
tipo não pode mudar
resolução não pode mudar
~~~

O tamanho do arquivo em bytes pode mudar.

## 13. Alpha1 e amostras locais

A prova local evoluiu em contêineres como:

| Amostra | Tamanho | Objetos |
|---|---:|---:|
| CommonObj | 3.525 bytes | 4 |
| P3_DATA | 17.304.104 | 20.946 |
| P4 | 1.345.772 | 2.699 |
| P5 | 89.819 | 254 |
| P6 | 984.947 | 517 |
| P7 | 1.011.734 | 770 |
| SEL | 4.741.821 | 2.801 |
| COMMON | 126.411.349 | 8.823 |

Conjunto local:

~~~text
8 contêineres
36.814 objetos
~~~

Provas acumuladas:

- repack sem mudanças byte-idêntico;
- árvore mista CRio + loose reconstruída;
- 'SEL' com 2.766 PNGs traduzidos funcional;
- 'SEL' quebrado rejeitado por inconsistência de tamanho;
- 'COMMON' round-trip byte-idêntico;
- flags '18 C0 00' preservadas.

## 14. Days CRio Universal Tool v1.0.0-alpha2

A pesquisa virou uma ferramenta independente, construída somente com stdlib Python.

Comandos:

~~~text
scan
inspect
extract
validate
repack
roundtrip
~~~

Fluxo:

~~~text
days_crio_tool.bat scan <origem> --json
days_crio_tool.bat inspect <arquivo> --json
days_crio_tool.bat extract <origem> <projeto>
days_crio_tool.bat validate <projeto> <referencia>
days_crio_tool.bat repack <projeto> <referencia> <saida>
days_crio_tool.bat roundtrip <origem> ...
~~~

A ferramenta independente foi mantida como referência técnica mesmo depois da integração no toolkit.

## 15. Scan completo do jogo

A alpha2 foi executada contra toda:

~~~text
EXE\rUGP.rio.Op
~~~

Resultado:

~~~text
73 contêineres CRio
137.741 objetos
27 arquivos externos não-CRio
0 erros de scan
0 contêineres sem suporte de repack
73/73 round-trips aprovados
0 falhas
0 hashes ausentes
~~~

Distribuição:

| Tipo | Quantidade |
|---|---:|
| PNG | 85.192 |
| OGG | 29.784 |
| FOLDER | 20.698 |
| WMV/ASF | 2.055 |
| RIFF/WAV | 8 |
| CSinpleText | 1 |
| CCursor | 1 |
| CIcon | 1 |
| UNKNOWN | 1 |
| **Total** | **137.741** |

O único 'UNKNOWN' conhecido é o segundo cursor com referência de classe reutilizada, não uma incompatibilidade estrutural.

## 16. Round-trip integral em jogo

O teste decisivo foi:

~~~text
extract completo
→ validate
→ repack completo
→ substituir numa cópia da instalação
→ executar o jogo
~~~

Resultado:

~~~text
PASS
~~~

Isso validou a aceitação pela própria engine, não apenas hashes.

## 17. Teste com payload modificado

Depois foi isolado:

~~~text
TITLE
~~~

Fluxo:

~~~text
extrair TITLE
→ editar payloads
→ validar
→ repack apenas TITLE
→ instalar numa cópia
→ abrir o jogo
~~~

Resultado:

~~~text
PASS
~~~

Logo, o backend não é apenas um round-tripper. Ele consegue gerar CRio funcional com conteúdo alterado.

## 18. Liberdade atual de edição

Permitido estruturalmente:

~~~text
PNG → PNG modificado
OGG → OGG modificado
WMV/ASF → WMV/ASF modificado
WAV/RIFF → WAV/RIFF modificado
BMP → BMP
DDS → DDS
JPEG → JPEG
ZIP → ZIP
CRio aninhado → CRio
~~~

O payload pode crescer ou encolher. Offsets e tamanhos são recalculados.

Não suportado:

~~~text
adicionar objeto
remover objeto
renomear objeto
reordenar objeto
trocar a árvore
~~~

Por padrão também é bloqueado:

~~~text
trocar tipo
trocar resolução de PNG
~~~

A estrutura usa offsets/tamanhos de 32 bits.

## 19. Contêiner x codec

Uma regra importante:

~~~text
CRio aceitar o arquivo ≠ rUGP aceitar qualquer codec/encode
~~~

O backend preserva a estrutura do contêiner, mas atualmente não garante semântica de mídia como:

- codec/profile;
- framerate;
- sample rate;
- canais;
- bitrate;
- duração;
- timestamps.

Áudio/vídeo modificados precisam ser testados no jogo.

## 20. Regra absoluta da referência

O backend é **reference-based**.

Fluxo correto:

~~~text
Extrair → ORIGINAL
Editar  → workspace
Validar → MESMO ORIGINAL
Repack  → MESMO ORIGINAL
~~~

O projeto grava o SHA-256 da referência.

Se a validação/repack usar um CRio já modificado:

~~~text
reference hash mismatch
~~~

Isso é uma proteção, não um bug.

Um caso real durante a integração ocorreu porque 'COMMON' modificado foi selecionado por engano no lugar do original. A ferramenta estava funcionando corretamente.

## 21. Por que integrar no Days ModToolkit

Depois de:

- fórmula de offset confirmada;
- fórmula de tamanho confirmada;
- flags conhecidas preservadas;
- 'CAutoFolder' entendido;
- 'SEL' funcional;
- 'COMMON' byte-idêntico;
- full-tree 73/73;
- repack integral aceito pela engine;
- 'TITLE' modificado aceito pela engine;

o backend já tinha evidência suficiente para sair da ferramenta experimental isolada e entrar no toolkit multi-game.

A decisão arquitetural foi **não misturar GPK e CRio**.

## 22. Arquitetura no repositório

O backend ficou isolado:

~~~text
src/sdhq_toolkit/
├── formats/
│   ├── gpk/
│   └── crio/
│       ├── parser.py
│       ├── workspace.py
│       ├── project.py
│       └── __init__.py
└── core/
    └── summer_days_crio.py
~~~

Decisão:

~~~text
School Days HQ / Shiny Days = GPK
Summer Days                 = CRio
~~~

Os writers não compartilham lógica de serialização.

## 23. Workspace amigável

Para um arquivo como 'TITLE':

~~~text
summer_workspace/
├── TITLE/
│   └── árvore editável pelo modder
└── .crio/
    └── TITLE/
        ├── _CRIO_PROJECT.json
        └── CONTAINERS/
            └── TITLE/
                ├── TREE/
                └── _CRIO/
                    ├── manifest.json
                    ├── header.bin
                    └── payloads técnicos
~~~

O usuário edita:

~~~text
summer_workspace\TITLE\
~~~

Não deve editar:

~~~text
summer_workspace\.crio\
~~~

Antes de validar/repackar, a árvore visível é sincronizada com o projeto técnico.

## 24. Aba 'Summer Days · CRio'

A GUI ganhou um fluxo separado do GPK.

Campos:

- instalação do Summer Days, opcional;
- CRio de referência;
- workspace;
- pasta de saída;
- pasta de relatórios.

Ações:

~~~text
Ler CRio
Extrair CRio
Conferir alterações
Gerar CRio
Abrir workspace
Abrir saída
~~~

Summer Days não usa GARbro nesse fluxo.

## 25. Regras da GUI

A camada de serviço:

- bloqueia payload esperado removido;
- mostra arquivo novo como 'novo — não incluído';
- não sintetiza objeto novo;
- valida SHA da referência;
- valida tipo;
- valida PNG/CRC/resolução;
- impede a saída de sobrescrever a referência;
- mantém relatórios separados;
- pede confirmação antes de reextrair e apagar workspace existente.

## 26. Tema Summer Days

O mesmo sistema de temas de School Days HQ/Shiny Days foi reutilizado.

~~~text
themes/summer_days/
├── Logo.jpg
├── Fundo.jpg
└── tema.json
~~~

A aba Summer Days aplica o perfil diretamente; não depende de PIDX.

Paleta consolidada:

~~~text
sky   #85AFD0
light #B5D2E4
white #F1F4F6
navy  #201524
ink   #100E18
red   #FB430B
~~~

Ao voltar para a aba GPK, a detecção PIDX volta a controlar o tema de School Days HQ/Shiny Days.

## 27. Testes da integração

Além dos testes reais anteriores, a integração ganhou teste sintético sem assets proprietários.

O teste:

1. cria um CRio mínimo;
2. extrai;
3. modifica um payload OGG;
4. valida;
5. repacka;
6. reabre a saída;
7. confirma que arquivo novo no workspace é detectado, mas não inserido.

Isso mantém a suíte pública reproduzível sem distribuir conteúdo do jogo.

## 28. Histórico de branch/PR

A integração foi desenvolvida originalmente na linha:

~~~text
summer-days-crio-integration
~~~

e documentada no Draft PR **#2 — Add Summer Days CRio extract/repack workflow**.

Esse PR serviu como trilha de integração do backend, GUI, tema, testes e documentação. O estado atual do repositório já contém o suporte Summer Days na branch pública de desenvolvimento, portanto esta página passa a ser o registro canônico do trabalho técnico.

## 29. Correções durante a integração

Duas correções importantes ficaram registradas no histórico técnico:

~~~text
6e8da381521d62b0b494bb399927fab47941869e
→ erros detalhados da validação CRio mostram path + causa

afbeffda424a595e48a4669b27353e4fe6fd0f93
→ proteção no browser contra caminho duplicado EXE\EXE
~~~

O 'reference hash mismatch' observado depois não era regressão: foi seleção de 'COMMON' modificado como referência.

## 30. Relação com a Stage 8C

O projeto de localização também produziu uma Stage 8C funcional para o script.

Resumo:

~~~text
16.078 / 16.078 traduções
8.489 maiores que o original
499.476 refs 0x14 reconhecidas
156.675 refs realocadas
fronteira 0x8000 preservada
cópia final duplicada reconstruída
no-op byte-idêntico
~~~

Saída PT-BR validada:

~~~text
20.247.390 bytes
SHA-256:
5c304cc8bbf01583c1dfcffd80a0b7e6871839f88804710e3cdfbb610d3d4175
~~~

A Stage 8C continua separada porque entende conceitos que o CRio genérico não entende:

- 'main.rsx';
- string pool;
- VM;
- refs '0x14';
- operandos compactos;
- fronteira '0x8000';
- região duplicada;
- metadados específicos do objeto de script.

Uma futura integração do script deve entrar como **backend Summer Days Script**, não como extensão improvisada do writer CRio.

## 31. Componentes funcionais do patch

O estado funcional conhecido do projeto de localização depende de:

~~~text
EXE\rUGP.rio
EXE\rUGP.rio.Op\DATA.Op\SEL
EXE\rUGP.rio.Op\_rUGPInstallFont.Op\
~~~

Funções:

~~~text
rUGP.rio            → diálogos/script PT-BR
SEL                 → escolhas visíveis PT-BR
_rUGPInstallFont.Op → acentos/glifos PT-BR
~~~

Isso ajuda a deixar claro o escopo atual do toolkit: hoje ele integra o backend **CRio** de 'rUGP.rio.Op'; a Stage 8C do script é documentada, mas permanece uma pipeline separada.

## 32. Regras para não regredir

### Script

- usar a edição rUGP 5.7 confirmada;
- preservar o 'rUGP.rio' original;
- editar apenas 'translation';
- preservar IDs, pool indexes, slots, vozes e hashes;
- não inserir NUL;
- usar CP932/EUDC suportado;
- não tratar 'max_bytes' como limite rígido individual na Stage 8C;
- não traduzir rótulos internos de rota como se fossem escolhas visíveis;
- não tratar 'chrN' como speaker ID absoluto;
- testar em jogo depois do repack.

### CRio

- extrair sempre de original;
- validar/repackar contra o mesmo original;
- nunca usar CRio modificado como referência daquele projeto;
- não editar '.crio' manualmente;
- não adicionar/remover/renomear/reordenar objetos;
- manter tipo do payload;
- manter resolução de PNG por padrão;
- preservar backup;
- testar mídia modificada na engine.

## 33. Próximos passos naturais

O núcleo CRio já passou por round-trip, repack integral e teste real com payload modificado. Evoluções futuras devem ser incrementais:

- validadores especializados para OGG;
- validadores especializados para WMV/ASF;
- validadores especializados para WAV/RIFF;
- validador DDS;
- relatórios mais ricos por payload;
- eventual suporte controlado a add/remove/rename/reorder.

Para o script, o passo natural é integrar a Stage 8C como backend separado, preservando todas as invariantes já validadas.

## 34. Documentação relacionada

- [Guia operacional CRio](../../docs/SUMMER_DAYS_CRIO.md)
- [README principal](../../README.md)
- [Temas da GUI](../../docs/TEMAS_GUI.md)

## 35. Aviso legal

O repositório deve conter apenas código, documentação, testes sintéticos e dados produzidos pelo próprio usuário.

Não incluir arquivos originais, executáveis, scripts ou assets proprietários de Summer Days.

Projeto independente e não oficial, sem vínculo com 0verflow ou outros detentores dos direitos.
