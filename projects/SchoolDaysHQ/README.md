# School Days HQ — projeto no Days ModToolkit

## Escopo

**School Days HQ v1.02** é o baseline original do Days ModToolkit e usa o backend **GPK/STACK**.

O fluxo do toolkit não redistribui conteúdo do jogo. O usuário fornece o GPK original como referência, extrai os assets com GARbro, edita externamente e usa o toolkit para validar/reconstruir o archive.

## Baseline

Estado consolidado do desenvolvimento:

~~~text
Versão: School Days HQ v1.02
GPKs catalogados: 29
Entradas no baseline consolidado: 69.936
~~~

Formatos/áreas exercitados ao longo do projeto incluem:

- 'Script.GPK';
- 'System.GPK';
- 'Ini.GPK';
- 'SysSe.GPK';
- 'Movie00.GPK';
- ORS;
- CMAP;
- PNG;
- OGG;
- WMV;
- INI/STARTSCRIPT.

A validação consolidada do baseline chegou a **69.936 assets** sem falhas no conjunto final usado durante o desenvolvimento.

## PIDX

Chave confirmada:

~~~text
82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49
~~~

O backend GPK não usa a chave cegamente. A chave candidata só é aceita se o PIDX resultante passar pelas verificações estruturais.

## Fluxo

~~~text
GPK original
    ↓
GARbro
    ↓
pasta extraída
    ↓
editar assets
    ↓
Days ModToolkit
    ↓
Conferir alterações
    ↓
Gerar GPK
    ↓
reabrir + validar
    ↓
teste no jogo
~~~

A referência continua sendo a autoridade para:

- nomes;
- ordem;
- flags;
- headers;
- campos desconhecidos;
- estrutura do archive;
- proteção do PIDX.

## Repack

O writer:

1. relê a referência;
2. identifica a proteção efetiva;
3. preserva entradas que não foram alteradas;
4. recompõe somente entradas substituídas;
5. recria o PIDX;
6. reaplica a proteção correta;
7. reabre e valida o arquivo temporário antes de publicar a saída.

Isso evita que o archive seja reconstruído com uma chave incompatível.

## CMAP

O projeto desenvolveu e testou um fluxo específico de export/build de CMAP.

Uma rodada consolidada registrou:

~~~text
137 CMAPs coloridos exportados
123 overlays
build: 1 modificado / 136 inalterados
~~~

O resultado foi testado no jogo.

## '.sdmod'

O toolkit também evoluiu para suportar pacotes '.sdmod', inclusive teste multi-GPK.

Exemplo histórico validado:

~~~text
rafael.multi-test-1.0.0.sdmod
2 arquivos
~~~

O formato existe para organizar alterações sem redistribuir o conteúdo original completo do jogo.

## Tema

School Days HQ usa o tema padrão da GUI.

Mapeamento:

~~~text
SCHOOL_DAYS_HQ → themes/school_days
~~~

A identificação visual ocorre depois da detecção técnica do PIDX e não altera o writer.

## Limitações

- novas entradas de índice não são inseridas automaticamente;
- remoção/renomeação não são suportadas;
- arquivo ausente na pasta de alterações mantém a referência;
- um GPK de outra versão não deve ser usado como referência;
- compatibilidade estrutural não substitui teste real no jogo.

## Documentação relacionada

- [Formato GPK/STACK](../../docs/GPK_FORMAT.md)
- [GARbro + repack](../../docs/GARBRO_REPACK.md)
- [Temas](../../docs/TEMAS_GUI.md)
- [Workspaces parciais](../../docs/PARTIAL_WORKSPACES.md)
- [Interface / .sdmod](../../docs/DESKTOP.md)
