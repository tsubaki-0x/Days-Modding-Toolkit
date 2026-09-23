# Summer Days — fluxo CRio

Esta integração adiciona ao Days ModToolkit um fluxo separado para os contêineres
**CRio/rUGP do Summer Days japonês (rUGP 5.7)**.

Ela não substitui o fluxo GPK de School Days HQ/Shiny Days e **não usa GARbro**.

## Ideia do fluxo

O arquivo CRio original é sempre a referência técnica.

Exemplo:

```text
Summer Days instalado
└── EXE
    └── rUGP.rio.Op
        └── DATA.Op
            └── TITLE       <- CRio original de referência
```

Ao selecionar `TITLE` e clicar em **Extrair CRio**, o toolkit cria uma árvore
editável com o mesmo nome:

```text
summer_workspace/
├── TITLE/
│   ├── ...
│   ├── subpastas/
│   │   └── arquivos...
│   └── ...
└── .crio/
    └── TITLE/
        ├── _CRIO_PROJECT.json
        └── CONTAINERS/
            └── TITLE/
                ├── TREE/
                └── _CRIO/
```

O modder trabalha somente em:

```text
summer_workspace/TITLE/
```

A pasta `.crio` contém manifests, cabeçalho e payloads técnicos necessários para
preservar a estrutura original. Ela não deve ser editada manualmente.

## Interface

A interface principal possui duas áreas independentes:

- **School Days HQ / Shiny Days · GPK** — mantém o fluxo GARbro + GPK atual;
- **Summer Days · CRio** — fluxo próprio de extração, validação e repack CRio.

Na aba Summer Days:

- **Instalação do Summer Days (opcional)**: usada como atalho para localizar
  `EXE\rUGP.rio.Op`;
- **CRio de referência**: arquivo original que será a autoridade técnica;
- **Workspace de edição**: raiz onde será criada a pasta com o nome do CRio;
- **Pasta de saída**: recebe o CRio reconstruído;
- **Pasta de relatórios**: relatórios das operações.

## Operações

### Ler CRio

Analisa a referência e confirma que ela pertence à variante CRio suportada.

### Extrair CRio

Extrai o contêiner e cria a árvore editável.

A extração não altera o arquivo original.

Se já existir um workspace para o mesmo CRio, a interface pede confirmação antes
de apagar as edições existentes e reextrair.

### Conferir alterações

Sincroniza a árvore visível com o projeto técnico e compara os payloads com o
CRio original.

O backend continua com as regras estritas da alpha2:

- a referência precisa ter o mesmo SHA-256 usado na extração;
- árvore, nomes, classes, quantidade e ordem dos objetos vêm da referência;
- PNG é validado por assinatura, CRC e resolução;
- mudança de tipo é bloqueada;
- mudança de resolução PNG é bloqueada;
- remoção de payload esperado bloqueia o repack.

Arquivos novos são mostrados como:

```text
novo — não incluído
```

Eles não são adicionados ao contêiner porque a integração não sintetiza novos
objetos CRio.

### Gerar CRio

Executa a validação e reconstrói somente o CRio selecionado.

Exemplo:

```text
referência:
E:\SummerDays\EXE\rUGP.rio.Op\DATA.Op\TITLE

workspace editável:
E:\DaysModWorkspace\TITLE\...

saída:
E:\DaysModOutput\TITLE
```

A saída nunca pode ser o próprio arquivo de referência.

## Backend

O código CRio fica separado do GPK:

```text
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
```

O backend CRio deriva da **Days CRio Universal Tool v1.0.0-alpha2** já validada
no Summer Days. A integração preserva a CLI/ferramenta independente como
referência técnica e não mistura o writer CRio com o writer GPK.

## Limitações atuais

- variante confirmada: Summer Days japonês / rUGP 5.7;
- não adiciona objetos;
- não remove objetos;
- não renomeia objetos;
- não reordena objetos;
- não permite por padrão alterar tipo de payload;
- não permite por padrão alterar resolução de PNG;
- o teste final no jogo continua obrigatório.

## Distribuição

O repositório deve conter apenas código, documentação, testes sintéticos e
manifests gerados pelo próprio usuário.

Não incluir arquivos originais, executáveis, scripts ou assets proprietários do
jogo.
