# DjVu RLE Image Plugin, for Pillow
This is a simple Pillow plugin for the DjVu RLE image format as defined in the ([DjVuLibre docs](http://djvu.sourceforge.net/doc/man/csepdjvu.html)). It is written in pure Python 3.

## Usage
Simply place `DjvuRleImagePlugin.py` where Python can find it and do
```python
from PIL import Image
import DjvuRleImagePlugin
```
to register the plugin. You should now be able to use Pillow to open DjVu RLE files:
```python
im = Image.open("image.djvurle")
```
Also, for opened images of the appropriate characteristics (see encoder notes below), you can save to DjVu RLE with
```python
im.save("image.djvurle")
```

## Decoder notes
- The color format doesn't support partial transparency. Pixels can only be fully transparent or not transparent at all. Wherever the decoder finds a transparent pixel, it sets the (R, G, B) values to (0, 0, 0) and the transparency to fully transparent. Everywhere else it's non-transparent.

## Encoder notes
There is no documentation in Pillow's docs as to how to implement an encoder in Python. The base class from which all encoder classes should inherit is not even implemented yet (see [#4059: PyEncoder doesn't exist](https://github.com/python-pillow/Pillow/issues/4059)). So I checked Pillow's source code files (especially [`ImageFile._save`](https://github.com/python-pillow/Pillow/blob/252c008ec6925aa6d3a523aeb85e53c72ec33189/src/PIL/ImageFile.py#L488)) to figure out what such a class would need. Apart from the setup methods (`__init__`, `setimage`, `setfd`, etc.) `encode_to_pyfd` is the one that does the heavy lifting. It works, but the code is probably very brittle.

- Pillow image modes "1", "L", "P", "RGB" and "RGBA" are supported, as long as no more than 4080 colors are used (format limitation).
- Only fully transparent pixels are made transparent. In partially transparent pixels the transparency value is ignored.
- Currently, there is no way of telling the encoder how to handle color indices greater than 0xFF0 ("reserved for pixels belonging to the background layer" and "used for don't-care runs") as mentioned in the format's [complementary specification](DJVURLE_specification.md#color-rle-images). The only exception is index 0xFFF, used for transparent runs.

## Tests
This repo includes several tests that cover all cases I could think of.

Starting with `hopper.png`, all other PNG test files were generated using XnView or GIMP; DJVURLE test files using `pbmtodjvurle/pamtodjvurle`.

## Current status: stable BETA
I have tested the decoder with several bitonal images generated with the DjVuLibre decoder (`ddjvu -format=rle out.djvu test.djvurle`). There is no way to generate color RLE files with the DjVuLibre tools, so I have used Netpbm's `pbmtodjvurle` and `pamtodjvurle` to generate DjVu RLE images and the decoder has had no trouble handling any of those files.

The encoder seems to handle all Pillow image modes mentioned above quite well and `csepdjvu` accepts all this files and produces correct DjVus with them.

## Future work
- Don't pull_fd/push_fd (experimental): work with Pillow's buffer.
- Make the encoder accept "PA" images.

## License
The plugin was written following PIL's source code files, specially [PpmImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/PpmImagePlugin.html), [DdsImagePlugin](https://github.com/python-pillow/Pillow/blob/master/docs/example/DdsImagePlugin.py) and [SgiImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/SgiImagePlugin.html), so I have used the same HPND License. See the LICENSE file for more details.

## Alternatives
There are only a couple alternatives I know of:
- [`pbmtodjvurle`](http://netpbm.sourceforge.net/doc/pbmtodjvurle.html) and [`pamtodjvurle`](http://netpbm.sourceforge.net/doc/pamtodjvurle.html) from the [Netpbm](http://netpbm.sourceforge.net/) toolkit. However, these only encode from PBM/PAM to DjVu RLE, and not vice versa. Also, no up to date binaries for Windows are available.
- `ddjvu`, the DjVuLibre DjVu decoder. It can only produce _bitonal_ DjVu RLE files from each of the available layers of a djvu input file.
