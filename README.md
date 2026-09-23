<img width="1672" height="941" alt="SUZU 2" src="https://github.com/user-attachments/assets/1e6f485d-9b96-4b36-af37-3fcacfc5001e" />


# Days ModToolkit

Toolkit não oficial para explorar, validar e reconstruir arquivos da série *Days*, com suporte atual a:

- **School Days HQ v1.02** — GPK/STACK
- **Shiny Days 1.01e** — GPK/STACK
- **Summer Days japonês / rUGP 5.7** — CRio

> **School Days HQ / Shiny Days:** GARbro explora e extrai; o Days ModToolkit faz o repack.  
> **Summer Days:** o próprio Days ModToolkit extrai, valida e reempacota CRio; GARbro não é usado.

Linha de desenvolvimento atual: **v0.13.0-dev1**.

O projeto nasceu como *School Days HQ Modding Toolkit* e evoluiu para um toolkit multi-game. O namespace Python `sdhq_toolkit` e alguns nomes de CLI continuam preservados por compatibilidade com versões anteriores.


## Como baixar

Este projeto **não usa GitHub Releases**. A versão pública atual fica sempre na branch principal **`days-modtoolkit`**.

Para baixar sem usar Git:

1. abra a página principal do repositório;
2. confirme que a branch selecionada é **`days-modtoolkit-v0.13`**;
3. clique no botão verde **Code**;
4. escolha **Download ZIP**;
5. extraia o ZIP completamente para uma pasta;
6. abra a pasta extraída;
7. execute `run_gui.bat`.

> Não execute o toolkit diretamente de dentro do arquivo ZIP. Extraia tudo primeiro para que `src/`, `themes/`, `docs/` e os demais arquivos permaneçam na estrutura esperada.

Se você baixar novamente pelo botão **Code → Download ZIP**, receberá o estado mais recente da branch principal.

## Destaques

- leitura e reconstrução de GPK/STACK;
- backend CRio de referência para Summer Days, com extração e repack próprios;
- autodetecção da variante/chave PIDX por arquivo;
- repack preservando a chave efetivamente detectada no GPK de referência;
- fluxo principal baseado em **GARbro + pasta editada + GPK original**;
- validações preventivas antes de publicar a saída;
- suporte a workspaces, relatórios e pacotes `.sdmod`;
- ferramentas para CMAP, ORS, PNG, OGG e outros assets já exercitados no projeto;
- interface gráfica com fluxo GPK e aba exclusiva **Summer Days · CRio**;
- **tema automático**: ao selecionar um GPK reconhecido, a GUI acompanha o jogo detectado sem alterar a lógica do parser/repack.

## Jogos suportados

### School Days HQ

Baseline principal do projeto:

- **v1.02**
- 29 GPKs catalogados durante o desenvolvimento;
- 69.936 entradas no baseline consolidado;
- testes realizados ao longo do projeto com INI, ORS, CMAP, PNG, OGG e WMV;
- tema visual padrão da GUI.

### Shiny Days

Baseline técnico:

- **Shiny Days 1.01e**
- patch oficial JAST 1.01e aplicado antes da extração/repack;
- PIDX de Shiny Days reconhecido por autodetecção;
- repack preservando a chave do próprio arquivo de referência;
- mesmo fluxo GARbro/pasta externa usado em School Days HQ;
- tema próprio de Shiny Days na linha v0.13.

O suporte ao **container GPK/STACK** está implementado. Isso não significa que todo formato interno exclusivo de Shiny Days possua um validador especializado; o teste final no jogo continua obrigatório.

### Summer Days

Suporte atual:

- jogo japonês executado com **rUGP 5.7**;
- contêineres CRio usados em `rUGP.rio.Op`;
- seleção de um **CRio original como referência**;
- extração direta para `<workspace>/<nome do CRio>/...`;
- manifests/cabeçalho técnicos mantidos separadamente em `<workspace>/.crio/`;
- validação contra SHA-256 e estrutura da referência;
- repack com offsets e tamanhos recalculados;
- sem dependência do GARbro.

A integração preserva a árvore, nomes, classes, ordem e demais metadados da
referência. Adicionar, remover, renomear ou reordenar objetos CRio não é
suportado.

Mais detalhes: [docs/SUMMER_DAYS_CRIO.md](docs/SUMMER_DAYS_CRIO.md).

## Chaves PIDX confirmadas

**School Days HQ**

```text
82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49
```

**Shiny Days**

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

Variante adicional conhecida:

```text
56 7C 1B 90 B6 FE 3F DB B6 06 79 EA CC 11 A0 4F
```

Uma chave só é aceita quando o PIDX resultante passa pelas verificações estruturais do toolkit.

## Temas automáticos da GUI

A linha v0.13 separa a apresentação da lógica técnica.

```text
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
```

Mapeamento atual:

```text
SCHOOL_DAYS_HQ -> tema School Days HQ
SHINY_DAYS     -> tema Shiny Days
```

A troca pode alterar:

- logo;
- arte lateral;
- paleta;
- cores de seleção e progresso;
- cabeçalho;
- título da janela.

Ela **não** altera a chave, codec, flags, offsets ou writer. O GPK continua sendo a autoridade técnica.

Mais detalhes: [docs/TEMAS_GUI.md](docs/TEMAS_GUI.md).

## Requisitos

- Windows
- Python **3.10+** com Tkinter/Tcl-Tk
- [GARbro](https://github.com/morkt/GARbro) para exploração/extração
- Pillow recomendado para recorte/redimensionamento da arte lateral:

```powershell
python -m pip install Pillow
```

O jogo, GARbro, GPKs originais e outros assets proprietários não acompanham o toolkit.

## Fluxo principal

1. Abra o GPK desejado no GARbro.
2. Extraia os arquivos preservando os caminhos internos.
3. Edite os assets em ferramentas externas.
4. Abra `run_gui.bat`.
5. Selecione o **GPK de referência**.
6. A GUI lê o índice e identifica a variante suportada.
7. Selecione a **pasta com as alterações**.
8. Clique em **Conferir alterações**.
9. Revise as substituições detectadas.
10. Clique em **Gerar GPK**.
11. Faça backup do GPK instalado e teste o resultado no jogo.

O GPK de referência é a autoridade para nomes, ordem, flags, headers, campos desconhecidos, estrutura e proteção do PIDX.

## Autodetecção de PIDX

O núcleo usa:

```python
read_stack_index(archive, key=None)
```

A ordem de tentativa inclui:

1. chave fornecida/CIPHERCODE, quando existir;
2. School Days HQ;
3. variante ALT_56;
4. Shiny Days;
5. PIDX sem XOR como fallback defensivo.

O relatório registra:

```text
index_key_name
index_key_hex
index_xor
index_codec
```

## Repack seguro

O writer:

- relê o GPK de referência;
- identifica a chave efetiva;
- preserva entradas não alteradas;
- recompõe apenas entradas modificadas;
- recria o PIDX;
- reutiliza a proteção correspondente ao arquivo de referência;
- valida o arquivo temporário antes de publicar a saída.

Assim, um GPK de Shiny Days não é convertido acidentalmente para a chave de School Days HQ.

## CLI

Os comandos continuam disponíveis pelo namespace histórico para compatibilidade:

```powershell
python -m sdhq_toolkit.cli read-index "D:\Shiny Days\Packs\Script.GPK"
```

`--key-report` é opcional nos fluxos GPK atuais.

## Shiny Days 1.01e

Para reproduzir o baseline usado pelo projeto, aplique primeiro o patch oficial **1.01e** da JAST e só então utilize os GPKs como referência.

Página oficial:

https://help.jastusa.com/en/knowledgebase/article/shiny-days-patch-1-01e-and-bugfixes

O patch corrige, entre outros itens, o final da Minami, Route Map, splash screens, Story Route/Kokoro Bad End, uniforme da rota da Inori e pequenos erros de texto.

## Limitações atuais

- inclusão de novas entradas no índice ainda não é suportada;
- remoção e renomeação de entradas ainda não são suportadas;
- arquivo ausente na pasta externa mantém a entrada da referência;
- arquivos novos aparecem como **novo — não incluído**;
- validações de assets são preventivas e não substituem teste real;
- compatibilidade do container não garante compatibilidade semântica de todo asset interno;
- não misture GPKs de versões diferentes como referência e origem da edição.

## Testes

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
```

A linha v0.13 inclui testes específicos para autodetecção multi-game, preservação de chave no repack, seleção automática de tema e regressões da GUI.

## Documentação

- [GARbro + repack](docs/GARBRO_REPACK.md)
- [Formato GPK](docs/GPK_FORMAT.md)
- [Shiny Days](docs/SHINY_DAYS.md)
- [Summer Days / CRio](docs/SUMMER_DAYS_CRIO.md)
- [Temas da GUI](docs/TEMAS_GUI.md)
- [Notas v0.13](docs/RELEASE_v0.13.md)
- [Notas v0.12](docs/RELEASE_v0.12.md)
- [Interface anterior e .sdmod](docs/DESKTOP.md)
- [Workspaces parciais](docs/PARTIAL_WORKSPACES.md)

## Licença e créditos

Código sob [MIT](LICENSE).

**SUZU / tsubaki-0x** — direção do projeto, testes, documentação e desenvolvimento do toolchain.

School Days, Shiny Days, logos, executáveis e assets pertencem aos respectivos titulares e não são cobertos pela licença MIT deste repositório.

Projeto independente e não oficial, sem vínculo com 0verflow, JAST USA ou GARbro.
