# Organização e distribuição — v0.11.1-dev

## O que serve para quê

| Local | Finalidade | Tratamento |
| --- | --- | --- |
| `run_gui.bat` | Abrir o programa | Manter na raiz |
| `src/` | Núcleo, CLI e interfaces | Necessário; manter |
| `docs/` e `README.md` | Uso, formatos e continuidade | Manter |
| `tests/` | Verificações com dados sintéticos | Manter para manutenção |
| `pipelines/`, `run_tests.bat`, `run_inventory.bat` | Ferramentas de desenvolvimento e CLI | Preservar compatibilidade |
| `LICENSE`, `pyproject.toml` | Licença e configuração do pacote | Manter |
| `docs/historico/` | Instruções das atualizações v0.1 até v0.10 | Arquivadas; não são instruções para instalar a versão atual |
| `ATUALIZACAO_v0.10_PARA_v0.11.txt` | Atualização incremental atual | Manter na raiz |
| `.sdhq-repack.json`, `.sdhq-desktop.json` | Preferências pessoais com caminhos locais | Preservar; não distribuir |
| `output/`, `output_v011/`, `reports/`, `workspace/` | Localizações salvas nas interfaces | Preservar nos caminhos atuais |
| `mods/`, `backups/` | Projetos e cópias de recuperação | Dados pessoais; preservar, não distribuir |
| `output_*`, `cmap_*`, `*.build.json` | Resultados/projetos de trabalhos anteriores | Dados locais; não são parte do aplicativo |
| `samples/` | Amostras locais, incluindo conteúdo extraído | Não distribuir |
| `research/` | Pesquisa de formatos | Preservar como material de desenvolvimento |
| `__pycache__/`, `*.pyc` | Cache regenerável do Python | Não distribuir |
| `dist/` | Pacotes de distribuição e pacotes de mod existentes | Compartilhar somente o ZIP do toolkit desejado |

As instruções antigas foram movidas para `docs/historico/`. O código continua nos
mesmos caminhos para preservar imports, launchers e ferramentas anteriores.
Dados locais não são classificados como descartáveis só por conterem “test” no nome.
Mover arquivos não libera espaço; apagar backups e resultados exige uma decisão separada.

## Pasta limpa para uso ou distribuição

O arquivo `dist/SchoolDaysHQ-Modding-Toolkit-v0.11.1-completo.zip` contém uma cópia
completa do programa, documentação e testes. Extraia em uma pasta nova e abra
`run_gui.bat`. Não depende de versões anteriores nem leva os dados desta pasta.
É uma distribuição Python: requer Python 3.10+ com Tkinter; não é um EXE autônomo.
Configure o GARbro manualmente na primeira abertura.

O ZIP incremental v0.10 → v0.11 permanece disponível para instalações existentes.
Uma extração incremental não remove instruções antigas da instalação de destino.
Para obter a organização limpa, use o ZIP completo em uma pasta nova.

Os ZIPs do toolkit não contêm GPKs, GARbro, executáveis do jogo, amostras extraídas,
mods pessoais, backups, relatórios, resultados ou configurações com caminhos locais.
O arquivo `MANIFESTO_DISTRIBUICAO.json` no ZIP completo lista os arquivos e seus hashes.
