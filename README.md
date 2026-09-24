<img width="1672" height="941" alt="SUZU 2" src="https://github.com/user-attachments/assets/1e6f485d-9b96-4b36-af37-3fcacfc5001e" />

# Days ModToolkit

Toolkit não oficial para explorar, validar e reconstruir arquivos da série *Days*.

Linha de desenvolvimento atual: **v0.13.0-dev1**.

O projeto nasceu como *School Days HQ Modding Toolkit* e evoluiu para um toolkit multi-game. O namespace Python 'sdhq_toolkit' e alguns nomes de CLI continuam preservados por compatibilidade histórica.

## Projetos suportados

| Projeto | Base confirmada | Backend | Fluxo | Página |
|---|---|---|---|---|
| School Days HQ | **v1.02** | GPK/STACK | GARbro → pasta editada → GPK de referência → repack | [Projeto](projects/SchoolDaysHQ/) |
| Shiny Days | **1.01e** | GPK/STACK | GARbro → pasta editada → GPK de referência → repack | [Projeto](projects/ShinyDays/) |
| Summer Days | Japonês / **rUGP 5.7** | CRio | CRio original → workspace → validate → repack | [Projeto](projects/SummerDays/) |

A separação é intencional:

~~~text
School Days HQ / Shiny Days
└─ GPK/STACK
   └─ GARbro para exploração/extração
      └─ Days ModToolkit para validação e repack

Summer Days
└─ CRio / rUGP.rio.Op
   └─ Days ModToolkit extrai, valida e reempacota diretamente
      └─ GARbro não participa desse fluxo
~~~

> O backend CRio de Summer Days e a Stage 8C do script 'rUGP.rio' são tecnologias diferentes. O toolkit atual integra o fluxo **CRio de assets**; a Stage 8C especializada continua sendo documentada como backend separado.

## Como baixar

Este projeto **não usa GitHub Releases**. A versão pública atual fica na branch principal de desenvolvimento do repositório.

Para baixar sem Git:

1. abra a página principal;
2. selecione a branch pública mais recente;
3. clique em **Code → Download ZIP**;
4. extraia o ZIP completamente;
5. execute 'run_gui.bat'.

Não execute o toolkit de dentro do ZIP. 'src/', 'themes/', 'docs/' e os demais diretórios precisam permanecer juntos.

## Destaques

- leitura e reconstrução de GPK/STACK;
- autodetecção multi-game do PIDX;
- preservação da chave efetivamente detectada no GPK de referência;
- backend CRio próprio para Summer Days;
- workspaces editáveis e metadados técnicos separados;
- validações preventivas antes da publicação da saída;
- suporte a relatórios e pacotes '.sdmod';
- ferramentas para CMAP, ORS, PNG, OGG, WMV e outros assets já exercitados no projeto;
- GUI com fluxo GPK e aba exclusiva **Summer Days · CRio**;
- temas visuais por jogo sem misturar apresentação e lógica de parser/repack.

## School Days HQ

O suporte original do toolkit nasceu em School Days HQ.

Resumo técnico:

- baseline **v1.02**;
- **29 GPKs** catalogados durante o desenvolvimento;
- **69.936 entradas** no baseline consolidado;
- PIDX/STACK validado;
- repacks exercitados com INI, ORS, CMAP, PNG, OGG e WMV;
- suporte a '.sdmod', relatórios e workspaces;
- tema padrão da GUI.

Tudo que é específico deste jogo foi concentrado em:

**[projects/SchoolDaysHQ/README.md](projects/SchoolDaysHQ/README.md)**

## Shiny Days

Shiny Days reutiliza o backend GPK/STACK, mas possui sua própria chave PIDX e seu próprio baseline.

Resumo técnico:

- base **1.01e**;
- patch oficial JAST aplicado antes dos GPKs usados como referência;
- chave PIDX específica confirmada;
- autodetecção por 'index_key_name';
- writer preserva a proteção detectada no próprio arquivo;
- mesmo fluxo GARbro/pasta externa/GPK original;
- tema visual próprio.

Detalhes:

**[projects/ShinyDays/README.md](projects/ShinyDays/README.md)**

## Summer Days

Summer Days exigiu um backend completamente diferente.

A engenharia reversa partiu dos contêineres CRio de:

~~~text
EXE\rUGP.rio.Op
~~~

e evoluiu de testes locais para uma ferramenta independente, **Days CRio Universal Tool v1.0.0-alpha2**, até chegar à integração no Days ModToolkit.

Estado canônico que motivou a integração:

~~~text
73 contêineres CRio
137.741 objetos
27 arquivos externos
73/73 round-trips aprovados
repack integral aceito pelo jogo
TITLE modificado e repackado com sucesso
~~~

A página de Summer Days documenta **todo o caminho**: descoberta do formato, fórmulas de offset/tamanho, 'SEL', falhas intermediárias, alpha1/alpha2, full-tree round-trip, regras de referência, arquitetura do backend, workspace, GUI, tema e entrada no toolkit.

**[projects/SummerDays/README.md](projects/SummerDays/README.md)**

Guia operacional curto: [docs/SUMMER_DAYS_CRIO.md](docs/SUMMER_DAYS_CRIO.md).

## Chaves PIDX confirmadas

### School Days HQ

~~~text
82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49
~~~

### Shiny Days

~~~text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
~~~

### Variante adicional conhecida

~~~text
56 7C 1B 90 B6 FE 3F DB B6 06 79 EA CC 11 A0 4F
~~~

Uma candidata só é aceita quando o PIDX resultante passa pelas verificações estruturais do toolkit.

## Temas da GUI

O sistema visual acompanha o projeto sem alterar o backend técnico.

~~~text
GPK selecionado
      ↓
leitura do PIDX
      ↓
index_key_name
   ↙       ↘
School    Shiny
Days HQ   Days
   ↓       ↓
tema      tema

aba Summer Days · CRio
      ↓
tema Summer Days
~~~

Mapeamento GPK atual:

~~~text
SCHOOL_DAYS_HQ → themes/school_days
SHINY_DAYS     → themes/shiny_days
~~~

Summer Days não depende de PIDX; sua aba aplica diretamente 'themes/summer_days'.

A troca de tema pode alterar logo, arte lateral, paleta, cabeçalho e título. Ela **não** altera chave, codec, flags, offsets ou writer.

Mais detalhes: [docs/TEMAS_GUI.md](docs/TEMAS_GUI.md).

## Requisitos

- Windows;
- Python **3.10+** com Tkinter/Tcl-Tk;
- [GARbro](https://github.com/morkt/GARbro) para o fluxo GPK de School Days HQ/Shiny Days;
- Pillow recomendado para recursos visuais da GUI.

~~~powershell
python -m pip install Pillow
~~~

O jogo, GARbro, GPKs originais, CRios originais e outros assets proprietários não acompanham o toolkit.

## Fluxo GPK — School Days HQ / Shiny Days

1. abra o GPK desejado no GARbro;
2. extraia os arquivos preservando os caminhos internos;
3. edite os assets externamente;
4. abra 'run_gui.bat';
5. selecione o **GPK de referência**;
6. selecione a **pasta com as alterações**;
7. use **Conferir alterações**;
8. revise as substituições;
9. use **Gerar GPK**;
10. faça backup do arquivo instalado e teste no jogo.

A referência é a autoridade para nomes, ordem, flags, headers, campos desconhecidos, estrutura e proteção do PIDX.

## Fluxo CRio — Summer Days

1. abra 'run_gui.bat';
2. entre em **Summer Days · CRio**;
3. selecione um **CRio original**;
4. escolha workspace, saída e relatórios;
5. use **Ler CRio**;
6. use **Extrair CRio**;
7. edite apenas '<workspace>/<nome do CRio>/';
8. use **Conferir alterações**;
9. use **Gerar CRio**;
10. substitua somente numa cópia/backup do jogo e teste.

Metadados técnicos ficam em:

~~~text
<workspace>/.crio/
~~~

e não devem ser editados manualmente.

A referência usada na validação/repack precisa ser exatamente o mesmo original usado na extração.

## Autodetecção de PIDX

O núcleo GPK usa:

~~~python
read_stack_index(archive, key=None)
~~~

A tentativa inclui:

1. chave fornecida/CIPHERCODE, quando existir;
2. School Days HQ;
3. variante ALT_56;
4. Shiny Days;
5. PIDX sem XOR como fallback defensivo.

O relatório registra:

~~~text
index_key_name
index_key_hex
index_xor
index_codec
~~~

## Repack seguro

### GPK

O writer:

- relê o GPK de referência;
- detecta a proteção efetiva;
- preserva entradas não alteradas;
- recompõe apenas entradas modificadas;
- recria o PIDX;
- reutiliza a mesma proteção;
- valida o temporário antes de publicar a saída.

### CRio

O backend:

- valida SHA-256 da referência;
- preserva árvore, nomes, classes, ordem e flags;
- recalcula offsets e tamanhos;
- valida PNG por assinatura/chunks/CRC/resolução;
- bloqueia remoção de payload esperado;
- mostra arquivo novo como **novo — não incluído**;
- nunca sobrescreve a referência;
- valida antes do repack.

## CLI

Os comandos históricos continuam disponíveis pelo namespace 'sdhq_toolkit' por compatibilidade.

Exemplo GPK:

~~~powershell
python -m sdhq_toolkit.cli read-index "D:\Shiny Days\Packs\Script.GPK"
~~~

## Limitações atuais

### GPK

- inclusão de novas entradas ainda não é suportada;
- remoção e renomeação ainda não são suportadas;
- arquivo ausente na pasta externa mantém a entrada da referência;
- arquivos novos não entram automaticamente no índice;
- não misture GPKs de versões diferentes.

### CRio

- não adiciona objetos;
- não remove objetos;
- não renomeia objetos;
- não reordena objetos;
- não troca a árvore;
- mudança de tipo é bloqueada por padrão;
- PNG deve manter resolução por padrão;
- compatibilidade estrutural não garante que a engine aceite qualquer codec de áudio/vídeo.

## Testes

~~~powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
~~~

Além dos testes sintéticos, o backend CRio de Summer Days passou por round-trip integral da árvore real e por testes em engine com contêiner modificado.

## Documentação

### Por projeto

- [School Days HQ](projects/SchoolDaysHQ/)
- [Shiny Days](projects/ShinyDays/)
- [Summer Days](projects/SummerDays/)

### Formatos e fluxos compartilhados

- [GARbro + repack GPK](docs/GARBRO_REPACK.md)
- [Formato GPK/STACK](docs/GPK_FORMAT.md)
- [Summer Days / guia CRio](docs/SUMMER_DAYS_CRIO.md)
- [Temas da GUI](docs/TEMAS_GUI.md)
- [Notas v0.13](docs/RELEASE_v0.13.md)
- [Notas v0.12](docs/RELEASE_v0.12.md)
- [Interface e .sdmod](docs/DESKTOP.md)
- [Workspaces parciais](docs/PARTIAL_WORKSPACES.md)

## Licença e créditos

Código sob [MIT](LICENSE).

**SUZU / tsubaki-0x** — direção do projeto, testes, documentação e desenvolvimento do toolchain.

School Days, Shiny Days, Summer Days, logos, executáveis e assets pertencem aos respectivos titulares e não são cobertos pela licença MIT deste repositório.

Projeto independente e não oficial, sem vínculo com 0verflow, JAST USA ou GARbro.
