# Temas automáticos da GUI

A interface principal do **Days ModToolkit** possui perfis visuais por jogo.

```text
themes/
├── school_days/
│   ├── Logo.png
│   ├── Fundo.png
│   └── tema.json
└── shiny_days/
    ├── Logo.png
    ├── Fundo.png
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
- `logo`: PNG da logo;
- `imagem`: arte lateral;
- `opacidade`: `1.0` significa totalmente opaco;
- `zoom`, `x`, `y`: enquadramento da arte;
- `cabecalho` e `subtitulo`: textos do topo;
- `cores`: paleta da GUI.

O tema de Shiny Days usa **100% de opacidade**. A paleta foi inspirada visualmente na logo do jogo, usando laranja, amarelo quente, creme e tons escuros para contraste.

## Override antigo

Um `tema.json` na raiz continua podendo alterar imagem/enquadramento do tema padrão de School Days HQ para compatibilidade com versões anteriores.

Quando um GPK de Shiny Days é detectado, o perfil oficial de Shiny Days assume a interface para que o override antigo não impeça a troca automática.

## Separação entre visual e parser

O sistema de tema recebe o resultado de `index_key_name`, mas não participa da escolha da chave. Isso evita que uma preferência visual possa alterar o comportamento técnico do GPK.
