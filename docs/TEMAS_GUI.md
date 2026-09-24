# Temas automáticos da GUI

A interface principal do **Days ModToolkit** possui perfis visuais por jogo.

```text
themes/
├── school_days/
│   ├── Logo.png
│   ├── Fundo.png
│   └── tema.json
├── shiny_days/
│   ├── Logo.png
│   ├── Fundo.png
│   └── tema.json
└── summer_days/
    ├── Logo.jpg
    ├── Fundo.jpg
    └── tema.json
```

## Comportamento

Ao abrir a GUI sem referência, o tema padrão é **School Days HQ**.

Quando um GPK é selecionado em **GPK de referência**, a GUI lê somente as informações necessárias do footer/PIDX para identificar a chave efetiva. Primeiro o parser reconhece o arquivo; só depois a interface usa esse resultado para escolher a apresentação visual.

Mapeamento atual:

```text
SCHOOL_DAYS_HQ -> themes/school_days
SHINY_DAYS     -> themes/shiny_days
```

O fluxo **Summer Days · CRio** não depende de PIDX. Ao selecionar essa aba, a
GUI aplica diretamente `themes/summer_days`; ao retornar ao fluxo GPK, a
autodetecção de School Days HQ/Shiny Days volta a ser a autoridade visual.

O tema pode trocar automaticamente:

- logo;
- arte lateral;
- paleta dos controles;
- cor de seleção e progresso;
- cabeçalho;
- título da janela.

A detecção do jogo permanece independente do repack. Trocar o tema nunca altera a chave do arquivo nem força um formato.

## tema.json

Os perfis usam:

- `id`: identificador interno;
- `nome`: nome mostrado na janela;
- `index_keys`: nomes de chave associados ao jogo;
- `logo`: arquivo da logo;
- `imagem`: arte lateral;
- `opacidade`: `1.0` significa totalmente opaco;
- `zoom`, `x`, `y`: enquadramento da arte;
- `cabecalho` e `subtitulo`: textos do topo;
- `cores`: paleta da GUI.

Os temas de Shiny Days e Summer Days usam **100% de opacidade**. A paleta de
Shiny Days usa laranja, amarelo quente, creme e tons escuros. A de Summer Days
segue a arte do jogo: azul-céu e azul-claro nos controles, índigo profundo no
fundo e laranja-vermelho da marca nos botões primários.

## Override antigo

Um `tema.json` na raiz continua podendo alterar imagem/enquadramento do tema padrão de School Days HQ para compatibilidade com versões anteriores.

Quando um GPK de Shiny Days é detectado, o perfil oficial de Shiny Days assume a interface para que o override antigo não impeça a troca automática. O perfil de Summer Days também é independente desse override.

## Separação entre visual e parser

O sistema de tema recebe o resultado de `index_key_name`, mas não participa da escolha da chave. Isso evita que uma preferência visual possa alterar o comportamento técnico do GPK.
