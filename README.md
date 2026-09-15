# School Days HQ Modding Toolkit

Ferramenta não oficial para reconstruir arquivos **GPK de School Days HQ v1.02**,
com interface desktop para Windows.

**GARbro explora e extrai. Você edita. O ModToolkit faz o repack.**

Versão atual: **0.11.1-dev**. Veja as [notas da release](RELEASES.md).

## O que o toolkit faz

- Monta um GPK usando uma referência original ou já modificada.
- Aceita uma pasta extraída externamente, sem exigir metadata do toolkit.
- Compara os arquivos e mostra substituições, arquivos iguais e avisos.
- Mantém da referência todas as entradas ausentes na pasta de alterações.
- Apresenta diferenças de formato como avisos, sem bloquear por compatibilidade.
- Grava o resultado na saída escolhida, preservando resultados anteriores.
- Oferece progresso, cancelamento, logs e relatórios.
- Inclui tema azul-marinho, textos claros e arte lateral configurável.
- Preserva a CLI e a interface anterior, inclusive os recursos de pacotes `.sdmod`.

## Requisitos

- Windows; a GUI foi desenvolvida e testada nesse ambiente.
- Python **3.10 ou superior**, com **Tkinter/Tcl-Tk**.
- Uma instalação de School Days HQ v1.02 para obter a chave do GPK.
- [GARbro](https://github.com/morkt/GARbro) para explorar e extrair arquivos.
  Não é necessário configurá-lo se você já tem os arquivos extraídos.
- **Pillow**, opcional para exibir a arte de fundo:

```powershell
python -m pip install Pillow
```

O pacote é uma aplicação Python, não um executável independente.
O jogo, o GARbro e seus arquivos não acompanham o toolkit.

## Instalação

1. Extraia o pacote completo da release em uma pasta própria, ou obtenha o código deste repositório.
2. Confirme que `run_gui.bat`, `src` e `docs` estão diretamente nessa pasta.
3. Abra **`run_gui.bat`**.
4. No campo **GARbro.exe**, selecione manualmente o executável do GARbro.
   Mantenha todos os arquivos que acompanham o programa.

O launcher procura `py -3` e, se não estiver disponível, usa `python`.
As localizações são salvas localmente em `.sdhq-repack.json`.

## Como criar um mod

### 1. Extrair no GARbro

Crie uma pasta exclusiva para o GPK e extraia nela os arquivos desejados,
**sem converter os formatos e preservando os caminhos internos**.

O GARbro pode extrair diretamente na pasta escolhida, sem criar uma pasta com
o nome do GPK. Usar esse nome ajuda na organização, mas não é obrigatório.

### 2. Editar

Edite os arquivos nos programas de sua preferência. Pode extrair tudo ou
somente as entradas que pretende alterar.

### 3. Configurar o repack

| Campo | O que selecionar |
| --- | --- |
| Instalação do jogo | Pasta principal que contém o executável do jogo; não a subpasta Packs |
| GPK de referência | GPK do qual vieram os arquivos, original ou modificado |
| Pasta com as alterações | Pasta que contém diretamente os arquivos e as subpastas extraídos |
| Pasta de saída | Destino separado da pasta de alterações e da pasta da referência |
| Pasta de relatórios | Destino dos logs e relatórios, fora da pasta de alterações |

**Exemplo com arquivos na raiz do GPK:**

```text
GPK de referência: D:\Jogo\Packs\Ini.GPK
Pasta selecionada: D:\MeuMod\Ini
Arquivo editado:   D:\MeuMod\Ini\EXEMPLO.INI
```

Se o caminho interno for `SYSTEM/EXEMPLO.PNG`, ele deverá ficar em
`PastaSelecionada/SYSTEM/EXEMPLO.PNG`. Os nomes acima são exemplos.

### 4. Conferir e montar

1. Clique em **Conferir alterações** e examine a lista.
2. Clique em **Gerar GPK**. A comparação é refeita para considerar edições recentes.
3. Aguarde **GPK gerado** ou **GPK gerado com avisos**.
4. Use **Abrir saída** para localizar o arquivo.

| Estado | Resultado |
| --- | --- |
| substituir | Usa o arquivo editado na entrada correspondente |
| igual | Mantém os dados armazenados na referência |
| manter referência | Arquivo ausente na pasta; mantém a entrada do GPK |
| novo — não incluído | Caminho fora do índice; aparece no relatório, mas não entra no GPK |

Se a saída já existir, o novo resultado vai para uma subpasta com data e hora.
A GUI não substitui automaticamente o GPK em `Packs`.

### 5. Testar no jogo

Feche **o jogo e o GARbro** antes de substituir um GPK em `Packs`: um arquivo
aberto pelo GARbro pode ficar bloqueado. Guarde uma cópia da versão anterior,
copie o GPK gerado para o jogo e teste a alteração.

## Avisos e limites

- A montagem trabalha com **uma referência por operação** e entradas existentes.
- **Inclusão, remoção e renomeação de entradas não são suportadas.**
- Arquivo ausente nunca significa remoção; seu conteúdo vem da referência.
- Avisos de PNG, OGG, ASF/WMV, CMAP e textos não impedem a montagem.
- Formatos desconhecidos podem ser substituídos, com aviso de compatibilidade.
- O toolkit não corrige nem descarta suas edições para passar na validação.
- Erros reais de leitura/escrita, índices não suportados ou mudanças durante
  a operação podem impedir a montagem; a GUI informa a falha.
- Gerar um GPK não garante que a edição funcione no jogo.
- A interface anterior e a CLI mantêm suas próprias regras de workspace e validação.

## Interface e personalização

Arraste a divisória entre configurações e resultados para aumentar a lista.
A configuração tem rolagem, e a tabela tem rolagem horizontal e vertical.

Para configurar a arte, copie `tema.example.json` para `tema.json`, indique
uma imagem local e ajuste opacidade, zoom e posição. Reabra a GUI depois de salvar.
O painel lateral é ocultado em larguras inferiores a 1280 pixels.

Veja [como ajustar o fundo](docs/FUNDO_GUI.md).
A imagem pessoal de fundo não é necessária para usar o repack.

## Relatórios e suporte

**Relatórios** abre a pasta com arquivos JSON e `desktop.log`.
Ao relatar um problema, informe a versão, a operação, a mensagem de erro e um
trecho relevante do relatório. Remova caminhos pessoais antes de compartilhar.
Não é necessário publicar GPKs ou arquivos proprietários do jogo.

## Testes e validação

Testes automatizados usam GPKs sintéticos:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
```

Os testes de janela são opcionais:

```powershell
$env:SDHQ_GUI_TESTS = "1"
python -m unittest discover -s tests -p "*gui*.py" -q
```

O histórico inclui extração/repack de 29 GPKs e 69.936 entradas e alterações de
INI, ORS, CMAP, PNG, OGG e WMV validadas no jogo. No novo fluxo GARbro + pasta
externa, o usuário confirmou um repack de `Ini.GPK` carregando a alteração desejada.
Esses testes manuais não certificam toda edição possível.

## Documentação

- [Guia do repack por pasta](docs/GARBRO_REPACK.md)
- [Interface anterior e pacotes .sdmod](docs/DESKTOP.md)
- [Workspaces parciais](docs/PARTIAL_WORKSPACES.md)
- [Comandos e histórico técnico anteriores](docs/README_ANTERIOR.md)
- [Organização dos arquivos](docs/ORGANIZACAO.md)
- [Preparação para publicação](docs/PUBLICACAO.md)

## Licença e créditos

O código é distribuído sob a [licença MIT](LICENSE).
School Days, sua logo e outras artes pertencem aos respectivos titulares e não
recebem a licença MIT por estarem associadas a este projeto.
Consulte a [origem da logo](src/sdhq_toolkit/gui/assets/README.md).

Projeto não oficial, sem vínculo com os titulares de School Days HQ ou com o GARbro.
