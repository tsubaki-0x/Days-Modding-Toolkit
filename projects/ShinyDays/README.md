# Shiny Days — projeto no Days ModToolkit

## Escopo

**Shiny Days 1.01e** usa o mesmo backend **GPK/STACK** de School Days HQ, mas com chave PIDX própria e tema próprio.

O baseline técnico foi construído depois de aplicar o patch oficial **JAST 1.01e**.

## PIDX

Chave confirmada:

~~~text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
~~~

A chave foi validada contra PIDX real por:

- XOR coerente;
- stream zlib válido;
- tamanho descompactado correto;
- índice parseável;
- nomes UTF-16LE válidos;
- offsets/tamanhos dentro do archive.

O writer reutiliza a chave efetivamente detectada no GPK de referência.

## Fluxo

~~~text
Shiny Days 1.01e
    ↓
GPK original
    ↓
GARbro
    ↓
pasta extraída
    ↓
editar
    ↓
Days ModToolkit
    ↓
Conferir alterações
    ↓
Gerar GPK
    ↓
teste no jogo
~~~

A camada GPK/STACK está suportada. Isso não significa que cada formato interno exclusivo de Shiny Days já possua validador especializado.

## Autodetecção

Não é necessário selecionar manualmente "Shiny Days" no parser.

O backend tenta as variantes conhecidas e só aceita a candidata que produz um PIDX estruturalmente válido.

O relatório expõe:

~~~text
index_key_name
index_key_hex
index_xor
index_codec
~~~

Para Shiny Days, a detecção técnica também alimenta o tema da interface:

~~~text
SHINY_DAYS → themes/shiny_days
~~~

A troca é somente visual.

## Tema

O tema de Shiny Days usa:

- logo própria;
- arte lateral própria;
- opacidade de 100%;
- paleta quente inspirada na identidade visual do jogo;
- cabeçalho/título adaptados ao jogo.

Nada disso altera chave, codec, flags, offsets ou writer.

## Patch oficial 1.01e

Página de referência:

https://help.jastusa.com/en/knowledgebase/article/shiny-days-patch-1-01e-and-bugfixes

O baseline do toolkit pressupõe essa atualização antes de usar os GPKs como referência.

## Limitações

- inclusão de novas entradas não é suportada;
- remoção/renomeação não é suportada;
- assets desconhecidos podem não ter validação especializada;
- o arquivo de referência deve vir da base compatível;
- o teste final no jogo continua obrigatório.

## Documentação relacionada

- [Documento histórico de Shiny Days](../../docs/SHINY_DAYS.md)
- [Formato GPK/STACK](../../docs/GPK_FORMAT.md)
- [GARbro + repack](../../docs/GARBRO_REPACK.md)
- [Temas](../../docs/TEMAS_GUI.md)
