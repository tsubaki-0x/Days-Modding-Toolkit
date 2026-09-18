# School Days HQ / Shiny Days Modding Toolkit — v0.12.0-dev

## Destaques

- Suporte de container GPK/STACK para **School Days HQ v1.02** e **Shiny Days 1.01e**.
- Autodetecção da chave PIDX por archive.
- Chave Shiny Days confirmada: `F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA`.
- Repack preserva a chave efetiva da referência.
- Fluxo GARbro funciona sem exigir diretório do jogo.
- `--key-report` opcional na CLI.
- Testes multi-game adicionados.

A compatibilidade desta versão é da camada GPK/STACK; formatos internos específicos de Shiny Days continuam sujeitos a teste no jogo.

Veja [docs/RELEASE_v0.12.md](docs/RELEASE_v0.12.md).

---

# School Days HQ Modding Toolkit — v0.11.1-dev

Texto preparado para a release do GitHub.
Tag sugerida: `v0.11.1-dev`, mantendo a identificação usada pelo programa.

## Destaques

- Fluxo simples: extrair no GARbro, editar e reconstruir no ModToolkit.
- Repack por pasta externa, sem metadata obrigatório.
- Referência original ou modificada; arquivos ausentes mantidos da referência.
- Prévia das substituições e avisos de formato sem bloqueio de compatibilidade.
- Cancelamento, progresso e relatórios; saídas anteriores preservadas.
- Tema azul-marinho com textos claros e logo no canto superior esquerdo.
- Arte lateral opcional, com opacidade, zoom e posição configuráveis.
- Configuração rolável, divisória ajustável e tabela com rolagem nos dois eixos.
- CLI e interface anterior/.sdmod preservadas.

## Instalação e uso

Requer Windows e Python 3.10+ com Tkinter. Pillow é opcional para a arte de fundo:
`python -m pip install Pillow`.

Extraia o pacote completo em uma pasta nova e abra `run_gui.bat`.
Selecione o GARbro.exe manualmente. Extraia um GPK para uma pasta exclusiva,
preservando seus caminhos e sem converter os formatos.

No toolkit, escolha a instalação do jogo, o GPK de referência, a pasta editada,
a saída e os relatórios. Use **Conferir alterações** e **Gerar GPK**.

Antes de trocar o GPK em Packs, feche o jogo e o GARbro e guarde uma cópia anterior.
Consulte o README para exemplos e detalhes.

## Limitações

Uma referência por operação. Inclusão, exclusão e renomeação de entradas não
são suportadas. Arquivos novos são mostrados como não incluídos. Avisos não
garantem funcionamento no jogo. A interface anterior conserva suas regras.

## Verificação

- Repack de Ini.GPK no fluxo GARbro confirmado pelo usuário no jogo.
- Quatro testes da GUI principal passaram após o tema escuro e a correção de layout.
- Layout verificado em 760×540, 1024×650, 1366×700 e 1460×900.
- Testes anteriores de extração, formatos e .sdmod preservados; detalhes no README.
- Nenhum teste manual do jogo foi repetido apenas para mudar a aparência.

## Conteúdo da distribuição

Código, launcher, documentação, testes, logo e configuração de exemplo.
Não incluir jogo, GARbro, GPKs, mods pessoais, workspace, backups, relatórios,
outputs ou configurações com caminhos locais. O fundo pessoal é opcional.

**Para quem publica:** os ZIPs anteriores ao tema/layout não contêm essas mudanças.
Recrie o pacote e seu manifesto antes de anexá-lo. Este arquivo prepara o texto
da release; não publica nada automaticamente.
