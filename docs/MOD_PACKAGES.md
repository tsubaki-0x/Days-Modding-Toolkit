# Pacotes de mod `.sdmod`

A v0.10 introduz projetos e pacotes de mod para **School Days HQ v1.02**. Um
`.sdmod` é um ZIP verificável que contém somente arquivos internos realmente
modificados. Ele não inclui GPKs originais nem assets inalterados do jogo.

## Fluxo do criador

Crie o projeto e limite a busca aos GPKs que o mod altera:

```powershell
py -3 pipelines\create_mod_project.py "mods\meu-mod" --id "autor.meu-mod" --name "Meu Mod" --author "Autor" --version "1.0.0" --archives System Ini
```

Edite normalmente os arquivos extraídos em `workspace\System`,
`workspace\Ini` etc. Depois gere o pacote:

```powershell
py -3 pipelines\build_mod_package.py "mods\meu-mod" --workspace "workspace" --output "dist" --asset-baseline "reports\asset_baseline.json"
```

O build compara os arquivos com os hashes de `.sdhq\archive.json`, rejeita
arquivos ausentes/novos e cria:

```text
dist\autor.meu-mod-1.0.0.sdmod
dist\autor.meu-mod-1.0.0.sdmod.build.json
```

O workspace do criador continua modificado. Ele pode usá-lo diretamente no
`repack_gpk.py`; não é necessário aplicar o próprio pacote sobre ele.

Com `--asset-baseline`, o build também executa a validação estrutural da v0.9
antes de criar o pacote. Essa opção é recomendada. Um formato desconhecido é
bloqueado; use `--allow-unknown` somente após um teste controlado.

## Estrutura do pacote

```text
autor.meu-mod-1.0.0.sdmod
├── mod.json
└── files
    ├── Ini
    │   └── STARTSCRIPT.INI
    └── System
        └── TITLE
            └── TITLE.PNG
```

Cada item do manifesto registra GPK-alvo, caminho interno, tamanho, SHA-256 do
arquivo original e SHA-256 da versão modificada. O pacote é recusado se sua
estrutura, tamanho ou hash não corresponder ao manifesto.

## Inspeção antes de instalar

```powershell
py -3 pipelines\inspect_mod_package.py "dist\autor.meu-mod-1.0.0.sdmod" --report "reports\meu_mod_inspection.json"
```

Essa etapa não altera o workspace.

## Fluxo do usuário do mod

O pacote deve ser aplicado sobre um workspace extraído e limpo, compatível com
os hashes do jogo original:

```powershell
py -3 pipelines\apply_mod_package.py "dist\autor.meu-mod-1.0.0.sdmod" --workspace "workspace" --report "reports\meu_mod_apply.json"
```

Antes de substituir cada asset, a ferramenta cria um backup em
`workspace\.sdhq\mods\<id-do-mod>\backup`. Se houver arquivo já alterado,
versão original incompatível, pacote adulterado ou destino ausente, a operação
é bloqueada. Em caso de falha durante a aplicação, os arquivos já processados
são restaurados.

Depois da aplicação, reconstrua somente os GPKs indicados no relatório usando
`repack_gpk.py` e os GPKs originais como referência. A v0.10 ainda não copia
resultados diretamente para a pasta `Packs` do jogo.

## Remoção

Enquanto o arquivo aplicado não tiver sido editado novamente, o backup pode
ser restaurado com:

```powershell
py -3 pipelines\remove_mod.py "autor.meu-mod" --workspace "workspace" --report "reports\meu_mod_remove.json"
```

Se outra alteração tiver sido feita por cima do mod, a remoção é bloqueada
para não apagar trabalho posterior.

## Limites da v0.10

- Um `.sdmod` substitui somente entradas que já existem nos GPKs originais.
- Adição e exclusão de entradas ainda não são suportadas.
- Dois mods não podem alterar o mesmo arquivo no mesmo workspace; o segundo é
  tratado como conflito.
- Aplicação e remoção atuam no workspace, nunca diretamente na instalação.
- O usuário ainda precisa validar os assets e repacotar cada GPK afetado.
