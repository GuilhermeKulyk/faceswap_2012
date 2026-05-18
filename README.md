# faceswap_2012

> Recriei o antigo FaceSwapp de 2012. 
> Recreated the old FaceSwapp from 2012. Make apps great again.

App nativo de **face swap manual** escrito em Python puro. Você escolhe duas
fotos, posiciona 3 marcadores (olho esquerdo, olho direito e boca) em cada
imagem e pinta com pincel pra revelar o rosto alinhado sobre a foto base —
exatamente como o app de 2012, mas com controle fino, zoom, casamento de
cor opcional e exportação em resolução total.

A native Python **manual face-swap** app. Pick two photos, place 3 markers
(left eye, right eye, mouth) on each, and paint with a brush to reveal the
warped face over the base — like the old 2012 app, but with precision zoom,
optional color matching, and full-resolution export.

---

## Pré-requisitos / Requirements

- **Python 3.10+** (necessário / required) — testado com 3.13.
- Windows, macOS ou Linux (qualquer SO com Tkinter, que vem com o Python).

Se você ainda não tem o Python, baixe em <https://www.python.org/downloads/>.
No Windows, marque a opção **"Add Python to PATH"** durante a instalação.

If you don't have Python yet, get it from <https://www.python.org/downloads/>.
On Windows, tick **"Add Python to PATH"** during install.

## Instalação / Installation

```bash
git clone https://github.com/GuilhermeKulyk/faceswap_2012.git
cd faceswap_2012
pip install -r requirements.txt
```

As dependências são / Dependencies are:

- `Pillow` — manipulação de imagens / image I/O
- `numpy` — máscara e composição / mask and blending
- `opencv-python` — warp afim 3-pontos e color transfer / 3-point affine warp and color transfer

`tkinter` já vem incluído no Python oficial — não precisa instalar.
`tkinter` ships with the official Python distribution — no extra install.

## Como rodar / Running

```bash
python faceswap.py
```

## Fluxo / Workflow

1. **Etapa 1 — Escolher fotos.** Carregue a *Foto Base* (onde o rosto entra) e
   a *Foto Face* (de onde o rosto vem). Suporta rotação manual (↺ / ↻ 90°) e
   correção automática de orientação EXIF para fotos de celular.

2. **Etapa 2 — Marcadores.** Clique para posicionar 3 marcadores em cada
   imagem, na ordem **olho esquerdo (verde) → olho direito (vermelho) →
   boca (azul)**. Arraste para ajustar.
   - **Scroll do mouse** = zoom centrado no cursor (até 8×)
   - **Botão do meio** ou **Shift + arrastar** = pan
   - **Duplo clique** ou botão *Fit* = reseta zoom

3. **Etapa 3 — Pincel.** Pinte sobre a Base pra revelar a Face já alinhada.
   - Tamanho do pincel: 4–300 px
   - Borda: **suave** (gradiente smoothstep) ou **dura** (fixa)
   - Opacidade configurável
   - **Clique esquerdo** = revela / **clique direito** = apaga
   - Botão **"← Editar marcadores"** preserva a pintura
   - **Filtro opcional "Casar cores com a Base"** — color transfer Reinhard
     em espaço LAB, com slider de intensidade. Útil quando a Base é P&B,
     muito quente, muito fria, etc.

4. **Download.** Botão *Baixar PNG* exporta na resolução original da Base
   (PNG ou JPG).

## Como funciona / How it works

O alinhamento entre Face e Base é uma **transformação afim de 3 pontos**
calculada com `cv2.getAffineTransform` a partir dos marcadores que você
posicionou, aplicada com `cv2.warpAffine`. A máscara de revelação é um
array float32 pintado pelo pincel, e a composição final é simplesmente
`Base * (1 - mask) + WarpedFace * mask`. O color transfer opcional usa a
estatística clássica de Reinhard em LAB (casa média e desvio padrão por
canal entre Face e Base).

The alignment is a **3-point affine transform** (`cv2.getAffineTransform` +
`cv2.warpAffine`) using your placed markers. The reveal mask is a float32
array painted by the brush, and the final composite is just
`Base * (1 - mask) + WarpedFace * mask`. Optional color transfer is the
classic Reinhard LAB statistics (mean + std per channel).

## Licença / License

MIT.
