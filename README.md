# faceswap_2012

> Recreated the old FaceSwapp from 2012. Make apps great again.
> Recriei o antigo FaceSwapp de 2012.

A native Python **manual face-swap** app. Pick two photos, place 3 markers
(left eye, right eye, mouth) on each, and paint with a brush to reveal the
warped face over the base — like the old 2012 app, but with precision zoom,
optional color matching, and full-resolution export.

---

## English

### Requirements

- **Python 3.10+** (required) — tested with 3.13.
- Windows, macOS, or Linux (any OS with Tkinter, which ships with Python).

If you don't have Python yet, get it from <https://www.python.org/downloads/>.
On Windows, tick **"Add Python to PATH"** during install.

### Installation

```bash
git clone https://github.com/GuilhermeKulyk/faceswap_2012.git
cd faceswap_2012
pip install -r requirements.txt
```

Dependencies:

- `Pillow` — image I/O
- `numpy` — mask and blending
- `opencv-python` — 3-point affine warp and color transfer

`tkinter` ships with the official Python distribution — no extra install needed.

### Running

```bash
python faceswap.py
```

### How to use

1. **Step 1 — Pick photos.** Load the *Base Photo* (where the face goes into)
   and the *Face Photo* (where the face comes from). Supports manual rotation
   (↺ / ↻ 90°) and automatic EXIF orientation correction for phone pictures.

2. **Step 2 — Markers.** Click to place 3 markers on each image, in this
   order: **left eye (green) → right eye (red) → mouth (blue)**. Drag to
   adjust.
   - **Mouse wheel** = zoom centered on the cursor (up to 8×)
   - **Middle button** or **Shift + drag** = pan
   - **Double click** or *Fit* button = reset zoom

3. **Step 3 — Brush.** Paint over the Base to reveal the aligned Face.
   - Brush size: 4–300 px
   - Edge: **soft** (smoothstep gradient) or **hard** (fixed)
   - Adjustable opacity
   - **Left click** = reveal · **Right click** = erase
   - **"← Edit markers"** button preserves your paint
   - **Optional "Match colors with Base" filter** — Reinhard color transfer
     in LAB space with an intensity slider. Useful when the Base is B&W, very
     warm, very cool, etc.

4. **Download.** *Download PNG* button exports at the Base's original
   resolution (PNG or JPG).

### How it works

Alignment between Face and Base is a **3-point affine transform**
(`cv2.getAffineTransform` + `cv2.warpAffine`) using your placed markers.
The reveal mask is a float32 array painted by the brush, and the final
composite is just `Base * (1 - mask) + WarpedFace * mask`. Optional color
transfer is the classic Reinhard LAB statistics (per-channel mean + std
matching).

### License

MIT.

---

## Português

### Pré-requisitos

- **Python 3.10+** (necessário) — testado com 3.13.
- Windows, macOS ou Linux (qualquer SO com Tkinter, que já vem com o Python).

Se você ainda não tem o Python, baixe em <https://www.python.org/downloads/>.
No Windows, marque a opção **"Add Python to PATH"** durante a instalação.

### Instalação

```bash
git clone https://github.com/GuilhermeKulyk/faceswap_2012.git
cd faceswap_2012
pip install -r requirements.txt
```

Dependências:

- `Pillow` — manipulação de imagens
- `numpy` — máscara e composição
- `opencv-python` — warp afim 3-pontos e color transfer

O `tkinter` já vem incluído no Python oficial — não precisa instalar.

### Como rodar

```bash
python faceswap.py
```

### Como usar

1. **Etapa 1 — Escolher fotos.** Carregue a *Foto Base* (onde o rosto entra)
   e a *Foto Face* (de onde o rosto vem). Suporta rotação manual (↺ / ↻ 90°)
   e correção automática de orientação EXIF para fotos de celular.

2. **Etapa 2 — Marcadores.** Clique para posicionar 3 marcadores em cada
   imagem, na ordem **olho esquerdo (verde) → olho direito (vermelho) →
   boca (azul)**. Arraste para ajustar.
   - **Scroll do mouse** = zoom centrado no cursor (até 8×)
   - **Botão do meio** ou **Shift + arrastar** = pan
   - **Duplo clique** ou botão *Fit* = reseta zoom

3. **Etapa 3 — Pincel.** Pinte sobre a Base para revelar a Face já alinhada.
   - Tamanho do pincel: 4–300 px
   - Borda: **suave** (gradiente smoothstep) ou **dura** (fixa)
   - Opacidade configurável
   - **Clique esquerdo** = revela · **clique direito** = apaga
   - Botão **"← Editar marcadores"** preserva a pintura
   - **Filtro opcional "Casar cores com a Base"** — color transfer Reinhard
     em espaço LAB, com slider de intensidade. Útil quando a Base é P&B,
     muito quente, muito fria, etc.

4. **Download.** Botão *Baixar PNG* exporta na resolução original da Base
   (PNG ou JPG).

### Como funciona

O alinhamento entre Face e Base é uma **transformação afim de 3 pontos**
calculada com `cv2.getAffineTransform` a partir dos marcadores que você
posicionou, aplicada com `cv2.warpAffine`. A máscara de revelação é um
array float32 pintado pelo pincel, e a composição final é simplesmente
`Base * (1 - mask) + WarpedFace * mask`. O color transfer opcional usa a
estatística clássica de Reinhard em LAB (casa média e desvio padrão por
canal entre Face e Base).

### Licença

MIT.
