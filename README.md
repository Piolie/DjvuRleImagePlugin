# DjVu RLE Image Plugin, for Pillow
This is a simple Pillow plugin for the DjVu RLE image format as defined in the ([DjVuLibre docs](http://djvu.sourceforge.net/doc/man/csepdjvu.html)). It is written in pure Python. So far only the decoder has been implemented.

## Usage
Simply place `DjvuRleImagePlugin.py` where Python can find it and do `import DjvuRleImagePlugin` to register the plugin; then `import PIL`. You should now be able to use PIL to open DjVu RLE files: `im = Image.open("image.djvurle")`.

## Decoder notes
- The color format doesn't support partial transparency. Pixels can only be fully transparent or not transparent at all. Wherever the decoder finds a transparent pixel, it sets the (R, G, B) values to (0, 0, 0) and the transparency to fully transparent. Everywhere else it's non-transparent.

## Current status: BETA
The plugin is a WIP. I'm still adding/modifying/bugfixing it.

I have tested it with several bitonal images generated with the DjVuLibre decoder (`ddjvu -format=rle out.djvu test.djvurle`).

There is no way to generate color RLE files with the DjVuLibre tools, so I have used Netpbm's `pbmtodjvurle` and `pamtodjvurle` to generate DjVu RLE images and so far the decoder seems to work fine on those files.

## Future work
- Write some tests.
- Write an encoder.

## License
The plugin was written following PIL's [PpmImagePlugin](https://github.com/python-pillow/Pillow/blob/master/src/PIL/PpmImagePlugin.py), [DdsImagePlugin](https://github.com/python-pillow/Pillow/blob/master/docs/example/DdsImagePlugin.py), [SgiImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/SgiImagePlugin.html) and [MspImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/MspImagePlugin.html) source code files, so I have used the same HPND License.

## Alternatives
There are only a couple alternatives I know of:
- [`pbmtodjvurle`](http://netpbm.sourceforge.net/doc/pbmtodjvurle.html) and [`pamtodjvurle`](http://netpbm.sourceforge.net/doc/pamtodjvurle.html) from the [Netpbm](http://netpbm.sourceforge.net/) toolkit. However, these only encode from PBM/PAM to DjVu RLE, and not vice versa. Also, no up to date binaries for Windows are available.
- `ddjvu`, the DjVuLibre DjVu decoder. It can only produce _bitonal_ DjVu RLE files from each of the available layers of a djvu input file.
