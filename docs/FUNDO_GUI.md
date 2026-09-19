# Arte e enquadramento da GUI

A v0.13 possui temas separados em `themes/school_days/` e `themes/shiny_days/`. A arte ativa acompanha automaticamente o GPK de referência quando a chave PIDX é reconhecida.

Campos de enquadramento em `tema.json`:

- `imagem`: arquivo de arte relativo à pasta do tema;
- `opacidade`: `1.0` = 100% opaco, sem esmaecimento;
- `zoom`: escala adicional da imagem;
- `x`: deslocamento horizontal em pixels;
- `y`: deslocamento vertical em pixels.

School Days HQ:

```json
{
  "opacidade": 1.0,
  "zoom": 1.0,
  "x": 50,
  "y": 0
}
```

Shiny Days:

```json
{
  "opacidade": 1.0,
  "zoom": 1.0,
  "x": 0,
  "y": 0
}
```

O recorte é centralizado antes dos deslocamentos. No tema de Shiny Days isso mantém as personagens agrupadas no centro do painel lateral sem distorcer a arte.

Em janelas estreitas, a arte lateral pode ser ocultada para preservar espaço para os controles.

Pillow é recomendado para recorte e redimensionamento de alta qualidade:

```powershell
python -m pip install Pillow
```

Sem Pillow, Tk 8.6 ainda consegue exibir PNG; o repack nunca depende da arte.

Veja também [TEMAS_GUI.md](TEMAS_GUI.md).
